#ifndef LKMC_AARCH64_DUMP_REGS_H
#define LKMC_AARCH64_DUMP_REGS_H

#include <lkmc.h>

/* https://cirosantilli.com/linux-kernel-module-cheat#dump-regs */

/* So that a sigle source will work with baremetal and printk from kernel module. */
#ifndef LKMC_DUMP_SYSTEM_REGS_PRINTF
#define LKMC_DUMP_SYSTEM_REGS_PRINTF printf
#endif

#ifndef PRIX32
#define PRIX32 "x"
#endif

#ifndef PRIX64
#define PRIX64 "llx"
#endif

/* Dump registers that are only visible from privileged levels of the system. */
void lkmc_dump_system_regs() {
    uint32_t sctlr_el1;
    __asm__ ("mrs %0, sctlr_el1" : "=r" (sctlr_el1) : :);
    LKMC_DUMP_SYSTEM_REGS_PRINTF("SCTLR_EL1 0x%" PRIX32 "\n", sctlr_el1);
    LKMC_DUMP_SYSTEM_REGS_PRINTF("SCTLR_EL1.nTWE 0x%" PRIX32 "\n", (sctlr_el1 >> 18) & 1);
    LKMC_DUMP_SYSTEM_REGS_PRINTF("SCTLR_EL1.A 0x%" PRIX32 "\n", (sctlr_el1 >> 1) & 1);
    /* https://cirosantilli.com/linux-kernel-module-cheat#arm-paging */
    LKMC_DUMP_SYSTEM_REGS_PRINTF("SCTLR_EL1.M 0x%" PRIX32 "\n", (sctlr_el1 >> 0) & 1);

    uint64_t id_aa64isar1_el1;
    __asm__ ("mrs %0, id_aa64isar1_el1" : "=r" (id_aa64isar1_el1) : :);
    LKMC_DUMP_SYSTEM_REGS_PRINTF("ID_AA64ISAR1_EL1 0x%" PRIX64 "\n", id_aa64isar1_el1);
    LKMC_DUMP_SYSTEM_REGS_PRINTF("ID_AA64ISAR1_EL1.JSCVT 0x%" PRIX64 "\n", (id_aa64isar1_el1 >> 12) & 0xF);

    uint32_t id_isar0_el1;
    __asm__ ("mrs %0, id_isar0_el1" : "=r" (id_isar0_el1) : :);
    LKMC_DUMP_SYSTEM_REGS_PRINTF("ID_ISAR0_EL1 0x%" PRIX32 "\n", id_isar0_el1);

    /* https://cirosantilli.com/linux-kernel-module-cheat#arm-system-register-encodings */
    uint32_t id_isar6_el1;
    __asm__ ("mrs %0, s3_0_c0_c2_7" : "=r" (id_isar6_el1) : :);
    LKMC_DUMP_SYSTEM_REGS_PRINTF("ID_ISAR6_EL1 0x%" PRIX32 "\n", id_isar6_el1);

    uint64_t id_aa64pfr0_el1;
    __asm__ ("mrs %0, id_aa64pfr0_el1" : "=r" (id_aa64pfr0_el1) : :);
    LKMC_DUMP_SYSTEM_REGS_PRINTF("ID_AA64PFR0_EL1 0x%" PRIX64 "\n", id_aa64pfr0_el1);
    LKMC_DUMP_SYSTEM_REGS_PRINTF("ID_AA64PFR0_EL1.SVE 0x%" PRIX64 "\n", (id_aa64pfr0_el1 >> 32) & 0xF);

    uint64_t CurrentEL;
    __asm__ ("mrs %0, CurrentEL;" : "=r" (CurrentEL) : :);
    LKMC_DUMP_SYSTEM_REGS_PRINTF("CurrentEL 0x%" PRIX64 "\n", CurrentEL);
    /* https://cirosantilli.com/linux-kernel-module-cheat#arm-exception-levels */
    LKMC_DUMP_SYSTEM_REGS_PRINTF("CurrentEL.EL 0x%" PRIX64 "\n", CurrentEL >> 2);

    /* https://cirosantilli.com/linux-kernel-module-cheat#arm-paging */
    {
        uint64_t tcr_el1;
        __asm__ ("mrs %0, tcr_el1;" : "=r" (tcr_el1) : :);
        LKMC_DUMP_SYSTEM_REGS_PRINTF("TCR_EL1 0x%" PRIX64 "\n", tcr_el1);
        LKMC_DUMP_SYSTEM_REGS_PRINTF("TCR_EL1.A1 0x%" PRIX64 "\n", (tcr_el1 >> 22) & 1);

        uint64_t ttbr0_el1;
        __asm__ ("mrs %0, ttbr0_el1;" : "=r" (ttbr0_el1) : :);
        LKMC_DUMP_SYSTEM_REGS_PRINTF("TTBR0_EL1 0x%" PRIX64 "\n", ttbr0_el1);

        uint64_t ttbr1_el1;
        __asm__ ("mrs %0, ttbr1_el1;" : "=r" (ttbr1_el1) : :);
        LKMC_DUMP_SYSTEM_REGS_PRINTF("TTBR1_EL1 0x%" PRIX64 "\n", ttbr1_el1);
    }
}

#endif
