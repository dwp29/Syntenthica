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
