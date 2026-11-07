#!/usr/bin/env python3
"""Offline guards and a stubbed execution of the actual patched KSU hook.

These host tests are not a live kernel, seccomp/BPF, Android or root test.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/synthetica3-seccomp/setuid_hook.c'
spec = importlib.util.spec_from_file_location('s3rc_test', ROOT / 'build-kit/scripts/build_synthetica3_rc.py')
s3 = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(s3)


def patched_source(directory: Path) -> str:
    path = directory / 'KernelSU-Next/kernel/hook/setuid_hook.c'
    path.parent.mkdir(parents=True)
    path.write_bytes(FIXTURE.read_bytes())
    subprocess.run(['git', 'apply', '--check', str(s3.PATCH)], cwd=directory, check=True)
    subprocess.run(['git', 'apply', str(s3.PATCH)], cwd=directory, check=True)
    if s3.s2x.v3.digest(path) != s3.SETUID_PATCHED_SHA256:
        raise AssertionError('patched source is not the pinned result')
    return path.read_text()


class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = s3.s2x.v3.verified_baseline(ROOT / 'artifacts/generated.config.txt')
        cls.tested = cls.baseline.replace('CONFIG_LOCALVERSION="-Synthetica-2.0"',
                                          'CONFIG_LOCALVERSION="-Synthetica-2.0-exp"')
        cls.tested += '\n' + '\n'.join((
            'CONFIG_UCLAMP_TASK=y', 'CONFIG_UCLAMP_TASK_GROUP=y', 'CONFIG_UCLAMP_BUCKETS_COUNT=5',
            'CONFIG_LRU_GEN=y', 'CONFIG_LRU_GEN_ENABLED=y', '# CONFIG_LRU_GEN_STATS is not set',
            'CONFIG_NR_LRU_GENS=7', 'CONFIG_TIERS_PER_GEN=4', ''))
        cls.candidate = cls.tested.replace('CONFIG_LOCALVERSION="-Synthetica-2.0-exp"',
                                           'CONFIG_LOCALVERSION="-Synthetica-3.0-rc1"')

    def test_inputs_and_manager_pin(self):
        s3.check_inputs()
        self.assertEqual(s3.s2x.v3.digest(FIXTURE), s3.SETUID_SOURCE_SHA256)
        self.assertEqual(s3.s2x.verify_manager()['package'], 'net.ember.labs')

    def test_tested_build_may_differ_only_in_localversion(self):
        with tempfile.TemporaryDirectory() as temp:
            baseline = Path(temp) / 'baseline'
            tested = Path(temp) / 'tested'
            generated = Path(temp) / 'candidate'
            baseline.write_text(self.baseline)
            tested.write_text(self.tested)
            generated.write_text(self.candidate)
            with mock.patch.object(s3, 'TESTED_CONFIG_SHA256', s3.s2x.v3.digest(tested)):
                changes = s3.check_config(baseline, generated, tested, 'on')
                self.assertEqual(list(changes['changes_from_user_tested_experiment']), ['LOCALVERSION'])
                for symbol in ('LRU_GEN_ENABLED', 'SECCOMP', 'SECCOMP_FILTER', 'KSU', 'THERMAL', 'MODULE_SIG_FORCE'):
                    bad = self.candidate.replace(f'CONFIG_{symbol}=y', f'# CONFIG_{symbol} is not set')
                    self.assertNotEqual(bad, self.candidate)
                    generated.write_text(bad)
                    with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                        s3.check_config(baseline, generated, tested, 'on')
                generated.write_text(self.candidate + 'CONFIG_UNREVIEWED_OPTION=y\n')
                with self.assertRaises(ValueError):
                    s3.check_config(baseline, generated, tested, 'on')
                generated.write_text(self.candidate)
                with self.assertRaises(ValueError):
                    s3.check_config(baseline, generated, tested, 'off')
            with self.assertRaisesRegex(ValueError, 'digest'):
                s3.compare_tested_config(tested, self.candidate)

    def test_real_tested_config_comparison_if_available(self):
        tested_path = os.environ.get('S3RC_TESTED_CONFIG')
        if not tested_path:
            self.skipTest('S3RC_TESTED_CONFIG not supplied; synthetic comparison covered separately')
        tested = Path(tested_path)
        text = tested.read_text()
        candidate = text.replace('CONFIG_LOCALVERSION="-Synthetica-2.0-exp"',
                                 'CONFIG_LOCALVERSION="-Synthetica-3.0-rc1"')
        self.assertNotEqual(candidate, text)
        self.assertEqual(list(s3.compare_tested_config(tested, candidate)), ['LOCALVERSION'])
        for symbol in ('SECCOMP', 'SECCOMP_FILTER', 'LRU_GEN_ENABLED', 'MODULE_SIG_FORCE'):
            bad = candidate.replace(f'CONFIG_{symbol}=y', f'# CONFIG_{symbol} is not set')
            with self.assertRaises(ValueError):
                s3.compare_tested_config(tested, bad)


class SetuidHookTests(unittest.TestCase):
    def test_patch_has_one_narrow_hunk_and_keeps_other_code_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            after = patched_source(Path(temp))
        before = FIXTURE.read_text()
        old = '#else\n\t\tdisable_seccomp(current);\n#endif\n\n#ifdef KSU_KPROBES_HOOK\n        ksu_set_task_tracepoint_flag(current);'
        new = '''#endif
        /* On pre-5.10 kernels there is no allow-cache. Keep the Manager's
         * inherited seccomp filter; it gets a KSU fd via task_work below.
         * The existing allowlisted-app and root-profile paths are unchanged.
         */

#ifdef KSU_KPROBES_HOOK
        ksu_set_task_tracepoint_flag(current);'''
        self.assertEqual(before.count(old), 1)
        self.assertEqual(after, before.replace(old, new, 1))
        self.assertEqual(after.count('disable_seccomp(current);'), 1)
        self.assertIn('cb->func = ksu_install_manager_fd_tw_func;', after)
        self.assertIn('if (ksu_is_allow_uid_for_current(new_uid))', after)
        self.assertNotIn('policy/app_profile.c', s3.PATCH.read_text())

    def test_actual_patched_hook_with_controlled_stubs(self):
        # Extract the real callback and function bodies from the patched source.
        # Stubs model a task, uid, callbacks and seccomp mode; no BPF executes.
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            source = patched_source(temp)
            start = source.index('static void ksu_install_manager_fd_tw_func(')
            end = source.index('\nextern void ksu_lsm_hook_init(', start)
            body = source[start:end]
            stubs = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stddef.h>
#include <sys/types.h>
#define CONFIG_KSU_SUSFS 1
#define CONFIG_KSU_SUSFS_SUS_MOUNT 1
#define KERNEL_VERSION(a,b,c) (((a)<<16)+((b)<<8)+(c))
#ifndef TEST_NEW_KERNEL
#define LINUX_VERSION_CODE KERNEL_VERSION(4,14,357)
#else
#define LINUX_VERSION_CODE KERNEL_VERSION(5,10,0)
#endif
#define SECCOMP_MODE_FILTER 2
#define __NR_reboot 142
#define GFP_ATOMIC 0
#define TWA_RESUME 0
#define unlikely(x) (x)
#define likely(x) (x)
#define pr_debug(...) ((void)0)
#define pr_info(...) ((void)0)
#define pr_warn(...) ((void)0)
struct callback_head { void (*func)(struct callback_head *); };
struct task_struct {
    struct { int mode; void *filter; } seccomp;
    struct callback_head *pending;
};
static struct task_struct task;
static struct task_struct *current = &task;
static int fd_installed, disable_calls, cache_calls, umount_calls, extra_calls, marked;
static int manager_uid = 10123, allowed_uid = 10234, sid_ok = 1, must_umount;
static int fail_alloc, fail_taskwork;
static unsigned int susfs_zygote_sid = 99;
struct uid_result { uid_t val; };
static struct uid_result current_uid(void) { return (struct uid_result){1000}; }
static void *current_cred(void) { return NULL; }
static bool susfs_is_sid_equal(void *cred, unsigned int sid) { (void)cred; (void)sid; return sid_ok; }
static bool is_zygote_isolated_service_uid(uid_t uid) { uid %= 100000; return uid >= 99000 && uid < 100000; }
static bool is_zygote_normal_app_uid(uid_t uid) { uid %= 100000; return uid >= 10000 && uid < 19999; }
static bool is_uid_manager(uid_t uid) { return uid == (uid_t)manager_uid; }
static bool ksu_is_allow_uid_for_current(uid_t uid) { return uid == (uid_t)allowed_uid; }
static bool ksu_uid_should_umount(uid_t uid) { (void)uid; return must_umount; }
static void *kzalloc(size_t n, int flags) { (void)flags; return fail_alloc ? NULL : calloc(1, n); }
static void kfree(void *p) { free(p); }
static int task_work_add(struct task_struct *t, struct callback_head *cb, int notify) {
    (void)notify; if (fail_taskwork) return -1; t->pending = cb; return 0;
}
static void ksu_install_fd(void) { fd_installed++; }
static void disable_seccomp(struct task_struct *t) { disable_calls++; t->seccomp.mode = 0; }
#ifdef TEST_NEW_KERNEL
static void ksu_seccomp_allow_cache(void *filter, int nr) { assert(filter && nr == __NR_reboot); cache_calls++; }
#endif
static void ksu_handle_umount(uid_t old, uid_t new_uid) { (void)old; (void)new_uid; umount_calls++; }
static void ksu_handle_extra_susfs_work(void) { extra_calls++; }
static void susfs_set_current_proc_umounted(void) { marked++; }
static void reset(void) {
    if (task.pending) { free(task.pending); task.pending = NULL; }
    task.seccomp.mode = SECCOMP_MODE_FILTER; task.seccomp.filter = &task;
    fd_installed = disable_calls = cache_calls = umount_calls = extra_calls = marked = 0;
    sid_ok = 1; must_umount = fail_alloc = fail_taskwork = 0;
}
'''
            main = r'''
int main(void) {
    /* Manager retains filter and still schedules the preexisting driver fd. */
    reset(); assert(ksu_handle_setresuid(10123, 10123, 10123) == 0);
    assert(task.seccomp.mode == SECCOMP_MODE_FILTER && disable_calls == 0);
    assert(task.pending && !fd_installed);
    struct callback_head *cb = task.pending; task.pending = NULL; cb->func(cb);
    assert(fd_installed == 1 && task.seccomp.mode == SECCOMP_MODE_FILTER);
#ifdef TEST_NEW_KERNEL
    assert(cache_calls == 1);
#else
    assert(cache_calls == 0);
#endif
    /* Allocation/task-work failures must not turn filtering off or invent an fd. */
    reset(); fail_alloc = 1; ksu_handle_setresuid(10123, 10123, 10123);
    assert(!task.pending && !fd_installed && task.seccomp.mode == SECCOMP_MODE_FILTER);
    reset(); fail_taskwork = 1; ksu_handle_setresuid(10123, 10123, 10123);
    assert(!task.pending && !fd_installed && task.seccomp.mode == SECCOMP_MODE_FILTER);
    /* Existing root-allowed UID branch remains unchanged. */
    reset(); ksu_handle_setresuid(10234, 10234, 10234);
#ifdef TEST_NEW_KERNEL
    assert(disable_calls == 0 && cache_calls == 1 && task.seccomp.mode == SECCOMP_MODE_FILTER);
#else
    assert(disable_calls == 1 && task.seccomp.mode == 0);
#endif
    assert(!task.pending && !fd_installed);
    /* A non-allowed app keeps its inherited filtering; it gets no KSU fd. */
    reset(); ksu_handle_setresuid(10555, 10555, 10555);
    assert(task.seccomp.mode == SECCOMP_MODE_FILTER && !disable_calls && !task.pending);
    /* SUSFS umount and isolated-service routes still take priority. */
    reset(); must_umount = 1; ksu_handle_setresuid(10555, 10555, 10555);
    assert(task.seccomp.mode == SECCOMP_MODE_FILTER && umount_calls == 1 && extra_calls == 1 && marked == 1);
    reset(); ksu_handle_setresuid(99001, 99001, 99001);
    assert(task.seccomp.mode == SECCOMP_MODE_FILTER && umount_calls == 1 && !disable_calls);
    /* No change for a non-zygote process or if no filter is installed. */
    reset(); sid_ok = 0; ksu_handle_setresuid(10123, 10123, 10123);
    assert(!task.pending && task.seccomp.mode == SECCOMP_MODE_FILTER && !disable_calls);
    reset(); task.seccomp.mode = 0; ksu_handle_setresuid(10123, 10123, 10123);
    assert(task.seccomp.mode == 0 && !disable_calls);  /* preservation cannot create a filter */
    assert(task.pending); free(task.pending); task.pending = NULL;
    return 0;
}
'''
            cfile = temp / 'hook-test.c'
            cfile.write_text(stubs + '\n' + body + '\n' + main)
            for label, defines in [('4.14', []), ('5.10-control', ['-DTEST_NEW_KERNEL'])]:
                binary = temp / ('test-' + label)
                cmd = ['gcc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                       '-Wno-unused-parameter', '-Wno-unused-function', *defines,
                       str(cfile), '-o', str(binary)]
                subprocess.run(cmd, check=True)
                subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
