# GTA San Andreas VR on Steam Frame — experimental source

**Upstream Quest port:** [dubrovskiy-yevhen-stakelogic/gta-sa-vr-quest](https://github.com/dubrovskiy-yevhen-stakelogic/gta-sa-vr-quest). This repository is the [astromaddie Steam Frame fork](https://github.com/astromaddie/gtasa-vr/tree/steam-frame). It adds the Lepton manifest and Frame controller profiles, relocates persistent game files to Documents, and includes an experimental paused camera preview with physical grip-and-stick adjustment. Quest support remains in the fork.

**Status: EXPERIMENTAL.** This is personal-use source preparation only; repository visibility and release state are unchanged. Older builds were worn; the prior camera-migration source and packaging repair passed host checks, ARM64 package verification and an unattended Steam-title boot. The current preview, modifier controls, remaps and recentring have not been accepted while worn. See [Steam Frame architecture and validation](docs/STEAM_FRAME.md).

| Area | Evidence and limit |
|---|---|
| Build and package | Prior runtime camera source `e7e8cb2ae8413412ba561689f8b014fd16dce484`; prior packaging repair `313999d742bc3f21c891a3e4bfd74e0d6011729d`. |
| Frame launch | The rebuilt ARM64 APK and Steam-title boot were verified unattended; session/profile suggestions and game frames were observed. |
| Worn behavior | Prior builds were worn; current camera preview and all new physical adjustments remain pending. |
| Save persistence | The save-folder link route exists, but writing and restoring an actual save through the link is not confirmed. |
| Performance | This README makes no current-source performance claim. Prior cadence observations do not establish a sustained rate. |

## Build from a fresh checkout

Build on macOS or Linux with JDK 21, Android SDK/NDK and Python 3. The package input must come from the user's legally owned Google Play GTA San Andreas 2.11.311 ARM64 APK or supported split set. The optional audio archive is not included.

```sh
git clone --branch steam-frame https://github.com/astromaddie/gtasa-vr.git
cd gtasa-vr
tools/build.sh --steam-frame --package \
  --game-package /path/to/your/GTA-SA-2.11.311-ARM64.apk \
  --build-dir "$PWD/.frame-build"
```

The command builds a personal signed package and payload; it does not install or launch the game. Do not redistribute the supplied game package, derived assets or signing key. Prerequisites and packaging details are in [docs/STEAM_FRAME.md](docs/STEAM_FRAME.md); license scope is in [NOTICE.md](NOTICE.md).

A focused headset acceptance run remains pending for installation, real input, tracking/recentering, stereo, menus, gameplay, pause/resume, save writes and reload, clean exit and actual performance. No Frame launch or mutation is part of this source-preparation task.

The previous root README is preserved in [docs/README_PRE_PR0.md](docs/README_PRE_PR0.md). Current source identity, checks and blockers are listed in [docs/PR0_READINESS.md](docs/PR0_READINESS.md).
