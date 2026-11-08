"""3.2-r1 guard and real-source host fixtures; not a device boot test."""
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
spec = importlib.util.spec_from_file_location('synthetica32_r1_test', ROOT/'build-kit/scripts/build_synthetica32_r1.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
FIXTURE = ROOT/'tests/fixtures/synthetica32-r1/vmscan.c'
MGLRU = ROOT/'build-kit/ci/synthetica2-experimental/patches/0001-mglru-4.14.patch'
CONFIG31 = Path(os.environ['S31_EXACT_CONFIG']) if os.environ.get('S31_EXACT_CONFIG') else None
SYMVERS31 = Path(os.environ['S31_EXACT_SYMVERS']) if os.environ.get('S31_EXACT_SYMVERS') else None
TESTED20 = Path(os.environ['S3RC_TESTED_CONFIG']) if os.environ.get('S3RC_TESTED_CONFIG') else None


def fixture_tree(path: Path, safety_patch=True) -> str:
    (path/'mm').mkdir()
    shutil.copyfile(FIXTURE, path/'mm/vmscan.c')
    if build.v3.digest(path/'mm/vmscan.c') != 'febf74dd61f37d772835bf22a8ae64fbc4475f6bc1ba354d6db8fd0f563cba10':
        raise ValueError('fixture source tampered')
    subprocess.run(['git', 'apply', '--include=mm/vmscan.c', str(MGLRU)], cwd=path, check=True)
    build.verify_vmscan(path, patched=False)
    if safety_patch:
        subprocess.run(['git', 'apply', '--check', str(build.PATCH)], cwd=path, check=True)
        subprocess.run(['git', 'apply', str(build.PATCH)], cwd=path, check=True)
        build.verify_vmscan(path, patched=True)
    return (path/'mm/vmscan.c').read_text()


def extract(source: str, signature: str) -> str:
    start = source.index(signature)
    open_brace = source.index('{', start)
    depth = 0
    for index in range(open_brace, len(source)):
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
            if depth == 0:
                return source[start:index+1]
    raise ValueError('unbalanced fixture function')


def run_c(path: Path, name: str, source: str) -> None:
    c, binary = path/(name+'.c'), path/name
    c.write_text(source)
    subprocess.run(['gcc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                    str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=10)


class RecipeTests(unittest.TestCase):
    def test_release_and_feature_guards_follow_31_not_previous_downgrade(self):
        self.assertEqual(build.RELEASE, '4.14.357-openela-synthetica-3.2-r1')
        self.assertEqual(build.base.EXPECTED_RELEASE, build.RELEASE)
        self.assertEqual(build.base.rc.EXPECTED_RELEASE, build.RELEASE)
        self.assertEqual(build.base.rc.s2x.EXPECTED_RELEASE, build.RELEASE)
        self.assertEqual(build.base.rc.EXPECTED_LOCALVERSION, build.LOCALVERSION)
        build.check_inputs()
        self.assertEqual(build.PATCH.read_text().count('diff --git '), 1)
        self.assertIn('diff --git a/mm/vmscan.c b/mm/vmscan.c', build.PATCH.read_text())
        with mock.patch.object(build, 'PATCH_SHA256', '0'*64), self.assertRaisesRegex(ValueError, 'patch digest'):
            build.check_inputs()

    def test_isolated_kit_keeps_inherited_root_and_feature_guards(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)/'kit'
            build.prepare(ROOT/'build-kit', dest, ROOT/'artifacts/generated.config.txt')
            script = (dest/'ci/rollercoaster/build-rollercoaster.sh').read_text()
            driver = (dest/'scripts/build_chronicle_base.py').read_text()
            self.assertIn('S2X_HELPER', script)
            self.assertIn('check-config', script)
            self.assertIn('prepare-tree', driver)
            self.assertIn('3.2-r1 compiled', driver)
            self.assertFalse((dest/'ci/rollercoaster/patches/port-allow-foreign-vermagic.patch').exists())
            subprocess.run(['bash', '-n', str(dest/'ci/rollercoaster/build-rollercoaster.sh')], check=True)

    @unittest.skipUnless(CONFIG31 is not None and TESTED20 is not None, 'exact pinned configs not provided')
    def test_complete_31_config_and_security_are_preserved(self):
        original = CONFIG31.read_text()
        generated = original.replace('CONFIG_LOCALVERSION="-synthetica-3.1"',
                                     'CONFIG_LOCALVERSION="-synthetica-3.2-r1"')
        self.assertNotEqual(original, generated)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'config'
            path.write_text(generated)
            report = build.check_config(ROOT/'artifacts/generated.config.txt', path, TESTED20, CONFIG31, 'on')
            self.assertEqual(report['changes_from_exact_3_1'],
                             {'LOCALVERSION': {'3.1': build.BASE31_LOCALVERSION, '3.2-r1': build.LOCALVERSION}})
            for key in ('LRU_GEN_ENABLED', 'UCLAMP_TASK', 'KSU', 'SECCOMP_FILTER', 'MODULE_SIG_FORCE', 'DM_VERITY'):
                altered = generated.replace(f'CONFIG_{key}=y', f'# CONFIG_{key} is not set')
                self.assertNotEqual(altered, generated)
                with self.subTest(key=key), self.assertRaises(ValueError):
                    build.compare_31_config(CONFIG31, altered)
            with self.assertRaises(ValueError):
                build.compare_31_config(CONFIG31, generated + '\nCONFIG_MODULE_FORCE_LOAD=y\n')
            path.write_text(original+'\n')
            with self.assertRaisesRegex(ValueError, 'match the pin'):
                build.compare_31_config(path, generated)

    @unittest.skipUnless(SYMVERS31 is not None, 'exact 3.1 Module.symvers not provided')
    def test_all_exports_compared_not_only_module_layout(self):
        info = build.compare_31_exports(SYMVERS31, SYMVERS31)
        self.assertEqual(info['exported_records_compared'], 12236)
        self.assertEqual(info['builtin_records_compared'], 12227)
        self.assertEqual(info['module_layout_crc'], '0xed5659d1')
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'Module.symvers'
            lines = SYMVERS31.read_text().splitlines()
            crc, name, owner, kind = lines[0].split()
            self.assertNotEqual(name, 'module_layout')
            lines[0] = f'0xffffffff\t{name}\t{owner}\t{kind}'
            path.write_text('\n'.join(lines)+'\n')
            with self.assertRaisesRegex(ValueError, 'export ABI differs'):
                build.compare_31_exports(SYMVERS31, path)
            link = Path(d)/'ref'
            link.symlink_to(SYMVERS31)
            with self.assertRaisesRegex(ValueError, 'pinned'):
                build.compare_31_exports(link, path)


class MglruSafetyTests(unittest.TestCase):
    def test_exact_source_pins_and_only_reviewed_hunks(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            source = fixture_tree(path)
            self.assertIn('spread < 0 || spread >= MAX_NR_GENS', source)
            self.assertIn('kvfree(pgdat->mm_walk_args);\n\tpgdat->mm_walk_args = NULL;', source)
            self.assertIn('''if (IS_ERR(pgdat->kswapd)) {
\t\t/* The worker did not start; release its MGLRU walk buffer. */
\t\tlru_gen_stop_kswapd(nid);''', source)
            (path/'mm/vmscan.c').write_text(source+'\n')
            with self.assertRaisesRegex(ValueError, 'source'):
                build.verify_vmscan(path, patched=True)

    def test_real_store_function_rejects_negative_and_keeps_valid_values(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            actual = fixture_tree(root)
            function = extract(actual, 'static ssize_t store_lru_gen_spread(')
            stubs = r'''
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <sys/types.h>
struct kobject { int unused; };
struct kobj_attribute { int unused; };
static int lru_gen_spread = 3;
#define MAX_NR_GENS 7
#define WRITE_ONCE(x, v) ((x) = (v))
static int kstrtoint(const char *s, unsigned int base, int *out) {
    char *end; long n; errno = 0; n = strtol(s, &end, (int)base);
    if (errno || end == s || (*end && *end != '\n') || n < INT_MIN || n > INT_MAX) return -1;
    *out = (int)n; return 0;
}
'''
            main = r'''
int main(void) {
    assert(store_lru_gen_spread(0, 0, "0", 1) == 1 && lru_gen_spread == 0);
    assert(store_lru_gen_spread(0, 0, "6", 1) == 1 && lru_gen_spread == 6);
    const char *bad[] = {"-1", "-2147483648", "7", "2147483647", "nope", "999999999999999"};
    for (unsigned i = 0; i < sizeof(bad)/sizeof(bad[0]); i++) {
        assert(store_lru_gen_spread(0, 0, bad[i], 1) == -EINVAL);
        assert(lru_gen_spread == 6);
    }
    return 0;
}
'''
            run_c(root, 'spread_test', stubs+function+main)

    def test_kswapd_failure_frees_buffer_and_success_keeps_mglru(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            actual = fixture_tree(root)
            functions = '\n'.join(extract(actual, sig) for sig in (
                'static void lru_gen_start_kswapd(', 'static void lru_gen_stop_kswapd(',
                'int kswapd_run(', 'void kswapd_stop('))
            stubs = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
struct task_struct { int value; };
struct pglist_data { struct task_struct *kswapd; void *mm_walk_args; };
typedef struct pglist_data pg_data_t;
static struct pglist_data node;
static struct task_struct task;
static int allocations, releases, stops, fail_thread, fail_allocation, warnings;
static int system_state = 1;
#define SYSTEM_RUNNING 1
#define GFP_KERNEL 0
#define NODE_DATA(nid) (&node)
#define WARN_ON_ONCE(x) do { if (x) warnings++; } while (0)
#define BUG_ON(x) assert(!(x))
#define pr_err(...) ((void)0)
#define IS_ERR(p) ((intptr_t)(p) < 0)
#define PTR_ERR(p) ((int)(intptr_t)(p))
static int size_of_mm_walk_args(void) { return 64; }
static void *kvzalloc_node(int n, int flags, int nid) {
    if (fail_allocation) return NULL;
    void *p = calloc(1, (size_t)n); if (p) allocations++; return p;
}
static void kvfree(void *p) { if (p) { releases++; free(p); } }
static struct task_struct *mock_kthread_run(void) { return fail_thread ? (struct task_struct *)(intptr_t)-ENOMEM : &task; }
#define kthread_run(...) mock_kthread_run()
static void kthread_stop(struct task_struct *p) { assert(p == &task); stops++; }
'''
            main = r'''
int main(void) {
    fail_thread = 1;
    assert(kswapd_run(0) == -ENOMEM);
    assert(node.kswapd == NULL && node.mm_walk_args == NULL && allocations == 1 && releases == 1);
    assert(kswapd_run(0) == -ENOMEM);
    assert(node.kswapd == NULL && node.mm_walk_args == NULL && allocations == 2 && releases == 2);
    fail_thread = 0;
    assert(kswapd_run(0) == 0 && node.kswapd == &task && node.mm_walk_args != NULL);
    assert(kswapd_run(0) == 0 && allocations == 3);
    kswapd_stop(0);
    assert(node.kswapd == NULL && node.mm_walk_args == NULL && releases == 3 && stops == 1);
    fail_allocation = 1;
    assert(kswapd_run(0) == 0 && node.kswapd == &task && node.mm_walk_args == NULL && warnings == 1);
    kswapd_stop(0);
    assert(node.kswapd == NULL && node.mm_walk_args == NULL && releases == 3 && stops == 2);
    return 0;
}
'''
            run_c(root, 'kswapd_test', stubs+functions+main)


if __name__ == '__main__':
    unittest.main()
