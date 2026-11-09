#!/usr/bin/env python3
"""Research-only pending-refresh candidate tested in a deterministic host model.

The candidate is layered onto the separately pinned generation guard in a new
scratch directory. The harness executes extracted candidate C functions with
pthread, filesystem, RCU, credential and kthread shims. It deliberately tests
both a handled busy-worker schedule and an UNHANDLED failure-to-start schedule.
It does not run kernel code, prove memory ordering or authorize integration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import audit_s40_susfs_abi as abi
import build_synthetica40 as s40
import probe_s40_susfs_priority as priority

PATCH = ROOT / 'build-kit/ci/s40-susfs-abi/research-only-priority-pending.patch'
PINS = abi.PINS['research_priority_pending']


def apply_pending(guarded: str, directory: Path) -> str:
    patch = PATCH.read_bytes()
    if hashlib.sha256(patch).hexdigest() != PINS['patch_sha256']:
        raise ValueError('Pending candidate patch SHA-256 mismatch')
    lines = patch.decode('utf-8').splitlines()
    if (sum(line.startswith('--- ') for line in lines) != 1 or
            sum(line.startswith('+++ ') for line in lines) != 1 or
            lines[:2] != ['--- a/fs/susfs.c', '+++ b/fs/susfs.c']):
        raise ValueError('Unexpected pending candidate patch paths')
    if hashlib.sha256(guarded.encode()).hexdigest() != PINS['input_guarded_susfs_c_sha256']:
        raise ValueError('Pending candidate input source SHA-256 mismatch')
    s40.check_work_directory(directory, [])
    path = directory / 'fs/susfs.c'
    path.parent.mkdir(parents=True)
    path.write_text(guarded)
    priority.run(['git', 'apply', '--check', str(PATCH)], cwd=directory)
    priority.run(['git', 'apply', str(PATCH)], cwd=directory)
    result = path.read_text()
    if hashlib.sha256(result.encode()).hexdigest() != PINS['pending_guarded_susfs_c_sha256']:
        raise ValueError('Unexpected pending candidate output SHA-256')
    return result


def replace_once(text: str, before: str, after: str) -> str:
    if text.count(before) != 1:
        raise ValueError('Unexpected host-model shim anchor')
    return text.replace(before, after, 1)


# The worker's final CAS is instrumented so the harness can force requests
# immediately before or after it. The CAS itself remains a real host atomic.
CAS_SHIM = r'''
static pthread_mutex_t finish_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t finish_cond = PTHREAD_COND_INITIALIZER;
static int finish_mode; /* 1: pause before CAS, 2: pause after successful CAS */
static bool finish_waiting, finish_resume;
static void finish_pause_locked(void) {
    finish_mode = 0; /* only this transition is paused */
    finish_waiting = true;
    assert(pthread_cond_signal(&finish_cond) == 0);
    while (!finish_resume) assert(pthread_cond_wait(&finish_cond, &finish_lock) == 0);
}
static int model_cmpxchg(atomic_t *ptr, int old, int next) {
    bool at_finish = is_worker_thread && ptr == &susfs_priority_app_strings_running &&
                     old == SUSFS_PRIORITY_REFRESH_RUNNING && next == SUSFS_PRIORITY_REFRESH_IDLE;
    if (at_finish) {
        assert(pthread_mutex_lock(&finish_lock) == 0);
        if (finish_mode == 1) finish_pause_locked();
        assert(pthread_mutex_unlock(&finish_lock) == 0);
    }
    int result = __sync_val_compare_and_swap(ptr, old, next);
    if (at_finish && result == old) {
        assert(pthread_mutex_lock(&finish_lock) == 0);
        if (finish_mode == 2) finish_pause_locked();
        assert(pthread_mutex_unlock(&finish_lock) == 0);
    }
    return result;
}
'''

THREAD_SHIM = r'''
static pthread_t requested_workers[16];
static int requested_worker_count;
static pthread_mutex_t launch_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t launch_cond = PTHREAD_COND_INITIALIZER;
static bool force_launch_failure, block_failed_launch, launch_waiting, launch_resume;
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
    assert(pthread_mutex_lock(&launch_lock) == 0);
    if (force_launch_failure) {
        launch_waiting = true;
        assert(pthread_cond_signal(&launch_cond) == 0);
        while (block_failed_launch && !launch_resume)
            assert(pthread_cond_wait(&launch_cond, &launch_lock) == 0);
        force_launch_failure = false;
        assert(pthread_mutex_unlock(&launch_lock) == 0);
        return NULL;
    }
    assert(pthread_mutex_unlock(&launch_lock) == 0);
    struct thread_args *args = malloc(sizeof(*args));
    assert(args && requested_worker_count < 16);
    args->fn = fn;
    args->data = data;
    int index = requested_worker_count++;
    assert(pthread_create(&requested_workers[index], NULL, requested_worker_entry, args) == 0);
    return &requested_workers[index];
}
#define kthread_run(fn, data, name) fake_kthread_run((fn), (data), (name))
#define IS_ERR(ptr) ((ptr) == NULL)
'''

MAIN = r'''
static void set_names(const char *name) {
    struct st_susfs_priority_uid_filter *info = calloc(1, sizeof(*info));
    assert(info && strlen(name) < sizeof(info->app_strings));
    strcpy(info->app_strings, name);
    info->err = 126;
    void *user_info = info;
    susfs_set_priority_uid_filter(&user_info);
    assert(info->err == 0);
    free(info);
}
static void setup_uid(uid_t uid, bool pause) {
    assert(pthread_mutex_lock(&gate) == 0);
    alpha_uid = uid;
    waiting = false;
    resume_worker = false;
    pause_worker = pause;
    worker_resolutions = 0;
    assert(pthread_mutex_unlock(&gate) == 0);
}
static void update_uid(uid_t uid) {
    assert(pthread_mutex_lock(&gate) == 0);
    alpha_uid = uid;
    assert(pthread_mutex_unlock(&gate) == 0);
}
static void wait_for_snapshot(void) {
    assert(pthread_mutex_lock(&gate) == 0);
    while (!waiting) assert(pthread_cond_wait(&gate_cond, &gate) == 0);
    assert(pthread_mutex_unlock(&gate) == 0);
}
static void release_snapshot(void) {
    assert(pthread_mutex_lock(&gate) == 0);
    resume_worker = true;
    assert(pthread_cond_signal(&gate_cond) == 0);
    assert(pthread_mutex_unlock(&gate) == 0);
}
static void arm_finish(int mode) {
    assert(pthread_mutex_lock(&finish_lock) == 0);
    finish_mode = mode;
    finish_waiting = false;
    finish_resume = false;
    assert(pthread_mutex_unlock(&finish_lock) == 0);
}
static void wait_for_finish(void) {
    assert(pthread_mutex_lock(&finish_lock) == 0);
    while (!finish_waiting) assert(pthread_cond_wait(&finish_cond, &finish_lock) == 0);
    assert(pthread_mutex_unlock(&finish_lock) == 0);
}
static void release_finish(void) {
    assert(pthread_mutex_lock(&finish_lock) == 0);
    finish_resume = true;
    assert(pthread_cond_signal(&finish_cond) == 0);
    assert(pthread_mutex_unlock(&finish_lock) == 0);
}
static void join_worker(int index) {
    assert(index >= 0 && index < requested_worker_count);
    assert(pthread_join(requested_workers[index], NULL) == 0);
}
static void *request_entry(void *unused) {
    (void)unused;
    susfs_parse_priority_app_strings();
    return NULL;
}
int main(void) {
    alarm(20);
    _Static_assert(sizeof(struct st_susfs_priority_uid_filter) == 65540, "unexpected payload");

    /* Original generation guard still protects a newer configuration. */
    setup_uid(10001, true);
    set_names("sample.alpha");
    int index = requested_worker_count;
    susfs_parse_priority_app_strings();
    wait_for_snapshot();
    set_names("sample.beta");
    release_snapshot();
    join_worker(index);
    assert(!susfs_is_priority_uid_filtered(10001));
    assert(susfs_is_priority_uid_filtered(10002));

    /* Several requests while the worker has an old UID snapshot coalesce into
     * one subsequent pass of the same worker. */
    setup_uid(10001, true);
    set_names("sample.alpha");
    index = requested_worker_count;
    susfs_parse_priority_app_strings();
    wait_for_snapshot();
    update_uid(10003);
    susfs_parse_priority_app_strings();
    susfs_parse_priority_app_strings();
    susfs_parse_priority_app_strings();
    assert(requested_worker_count == index + 1);
    release_snapshot();
    join_worker(index);
    assert(worker_resolutions == 2);
    assert(!susfs_is_priority_uid_filtered(10001));
    assert(susfs_is_priority_uid_filtered(10003));
    assert(atomic_read(&susfs_priority_app_strings_running) == SUSFS_PRIORITY_REFRESH_IDLE);

    /* Request just BEFORE RUNNING->IDLE: it must cause a second pass. */
    setup_uid(10003, false);
    set_names("sample.alpha");
    arm_finish(1);
    index = requested_worker_count;
    susfs_parse_priority_app_strings();
    wait_for_finish();
    update_uid(10004);
    susfs_parse_priority_app_strings();
    release_finish();
    join_worker(index);
    assert(worker_resolutions == 2);
    assert(susfs_is_priority_uid_filtered(10004));
    assert(!susfs_is_priority_uid_filtered(10003));

    /* Request just AFTER RUNNING->IDLE starts a fresh worker. The first
     * worker has finished all shared-state accesses before the paused CAS. */
    setup_uid(10004, false);
    set_names("sample.alpha");
    arm_finish(2);
    index = requested_worker_count;
    susfs_parse_priority_app_strings();
    wait_for_finish();
    update_uid(10005);
    susfs_parse_priority_app_strings();
    assert(requested_worker_count == index + 2);
    join_worker(index + 1);
    release_finish();
    join_worker(index);
    assert(susfs_is_priority_uid_filtered(10005));
    assert(!susfs_is_priority_uid_filtered(10004));

    /* Known hole: a request arrives while kthread creation is blocked, then
     * creation fails. The pending request is lost when the state is reset. */
    setup_uid(10005, false);
    set_names("sample.alpha");
    assert(pthread_mutex_lock(&launch_lock) == 0);
    force_launch_failure = true;
    block_failed_launch = true;
    launch_waiting = false;
    launch_resume = false;
    assert(pthread_mutex_unlock(&launch_lock) == 0);
    index = requested_worker_count;
    pthread_t requester;
    assert(pthread_create(&requester, NULL, request_entry, NULL) == 0);
    assert(pthread_mutex_lock(&launch_lock) == 0);
    while (!launch_waiting) assert(pthread_cond_wait(&launch_cond, &launch_lock) == 0);
    assert(pthread_mutex_unlock(&launch_lock) == 0);
    update_uid(10006);
    susfs_parse_priority_app_strings();
    assert(atomic_read(&susfs_priority_app_strings_running) == SUSFS_PRIORITY_REFRESH_PENDING);
    assert(pthread_mutex_lock(&launch_lock) == 0);
    launch_resume = true;
    assert(pthread_cond_signal(&launch_cond) == 0);
    assert(pthread_mutex_unlock(&launch_lock) == 0);
    assert(pthread_join(requester, NULL) == 0);
    assert(requested_worker_count == index);
    assert(atomic_read(&susfs_priority_app_strings_running) == SUSFS_PRIORITY_REFRESH_IDLE);
    assert(susfs_is_priority_uid_filtered(10005));
    assert(!susfs_is_priority_uid_filtered(10006));
    /* A later independent request can recover; it is not guaranteed. */
    susfs_parse_priority_app_strings();
    join_worker(index);
    assert(!susfs_is_priority_uid_filtered(10005));
    assert(susfs_is_priority_uid_filtered(10006));

    free(priority_uid_filter_bitmap);
    free(susfs_priority_app_strings);
    puts("modeled busy and exit schedules improve; failed launch still drops an event");
    return 0;
}
'''


def build_program(source: str, header: str, expected_source: str, main: str) -> str:
    if hashlib.sha256(source.encode()).hexdigest() != expected_source:
        raise ValueError('Unpinned pending candidate source')
    if hashlib.sha256(header.encode()).hexdigest() != abi.PINS['sources']['susfs'][priority.HEADER]:
        raise ValueError('Unpinned priority header')
    parts = priority.source_parts(source, header)
    once = priority.extract_function(source, 'static int susfs_priority_app_strings_worker_once(')
    preamble = replace_once(priority.PREAMBLE,
        '#define atomic_cmpxchg(p, old, new) __sync_val_compare_and_swap((p), (old), (new))',
        'static int model_cmpxchg(atomic_t *ptr, int old, int next);\n'
        '#define atomic_cmpxchg(p, old, new) model_cmpxchg((p), (old), (new))\n'
        '#define atomic_read(p) __atomic_load_n((p), __ATOMIC_SEQ_CST)\n'
        '#define atomic_xchg(p, v) __atomic_exchange_n((p), (v), __ATOMIC_SEQ_CST)')
    resolver = replace_once(priority.RESOLVER,
        'static uid_t alpha_uid = 10001; /* protected by gate */',
        'static uid_t alpha_uid = 10001; /* protected by gate */\nstatic int worker_resolutions;')
    resolver = replace_once(resolver,
        'if (is_worker_thread && pause_worker) {',
        'if (is_worker_thread) worker_resolutions++;\n        if (is_worker_thread && pause_worker) {')
    return '\n'.join((preamble, parts['globals'], parts['payload'], parts['valid'], resolver,
                      CAS_SHIM, parts['parse'], parts['set'], once, parts['worker'], THREAD_SHIM,
                      parts['request'], parts['lookup'], main))


def program(source: str, header: str) -> str:
    return build_program(source, header, PINS['pending_guarded_susfs_c_sha256'], MAIN)


def probe(susfs: Path, compiler: str = 'gcc') -> dict:
    original = priority.checked_susfs_file(susfs, priority.SOURCE)
    header = priority.checked_susfs_file(susfs, priority.HEADER)
    with tempfile.TemporaryDirectory(prefix='s40-susfs-pending-host-model-') as temporary:
        temp = Path(temporary)
        guarded = priority.apply_candidate(original, temp / 'generation')
        pending = apply_pending(guarded, temp / 'pending')
        source, executable = temp / 'pending-model.c', temp / 'pending-host-probe'
        source.write_text(program(pending, header))
        priority.run([compiler, '-std=gnu11', '-O1', '-Wall', '-Wextra', '-Werror',
                      '-Wno-unused-parameter', '-pthread', str(source), '-o', str(executable)])
        priority.run([str(executable)])
    return {
        'scope': 'HOST_SHIM_SCHEDULE_MODEL_ONLY',
        'generation_guard_preserves_new_config_in_model': True,
        'busy_requests_coalesce_into_another_pass_in_model': True,
        'requests_immediately_before_and_after_idle_transition_modeled': True,
        'failed_worker_creation_can_still_drop_concurrent_request_in_model': True,
        'later_request_can_recover_after_modeled_failure': True,
        'candidate_is_complete_or_safe_for_kernel': False,
        'real_rcu_filesystem_selinux_kthreads_or_device_tested': False,
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
    except (OSError, ValueError, RuntimeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
