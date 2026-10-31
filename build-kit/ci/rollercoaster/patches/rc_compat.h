/* SPDX-License-Identifier: GPL-2.0 */
#ifndef __RC_COMPAT_H
#define __RC_COMPAT_H

#include <linux/types.h>

/* true bila proses saat ini adalah aplikasi Manager Rollercoaster
 * (dikenali dari path executable / APK-nya). */
bool rc_current_is_manager_pkg(void);

/* Cek izin su: allowlist kernel ATAU proses Manager Rollercoaster. */
bool rc_su_allowed_for_current(uid_t uid);

#endif /* __RC_COMPAT_H */
