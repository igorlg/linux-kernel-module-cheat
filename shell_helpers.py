#!/usr/bin/env python3

import base64
import distutils.file_util
import io
import itertools
import os
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import threading
from typing import List, Union
import urllib.request

class LF:
    '''
    LineFeed (AKA newline).

    Singleton class. Can be used in print_cmd to print out nicer command lines
    with --key on the same line as "--key value".
    '''
    pass

class ShellHelpers:
    '''
    Helpers to do things which are easy from the shell,
    usually filesystem, process or pipe operations.

    Attempt to print shell equivalents of all commands to make things
    easy to debug and understand what is going on.
    '''

    _print_lock = threading.Lock()

    def __init__(self, dry_run=False, quiet=False, force_oneline=False):
        '''
        :param dry_run: don't run the commands, just potentially print them. Debug aid.
        :type dry_run: Bool

        :param quiet: don't print the commands
        :type dry_run: Bool
        '''
        self.dry_run = dry_run
        self.force_oneline_default = force_oneline
        self.quiet = quiet

    @classmethod
    def _print_thread_safe(cls, string):
        '''
        Python sucks: a naive print adds a bunch of random spaces to stdout,
        and then copy pasting the command fails.
        https://stackoverflow.com/questions/3029816/how-do-i-get-a-thread-safe-print-in-python-2-6
        The initial use case was test-gdb which must create a thread for GDB to run the program in parallel.
        '''
        with cls._print_lock:
            try:
                print(string, flush=True)
            except BrokenPipeError:
                # https://stackoverflow.com/questions/26692284/how-to-prevent-brokenpipeerror-when-doing-a-flush-in-python
                # https://stackoverflow.com/questions/16314321/suppressing-printout-of-exception-ignored-message-in-python-3
                pass

    def add_newlines(self, cmd):
        out = []
        for arg in cmd:
            out.extend([arg, LF])
        return out

    def base64_encode(self, string):
        '''
        TODO deal with redirection and print nicely.
        '''
        return base64.b64encode(string.encode()).decode()

    def base64_decode(self, string):
        return base64.b64decode(string.encode()).decode()

    def check_output(self, *args, **kwargs):
        '''
        Analogous to subprocess.check_output: get the stdout / stderr
        of a program back as a byte array.
        '''
        out_str = []
        actual_kwargs = {
            'show_stdout': False,
            'show_cmd': False
        }
        actual_kwargs.update(kwargs)
        self.run_cmd(
            *args,
            out_str=out_str,
            **actual_kwargs
        )
        return out_str[0]

    def chmod(self, path, add_rm_abs='+', mode_delta=stat.S_IXUSR):
        '''
        TODO extend further, shell print equivalent.
        '''
        old_mode = os.stat(path).st_mode
        if add_rm_abs == '+':
            new_mode = old_mode | mode_delta
        elif add_rm_abs == '':
            new_mode = mode_delta
        elif add_rm_abs == '-':
            new_mode = old_mode & ~mode_delta
        os.chmod(path, new_mode)

    def force_oneline(self, force_oneline):
        if force_oneline is not None:
            return force_oneline
        else:
            return self.force_oneline_default

    def cmd_to_string(
        self,
        cmd: List[Union[str, LF]],
        cwd=None,
        extra_env=None,
        extra_paths=None,
        force_oneline: Union[bool,None] =None,
        *,
        stdin_path: Union[str,None] =None
    ):
        '''
        Format a command given as a list of strings so that it can
        be viewed nicely and executed by bash directly and print it to stdout.

        If cmd contains:

        * no LF, then newlines are added after every word
        * exactly one LF at the end, then no newlines are added
        * otherwise: newlines are added exactly at each LF
        '''
        last_newline = ' \\\n'
        newline_separator = last_newline + '  '
        out = []
        if extra_env is None:
            extra_env = {}
        preffix_arr = []
        if cwd is not None:
            preffix_arr.append('cd {} &&'.format(shlex.quote(cwd)))
        extra_env2 = extra_env.copy()
        if extra_paths is not None:
            extra_env2['PATH'] = '{}:"${{PATH}}"'.format(shlex.quote(':'.join(extra_paths)))
        for key in extra_env2:
            preffix_arr.append('{}={}'.format(shlex.quote(key), shlex.quote(extra_env2[key])))
        cmd_quote = []
        newline_count = 0
        for arg in cmd:
            if arg == LF:
                if not self.force_oneline(force_oneline):
                    cmd_quote.append(arg)
                    newline_count += 1
            else:
                cmd_quote.append(shlex.quote(arg))
        if self.force_oneline(force_oneline) or newline_count > 0:
            cmd_quote = [
                ' '.join(list(y))
                for x, y in itertools.groupby(
                    cmd_quote,
                    lambda z: z == LF
                )
                if not x
            ]
        if self.force_oneline(force_oneline):
            cmd_quote = [' '.join(preffix_arr + cmd_quote)]
        else:
            cmd_quote = preffix_arr + cmd_quote
        out.extend(cmd_quote)
        if stdin_path is not None:
            out.append('< {}'.format(shlex.quote(stdin_path)))
        if self.force_oneline(force_oneline) or newline_count == 1 and cmd[-1] == LF:
            ending = ''
        else:
            ending = last_newline + ';'
        return newline_separator.join(out) + ending

    def copy_file_if_update(self, src, destfile):
        if os.path.isdir(destfile):
            destfile = os.path.join(destfile, os.path.basename(src))
        self.mkdir_p(os.path.dirname(destfile))
        if (
            not os.path.exists(destfile) or \
            os.path.getmtime(src) > os.path.getmtime(destfile)
        ):
            self.cp(src, destfile)

    def copy_dir_if_update_non_recursive(
        self,
        srcdir,
        destdir,
        filter_ext=None
    ):
        # TODO print rsync equivalent.
        os.makedirs(destdir, exist_ok=True)
        if not os.path.exists(srcdir) and self.dry_run:
            basenames = []
        else:
            basenames = os.listdir(srcdir)
        for basename in sorted(basenames):
            src = os.path.join(srcdir, basename)
            if os.path.isfile(src) or os.path.islink(src):
                noext, ext = os.path.splitext(basename)
                if (filter_ext is None or ext == filter_ext):
                    dest = os.path.join(destdir, basename)
                    self.copy_file_if_update(src, dest)

    def copy_dir_if_update(
        self,
        srcdir,
        destdir,
        filter_ext=None
    ):
        self.copy_dir_if_update_non_recursive(srcdir, destdir, filter_ext)
        srcdir_abs = os.path.abspath(srcdir)
        srcdir_abs_len = len(srcdir_abs)
        for path, dirnames, filenames in self.walk(srcdir_abs):
            for dirname in dirnames:
                dirpath = os.path.join(path, dirname)
                dirpath_relative_root = dirpath[srcdir_abs_len + 1:]
                self.copy_dir_if_update_non_recursive(
                    dirpath,
                    os.path.join(destdir, dirpath_relative_root),
                    filter_ext
                )

    def cp(self, src, dest, **kwargs):
        if not kwargs.get('quiet', False):
            self.print_cmd(['cp', src, dest])
        if not self.dry_run:
            if os.path.islink(src):
                if os.path.lexists(dest):
                    os.unlink(dest)
                linkto = os.readlink(src)
                os.symlink(linkto, dest)
            else:
                shutil.copy2(src, dest)

    def mkdir_p(self, d):
        if not os.path.exists(d):
            self.print_cmd(['mkdir', d, LF])
            if not self.dry_run:
                os.makedirs(d)

    def mv(self, src, dest, **kwargs):
        self.print_cmd(['mv', src, dest])
        if not self.dry_run:
            shutil.move(src, dest)

    def print_cmd(
        self,
        cmd,
        cwd=None,
        cmd_file=None,
        cmd_files=None,
        extra_env=None,
        extra_paths=None,
        force_oneline: Union[bool,None] =None,
        *,
        stdin_path: Union[str,None] =None
    ):
        '''
        Print cmd_to_string to stdout.

        Optionally save the command to cmd_file file, and add extra_env
        environment variables to the command generated.
        '''
        if type(cmd) is str:
            cmd_string = cmd
        else:
            cmd_string = self.cmd_to_string(
                cmd,
                cwd=cwd,
                extra_env=extra_env,
                extra_paths=extra_paths,
                force_oneline=force_oneline,
                stdin_path=stdin_path
            )
        if not self.quiet:
            self._print_thread_safe('+ ' + cmd_string)
        if cmd_files is None:
            cmd_files = []
        if cmd_file is not None:
            cmd_files.append(cmd_file)
        for cmd_file in cmd_files:
            os.makedirs(os.path.dirname(cmd_file), exist_ok=True)
            with open(cmd_file, 'w') as f:
                f.write('#!/usr/bin/env bash\n')
                f.write(cmd_string)
            self.chmod(cmd_file)

    def rmrf(self, path):
        self.print_cmd(['rm', '-r', '-f', path, LF])
        if not self.dry_run and os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.unlink(path)

    def run_cmd(
        self,
        cmd,
        cmd_file=None,
        cmd_files=None,
        out_file=None,
        show_stdout=True,
        show_cmd=True,
        extra_env=None,
        extra_paths=None,
        delete_env=None,
        raise_on_failure=True,
        *,
        out_str=None,
        stdin_path: Union[str,None] =None,
        **kwargs
    ):
        '''
        Run a command. Write the command to stdout before running it.

        Wait until the command finishes execution.

        :param cmd: command to run. LF entries are magic get skipped.
        :type cmd: List[str]

        :param cmd_file: if not None, write the command to be run to that file
        :type cmd_file: str

        :param cmd_files: if not None, write the command to be run to all files in this list
                          cmd_file gets appended to that list if given.
        :type cmd_files: List[str]

        :param out_file: if not None, write the stdout and stderr of the command the file
        :type out_file: str

        :param out_str: if not None, append the stdout and stderr string to this list
        :type out_str: Union(List,None)

        :param show_stdout: wether to show stdout and stderr on the terminal or not
        :type show_stdout: bool

        :param extra_env: extra environment variables to add when running the command
        :type extra_env: Dict[str,str]

        :return: exit status of the command
        :rtype: int
        '''
        if out_file is None and out_str is None:
            if show_stdout:
                stdout = None
                stderr = None
            else:
                stdout = subprocess.DEVNULL
                stderr = subprocess.DEVNULL
        else:
            stdout = subprocess.PIPE
            stderr = subprocess.STDOUT
        if extra_env is None:
            extra_env = {}
        if delete_env is None:
            delete_env = []
        if 'cwd' in kwargs:
            cwd = kwargs['cwd']
        else:
            cwd = None
        env = os.environ.copy()
        env.update(extra_env)
        if extra_paths is not None:
            path = ':'.join(extra_paths)
            if 'PATH' in os.environ:
                path += ':' + os.environ['PATH']
            env['PATH'] = path
        for key in delete_env:
            if key in env:
                del env[key]
        if show_cmd:
            self.print_cmd(
                cmd,
                cwd=cwd,
                cmd_file=cmd_file,
                cmd_files=cmd_files,
                extra_env=extra_env,
                extra_paths=extra_paths,
                stdin_path=stdin_path
            )

        # Otherwise, if called from a non-main thread:
        # ValueError: signal only works in main thread
        if threading.current_thread() == threading.main_thread():
            # Otherwise Ctrl + C gives:
            # - ugly Python stack trace for gem5 (QEMU takes over terminal and is fine).
            # - kills Python, and that then kills GDB:
            #   https://stackoverflow.com/questions/19807134/does-python-always-raise-an-exception-if-you-do-ctrlc-when-a-subprocess-is-exec
            sigint_old = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, signal.SIG_IGN)

            # Otherwise BrokenPipeError when piping through | grep
            # But if I do this_module, my terminal gets broken at the end. Why, why, why.
            # https://stackoverflow.com/questions/14207708/ioerror-errno-32-broken-pipe-python
            # Ignoring the exception is not enough as it prints a warning anyways.
            #sigpipe_old = signal.getsignal(signal.SIGPIPE)
            #signal.signal(signal.SIGPIPE, signal.SIG_DFL)

        cmd = self.strip_newlines(cmd)
        if not self.dry_run:
            if stdin_path is None:
                stdin = None
            else:
                stdin = open(stdin_path, 'r')
            # https://stackoverflow.com/questions/15535240/python-popen-write-to-stdout-and-log-file-simultaneously/52090802#52090802
            with subprocess.Popen(
                cmd,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                env=env,
                **kwargs
            ) as proc:
                if out_file is not None or out_str is not None:
                    if out_file is not None:
                        os.makedirs(os.path.split(os.path.abspath(out_file))[0], exist_ok=True)
                    if out_file is not None:
                        logfile = open(out_file, 'bw')
                    logfile_str = []
                    while True:
                        byte = proc.stdout.read(1)
                        if byte:
                            if show_stdout:
                                sys.stdout.buffer.write(byte)
                                try:
                                    sys.stdout.flush()
                                except BlockingIOError:
                                    # TODO understand. Why, Python, why.
                                    pass
                            if out_file is not None:
                                logfile.write(byte)
                            if out_str is not None:
                                logfile_str.append(byte)
                        else:
                            break
                    if out_file is not None:
                        logfile.close()
                    if out_str is not None:
                        out_str.append((b''.join(logfile_str)))
            if threading.current_thread() == threading.main_thread():
                signal.signal(signal.SIGINT, sigint_old)
                #signal.signal(signal.SIGPIPE, sigpipe_old)
            if stdin_path is not None:
                stdin.close()
            returncode = proc.returncode
            if returncode != 0 and raise_on_failure:
                e = Exception('Command exited with status: {}'.format(returncode))
                e.returncode = returncode
                raise e
            return returncode
        else:
            if not out_str is None:
                out_str.append(b'')
            return 0

    def shlex_split(self, string):
        '''
        shlex_split, but also add Newline after every word.

        Not perfect since it does not group arguments, but I don't see a solution.
        '''
        return self.add_newlines(shlex.split(string))

    def strip_newlines(self, cmd):
        if type(cmd) is str:
            return cmd
        else:
            return [x for x in cmd if x != LF]

    def walk(self, root):
        '''
        Extended walk that can take files or directories.
        '''
        if not os.path.exists(root):
            raise Exception('Path does not exist: ' + root)
        if os.path.isfile(root):
            dirname, basename = os.path.split(root)
            yield dirname, [], [basename]
        else:
            for path, dirnames, filenames in os.walk(root):
                dirnames.sort()
                filenames.sort()
                yield path, dirnames, filenames

    def wget(self, url, download_path):
        '''
        Append extra KEY=val configs into the given config file.

        I wissh we could have a progress indicator, but impossible:
        https://stackoverflow.com/questions/51212/how-to-write-a-download-progress-indicator-in-python
        '''
        self.print_cmd([
            'wget', LF,
            '-O', download_path, LF,
            url, LF,
        ])
        urllib.request.urlretrieve(url, download_path)

    def write_configs(self, config_path, configs, config_fragments=None, mode='a'):
        '''
        Append extra KEY=val configs into the given config file.
        '''
        if config_fragments is None:
            config_fragments = []
        for config_fragment in config_fragments:
            self.print_cmd(['cat', config_fragment, '>>', config_path])
        if not self.dry_run:
            with open(config_path, 'a') as config_file:
                for config_fragment in config_fragments:
                    with open(config_fragment, 'r') as config_fragment_file:
                        for line in config_fragment_file:
                            config_file.write(line)
        self.write_string_to_file(config_path, '\n'.join(configs), mode=mode)

    def write_string_to_file(self, path, string, mode='w'):
        if mode == 'a':
            redirect = '>>'
        else:
            redirect = '>'
        self.print_cmd("cat << 'EOF' {} {}\n{}\nEOF".format(redirect, path, string))
        if not self.dry_run:
            with open(path, mode) as f:
                f.write(string)

