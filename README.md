# GTA San Andreas VR for Steam Frame

This is my Steam Frame fork of [GTA San Andreas VR for Quest](https://github.com/dubrovskiy-yevhen-stakelogic/gta-sa-vr-quest). It runs on the headset through Lepton and SteamVR OpenXR; no gaming PC or streaming is needed.

**EXPERIMENTAL.** I made this for personal use, and it is still a work in progress. It targets the Valve Steam Frame. You need your own copy of the Google Play GTA San Andreas **2.11.311 ARM64** game package, either as a merged APK or a supported split set. No game APK, commercial game data or signing key is included.

I've played it on my Frame. Stereo gameplay, menus, 3D cutscenes with subtitles and fades, and the third-person locked camera are working well.

## What this fork adds

### Views, cutscenes and camera settings

- First-person play and a default **third-person over-the-shoulder** view with a level horizon and head tracking.
- A third-person movement option for turning with the direction of travel or keeping CJ facing the view.
- 3D stereo cutscenes with subtitles and fades, plus flat cinema and head-tracked cinematic options.
- Live camera previews in the paused VR settings menu. Adjust world size, camera distance and height while seeing the effect on the game.
- Hold left grip and use the right stick to adjust world size, camera distance and height during play.
- Snap, smooth or disabled stick turning, movement direction options, seated calibration and head movement settings.

A third-person 3D-screen view has not been implemented; the available third-person view is over the shoulder.

### Frame controls and menus

- The Frame layout uses the left trigger to target and the right trigger to fire. While targeting, the right stick aims.
- The left and right bumpers cycle through owned weapons; the left D-pad reaches the game's directional controls.
- View goes back in menus or recentres the view when held. The right controller's physical Menu button pauses the game, and both grips plus Menu opens the VR settings.
- Point-and-click navigation for flat game menus and VR settings, using the right controller's laser and trigger.
- Remappable face buttons, triggers, grips, sticks and stick clicks. Quest, Index and Touch controller profiles remain available.

### HUD, display and storage

- A level front-panel HUD, with the original wrist-panel and classic HUD options still available.
- Optional PS2-style color grading, enabled by default on Frame.
- A native **2160×2160 per-eye** target and a 120 Hz display setting, with the active eye size and rate shown in the menus.
- Game data, audio, VR settings and linked saves under `~/Documents/GTASAVR`, outside disposable app storage.

The original Quest port supplies the core first-person VR game, tracked hands and weapons, and vehicle interactions. Those features stay available here.

The [Steam Frame guide](docs/STEAM_FRAME.md) covers the setup, controls, display options and camera details. The [archived Quest README](docs/README_PRE_PR0.md) is preserved for the original port.

## Default Frame controls

| Input | Action |
| --- | --- |
| Left trigger | Target |
| Right trigger | Fire |
| Right stick while targeting | Aim |
| Left/right bumper | Previous/next owned weapon |
| Left D-pad | Game directional controls and menus |
| Left grip + right stick | Adjust apparent world size, camera distance and height |
| View, short press | Back in menus; switch view in play |
| View, held | Recentre; hold longer to recalibrate standing height |
| Right controller Menu | Pause |
| Both grips + Menu or Y | Open the VR settings menu |

Set GTASAVR's display rate in SteamVR's per-app settings. The render-scale default adapts to SteamVR's recommended eye size to target 2160×2160 per eye.

## Build the Frame APK and payload

Build on x86-64 Linux, macOS, or x86-64 Ubuntu under Windows WSL2. The Frame is an ARM64 run target; the NDK's Linux host tools are x86-64. Apple Silicon Macs need Rosetta for the pinned x86-64 tools.

On Windows, install Ubuntu with [WSL2](https://learn.microsoft.com/windows/wsl/install), then install a Linux JDK 21 and the Linux Android SDK Command-Line Tools inside Ubuntu. For example, install OpenJDK with `sudo apt update && sudo apt install -y openjdk-21-jdk`, and download/extract the Linux SDK Command-Line Tools under `$HOME/Android/Sdk`. Keep the checkout, SDK and build output in the Linux filesystem (for example, `~/src/gtasa-vr`). A game package already on Windows can be passed through its WSL path, such as `/mnt/c/Users/you/Downloads/GTA-SA-2.11.311-ARM64.apk`; copying it into Linux first can improve file access speed. See Android's [SDK command-line tools](https://developer.android.com/tools/sdkmanager) and [NDK downloads](https://developer.android.com/ndk/downloads).

Install Python 3.10+, JDK 21 and Android SDK command-line tools. The pinned SDK packages are Android platform 35, build-tools 35.0.0, NDK 27.2.12479018 and CMake 3.22.1. Set `ANDROID_HOME` and `JAVA_HOME` to your own paths (`$HOME/Library/Android/sdk` on macOS or `$HOME/Android/Sdk` on Linux/WSL2):

```sh
mkdir -p "$HOME/src"
cd "$HOME/src"
git clone --branch steam-frame https://github.com/astromaddie/gtasa-vr.git
cd gtasa-vr
export JAVA_HOME="/path/to/linux-jdk-21"
export ANDROID_HOME="/path/to/linux-android-sdk"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
sdkmanager --sdk_root="$ANDROID_HOME" \
  "platforms;android-35" "build-tools;35.0.0" \
  "ndk;27.2.12479018" "cmake;3.22.1"
sdkmanager --licenses
```

The build also needs the pinned Apktool 3.0.3 JAR and Khronos OpenXR Android loader 1.1.43 for arm64. Download the Apktool JAR from its [3.0.3 release](https://github.com/iBotPeaches/Apktool/releases/tag/v3.0.3) and the OpenXR loader [AAR from Maven Central](https://repo1.maven.org/maven2/org/khronos/openxr/openxr_loader_for_android/1.1.43/openxr_loader_for_android-1.1.43.aar). Extract the arm64 loader at `prefab/modules/openxr_loader/libs/android.arm64-v8a/libopenxr_loader.so` from the AAR. The build checks both files against their pinned SHA-256 hashes.

Supply your own Google Play 2.11.311 ARM64 package as a merged APK or supported split set. A merged or resigned backup is supported with `--allow-unofficial-source`; a different signer alone is not a rejection on this Steam Frame route. The flag does not bypass the pinned retail `libGame.so` hash check, and the build records the input as unofficial. The PS2 audio pack is optional for the Frame build.

```sh
/bin/bash tools/build.sh --steam-frame --package \
  --android-sdk "$ANDROID_HOME" --java-home "$JAVA_HOME" \
  --openxr-loader "/path/to/libopenxr_loader.so" \
  --apktool "/path/to/apktool_3.0.3.jar" \
  --build-dir "$PWD/.frame-build" \
  --game-package "/mnt/c/Users/you/Downloads/GTA-SA-2.11.311-ARM64.apk"
```

For a split set, point `--game-package` at the supported archive or folder. The APK and payload are written under `.frame-build/out` and `.frame-build/payload`; the script builds a personal signed package and does not install or launch it. The APK is `.frame-build/out/base.apk`. The exact source revision, input classification and previous checks are recorded in [PR0 readiness](docs/PR0_READINESS.md).

Add `--allow-unofficial-source` to the command above when using a merged or resigned backup. A generated combined APK contains commercial game data and is for your personal use; this repository does not distribute it.

## Install and play on Steam Frame

Create the first **GTASAVR** library entry with Valve's public [SteamOS Devkit Client Title Upload](https://partner.steamgames.com/doc/steamhardware/steamframe/loadgames). Pair the Frame with the client and upload a folder containing the APK with **Name** `GTASAVR`, **Local Folder** set to that folder, **Start Command** `GTASA-VR.apk`, and **Runtime** `Android`:

```sh
mkdir -p .frame-upload/gtasa
cp .frame-build/out/base.apk .frame-upload/gtasa/GTASA-VR.apk
```

On Windows, copy `.frame-upload/gtasa` to your Windows Downloads folder (available inside WSL at `/mnt/c/Users/YOUR_WINDOWS_USERNAME/Downloads/`), then select that copied folder in the Devkit Client.

The build computer needs OpenSSH and `rsync` for file transfer. Then enable SSH to the Frame and set its address. This route copies the payload to persistent Documents and refreshes the APK in an existing `~/devkit-game/GTASAVR` title folder without ADB:

```sh
export FRAME_HOST="steamos@FRAME_HOST_OR_IP"
tools/steam_frame/deploy.sh --apk "$PWD/.frame-build/out/base.apk" \
  --payload "$PWD/.frame-build/payload" --no-adb
```

If the Devkit Client stored the title in a different directory, upload the new APK with the client. Launch **GTASAVR from the Steam library** so SteamVR supplies the controllers. After the first launch, close the game and run the save-link step to keep saves in Documents:

```sh
tools/steam_frame/deploy.sh --no-adb --no-install --no-launch --link-saves
```

Game files, settings and saves live under `~/Documents/GTASAVR` on the Frame. The [setup guide](docs/STEAM_FRAME.md) has further details.

The ADB development-install route is optional: add Android SDK platform-tools (`adb`) to the build computer, start **Lepton Development** and omit `--no-adb`. For play, use the Steam library title. `FRAME_HOST` must be your own Frame SSH target.

## Credits and licenses

This fork is based on [GTA San Andreas VR for Quest](https://github.com/dubrovskiy-yevhen-stakelogic/gta-sa-vr-quest). Shared Steam Frame camera helpers come from [sfvr](https://github.com/astromaddie/sfvr). The [MIT license](LICENSE) covers original port contributions; the [third-party notices](NOTICE.md) list component licenses and attribution. It doesn't grant permission to redistribute GTA San Andreas. Commercial game files and optional sound packs keep their own terms; supply game data from your own copy.
