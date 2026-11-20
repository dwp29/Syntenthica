/* Shim for Linux 4.14: <linux/hex.h> arrived after this tree was cut.
 * bin2hex() lives in <linux/kernel.h> here, with the same signature. */
#ifndef _BKA_COMPAT_LINUX_HEX_H
#define _BKA_COMPAT_LINUX_HEX_H
#include <linux/kernel.h>
#endif
