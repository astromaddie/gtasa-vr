# ROM-free Steam Frame kit

This experimental kit contains an ARM64 native library with no embedded aircraft HLOD, the loader DEX, the pinned Khronos OpenXR loader, and the tools and notices needed to create a personal install. It contains no GTA APK, game map, generated HLOD, save, audio pack or signing key.

The native renderer first checks its embedded HLOD section. In this kit the section is empty, so it reads `files/savr_aircraft.hlod` from the Steam Frame payload. The local packaging helper creates that file from the map textures in the APK you provide.

## Make a personal install

Use macOS, x86-64 Linux, or Windows with WSL2. Install Python 3.10+, JDK 21, and Android SDK `platforms;android-35` and `build-tools;35.0.0`. Set `JAVA_HOME` and `ANDROID_SDK_ROOT` to those installations. You do not need the NDK, CMake, or a C++ compiler to use this prebuilt kit. Apktool is included.

Keep your APK and output scratch directory outside the extracted kit. Then run:

```sh
python3 tools/package_from_release.py \
  --release-kit "$PWD" \
  --game-package "$HOME/Downloads/GTA-SA-2.11.311.apk" \
  --build-dir "$HOME/SAVRBuild" \
  --allow-unofficial-source
```

Omit `--allow-unofficial-source` for a Google Play-signed APK. It allows a merged or resigned backup while retaining the pinned retail `libGame.so` check. The helper validates the input, generates HLOD locally, patches and signs the APK, and writes the game-data payload.

Copy `SAVRBuild/personal-apks/base.apk` to a separate upload folder and rename it `GTASA-VR.apk`. Add that folder with SteamOS Devkit Client as an Android title named **GTASAVR**, using `GTASA-VR.apk` as the start command. On Windows, choose the upload folder from your Windows filesystem. Then use OpenSSH and `rsync` to copy the payload:

```sh
export FRAME_HOST="steamos@YOUR_FRAME_IP"
bash tools/steam_frame/deploy.sh \
  --payload "$HOME/SAVRBuild/personal-payload" \
  --no-adb --no-install --no-launch
```

This puts `data_main/` under `~/Documents/GTASAVR/data_main/`, the HLOD file directly under `~/Documents/GTASAVR/files/`, and other payload folders such as `vrhands/` under `~/Documents/GTASAVR/files/vrhands/`. Launch **GTASAVR** from your Steam library for controller input. Keep the personal APK, payload and signing key private: they contain or derive from your retail game copy.

The kit was built for ARM64 Steam Frame / Lepton with NDK 27.2.12479018, CMake 3.22.1, Android API 35 and Khronos OpenXR loader 1.1.43. `SOURCE-IDENTITY.json` records the source commit and build hashes. See `LICENSE`, `NOTICE.md`, and `licenses/` for applicable terms and attributions.
