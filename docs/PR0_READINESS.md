# PR0 source readiness

**State: EXPERIMENTAL source preparation only.** No visibility change, release or publication action is included.

- **Baseline source commit before this preparation:** a937601e91641d36300452710dd4726e1de9bb37.
- **Prior runtime camera source:** e7e8cb2ae8413412ba561689f8b014fd16dce484.
- **Prior packaging repair:** 313999d742bc3f21c891a3e4bfd74e0d6011729d.
- **Target:** Steam Frame standalone Android/Lepton ARM64; the repository also retains its Quest port. Build host: macOS or Linux.
- **External data:** user must provide the legally owned Google Play GTA San Andreas 2.11.311 ARM64 APK or supported split set. Optional audio is user-supplied. No game APK, commercial assets or signing key is included.
- **Fresh package route:**

  ~~~sh
  tools/build.sh --steam-frame --package \
    --game-package /path/to/your/GTA-SA-2.11.311-ARM64.apk \
    --build-dir "$PWD/.frame-build"
  ~~~

  Requires JDK 21, Android SDK/NDK and Python 3. The script builds and verifies a personal package; it does not install or launch it. See [Steam Frame architecture and validation](STEAM_FRAME.md) and [NOTICE.md](../NOTICE.md).

The immutable PR0 test source commit, supported targets and final check results are in [PR0_METADATA.json](PR0_METADATA.json).

## Evidence

| Surface | Evidence |
|---|---|
| Host source/build | Camera source and packaging repair were host-checked; ARM64 package, signature/alignment and a rebaked Steam title were verified unattended. |
| Unattended Frame | Current Steam title boot, profile suggestions, READY/SYNCHRONIZED session and game frames were observed. Documents configuration and saves retained their pre-run hashes and modes. |
| Worn | Earlier builds were worn. The current camera preview and packaging repair have not been accepted while worn. |
| Save persistence | The save-link route exists, but a real save write/reload through the link is not confirmed. |
| Fresh isolated source checks | Passed in a fresh local clone with temporary HOME and Git config disabled. Exact commands are below. |

## Known gaps and pending focused acceptance

Current source still needs a focused headset run covering installation, real input, tracking/recentering, stereo, menus, gameplay, pause/resume, save write and reload, clean exit, and actual performance. Exercise the paused camera preview and physical modifier/remaps while worn. Save-link persistence is a specific open item. Past frame cadence observations do not establish sustained performance. No device install or launch is part of this PR0 task.

The previous root README is preserved in [README_PRE_PR0.md](README_PRE_PR0.md); implementation detail and device evidence remain in [STEAM_FRAME.md](STEAM_FRAME.md).

ROM-free source checks run from the isolated clone:

~~~sh
python3 tools/test-camera-comfort.py
python3 tools/test-frame-targeting.py
python3 tools/test-apk-assembly.py
bash -n tools/steam_frame/deploy.sh
env -u FRAME_HOST tools/steam_frame/deploy.sh
~~~

The last command is expected to stop at the required-host guard before any SSH, ADB, install or launch step. A complete package rebuild requires an explicit user-owned GTA SA 2.11.311 ARM64 APK or split set, which was not present in the repository or indexed by its expected name during this check.
