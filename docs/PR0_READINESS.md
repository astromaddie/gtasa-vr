# PR0 source readiness

**EXPERIMENTAL — ready for public source.** This check produced a personal build for validation; no APK or game data is included in the source publication.

- **Source commit:** `f90113a2190eac0d8fdde33287e620ef730741bc`, plus the `tools/build.sh` preflight-order change recorded in [PR0_METADATA.json](PR0_METADATA.json).
- **Target:** Steam Frame Lepton, Android 11, ARM64, SteamVR OpenXR.
- **Input:** user-owned Google Play GTA San Andreas 2.11.311 ARM64 backup, merged by a backup tool. Its source signer was not the pinned Google Play signer, so validation and packaging used the documented `--allow-unofficial-source` route. The mandatory retail `libGame.so` hash matched. The result records `officialSource=false`.
- **Distribution:** the personal combined APK contains proprietary game files and is not part of this repository or a release. The source kit does not include a game package, extracted game data, or a personal signing key.

## Fresh checks

Checks ran from a fresh source export at the source commit, with the tested build-script patch applied, isolated HOME, JVM `user.home`, and Gradle home, `env -i`, no personal Git credentials, and public pinned build dependencies.

These passed:

~~~sh
python3 tools/test-camera-comfort.py
python3 tools/test-frame-targeting.py
python3 tools/test-apk-assembly.py
bash -n tools/steam_frame/deploy.sh
bash -n tools/build.sh
~~~

The deploy script was also invoked without `FRAME_HOST`; it stopped at its required-host guard before SSH, ADB, install, or launch. No device operation was performed.

## Build and package checks

A clean full `--steam-frame --package` build passed using the user's merged backup and the explicit `--allow-unofficial-source` option. Package validation generated the required aircraft HLOD from the supplied game data before the native build. The HLOD contained 36 tiles and 131,335 triangles. Native ARM64 and loader DEX builds completed; the output package signature verified and Android `zipalign -c -P 16 4` passed.

The package contained ARM64 `libGame.so`, `libsavr.so`, and the pinned OpenXR loader. Their ELF `PT_LOAD p_align` values were respectively `0x4000`, `0x1000`, and `0x1000`. APK ZIP alignment passed the 16 KiB check; that does not establish 16 KiB ELF page compatibility. This build targets the Steam Frame's Android 11 runtime. General [Android 16 KiB page support](https://developer.android.com/guide/practices/page-sizes) has not been established.

The generated APK and payload were kept outside the repository and removed after their private hashes and verification results were recorded. The private receipt is not part of the source kit. No APK was installed or launched during this build check.

The former root README is preserved in [README_PRE_PR0.md](README_PRE_PR0.md). Current port details and prior device observations are in [STEAM_FRAME.md](STEAM_FRAME.md).
