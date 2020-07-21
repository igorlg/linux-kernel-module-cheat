/* https://cirosantilli.com/linux-kernel-module-cheat#atomic-c */

#if __STDC_VERSION__ >= 201112L && !defined(__STDC_NO_THREADS__)
#include <assert.h>
#include <stdatomic.h>
#include <stdio.h>
#include <threads.h>
#include <string.h>
#include <stdlib.h>

atomic_int acnt;
int cnt;

int my_thread_main(void *thr_data) {
    size_t niters = *(size_t *)thr_data;
    for (size_t i = 0; i < niters; ++i) {
        ++cnt;
        ++acnt;
    }
    return 0;
}
#endif

int main(int argc, char **argv) {
#if __STDC_VERSION__ >= 201112L && !defined(__STDC_NO_THREADS__)
    size_t niters, nthreads;
    thrd_t *threads;
    if (argc > 1) {
        nthreads = strtoull(argv[1], NULL, 0);
    } else {
        nthreads = 2;
    }
    if (argc > 2) {
        niters = strtoull(argv[2], NULL, 0);
    } else {
        niters = 10;
    }
    threads = malloc(sizeof(thrd_t) * nthreads);
    for(size_t i = 0; i < nthreads; ++i)
        assert(thrd_create(threads + i, my_thread_main, &niters) == thrd_success);
    for(size_t i = 0; i < nthreads; ++i)
        assert(thrd_join(threads[i], NULL) == thrd_success);
    free(threads);
    printf("atomic %u\n", acnt);
    printf("non-atomic %u\n", cnt);
#else
    (void)argc;
    (void)argv;
#endif
}
