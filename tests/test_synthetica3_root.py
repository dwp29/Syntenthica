#!/usr/bin/env python3
"""Source, security-boundary and real host exec/seccomp tests; not Android tests."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/synthetica3-root'
spec = importlib.util.spec_from_file_location('s3root_test', ROOT / 'build-kit/scripts/build_synthetica3_root.py')
build = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(build)


def patched_sources(directory: Path) -> tuple[str, str]:
    shutil.copytree(FIXTURE / 'fs', directory / 'fs')
    shutil.copytree(FIXTURE / 'KernelSU-Next', directory / 'KernelSU-Next')
    build.verify_root_source(directory, patched=False)
    # The prior MGLRU patch also touches fs/exec.c, but not the exec hook.
    subprocess.run(['git', 'apply', '--include=fs/exec.c',
                    str(ROOT / 'build-kit/ci/synthetica2-experimental/patches/0001-mglru-4.14.patch')],
                   cwd=directory, check=True)
    subprocess.run(['git', 'apply', '--check', str(build.PATCH)], cwd=directory, check=True)
    subprocess.run(['git', 'apply', str(build.PATCH)], cwd=directory, check=True)
    build.verify_root_source(directory, patched=True)
    return ((directory / 'fs/exec.c').read_text(),
            (directory / 'KernelSU-Next/kernel/supercall/supercall.c').read_text())


def helper(source: str) -> str:
    start = source.index('void ksu_install_manager_exec_fd(')
    end = source.index('\nbool ksu_is_su_session_fd(', start)
    return source[start:end]


def compile_and_run(directory: Path, source: str, name: str) -> None:
    path = directory / (name + '.c')
    binary = directory / name
    path.write_text(source)
    subprocess.run(['gcc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', str(path), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=15)


class RootCandidateGuardTests(unittest.TestCase):
    def test_pinned_source_patch_and_success_only_call_site(self):
        build.check_inputs()
        with tempfile.TemporaryDirectory() as name:
            exec_c, supercall = patched_sources(Path(name))
        self.assertIn('''retval = exec_binprm(bprm);
\tif (retval < 0)
\t\tgoto out;

#ifdef CONFIG_KSU''', exec_c)
        hook = exec_c.index('ksu_install_manager_exec_fd(bprm->filename);')
        self.assertLess(exec_c.index('retval = exec_binprm(bprm);'), hook)
        self.assertLess(hook, exec_c.index('free_bprm(bprm);', hook))
        self.assertEqual(exec_c.count('ksu_install_manager_exec_fd(bprm->filename);'), 1)
        self.assertIn('return ksu_install_fd_with_permissions(O_CLOEXEC, 0);', supercall)
        self.assertIn('return ksu_install_fd_with_permissions(O_CLOEXEC, KSU_DRIVER_PERMISSION_SU_SESSION);', supercall)
        body = helper(supercall)
        self.assertIn('!ksu_is_manager_appid_valid() || !is_manager()', body)
        self.assertIn('strcmp(name + 1, "libksud.so")', body)
        self.assertIn('ksu_install_fd()', body)
        for forbidden in ('ksu_install_su_fd', 'disable_seccomp', 'escape_with_root_profile'):
            self.assertNotIn(forbidden, body)
        # The patch never changes seccomp policy, ioctl authorization, setuid,
        # root profiles, or the separate legacy su-session behavior.
        patch = build.PATCH.read_text()
        self.assertEqual(patch.count('diff --git '), 2)
        for forbidden in ('kernel/seccomp.c', 'supercall/perm.c', 'policy/app_profile.c', 'feature/sucompat.c'):
            self.assertNotIn('diff --git a/' + forbidden, patch)

    def test_pinned_inputs_detect_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            tree = Path(d)
            shutil.copytree(FIXTURE / 'fs', tree / 'fs')
            shutil.copytree(FIXTURE / 'KernelSU-Next', tree / 'KernelSU-Next')
            build.verify_root_source(tree, patched=False)
            path = tree / 'fs/exec.c'
            path.write_bytes(path.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'unexpected Manager helper source'):
                build.verify_root_source(tree, patched=False)
        with mock.patch.object(build, 'PATCH_SHA256', '0' * 64), self.assertRaisesRegex(ValueError, 'digest'):
            build.check_inputs()

    def test_actual_helper_uid_path_and_failure_boundaries(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            _, supercall = patched_sources(directory)
            stubs = r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
static int valid, manager, installed, warned, fail_install;
static int mode = 2;
static bool ksu_is_manager_appid_valid(void) { return valid; }
static bool is_manager(void) { return manager; }
static int ksu_install_fd(void) { installed++; return fail_install ? -1 : 4; }
#define pr_warn(...) (warned++)
'''
            main = r'''
int main(void) {
    const char *good = "/data/app/~~id/net.ember.labs-id/lib/arm64/libksud.so";
    const char *bad[] = {0, "", "libksud.so", "/system/bin/su", "/libksud.so.old",
                         "/libksud.so/other", "/libksud.so2", "/libksud.sO"};
    valid = manager = 1;
    for (unsigned i = 0; i < sizeof(bad)/sizeof(bad[0]); i++) {
        ksu_install_manager_exec_fd(bad[i]);
        assert(installed == 0 && mode == 2);
    }
    ksu_install_manager_exec_fd(good);
    assert(installed == 1 && warned == 0 && mode == 2);
    valid = 0; ksu_install_manager_exec_fd(good); assert(installed == 1);
    valid = 1; manager = 0; ksu_install_manager_exec_fd(good); assert(installed == 1);
    manager = 1; fail_install = 1; ksu_install_manager_exec_fd(good);
    assert(installed == 2 && warned == 1 && mode == 2);
    return 0;
}
'''
            compile_and_run(directory, stubs + helper(supercall) + main, 'scope-test')

    @unittest.skipUnless(os.name == 'posix' and Path('/proc/self/fd').is_dir(), 'Linux procfs required')
    def test_real_host_exec_cloexec_and_bpf_with_stub_driver(self):
        # Actual Linux exec, FD_CLOEXEC, and BPF; the driver is deliberately a
        # /dev/null stub and helper injection is called in userspace after exec.
        # This proves the lifecycle, not the Android kernel hook or root access.
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            _, supercall = patched_sources(directory)
            stubs = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>
static int injected = -1;
static bool ksu_is_manager_appid_valid(void) { return true; }
static bool is_manager(void) { return true; }
static int ksu_install_fd(void) { injected = open("/dev/null", O_RDONLY | O_CLOEXEC); return injected; }
#define pr_warn(...) ((void)0)
'''
            main = r'''
int main(int argc, char **argv) {
    if (argc == 1) {
        struct sock_filter filter[] = {
            BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
            BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_reboot, 0, 1),
            BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
            BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        };
        struct sock_fprog prog = { .len = sizeof(filter)/sizeof(filter[0]), .filter = filter };
        int old = open("/dev/null", O_RDONLY | O_CLOEXEC);
        char fd[24]; assert(old >= 0); snprintf(fd, sizeof(fd), "%d", old);
        assert(prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == 0);
        assert(prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog) == 0);
        execl("/proc/self/exe", "host-exec", "after-first", fd, (char *)NULL);
        return 100;
    }
    int old = atoi(argv[2]);
    errno = 0; assert(fcntl(old, F_GETFD) == -1 && errno == EBADF);
    assert(prctl(PR_GET_SECCOMP, 0, 0, 0, 0) == SECCOMP_MODE_FILTER);
    errno = 0; assert(syscall(SYS_reboot, 0, 0, 0, 0) == -1 && errno == EPERM);
    if (strcmp(argv[1], "after-first") == 0) {
        ksu_install_manager_exec_fd("/data/app/manager/lib/arm64/libksud.so");
        assert(injected >= 0 && (fcntl(injected, F_GETFD) & FD_CLOEXEC));
        int value = 0;
        errno = 0; assert(ioctl(injected, FIONREAD, &value) == -1 && errno == ENOTTY);
        char fd[24]; snprintf(fd, sizeof(fd), "%d", injected);
        execl("/proc/self/exe", "host-exec", "after-second", fd, (char *)NULL);
        return 101;
    }
    assert(strcmp(argv[1], "after-second") == 0);
    return 0;
}
'''
            compile_and_run(directory, stubs + helper(supercall) + main, 'exec-bpf-test')

    def test_standard_release_and_preserved_feature_guards(self):
        self.assertEqual(build.EXPECTED_RELEASE, '4.14.357-openela-synthetica-3.0')
        self.assertEqual(build.rc.EXPECTED_LOCALVERSION, '"-synthetica-3.0"')
        self.assertEqual(build.rc.s2x.EXPECTED_RELEASE, build.EXPECTED_RELEASE)
        for marker in ('"SECCOMP"', '"SECCOMP_FILTER"', '"MODULE_SIG_FORCE"', '"MODVERSIONS"'):
            self.assertIn(marker, (ROOT / 'build-kit/scripts/build_synthetica3_rc.py').read_text())


if __name__ == '__main__':
    unittest.main()
