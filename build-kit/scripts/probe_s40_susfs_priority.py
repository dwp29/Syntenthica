#!/usr/bin/env python3
"""Model one priority-filter publication race in pinned SUSFS 2.4 source.

Extracts actual upstream functions into a host harness. Fake file resolution,
credentials, user copies, allocation and RCU substitute for kernel facilities;
pthreads provide deliberately scheduled interleavings for a stale configuration
and a lost refresh request. Also tests a small, unintegrated candidate guard
applied ONLY to a temporary source copy. Neither this model nor that candidate
is a kernel/device test or a complete SUSFS port.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import audit_s40_susfs_abi as abi

PATCH = ROOT / 'build-kit/ci/s40-susfs-abi/research-only-priority-generation.patch'
SOURCE = 'kernel_patches/fs/susfs.c'
HEADER = 'kernel_patches/include/linux/susfs.h'


def checked_susfs_file(root: Path, relative: str) -> str:
    expected = abi.PINS['sources']['susfs'][relative]
    root = root.resolve(strict=True)
    path = root
    for part in Path(relative).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f'Symlinked source path: {path}')
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f'Missing or unpinned SUSFS source: {path}')
    return path.read_text()


def extract_function(source: str, signature: str) -> str:
    if source.count(signature) != 1:
        raise ValueError(f'Expected one source function: {signature}')
    start = source.index(signature)
    end = source.find('\n}', start)
    if end < 0:
        raise ValueError(f'Unterminated source function: {signature}')
    return source[start:end + 2]


def source_parts(source: str, header: str) -> dict[str, str]:
    start_marker = '#define SUSFS_PRIORITY_UID_FILTER_MIN_UID '
    end_marker = 'static atomic_t susfs_priority_app_strings_running = ATOMIC_INIT(0);'
    if source.count(start_marker) != 1 or source.count(end_marker) != 1:
        raise ValueError('Unexpected upstream priority globals')
    start, end = source.index(start_marker), source.index(end_marker) + len(end_marker)
    if end <= start:
        raise ValueError('Priority source globals out of order')
    struct_def = abi.extract_structs([header], {'st_susfs_priority_uid_filter'})
    constants = abi.numeric_defines([header])
    if constants.get('SUSFS_APP_STR_BUF_SIZE') != 65535 or len(struct_def) != 1:
        raise ValueError('Unexpected priority payload source')
    return {
        'globals': source[start:end],
        'payload': struct_def['st_susfs_priority_uid_filter']['definition'],
        'valid': extract_function(source, 'static bool susfs_is_valid_app_name('),
        'parse': extract_function(source, 'static int susfs_parse_priority_app_names('),
        'set': extract_function(source, 'void susfs_set_priority_uid_filter('),
        'worker': extract_function(source, 'static int susfs_priority_app_strings_worker('),
        'request': extract_function(source, 'void susfs_parse_priority_app_strings('),
        'lookup': extract_function(source, 'bool susfs_is_priority_uid_filtered('),
    }


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, **kwargs)
    if result.returncode:
        raise RuntimeError(f'{Path(command[0]).name} returned {result.returncode}: '
                           f'{(result.stdout + result.stderr)[-4000:]}')
    return result


def apply_candidate(original: str, directory: Path) -> str:
    pin = abi.PINS['research_priority_guard']
    patch = PATCH.read_bytes()
    if hashlib.sha256(patch).hexdigest() != pin['patch_sha256']:
        raise ValueError('Research-only candidate patch SHA-256 mismatch')
    lines = patch.decode('utf-8').splitlines()
    if (sum(line.startswith('--- ') for line in lines) != 1 or
            sum(line.startswith('+++ ') for line in lines) != 1 or
            lines[:2] != ['--- a/fs/susfs.c', '+++ b/fs/susfs.c']):
        raise ValueError('Unexpected patch paths')
    if hashlib.sha256(original.encode()).hexdigest() != abi.PINS['sources']['susfs'][SOURCE]:
        raise ValueError('Original research source SHA-256 mismatch')
    path = directory / 'fs/susfs.c'
    path.parent.mkdir(parents=True)
    path.write_text(original)
    # The tiny patch uses zero-context hunks. Both the ENTIRE input and output
    # are pinned, and application is confined to this newly created scratch.
    run(['git', 'apply', '--unidiff-zero', '--check', str(PATCH)], cwd=directory)
    run(['git', 'apply', '--unidiff-zero', str(PATCH)], cwd=directory)
    changed = path.read_text()
    if hashlib.sha256(changed.encode()).hexdigest() != pin['guarded_susfs_c_sha256']:
        raise ValueError('Unexpected guarded research source hash')
    return changed


PREAMBLE = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <ctype.h>
#include <sys/types.h>
#include <pthread.h>
#include <unistd.h>
typedef uint64_t u64;
typedef int atomic_t;
struct rcu_head { int unused; };
struct cred { int unused; };
#define __rcu
#define __user
#define ATOMIC_INIT(x) (x)
#define atomic_set(p, v) __atomic_store_n((p), (v), __ATOMIC_SEQ_CST)
#define atomic_cmpxchg(p, old, new) __sync_val_compare_and_swap((p), (old), (new))
#define DEFINE_MUTEX(name) pthread_mutex_t name = PTHREAD_MUTEX_INITIALIZER
#define GFP_KERNEL 1
#define __GFP_ZERO 2
#define BITS_PER_LONG (sizeof(unsigned long) * 8)
#define BITS_TO_LONGS(n) (((n) + BITS_PER_LONG - 1) / BITS_PER_LONG)
#define SUSFS_APP_STR_BUF_SIZE 65535
#define SUSFS_LOGI(...) ((void)0)
#define SUSFS_LOGE(...) ((void)0)
#define likely(x) (x)
#define rcu_dereference(p) (p)
#define rcu_dereference_protected(p, held) (p)
#define rcu_assign_pointer(p, value) ((p) = (value))
#define kfree_rcu(p, member) free(p)
static void synchronize_rcu(void) { /* no concurrent readers in this model */ }
static void mutex_lock(pthread_mutex_t *m) { assert(pthread_mutex_lock(m) == 0); }
static void mutex_unlock(pthread_mutex_t *m) { assert(pthread_mutex_unlock(m) == 0); }
static void *kvmalloc(size_t n, int flags) { (void)flags; return calloc(1, n); }
static void *kzalloc(size_t n, int flags) { (void)flags; return calloc(1, n); }
static void kvfree(void *p) { free(p); }
static void kfree(void *p) { free(p); }
static int copy_from_user(void *to, const void *from, size_t n) { memcpy(to, from, n); return 0; }
static int copy_to_user(void *to, const void *from, size_t n) { memcpy(to, from, n); return 0; }
static struct cred fake_cred;
static struct cred *susfs_switch_to_ksu_domain(void) { return &fake_cred; }
static void susfs_restore_creds(struct cred *cred) { (void)cred; }
static void set_bit(unsigned long bit, unsigned long *bits) {
    bits[bit / BITS_PER_LONG] |= 1UL << (bit % BITS_PER_LONG);
}
static bool test_bit(unsigned long bit, const unsigned long *bits) {
    return !!(bits[bit / BITS_PER_LONG] & (1UL << (bit % BITS_PER_LONG)));
}
static char *strim(char *s) {
    while (isspace((unsigned char)*s)) ++s;
    char *end = s + strlen(s);
    while (end > s && isspace((unsigned char)end[-1])) *--end = '\0';
    return s;
}
'''

RESOLVER = r'''
/* Deterministic stand-in for filesystem/SELinux-dependent package resolution. */
static pthread_mutex_t gate = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t gate_cond = PTHREAD_COND_INITIALIZER;
static bool waiting, resume_worker, pause_worker = true;
static uid_t alpha_uid = 10001; /* protected by gate */
static _Thread_local bool is_worker_thread;
static int susfs_resolve_priority_app_uid(const char *name, uid_t *uid) {
    if (!strcmp(name, "sample.alpha")) {
        assert(pthread_mutex_lock(&gate) == 0);
        uid_t resolved = alpha_uid;
        if (is_worker_thread && pause_worker) {
            /* Pause AFTER taking the simulated packages.list UID snapshot. */
            waiting = true;
            assert(pthread_cond_signal(&gate_cond) == 0);
            while (!resume_worker) assert(pthread_cond_wait(&gate_cond, &gate) == 0);
        }
        assert(pthread_mutex_unlock(&gate) == 0);
        *uid = resolved;
        return 0;
    }
    if (!strcmp(name, "sample.beta")) { *uid = 10002; return 0; }
    return -ENOENT;
}
'''

THREAD_SHIM = r'''
/* kthread stand-in: records requests and joins from the harness, not kernel code. */
static pthread_t requested_worker;
static int requested_worker_count;
struct thread_args { int (*fn)(void *); void *data; };
static void *requested_worker_entry(void *opaque) {
    struct thread_args args = *(struct thread_args *)opaque;
    free(opaque);
    is_worker_thread = true;
    assert(args.fn(args.data) == 0);
    return NULL;
}
static void *fake_kthread_run(int (*fn)(void *), void *data, const char *name) {
    (void)name;
    struct thread_args *args = malloc(sizeof(*args));
    if (!args) return NULL;
    args->fn = fn;
    args->data = data;
    if (pthread_create(&requested_worker, NULL, requested_worker_entry, args)) {
        free(args);
        return NULL;
    }
    requested_worker_count++;
    return &requested_worker;
}
#define kthread_run(fn, data, name) fake_kthread_run((fn), (data), (name))
#define IS_ERR(ptr) ((ptr) == NULL)
'''

MAIN = r'''
static void set_names(const char *name) {
    struct st_susfs_priority_uid_filter *info = calloc(1, sizeof(*info));
    assert(info);
    assert(strlen(name) < sizeof(info->app_strings));
    strcpy(info->app_strings, name);
    info->err = 126;
    void *user_info = info;
    susfs_set_priority_uid_filter(&user_info);
    assert(info->err == 0);
    free(info);
}
static void *worker_entry(void *unused) {
    (void)unused;
    is_worker_thread = true;
    int ret = susfs_priority_app_strings_worker(NULL);
    assert(ret == 0);
    return NULL;
}
int main(int argc, char **argv) {
    alarm(15);
    assert(argc == 2 && (!strcmp(argv[1], "original") || !strcmp(argv[1], "guarded")));
    const bool guarded = !strcmp(argv[1], "guarded");
    _Static_assert(sizeof(struct st_susfs_priority_uid_filter) == 65540, "unexpected payload size");
    _Static_assert(offsetof(struct st_susfs_priority_uid_filter, err) == 65536, "unexpected err offset");
    assert(susfs_is_valid_app_name("sample.alpha_1"));
    assert(!susfs_is_valid_app_name("") && !susfs_is_valid_app_name(".."));
    assert(!susfs_is_valid_app_name("sample/alpha") && !susfs_is_valid_app_name("sample-alpha"));
    set_names("sample.alpha");
    assert(susfs_is_priority_uid_filtered(10001));
    assert(susfs_is_priority_uid_filtered(110001)); /* Android user-id normalization */
    assert(!susfs_is_priority_uid_filtered(10002));
    assert(!susfs_is_priority_uid_filtered(20000));
    assert(susfs_priority_app_strings_worker(NULL) == 0); /* ordinary refresh */
    assert(susfs_is_priority_uid_filtered(10001));

    pthread_t thread;
    assert(pthread_create(&thread, NULL, worker_entry, NULL) == 0);
    assert(pthread_mutex_lock(&gate) == 0);
    while (!waiting) assert(pthread_cond_wait(&gate_cond, &gate) == 0);
    assert(pthread_mutex_unlock(&gate) == 0);

    /* The worker has copied alpha but is paused before resolving it. */
    set_names("sample.beta");
    assert(!strcmp(susfs_priority_app_strings, "sample.beta"));
    assert(!susfs_is_priority_uid_filtered(10001));
    assert(susfs_is_priority_uid_filtered(10002));

    assert(pthread_mutex_lock(&gate) == 0);
    resume_worker = true;
    assert(pthread_cond_signal(&gate_cond) == 0);
    assert(pthread_mutex_unlock(&gate) == 0);
    assert(pthread_join(thread, NULL) == 0);
    assert(!strcmp(susfs_priority_app_strings, "sample.beta"));
    if (guarded) {
        assert(!susfs_is_priority_uid_filtered(10001));
        assert(susfs_is_priority_uid_filtered(10002));
    } else {
        /* The original worker has overwritten beta with its stale alpha bitmap. */
        assert(susfs_is_priority_uid_filtered(10001));
        assert(!susfs_is_priority_uid_filtered(10002));
    }
    /* Another nonconcurrent refresh can recover; it is not guaranteed to happen. */
    assert(susfs_priority_app_strings_worker(NULL) == 0);
    assert(!susfs_is_priority_uid_filtered(10001));
    assert(susfs_is_priority_uid_filtered(10002));

    /* Second schedule: an app's simulated UID changes while a refresh is
     * running. The real request function discards a second request while busy;
     * a configuration-generation guard cannot observe this UID-only change. */
    set_names("sample.alpha");
    assert(susfs_is_priority_uid_filtered(10001));
    assert(pthread_mutex_lock(&gate) == 0);
    waiting = false;
    resume_worker = false;
    pause_worker = true;
    assert(pthread_mutex_unlock(&gate) == 0);
    susfs_parse_priority_app_strings();
    assert(requested_worker_count == 1);
    assert(pthread_mutex_lock(&gate) == 0);
    while (!waiting) assert(pthread_cond_wait(&gate_cond, &gate) == 0);
    alpha_uid = 10003; /* simulated packages.list update after worker snapshot */
    assert(pthread_mutex_unlock(&gate) == 0);
    susfs_parse_priority_app_strings(); /* deliberately arrives while busy */
    assert(requested_worker_count == 1); /* request was dropped, not queued */
    assert(pthread_mutex_lock(&gate) == 0);
    resume_worker = true;
    assert(pthread_cond_signal(&gate_cond) == 0);
    assert(pthread_mutex_unlock(&gate) == 0);
    assert(pthread_join(requested_worker, NULL) == 0);
    assert(!strcmp(susfs_priority_app_strings, "sample.alpha"));
    assert(susfs_is_priority_uid_filtered(10001));
    assert(!susfs_is_priority_uid_filtered(10003));

    /* A separate later request can recover, but the dropped event did not. */
    assert(pthread_mutex_lock(&gate) == 0);
    pause_worker = false;
    assert(pthread_mutex_unlock(&gate) == 0);
    susfs_parse_priority_app_strings();
    assert(requested_worker_count == 2);
    assert(pthread_join(requested_worker, NULL) == 0);
    assert(!susfs_is_priority_uid_filtered(10001));
    assert(susfs_is_priority_uid_filtered(10003));
    free(priority_uid_filter_bitmap);
    free(susfs_priority_app_strings);
    puts(guarded ? "guard retained newer config; busy refresh still dropped" :
                   "original published stale config; busy refresh also dropped");
    return 0;
}
'''


def build_and_run(source: str, header: str, compiler: str, directory: Path, mode: str) -> None:
    parts = source_parts(source, header)
    program = '\n'.join((PREAMBLE, parts['globals'], parts['payload'], parts['valid'], RESOLVER,
                         parts['parse'], parts['set'], parts['worker'], THREAD_SHIM, parts['request'],
                         parts['lookup'], MAIN))
    c_file, exe = directory / f'{mode}.c', directory / f'{mode}-host-probe'
    c_file.write_text(program)
    run([compiler, '-std=gnu11', '-O1', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
         '-pthread', str(c_file), '-o', str(exe)])
    run([str(exe), mode])


def probe(susfs: Path, compiler: str = 'gcc') -> dict:
    original = checked_susfs_file(susfs, SOURCE)
    header = checked_susfs_file(susfs, HEADER)
    with tempfile.TemporaryDirectory(prefix='s40-susfs-priority-host-model-') as temporary:
        temp = Path(temporary)
        guarded = apply_candidate(original, temp / 'scratch')
        build_and_run(original, header, compiler, temp, 'original')
        build_and_run(guarded, header, compiler, temp, 'guarded')
    return {
        'scope': 'HOST_SHIM_SCHEDULE_MODEL_ONLY',
        'upstream_functions_extracted_from_pinned_source': True,
        'baseline_worker_can_publish_stale_bitmap_in_modeled_interleaving': True,
        'research_generation_guard_preserves_newer_bitmap_in_same_model': True,
        'another_sequential_refresh_recovers_in_model': True,
        'busy_refresh_request_can_be_lost_in_second_scheduled_model': True,
        'research_generation_guard_does_not_prevent_lost_uid_refresh': True,
        'later_request_recovers_after_simulated_uid_change': True,
        'candidate_patch_applied_to_kernel_or_release': False,
        'real_rcu_filesystem_selinux_faults_or_device_tested': False,
        'full_concurrency_or_refresh_correctness_proven': False,
        'susfs_2_4_integrated': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--susfs', required=True, type=Path)
    parser.add_argument('--cc', default='gcc')
    args = parser.parse_args()
    print(json.dumps(probe(args.susfs, args.cc), indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
