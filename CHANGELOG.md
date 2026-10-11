# Changelog

## 2026-10-11 — Experimental Steam Frame source prep

- Replaced the root landing page with the Frame build route and current acceptance limits; preserved the former README in docs/README_PRE_PR0.md.
- Added the PR0 source-readiness record and sfvr vendor provenance/license notice.
- Moved package validation and aircraft HLOD generation ahead of the native build, so a clean package build prepares its required generated input before CMake compiles.
- Verified a fresh source build and personal package using a user-owned merged 2.11.311 ARM64 backup; the retail engine hash remained enforced. The private APK and game data were excluded from the source tree and release scope.
- Updated PR0 readiness with build checks, source-only publication status, and the exact distinction between 16 KiB ZIP alignment and ELF page alignment for the Android 11 target.
