#pragma once

namespace savr::frame_target {

// Single source of truth for the experiment. GTA's cap word, the outer pacer,
// and the OpenXR display-refresh request all derive from this value.
//
// Steam Frame: this is the CEILING (120 Hz, the display standard). GTA's cap word
// is written once at launch, so it has to be the highest rate the port may run;
// the rate actually requested and paced comes from the refresh_rate setting and
// the automatic fallback in Xr.cpp (xr::TargetFrameRateHz), which can only be at
// or below it. Quest keeps its fixed 72.
#ifdef SAVR_STEAM_FRAME
inline constexpr int kFps = 120;
#else
inline constexpr int kFps = 72;
#endif

static_assert(kFps > 0 && kFps <= 0xffff,
              "target FPS must fit the retail ARM64 MOVZ immediate");

} // namespace savr::frame_target
