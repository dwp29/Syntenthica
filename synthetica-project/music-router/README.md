# SpatialFlow MUSIC_PLAYER router — source prototype only

This is an alternative to rebuilding or re-signing the existing SpatialFlow APK.
It declares only the no-data `MUSIC_PLAYER` action and explicitly starts the
upstream app's exported `MainActivity` with `MAIN`/`DEFAULT`. It requests no
permissions, is not privileged, forwards no caller data, and closes on failure.
It does **not** handle `VIEW`/audio URIs or make an app the default by itself.
The accompanying preferred-app XML is a prototype for a new user only if the
actual ROM's package manager honors it. Existing user choices are not modified.

Nothing here has been installed in candidate 04 or on a device. A host test may
compile and sign a disposable copy with a randomly generated, immediately
discarded key; that artifact and key must never be shipped. A real candidate
would require a persistent, privately held, non-public signing key and independent
verification; the upstream APK's existing signature remains unchanged. Before any
integration, verify its actual exported component, the candidate's package-name
collisions, final image free space/metadata, recovery/AVB and boot behavior.
No fallback should weaken signature checks. The host tests do not demonstrate
HyperOS preference handling, audio playback or normal function.
