# Legacy kernel source fixtures

`fs/exec.c` and `KernelSU-Next/kernel/supercall/supercall.c` are exact source
files from
[Saamitk/kernel_xiaomi_sm6250-switchoff at c1e6f795b557b7bf92220c91f05a42b456de7a74](https://github.com/Saamitk/kernel_xiaomi_sm6250-switchoff/tree/c1e6f795b557b7bf92220c91f05a42b456de7a74).
They are used only to apply and test the guarded post-exec patch. The kernel is
GPL-2.0; its source notices remain intact. The build script pins the original
and fully patched SHA-256 values. Host stubs do not constitute a device test.
