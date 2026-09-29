# GTA San Andreas VR for Quest

Version `0.3.1 alpha`. Source code and build tools for the Quest VR mod.

## Requirements

- A complete Google Play GTA San Andreas `2.11.311` ARM64 APK split set.
- The supported audio archive `gta-sa-ps2-style-mod-pack_1786856007_737162.7z`,
  or its extracted audio directory. Select **Original plan mod pack** on the
  [download page](https://libertycity.net/files/gta-san-andreas-ios-android/241069-gta-sa-classic-avanced-mod-pack.html).
- Windows 10/11, Linux x86_64, or macOS, with an internet connection for tools.
- Quest Developer Mode and authorized USB debugging for installation.

## Build and install

1. Export the installed Google Play game from an Android device with
   `EXPORT_PLAY_APKS.bat`. Keep `base.apk` and every exported split together.
2. Run `BUILD_AND_INSTALL.bat` on Windows or `bash BUILD_AND_INSTALL.sh` on
   Linux/macOS.
3. Select the complete APK export and the supported audio input.
4. Connect Quest, authorize USB debugging, and follow the installer prompts.

The installer leaves the game stopped. Preserve the personal signing key for
future installations. See [BUILDING.md](BUILDING.md) for command-line options.

## Proper Fixes

1. Supply an SA Mobile - Proper Fixes archive or extracted directory containing
   `com.rockstargames.gtasa/files`.
2. Run `INSTALL_PROPER_FIXES.bat` and select that input.
3. Start the game, open **VR MENU > MODEL SET**, enable **PROPER FIXES**, and
   fully restart the game.

The script prepares and verifies the pack under `files/optionalmods/properfixes`.
It retains the input pack and its credits. Set **PROPER FIXES** to **OFF** and
restart to use the original game assets. `DISABLE_OPTIONAL_MODS.bat` disables
optional model sets from the computer.

To prepare the pack without installing it:

```powershell
./tools/install-optional-mod.ps1 -Kind properfixes -Archive <path> -PrepareOnly
```

## HD weapons

Run `INSTALL_HD_WEAPONS.bat` with a compatible mobile weapon pack, then enable
**HD WEAPONS** in **VR MENU > MODEL SET** and fully restart the game. Weapon
packs are supplied separately.

## Settings

- `RESET_VR_SETTINGS.bat` or `bash RESET_VR_SETTINGS.sh` restores default VR
  settings after confirmation, preserving saves and game assets.
- `tools/export-savr-settings.ps1` exports VR settings to the computer.
- `COLLECT_RENDER_REPORT.bat` collects a render diagnostic report.

## License

See [LICENSE](LICENSE), [NOTICE.md](NOTICE.md), and the licenses alongside
third-party files. Game APKs, game assets, audio packs, and signing keys are
provided locally and are not included in this source kit.
