# GTA San Andreas VR on the Steam Frame

This branch runs the Quest kit on the Valve Steam Frame. The Frame runs
Android apps inside a container called Lepton, on top of SteamVR's OpenXR
runtime. The game itself is unchanged: it's the same Google Play build
(2.11.311) with the same VR layer. What's different is how it's packaged,
where its files live and how the controllers map.

Status: it starts on the Frame and runs its menus at 72 fps. Nobody has
played it in the headset yet.

## What's different from the Quest build

All of it sits behind `--steam-frame` (CMake `SAVR_STEAM_FRAME`), so Quest
builds come out the same as before.

- **One APK.** Lepton's Steam titles take a single APK, so the Frame build
  wants a merged ("monolithic") game APK as input and produces one
  `base.apk`. A backup tool's merged APK works with
  `--allow-unofficial-source`. Its signer differs from Google's, but the
  kit still checks `libGame.so` against the expected hash, so you know it's
  the right game.
- **Manifest.** Head tracking is no longer a hard install requirement,
  because Lepton doesn't advertise it. The Quest-only focus-aware flag is
  gone.
- **Files.** Settings, logs, audio, the VR hands and the game data go in
  `/sdcard/Documents/GTASAVR` (`~/Documents/GTASAVR` on the headset). That
  folder survives a Lepton reset; the app's own storage doesn't. If the
  folder can't be written, it falls back to the old Quest paths and logs
  why.
- **Controllers.** The Frame controller profile comes first, then Index,
  then the original Touch map. A, B, X, Y and Menu are on the right
  controller, View is on the left. Hold View for a second to recentre (both
  hands buzz). A short View press is back in the VR menu. Clicking both
  sticks no longer recentres.
- **OpenXR.** Only extensions SteamVR actually offers are switched on, and
  the swapchain format comes from SteamVR's own list. Everything is logged
  with a `[savr-frame]` prefix.
- **Audio.** The PS2 audio pack is still what you want, but on the Frame
  it's optional. Without it the game should fall back to its own audio.

## Build (Mac or Linux)

You need the merged game APK, the PS2 audio pack (extracted is fine), an
Android SDK with NDK 27.2, a JDK, apktool 3.0.3, and the Khronos OpenXR
loader `.so` (`build-and-install.sh` normally fetches the last two). Run the
validation step first, because it also generates the aircraft LOD data the
native build needs:

```sh
python3 tools/assemble.py --validate-only --steam-frame --allow-unofficial-source \
  --game-package <merged.apk> --audio-source <audio dir or .7z> \
  --build-dir <build> --sdk <sdk> --java-home <jdk> --apktool <apktool.jar>

/bin/bash tools/build.sh --package --steam-frame --allow-unofficial-source \
  --android-sdk <sdk> --java-home <jdk> --openxr-loader <libopenxr_loader.so> \
  --apktool <apktool.jar> --build-dir <build> \
  --game-package <merged.apk> --audio-source <audio dir or .7z>
```

You get `<build>/out/base.apk` (about 1.4 GB) and `<build>/payload` (about
2.5 GB). Keep at least 8 GB free while it builds.

## Put it on the headset

```sh
tools/steam_frame/deploy.sh --apk <build>/out/base.apk \
  --payload <build>/payload --register-title --no-adb
```

That copies the game data into `~/Documents/GTASAVR` over SSH, then puts the
APK in a persistent **GTASAVR** title in the Steam library. Launch that
title to play. A game started over adb gets no controllers. You can also launch the title
from SSH by writing `steam://rungameid/<id>` into `~/.steam/steam.pipe`. The
id is `(appid << 32) | 0x02000000`, and the appid is in Steam's
`shortcuts.vdf`.

`FRAME_HOST` picks the SSH target. The default is the Frame on Wi-Fi,
`steamos@192.168.1.31`.

## Known gaps

- The game's own saves go to its app storage. On the Frame that's a folder
  in the title's compatdata, which a Lepton reset can take with it. Run
  `deploy.sh --link-saves` once, after the first launch and with the game
  closed, to point that folder at `~/Documents/GTASAVR/saves`. The game
  sees the link fine. Whether it writes saves through it is still to be
  confirmed with a real save.
- The game data is in the APK and in `data_main`, so it takes up space
  twice.
- Bumpers and the D-pad aren't bound yet.
- What's been checked on the Frame (no one in the headset, 2026-10-03):
  - The title installs and launches from Steam.
  - The hooks patch the game fine.
  - OpenXR comes up on SteamVR's GLES path with an sRGB swapchain.
  - All three controller profiles are accepted.
  - Data, PS2 audio and settings load from `~/Documents/GTASAVR`.
  - The menus present at 72 fps with no failed frames.
- Still open: stereo gameplay. The game renders each eye with shared GL
  contexts, and that hasn't run yet, because getting into a game needs
  someone pressing buttons.