if __name__ == '__main__':
    shell_helpers = ShellHelpers()
    if 'cmd_to_string':
        # Default.
        assert shell_helpers.cmd_to_string(['cmd']) == 'cmd \\\n;'
        assert shell_helpers.cmd_to_string(['cmd', 'arg1']) == 'cmd \\\n  arg1 \\\n;'
        assert shell_helpers.cmd_to_string(['cmd', 'arg1', 'arg2']) == 'cmd \\\n  arg1 \\\n  arg2 \\\n;'

        # Argument with a space gets escaped.
        assert shell_helpers.cmd_to_string(['cmd', 'arg1 arg2']) == "cmd \\\n  'arg1 arg2' \\\n;"

        # Ending in LF with no other LFs get separated only by spaces.
        assert shell_helpers.cmd_to_string(['cmd', LF]) == 'cmd'
        assert shell_helpers.cmd_to_string(['cmd', 'arg1', LF]) == 'cmd arg1'
        assert shell_helpers.cmd_to_string(['cmd', 'arg1', 'arg2', LF]) == 'cmd arg1 arg2'

        # More than one LF adds newline separators at each LF.
        assert shell_helpers.cmd_to_string(['cmd', LF, 'arg1', LF]) == 'cmd \\\n  arg1 \\\n;'
        assert shell_helpers.cmd_to_string(['cmd', LF, 'arg1', LF, 'arg2', LF]) == 'cmd \\\n  arg1 \\\n  arg2 \\\n;'
        assert shell_helpers.cmd_to_string(['cmd', LF, 'arg1', 'arg2', LF]) == 'cmd \\\n  arg1 arg2 \\\n;'

        # force_oneline separates everything simply by spaces.
        assert \
            shell_helpers.cmd_to_string(['cmd', LF, 'arg1', LF, 'arg2', LF], force_oneline=True) \
            == 'cmd arg1 arg2'

        # stdin_path
        assert shell_helpers.cmd_to_string(['cmd'], stdin_path='ab') == "cmd \\\n  < ab \\\n;"
        assert shell_helpers.cmd_to_string(['cmd'], stdin_path='a b') == "cmd \\\n  < 'a b' \\\n;"
