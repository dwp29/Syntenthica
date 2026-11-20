/* Shim for Linux 4.14: <linux/unaligned.h> was split out of
 * <asm/unaligned.h> in 5.5. Only the riscv64 patch path used it. */
#ifndef _BKA_COMPAT_LINUX_UNALIGNED_H
#define _BKA_COMPAT_LINUX_UNALIGNED_H
#include <asm/unaligned.h>
#endif
