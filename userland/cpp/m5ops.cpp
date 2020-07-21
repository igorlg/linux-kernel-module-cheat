/* https://cirosantilli.com/linux-kernel-module-cheat#m5ops-instructions */

#define LKMC_M5OPS_ENABLE 1
#include <lkmc/m5ops.h>

int main(int argc, char **argv) {
    char action;
    if (argc > 1) {
        action = argv[1][0];
    } else {
        action = 'e';
    }
    switch (action) {
        case 'c':
            LKMC_M5OPS_CHECKPOINT;
            break;
        case 'd':
            LKMC_M5OPS_DUMPSTATS;
            break;
        case 'e':
            LKMC_M5OPS_EXIT;
            break;
        case 'f':
            LKMC_M5OPS_FAIL_1;
            break;
        case 'r':
            LKMC_M5OPS_RESETSTATS;
            break;
    }
}
