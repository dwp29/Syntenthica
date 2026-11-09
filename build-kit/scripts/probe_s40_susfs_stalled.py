#!/usr/bin/env python3
"""Explore an incomplete failed-launch marker in a scratch-only host model.

The candidate records a failed launch in a stalled state instead of resetting
it to idle. A later request can retry, but no automatic retry or external error
reporting exists. It is NOT a kernel-ready solution, an integration, or a
proof of Linux memory ordering, credential safety, RCU or device behavior.
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
import build_synthetica40 as s40
import probe_s40_susfs_priority as priority
import probe_s40_susfs_pending as pending

PATCH = ROOT / 'build-kit/ci/s40-susfs-abi/research-only-priority-stalled.patch'
PINS = abi.PINS['research_priority_stalled']


def apply_stalled(source: str, directory: Path) -> str:
    patch = PATCH.read_bytes()
    if hashlib.sha256(patch).hexdigest() != PINS['patch_sha256']:
        raise ValueError('Stalled candidate patch SHA-256 mismatch')
    lines = patch.decode('utf-8').splitlines()
    if (sum(line.startswith('--- ') for line in lines) != 1 or
            sum(line.startswith('+++ ') for line in lines) != 1 or
            lines[:2] != ['--- a/fs/susfs.c', '+++ b/fs/susfs.c']):
        raise ValueError('Unexpected stalled candidate patch paths')
    if hashlib.sha256(source.encode()).hexdigest() != PINS['input_pending_susfs_c_sha256']:
        raise ValueError('Stalled candidate input source SHA-256 mismatch')
    s40.check_work_directory(directory, [])
    path = directory / 'fs/susfs.c'
    path.parent.mkdir(parents=True)
    path.write_text(source)
    priority.run(['git', 'apply', '--check', str(PATCH)], cwd=directory)
    priority.run(['git', 'apply', str(PATCH)], cwd=directory)
    result = path.read_text()
    if hashlib.sha256(result.encode()).hexdigest() != PINS['stalled_susfs_c_sha256']:
        raise ValueError('Unexpected stalled candidate output SHA-256')
    return result


def stalled_main() -> str:
    # Preserve the four original schedules; modify only the failed-launch
    # expectations and add a repeated failure. An unretried stalled state is a
    # documented liveness failure, NOT successful delivery of the request.
    main = pending.replace_once(pending.MAIN,
        '    /* Known hole: a request arrives while kthread creation is blocked, then\n'
        '     * creation fails. The pending request is lost when the state is reset. */',
        '    /* A request arrives during a failed launch; failure stays marked. */')
    old = '''    assert(requested_worker_count == index);
    assert(atomic_read(&susfs_priority_app_strings_running) == SUSFS_PRIORITY_REFRESH_IDLE);
    assert(susfs_is_priority_uid_filtered(10005));
    assert(!susfs_is_priority_uid_filtered(10006));
    /* A later independent request can recover; it is not guaranteed. */
    susfs_parse_priority_app_strings();
    join_worker(index);
    assert(!susfs_is_priority_uid_filtered(10005));
    assert(susfs_is_priority_uid_filtered(10006));
'''
    new = '''    assert(requested_worker_count == index);
    assert(atomic_read(&susfs_priority_app_strings_running) == SUSFS_PRIORITY_REFRESH_STALLED);
    assert(susfs_is_priority_uid_filtered(10005));
    assert(!susfs_is_priority_uid_filtered(10006)); /* stale until a retry */
    /* There is no scheduled retry. A second failed explicit request still
     * leaves the state stalled, with no worker and no new bitmap. */
    assert(pthread_mutex_lock(&launch_lock) == 0);
    force_launch_failure = true;
    block_failed_launch = false;
    assert(pthread_mutex_unlock(&launch_lock) == 0);
    susfs_parse_priority_app_strings();
    assert(requested_worker_count == index);
    assert(atomic_read(&susfs_priority_app_strings_running) == SUSFS_PRIORITY_REFRESH_STALLED);
    assert(!susfs_is_priority_uid_filtered(10006));
    /* A later request can retry successfully; it is not guaranteed to occur. */
    susfs_parse_priority_app_strings();
    join_worker(index);
    assert(atomic_read(&susfs_priority_app_strings_running) == SUSFS_PRIORITY_REFRESH_IDLE);
    assert(!susfs_is_priority_uid_filtered(10005));
    assert(susfs_is_priority_uid_filtered(10006));
'''
    main = pending.replace_once(main, old, new)
    # Inject resolver failures into the actual extracted parser/worker/setter.
    # The fake resolver is not a real filesystem or errno-behavior test.
    main = pending.replace_once(main, '    free(priority_uid_filter_bitmap);', r'''
    const int errors[] = { -ENOENT, -EIO, -EACCES, -ENOMEM };
    for (size_t i = 0; i < sizeof(errors) / sizeof(errors[0]); ++i) {
        assert(susfs_is_priority_uid_filtered(10006));
        injected_resolver_error = errors[i];
        index = requested_worker_count;
        susfs_parse_priority_app_strings();
        join_worker(index);
        assert(atomic_read(&susfs_priority_app_strings_running) == SUSFS_PRIORITY_REFRESH_IDLE);
        assert(!susfs_is_priority_uid_filtered(10006)); /* skipped, bitmap published */
        injected_resolver_error = 0;
        index = requested_worker_count;
        susfs_parse_priority_app_strings();
        join_worker(index);
        assert(susfs_is_priority_uid_filtered(10006));
    }
    /* Setter's skip_failed path can also report success with an empty bitmap. */
    injected_resolver_error = -EIO;
    set_names("sample.alpha"); /* helper asserts info->err == 0 */
    assert(!susfs_is_priority_uid_filtered(10006));
    injected_resolver_error = 0;
    set_names("sample.alpha");
    assert(susfs_is_priority_uid_filtered(10006));

    free(priority_uid_filter_bitmap);''')
    return pending.replace_once(main,
        '    puts("modeled busy and exit schedules improve; failed launch still drops an event");',
        '    puts("failed launch remains stalled, without automatic recovery; later request can retry");')


def probe(susfs: Path, compiler: str = 'gcc') -> dict:
    original = priority.checked_susfs_file(susfs, priority.SOURCE)
    header = priority.checked_susfs_file(susfs, priority.HEADER)
    with tempfile.TemporaryDirectory(prefix='s40-susfs-stalled-host-model-') as temporary:
        temp = Path(temporary)
        guarded = priority.apply_candidate(original, temp / 'generation')
        candidate = pending.apply_pending(guarded, temp / 'pending')
        stalled = apply_stalled(candidate, temp / 'stalled')
        source, executable = temp / 'stalled-model.c', temp / 'stalled-host-probe'
        program = pending.build_program(stalled, header, PINS['stalled_susfs_c_sha256'], stalled_main())
        program = pending.replace_once(program,
            'static int susfs_resolve_priority_app_uid(const char *name, uid_t *uid) {',
            'static int injected_resolver_error;\n'
            'static int susfs_resolve_priority_app_uid(const char *name, uid_t *uid) {\n'
            '    if (injected_resolver_error) return injected_resolver_error;')
        source.write_text(program)
        priority.run([compiler, '-std=gnu11', '-O1', '-Wall', '-Wextra', '-Werror',
                      '-Wno-unused-parameter', '-pthread', str(source), '-o', str(executable)])
        priority.run([str(executable)])
    return {
        'scope': 'HOST_SHIM_SCHEDULE_MODEL_ONLY',
        'busy_requests_and_idle_boundary_schedules_modeled': True,
        'failed_launch_concurrent_request_leaves_internal_stalled_marker': True,
        'repeated_explicit_launch_failure_remains_stalled': True,
        'later_explicit_request_can_recover_in_model': True,
        'worker_skip_failed_can_publish_empty_bitmap_for_injected_errors': True,
        'setter_skip_failed_can_report_success_for_injected_io_error': True,
        'automatic_retry_or_external_failure_reporting_implemented': False,
        'stalled_state_alone_guarantees_eventual_refresh': False,
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
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
