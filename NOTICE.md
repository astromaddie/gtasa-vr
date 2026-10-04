# Third-party notices

- **OpenXR headers** (`native/vendor/openxr/`): Khronos OpenXR SDK 1.1.43,
  Apache License 2.0. License: `native/vendor/openxr/LICENSE`.
- **OpenXR Android loader**: Khronos
  `org.khronos.openxr:openxr_loader_for_android:1.1.43`, Apache License 2.0.
  Downloaded and verified at build time.
- **Apktool**: version 3.0.3, Apache License 2.0. Downloaded at build time.
- **VR hand assets** (`assets/vrhands/`): derived from UltimateXR SDK,
  copyright VRMADA, MIT License. Source attribution and license are beside
  the assets.
- **gta-reversed / gta-reversed-modern**:
  [community reverse-engineering reference](https://github.com/gta-reversed/gta-reversed-modern)
  for original game behavior. The VR layer targets the retail mobile ARM64
  binary and does not distribute source code from that project.
- **SkyGfx** by aap ([github.com/aap/skygfx](https://github.com/aap/skygfx)):
  the PS2 colour filter option (`COLOUR FILTER < MOBILE | PS2 >`) follows how
  SkyGfx rebuilds the PS2 game's `CPostEffects::ColourFilter` (two timecycle
  post-fx colours: frame x colour 1, plus frame x colour 2 x its alpha). The
  repository carries no licence file, so no SkyGfx code, shaders or data are
  copied or linked; only the published behaviour was read and the arithmetic
  re-implemented from scratch in `native/src/GraphicsEffects.cpp`.

Game APKs, Rockstar source code and assets, extracted game libraries, sound
packs, and signing keys are not included. Optional packs retain their own
licenses and credits.
