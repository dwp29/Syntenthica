# Synthetica Manager 3.1 Neon

A Manager appearance, diagnostics, and ZIP confirmation update. It is not a
kernel, recovery ZIP, module, camera fix, or replacement for the daemon.

## Appearance and Device Check

- System, Light, Dark, and AMOLED choices; AMOLED uses a black canvas. Oxanium
  is bundled for headings under the SIL Open Font License; body text uses the
  system font. Accent, glow, and ambient motion are adjustable.
- The shared ambient pulse stops when the app is paused or Android reports that
  animations are disabled. Other animations follow Android's own settings.
- Device Check reads available Android/device, CPU, RAM, storage, battery,
  display, sensor, Camera2 metadata and thermal information. It also reads
  accessible GPU clock/governor, zram0, Linux load averages, and pressure-stall
  information. Load average is **not** CPU utilization; PSI is the percentage
  of time stalled over its 10-second averaging window. A real zero remains a
  reading; restricted or missing values are shown as unavailable.
- Readings refresh only while the page is resumed. This feature does not change
  performance settings, open a camera, request new sensitive permissions,
  invoke root, or automatically transmit readings.
- Copying is opt-in: no sections are selected initially, and the selected
  fields are previewed before the user taps Copy. The report omits serial
  numbers, IMEI and Android ID. Android 13 and later are asked to mark the clip
  as sensitive. The clipboard or keyboard may still expose or sync copied data.

Camera capabilities vary between ROMs. This page does **not** repair or establish
the cause of the earlier 0.6× camera freeze.

## ZIP preflight before installation

Module and AnyKernel3 ZIP paths converge on one background preflight. It makes
an app-private copy, calculates SHA-256, identifies the type, displays safe
module metadata if present, and asks for confirmation for **each** package.
All packages must be checked and approved before any batch installation starts.
Unknown, ambiguous, unreadable or structurally unsafe ZIPs are stopped. An
AnyKernel ZIP is checked alone; a module-only repository source cannot silently
turn into a kernel flash. If a later module fails during installation, earlier
ones may already be installed: there is no batch rollback.

The inspection is deliberately bounded: at most 16 ZIPs and 512 MiB combined,
10,000 entries per ZIP, and 64 KiB for module metadata. It checks paths,
duplicates, local versus central ZIP headers, special entries and marker
metadata without unpacking the whole archive. Recognized markers must be at
the exact root paths expected by the installers. ZIP64, split or encrypted ZIPs
are not supported by this preflight. These restrictions may reject otherwise
usable archives; no installer starts for rejected ZIPs. Staged copies are
removed on cancellation/completion where possible, and old owned stages are
pruned on a later inspection; a killed process or Android cache eviction can
still affect temporary files.

Immediately before the existing module install command, the private installer
copy is checked against the approved SHA-256. For AnyKernel, the copied ZIP is
also checked with BusyBox SHA-256 **before** extracting or running the installer;
if that applet is unavailable, the operation fails closed. The kernel, UAPI,
daemon, app root authorization and installer script payloads are not changed.
The Manager's AnyKernel shell sequence is modified to require that verified copy.

**A checksum does not establish authenticity, safety, device compatibility, or
malware absence.** The preflight is not an antivirus, signature verifier, or
full integrity/compatibility test; trusted source and a recovery plan remain
important. A malicious process with root can defeat ordinary app-level checks.

## Compatibility and validation limits

- Package: `net.ember.labs`; version `3.1.0`, code `41000`.
- UAPI 4 and the ARM64 root daemon remain the same as the earlier Manager
  baseline. No kernel or root-permission changes are included.
- A real in-place Android update requires the original signing certificate, a
  matching installed package, and Android accepting the higher version code.
  A signature check alone cannot prove update, root or device-feature behavior.
- The separate preview package is debug-signed, contains no root backend, and
  exercises simulated ZIPs without installing them. It is **not** the Manager
  and cannot update or manage root.
- Integrated Zygisk, multi-manager, SUSFS and live tuning remain out of scope
  pending a separate security and compatibility review.

## Reproducibility and privacy

`build-kit/scripts/build_manager_31_neon.py` prepares the pinned Manager source
and builds an **unsigned** APK; `.github/workflows/synthetica31-manager.yml`
compiles and checks it. `build-kit/scripts/sign_manager_31_locally.py` requires
a previously verified SHA-256 and the original public certificate, prompts for
passwords interactively, verifies its output, and requires the private keystore
to be outside the checkout. Never commit, log, or upload the private key to
public CI. Signing is a separate, explicitly authorized step.

The Manager does not automatically send Device Check readings, but the existing
application retains its previous network features; this is not a claim that the
whole Manager never uses the network.

## Validation snapshot — 2026-11-07

- Build [42367954269](https://github.com/dwp29/Syntenthica/actions/runs/42367954269)
  from application-source commit `2afee99` compiled both the unsigned Manager
  and the separate preview. The independently downloaded Manager has SHA-256
  `794b0e618f2ffa848f86ba2557deff5687acb9e32a1a757b51057b06e73bdaf3`.
  Its ZIP integrity, alignment, package/version and permissions were checked;
  its permissions match both the 2.0 baseline and the signed 3.0 Manager. JNI,
  daemon, and root-facing packaged assets match the baseline as described
  above. **It is unsigned and cannot be installed as an update.**
- [Emulator run 42368656302](https://github.com/dwp29/Syntenthica/actions/runs/42368656302)
  used the exact separate preview from that build (SHA-256
  `779203510ea167e3f835ebc091427168f4671e19768321f9623716ffa72206ae`).
  Theme persistence, selected-only copy preview, diagnostics, simulated ZIP
  classification/confirmation/cancellation, multiple-package approvals,
  rejected batches, callback dialogs, staged-file cleanup, and tamper refusal
  passed. No Manager or installer was run there.
- The local host suite passed 194 tests with 16 opt-in/fixture-dependent skips;
  the Kotlin preflight/device unit runner passed 12 methods. The real 3.0
  candidate ZIP was classified and hashed without installation. Pinned x86
  BusyBox verified and extracted its installer on Linux without executing it,
  and refused a modified copy; Android/ARM/root execution remains untested.
- Five signing-tool tests passed against this unsigned APK using a freshly
  generated throwaway key. After the user's explicit authorization, the final
  APK was signed locally using the original Manager identity; temporary private
  material was removed afterward. Signed APK SHA-256:
  `120a218656869b5442d3de9cb114dec3c8a9a74534f07c6230b0a8ddb8def207`.
  Its certificate matches the signed 3.0 Manager; v2/v3 signatures, 4-byte
  and 16-KiB alignment, unchanged non-signature payload, and rejection of a
  tampered copy were independently verified.
- The APK was not installed on a phone. Physical-device behavior, an actual
  Manager upgrade, root authorization and real module/kernel flashing remain
  unverified; matching package, version, and signature do not prove them.
