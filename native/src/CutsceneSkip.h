#pragma once

#include <cstdint>

namespace savr::cutsceneskip {

// Called once on GameThread after the native tick. Owns only a fresh A
// hold in a loaded formal cinematic; never advances mission script bytecode.
class Button {
public:
    bool Update(bool aDown, bool focused, bool blocked, std::uint64_t nowMs);
    float Progress() const { return progress_; } // 0..1, zero when cancelled
    bool Eligible() const { return eligible_; }

private:
    bool armed_{};
    bool holding_{};
    bool haveScene_{};
    std::uint64_t downAtMs_{};
    std::uint64_t lastSampleMs_{};
    char sceneName_[8]{};
    float lastSceneTime_{};
    float progress_{};
    bool eligible_{};
};

// Formal cinematics use the deliberate hold, never a native A-down edge.
// Outside them preserve the original predicate used by authored script skips.
bool FilterNativeInput(bool (*original)(), bool focused = true, bool blocked = false);
void SetNativeInputFilterInstalled(bool installed);

} // namespace savr::cutsceneskip
