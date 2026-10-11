# Building

This page documents the original Quest builder helpers. For the Steam Frame
APK and payload, use the [Frame build guide](README.md#build-the-frame-apk-and-payload):
that route uses Bash on macOS, Linux, or Windows WSL2 and accepts a supported
merged/resigned backup with `--allow-unofficial-source` while retaining the
pinned retail `libGame.so` hash check. The PowerShell commands below are not a
Steam Frame build route.

## Windows

Run `BUILD_AND_INSTALL.bat`, or prepare a build without a Quest:

```powershell
./tools/build-and-install.ps1 `
  -GamePackage "D:\Backups\GTA-SA-Play-export" `
  -AudioSource "D:\Mods\gta-sa-ps2-style-mod-pack_1786856007_737162.7z" `
  -BuildOnly
```

The builder downloads pinned tools, validates the game and audio inputs, builds
ARM64 native code and the Java loader, and signs the assembled APK split set.
Outputs are stored under `C:\SAVRBuild`, or the directory passed with `-WorkDir`.

## Linux and macOS

Install Bash, Python 3.10 or newer, curl, tar with xz support, and unzip. Run:

```bash
bash BUILD_AND_INSTALL.sh \
  --game-package "$HOME/Backups/GTA-SA-Play-export" \
  --audio-source "$HOME/Downloads/gta-sa-ps2-style-mod-pack_1786856007_737162.7z" \
  --build-only
```

Omit `--build-only` for installation. Output runs are stored under
`~/SAVRBuild/runs`, or the directory passed with `--work-dir`.

## Inputs and signing

For this Quest workflow, the game input must contain the official Google Play `com.rockstargames.gtasa`
version `2.11.311` (`4234641`), its ARM64 library, the `data_main` split, and any
installed locale/density splits. Selecting `base.apk` includes sibling splits.
The Quest builder verifies the official signer and supported `libGame.so` hash.

The audio input must match `tools/audio-reference.json`. Only validated audio
files are copied. Aircraft HLOD is generated locally from the supplied game
assets during the build.

Keep the signing key at `%LOCALAPPDATA%\GTASAVRBuilder\signing` on Windows,
or `$XDG_DATA_HOME/gtasavr-builder/signing` (`~/.local/share/gtasavr-builder/signing`
by default) on Linux/macOS. Updates require the same key as the installed build.

## Developer build

Public builds use `SAVR_DEV=OFF`. Pass `-Developer` to `tools/build.ps1`,
`--developer` to `tools/build.sh`, or `-DSAVR_DEV=ON` directly to CMake for the
profiler and developer capture support. Use **VR MENU > PROFILER** to toggle it.

## Reset settings

`RESET_VR_SETTINGS.bat` and `RESET_VR_SETTINGS.sh` remove only:

```text
vr_appearance.ini
vr_basketball.ini
vr_calib.ini
vr_calib.ini.tmp
vr_driving.ini
vr_graphics.ini
vr_holsters.ini
vr_hud.ini
vr_jetpack.ini
vr_locomotion.ini
vr_modelsets.ini
```

Both scripts require confirmation. Saves, game assets, and installed APKs are
preserved. Build-only commands perform no headset installation or game launch.
