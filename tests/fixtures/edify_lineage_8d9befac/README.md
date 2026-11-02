# Host-only reference edify test fixture

The files under `edify/` and `otautil/` are unmodified copies from
[LineageOS/android_bootable_recovery](https://github.com/LineageOS/android_bootable_recovery/tree/8d9befac75660d6c62817dc16389c876f73e8f48)
at commit `8d9befac75660d6c62817dc16389c876f73e8f48`. Their individual source
headers carry the Apache-2.0 license notice. They are a **reference**, not a
claim that the distributed Android updater or the user's installed recovery
was built from this commit.

| File | SHA-256 |
| --- | --- |
| `edify/expr.cpp` | `f9315b5cc06adf73ba96f789de8e49bb2792068ba2f6e67aa49d157a6d6efe4f` |
| `edify/include/edify/expr.h` | `a33e888c144009172d35a111d8db98d12a53c2072767f0edcbd925bfb121bc76` |
| `edify/include/edify/updater_interface.h` | `6522665c1c28fc14c8a81b8604397a458c67d104f9af1187c410bd763a7022c7` |
| `edify/lexer.ll` | `04eea10827be985b8468c88096a97a2075a8639ec86b633a8a25d242003fd729` |
| `edify/parser.yy` | `fa6a89c55d81b1d50a5954f42add76f9d8ce5317027ffa45ea9df50b6d237aa3` |
| `edify/yydefs.h` | `6a44cf51acf703c9e290f9afcdaaca68b132ef2e7d57163abd91775a430906ac` |
| `otautil/include/otautil/error_code.h` | `b96506641cc57ea2b4dfa19bd2b1ca3b07a09e8f208a35a315b3fe991c68d75c` |

`host_harness.cpp` replaces every installer-specific operation with a mock:
the fake extractor records names in memory and never opens any block device or
file. Host shims deliberately abort if an unused Android base helper is
unexpectedly executed. These checks simulate edify return values; they do not
run the updater binary, perform a real partition write, test recovery/ZIP
acceptance, establish actual device behavior, or prove the ROM boots.

Bison 3.8.2 and Flex 2.6.4 can be installed from the hash-pinned PyPI wheels in
`requirements.txt`; an `m4` binary and C++17 compiler are also needed. The test
runs against a small synthetic installer by default. Setting
`SYNTHETICA_REFERENCE_ZIP` additionally tests the exact original installer
script read from the first candidate and its guarded transformation; the ROM
script itself is not copied into this repository. Set
`SYNTHETICA_REQUIRE_EDIFY=1` to fail rather than skip when the toolchain is
missing.
