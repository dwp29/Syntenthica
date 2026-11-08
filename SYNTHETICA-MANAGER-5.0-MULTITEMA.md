# Synthetica Manager 5.0 — multi-theme release

One Manager APK offers Pixel Signal, Cyberpunk (inspired by the earlier Cyberbrutal design), iOS-inspired Glass and Neon. The selector is in **Settings → Customization → Design theme**; changes take effect immediately and survive a process restart. The existing accent, follow-system/light/dark/AMOLED, glow and motion controls remain. Existing 4.0 installations default to Pixel until a different design is selected. Design selection changes presentation only.

## Deliverables

- Private Drive folder: [Synthetica-Arsip-dan-Manager-5.0](https://drive.google.com/drive/folders/1NX6JLc8k4R9fYr80DtqV3sheb0FgCQjq).
- [Signed Manager 5.0 APK](https://drive.google.com/file/d/1chTB1qpJ2jzw_QJfSOGfgO02bII-rFbF/view?usp=drivesdk), 8,695,088 bytes; SHA-256 `72322e05616313ec4b3c81ec045575c45edc2b7067833a325cb02ddc740401b6`.
- [APK checksum](https://drive.google.com/file/d/1Xabw8dtSMbUFQ4bhVcpfxSL1mrQYUmOZ/view?usp=drivesdk) and [Indonesian guide](https://drive.google.com/file/d/1D_6OKVXdg6N7UUdu6j_IhcBgpBp6WAF9/view?usp=drivesdk).
- The folder also has organized copies of earlier Manager versions, the existing 3.1 **TEST** kernel, diagnostic tools and their guides/checksums, and emulator-preview screenshots. Links point to the remaining old archives; the originals were not moved or deleted. The new folder does not contain a private signing key.
- Permissions of the new folder, its three subfolders, the main APK and representative archive copies were checked: owner only at verification time.

## Identity and scope

- Package `net.ember.labs`; version `5.0.0`, code `60000`; min SDK 26; ARM64 native payload; KernelSU UAPI 4.
- Original Manager certificate SHA-256 `fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140`. The user separately authorized one-time local use of the original key. It was not committed or sent to CI, and the temporary key and downloaded backup part were removed after signing.
- Source preparation layers `build-kit/scripts/build_manager_50_multitheme.py` on the 4.0 pipeline and pinned upstream `KernelSU-Next/KernelSU-Next@ea51427ff700f73909e7e8c8717cc3241322ee1e`. The 5.0 overlay is in `build-kit/ci/ksun-multitheme50/`. It reuses 4.0 Manager authorization, `libksud.so`, profiles, optional app lock, Device Check, ZIP preflight, module/WebUI, read-only diagnostics and explicit, confirmed Control/Boost actions. Theme changes do not grant root or execute tuning.
- The style selector persists its own ID in the existing settings store, retaining the earlier theme-mode, accent and motion keys. Unknown IDs safely fall back to Pixel. The iOS-style glass is an approximation using lightweight static gradients, not Apple's implementation or a live backdrop blur. The single shared decorative animation stops when the app is paused or system/app motion is disabled; it is omitted entirely for the static glass background.

## Evidence

- [Manager/preview build 42450727175](https://github.com/dwp29/Syntenthica/actions/runs/42450727175), application-source commit `8a9b64aec2b2ee753730445ee8c331465aafe5fc`: compiled the unsigned Manager and a separate non-root preview; preview Kotlin unit tests, package/version/permissions, APK ZIP and root-facing asset checks passed. Unsigned Manager SHA-256 `76b125554a6f989758457773f0eff7eda54047b65ede385a36201cec3985e337`, Git blob `60b57ef532747f9b26a57f8ad600f5f556524cd8`.
- The final local host suite ran 305 tests with 50 fixture/optional skips. Source-diff tests check that all non-presentation bytes in the prepared tree equal 4.0; the only MainActivity differences are the two dock shapes. A separate signing-gate integration passed five tests using a throwaway test key, including wrong-key/digest refusal and modified-APK rejection.
- [Emulator run 42450977158](https://github.com/dwp29/Syntenthica/actions/runs/42450977158) used only the separately packaged debug-signed preview (no root Manager, no network permission, no root helpers). It exercised all four selections, light/dark/AMOLED for each, persisted selection after restart, and disabled motion. Edge samples were black in AMOLED and the motion-off frames matched. Preview screenshots are labeled as such; simulated root actions are not proof of actual Manager behavior.
- The real APK was signed locally after consent using `build-kit/scripts/sign_manager_50_locally.py`. Independent checks verified certificate, v2/v3 signatures, 4-byte and 16-KiB ZIP alignment, unchanged non-signature payload, reference permissions and rejection of a modified APK. The uploaded Drive APK was downloaded again and matched the local file byte-for-byte and by SHA-256.

## Limitations

No physical phone installation, upgrade, root authorization, module/WebUI operation, tuning/writeback, kernel boot, recovery or AVB compatibility was tested. A matching package/certificate and higher version code are necessary for an update, not proof it will work on a given ROM or kernel. If an update is rejected, do not casually uninstall the prior Manager (its settings/data could be lost); investigate and retain a recovery plan. The kernel ZIP is a separate TEST artifact, not automatically installed by this APK. Do not disable AVB/vbmeta or wipe data to force boot. Read `SYNTHETICA-MANAGER-4.0-PIXEL.md` and `SYNTHETICA-3.1.md` for inherited feature and kernel limitations.
