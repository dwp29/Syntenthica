/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Rollercoaster — pengenalan Manager tanpa bergantung pada pemindaian paket.
 *
 * Masalah: KernelSU menentukan "Manager" dengan memindai /data/app lalu mencocokkan
 * sertifikat. Kalau pemindaian itu gagal (mis. parse sertifikat / timing boot),
 * ksu_manager_appid tetap -1, is_uid_manager() selalu false, dan sucompat tidak
 * pernah memberi root ke aplikasi Manager — walau kernelnya sehat.
 *
 * Solusi: pengenalan langsung dari path executable proses yang memanggil su.
 * Untuk proses aplikasi, mm->exe_file adalah APK-nya, mis.
 *   /data/app/~~xxxx/com.rifsxd.ksunext-yyyy/base.apk
 * Jadi cukup menelusuri nama dentry 3 tingkat ke atas. Tidak ada alokasi memori,
 * tidak ada I/O, aman dipanggil dari syscall hook (tidak bisa sleep).
 */

#include <linux/cred.h>
#include <linux/dcache.h>
#include <linux/fs.h>
#include <linux/kernel.h>
#include <linux/mm.h>
#include <linux/sched.h>
#include <linux/string.h>

#include "rc_compat.h"
#include "manager/manager_identity.h"
#include "policy/allowlist.h"

#define RC_MANAGER_PKG "com.rifsxd.ksunext"

bool rc_current_is_manager_pkg(void)
{
	struct file *exe;
	struct dentry *d;
	int i;

	if (!current)
		return false;

	/* Proses kernel thread tidak punya mm. */
	if (!current->mm)
		return false;

	exe = current->mm->exe_file;
	if (!exe)
		return false;

	d = exe->f_path.dentry;
	for (i = 0; i < 3 && d; i++) {
		const char *name = d->d_name.name;

		if (name && strstr(name, RC_MANAGER_PKG))
			return true;

		if (d == d->d_parent)
			break;
		d = d->d_parent;
	}

	return false;
}

bool rc_su_allowed_for_current(uid_t uid)
{
	if (ksu_is_allow_uid_for_current(uid))
		return true;

	return rc_current_is_manager_pkg();
}

static int __init rc_compat_init(void)
{
	pr_info("rc_compat: aktif (pengenalan Manager via exe path)\n");
	pr_info("rc_compat: manager_appid=%d valid=%d\n",
		(int)ksu_get_manager_appid(),
		ksu_is_manager_appid_valid() ? 1 : 0);
	return 0;
}
late_initcall(rc_compat_init);
