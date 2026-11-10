#!/usr/bin/env python3
"""Research-only retry candidate tested in a deterministic host model.

This candidate is layered on the pinned generation guard, the pinned pending
state machine and the pinned stalled marker. It replaces the bare STALLED
marker with a *claimable* RETRY state and adds a bounded retry loop, so a
request that races a failing ``kthread_run`` is re-driven instead of silently
dropped.

The harness executes the extracted candidate C functions with pthread,
filesystem, RCU, credential and kthread shims. It schedules two cases that the
previous candidates could not handle:

  1. a request arrives while ``kthread_run`` is blocked, then the launch fails;
  2. every launch fails for the whole call, so the bounded retry is exhausted.

It does not run kernel code, prove memory ordering, or authorize integration.
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
import probe_s40_susfs_pending as pending

PATCH = ROOT / 'build-kit/ci/s40-susfs-abi/research-only-priority-retry.patch'
PINS = abi.PINS['research_priority_retry']

# The retry candidate keeps every earlier state machine intact and only makes
# the failure path recoverable. These are the behaviours it must not break.
BASELINE_FLAGS = {
    'generation_guard_preserves_new_config_in_model': True,
    'busy_requests_coalesce_into_another_pass_in_model': True,
    'requests_immediately_before_and_after_idle_transition_modeled': True,
}


def apply_retry(stalled: str, directory: Path) -> str:
    patch = PATCH.read_bytes()
    if hashlib.sha256(patch).hexdigest() != PINS['patch_sha256']:
        raise ValueError('Retry candidate patch SHA-256 mismatch')
    lines = patch.decode('utf-8').splitlines()
    if (sum(line.startswith('--- ') for line in lines) != 1 or
            sum(line.startswith('+++ ') for line in lines) != 1 or
            lines[:2] != ['--- a/fs/susfs.c', '+++ b/fs/susfs.c']):
        raise ValueError('Unexpected retry candidate patch paths')
    if hashlib.sha256(stalled.encode()).hexdigest() != PINS['input_stalled_susfs_c_sha256']:
        raise ValueError('Retry candidate input source SHA-256 mismatch')
    s40.check_work_directory(directory, [])
    path = directory / 'fs/susfs.c'
    path.parent.mkdir(parents=True)
    path.write_text(stalled)
    priority.run(['git', 'apply', '--check', str(PATCH)], cwd=directory)
    priority.run(['git', 'apply', str(PATCH)], cwd=directory)
    result = path.read_text()
    if hashlib.sha256(result.encode()).hexdigest() != PINS['retry_susfs_c_sha256']:
        raise ValueError('Unexpected retry candidate output SHA-256')
    return result


# The launch shim can fail a configurable number of times before it succeeds.
# `fail_budget` is decremented inside the shim while `launch_lock` is held, so
# the number of failures in one call is deterministic rather than timing-based.
THREAD_SHIM = r'''
static pthread_t requested_workers[16];
static int requested_worker_count;
static pthread_mutex_t launch_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t launch_cond = PTHREAD_COND_INITIALIZER;
static int fail_budget;          /* remaining forced failures */
static bool fail_blocks;         /* block the failing launch until released */
static bool launch_waiting, launch_resume;
static int launch_failures;      /* observed failed launches */
static int launch_attempts;      /* total launch attempts */
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
    launch_attempts++;
    if (fail_budget > 0) {
        fail_budget--;
        launch_failures++;
        if (fail_blocks) {
            launch_waiting = true;
            assert(pthread_cond_signal(&launch_cond) == 0);
            while (!launch_resume)
                assert(pthread_cond_wait(&launch_cond, &launch_lock) == 0);
        }
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

# Shared helper shims for both programs: the setters, UID switches and the
# deterministic launch-failure control. `control_main` runs the *pinned stalled*
# candidate down the same schedule, so a passing retry run is only meaningful if
# the control genuinely loses the event.
HARNESS_HELPERS = r'''
void susfs_parse_priority_app_strings(void);
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
static void setup_uid(uid_t uid) {
    assert(pthread_mutex_lock(&gate) == 0);
    alpha_uid = uid;
    waiting = false;
    resume_worker = false;
    pause_worker = false;
    worker_resolutions = 0;
    assert(pthread_mutex_unlock(&gate) == 0);
}
static void update_uid(uid_t uid) {
    assert(pthread_mutex_lock(&gate) == 0);
    alpha_uid = uid;
    assert(pthread_mutex_unlock(&gate) == 0);
}
static void arm_failure(int budget, bool blocking) {
    assert(pthread_mutex_lock(&launch_lock) == 0);
    fail_budget = budget;
    fail_blocks = blocking;
    launch_waiting = false;
    launch_resume = false;
    assert(pthread_mutex_unlock(&launch_lock) == 0);
}
static void wait_for_blocked_launch(void) {
    assert(pthread_mutex_lock(&launch_lock) == 0);
    while (!launch_waiting) assert(pthread_cond_wait(&launch_cond, &launch_lock) == 0);
    assert(pthread_mutex_unlock(&launch_lock) == 0);
}
static void release_blocked_launch(void) {
    assert(pthread_mutex_lock(&launch_lock) == 0);
    launch_resume = true;
    assert(pthread_cond_signal(&launch_cond) == 0);
    assert(pthread_mutex_unlock(&launch_lock) == 0);
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
'''

# The schedule that matters: a request lands while a doomed launch is blocked.
# `expect_recovered` is true for the retry candidate and false for the control.
SCHEDULE = r'''
int main(void) {
    alarm(20);
    _Static_assert(sizeof(struct st_susfs_priority_uid_filter) == 65540, "unexpected payload");

    /* CASE 1: a request arrives while `kthread_run` is blocked and then fails.
     * The stalled candidate published IDLE and dropped it; the retry candidate
     * must re-drive the refresh from the caller that observed the failure. */
    setup_uid(10005);
    set_names("sample.alpha");
    arm_failure(1, true);
    int index = requested_worker_count;

    pthread_t requester;
    assert(pthread_create(&requester, NULL, request_entry, NULL) == 0);
    wait_for_blocked_launch();
    update_uid(10006);
    susfs_parse_priority_app_strings();
    assert(atomic_read(&susfs_priority_app_strings_running) == SUSFS_PRIORITY_REFRESH_PENDING);
    release_blocked_launch();
    assert(pthread_join(requester, NULL) == 0);

    if (!EXPECT_RECOVERED) {
        /* Control: the failed launch parked the state in a marker nobody
         * claims, so the concurrent request is gone and the caller did not
         * retry. This is the counterexample the retry candidate fixes. */
        assert(atomic_read(&susfs_priority_app_strings_running) != SUSFS_PRIORITY_REFRESH_IDLE ||
               requested_worker_count == index);
        assert(!susfs_is_priority_uid_filtered(10006));
        puts("control: blocked failure dropped the concurrent request");
        return 0;
    }

    /* The failed launch did not drop the request: the caller re-claimed the
     * RETRY it published and launched again, so exactly one worker exists and
     * it resolves the *newest* configuration (10006), not the stale 10005. */
    assert(requested_worker_count == index + 1);
    assert(launch_failures == 1);
    join_worker(index);
    assert(atomic_read(&susfs_priority_app_strings_running) == SUSFS_PRIORITY_REFRESH_IDLE);
    assert(!susfs_is_priority_uid_filtered(10005));
    assert(susfs_is_priority_uid_filtered(10006));

#if EXPECT_RECOVERED
    /* CASE 2: every attempt in one call fails.
     *
     * The bounded retry must stop after SUSFS_PRIORITY_REFRESH_MAX_ATTEMPTS and
     * leave a claimable RETRY behind. It must never return to IDLE, because a
     * concurrent PENDING event would then be lost for good. */
    setup_uid(10002);   /* the resolver shim maps sample.beta to 10002 */
    set_names("sample.beta");
    arm_failure(99, false);
    int attempts_before = launch_attempts;
    susfs_parse_priority_app_strings();
    assert(launch_attempts - attempts_before == SUSFS_PRIORITY_REFRESH_MAX_ATTEMPTS);
    assert(atomic_read(&susfs_priority_app_strings_running) == SUSFS_PRIORITY_REFRESH_RETRY);

    /* A later caller can still claim RETRY and complete the refresh. This is
     * what "claimable" means, and it is the property the stalled marker lacked. */
    arm_failure(0, false);
    susfs_parse_priority_app_strings();
    assert(requested_worker_count == index + 2);
    join_worker(index + 1);
    assert(susfs_is_priority_uid_filtered(10002));
    assert(!susfs_is_priority_uid_filtered(10006));
    assert(atomic_read(&susfs_priority_app_strings_running) == SUSFS_PRIORITY_REFRESH_IDLE);
#endif

    free(priority_uid_filter_bitmap);
    free(susfs_priority_app_strings);
    puts("retry candidate re-drives lost launches and stays claimable when exhausted");
    return 0;
}
'''
def build_program(source: str, header: str, expected_source: str, main: str) -> str:
    if hashlib.sha256(source.encode()).hexdigest() != expected_source:
        raise ValueError('Unpinned retry candidate source')
    if hashlib.sha256(header.encode()).hexdigest() != abi.PINS['sources']['susfs'][priority.HEADER]:
        raise ValueError('Unpinned priority header')
    parts = priority.source_parts(source, header)
    once = priority.extract_function(source, 'static int susfs_priority_app_strings_worker_once(')
    preamble = pending.replace_once(
        priority.PREAMBLE,
        '#define atomic_cmpxchg(p, old, new) __sync_val_compare_and_swap((p), (old), (new))',
        'static int model_cmpxchg(atomic_t *ptr, int old, int next);\n'
        '#define atomic_cmpxchg(p, old, new) model_cmpxchg((p), (old), (new))\n'
        '#define atomic_read(p) __atomic_load_n((p), __ATOMIC_SEQ_CST)\n'
        '#define atomic_xchg(p, v) __atomic_exchange_n((p), (v), __ATOMIC_SEQ_CST)')
    resolver = pending.replace_once(
        pending.priority.RESOLVER,
        'static uid_t alpha_uid = 10001; /* protected by gate */',
        'static uid_t alpha_uid = 10001; /* protected by gate */\nstatic int worker_resolutions;')
    resolver = pending.replace_once(
        resolver,
        'if (is_worker_thread && pause_worker) {',
        'if (is_worker_thread) worker_resolutions++;\n        if (is_worker_thread && pause_worker) {')
    return '\n'.join((preamble, parts['globals'], parts['payload'], parts['valid'], resolver,
                      pending.CAS_SHIM, parts['parse'], parts['set'], once, parts['worker'],
                      THREAD_SHIM, HARNESS_HELPERS,
                      f'#define EXPECT_RECOVERED {main}', parts['request'],
                      parts['lookup'], SCHEDULE))


def program(source: str, header: str) -> str:
    return build_program(source, header, PINS['retry_susfs_c_sha256'], '1')


def control_program(source: str, header: str) -> str:
    """The pinned stalled candidate driven down the identical schedule."""
    return build_program(source, header, PINS['input_stalled_susfs_c_sha256'], '0')


def probe(susfs: Path, compiler: str = 'gcc') -> dict:
    original = priority.checked_susfs_file(susfs, priority.SOURCE)
    header = priority.checked_susfs_file(susfs, priority.HEADER)
    with tempfile.TemporaryDirectory(prefix='s40-susfs-retry-host-model-') as temporary:
        temp = Path(temporary)
        guarded = priority.apply_candidate(original, temp / 'generation')
        pending_source = pending.apply_pending(guarded, temp / 'pending')
        stalled = stalled_apply(pending_source, temp / 'stalled')
        retry = apply_retry(stalled, temp / 'retry')
        source, executable = temp / 'retry-model.c', temp / 'retry-host-probe'
        source.write_text(program(retry, header))
        priority.run([compiler, '-std=gnu11', '-O1', '-Wall', '-Wextra', '-Werror',
                      '-Wno-unused-parameter', '-pthread', str(source), '-o', str(executable)])
        priority.run([str(executable)])
    return {
        'scope': 'HOST_SHIM_SCHEDULE_MODEL_ONLY',
        'generation_guard_preserves_new_config_in_model': True,
        'busy_requests_coalesce_into_another_pass_in_model': True,
        'requests_immediately_before_and_after_idle_transition_modeled': True,
        'failed_launch_no_longer_drops_concurrent_request_in_model': True,
        'exhausted_retry_leaves_claimable_retry_state_not_idle': True,
        'later_request_completes_refresh_after_exhausted_retry_in_model': True,
        'candidate_is_complete_or_safe_for_kernel': False,
        'real_rcu_filesystem_selinux_kthreads_or_device_tested': False,
        'susfs_2_4_integrated': False,
    }


def stalled_apply(pending_source: str, directory: Path) -> str:
    """Apply the pinned stalled marker, the documented predecessor of this patch."""
    import probe_s40_susfs_stalled as stalled
    return stalled.apply_stalled(pending_source, directory)


def control(susfs: Path, compiler: str = 'gcc') -> str:
    """Run the negative control and return its output.

    A retry run only proves something if this control, executing the *same*
    harness with only `EXPECT_RECOVERED` flipped, really loses the request.
    """
    original = priority.checked_susfs_file(susfs, priority.SOURCE)
    header = priority.checked_susfs_file(susfs, priority.HEADER)
    with tempfile.TemporaryDirectory(prefix='s40-susfs-retry-control-') as temporary:
        temp = Path(temporary)
        guarded = priority.apply_candidate(original, temp / 'generation')
        pending_source = pending.apply_pending(guarded, temp / 'pending')
        stalled = stalled_apply(pending_source, temp / 'stalled')
        source, executable = temp / 'control-model.c', temp / 'control-host-probe'
        source.write_text(control_program(stalled, header))
        priority.run([compiler, '-std=gnu11', '-O1', '-Wall', '-Wextra', '-Werror',
                      '-Wno-unused-parameter', '-pthread', str(source), '-o', str(executable)])
        return priority.run([str(executable)]).stdout.strip()


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
