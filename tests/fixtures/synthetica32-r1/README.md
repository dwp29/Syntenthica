# MGLRU source fixture

`vmscan.c` is the unmodified GPL-2.0 source from
`Saamitk/kernel_xiaomi_sm6250-switchoff@c1e6f795b557b7bf92220c91f05a42b456de7a74`,
SHA-256 `febf74dd61f37d772835bf22a8ae64fbc4475f6bc1ba354d6db8fd0f563cba10`.
Tests apply the pinned 3.1 MGLRU patch and then the 3.2-r1 safety patch only to a
new temporary copy. Host harnesses exercise extracted functions, not a phone.
