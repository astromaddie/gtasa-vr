#pragma once
#include <cmath>
#include <cstddef>
#include <cstdint>
namespace savr::catalyst {
bool Install(void* handle);
// GameThread only, after ordinary throwable/basketball trajectory publishers.
void Update(bool blocked);
void Reset();
bool Active();
namespace detail {
constexpr std::size_t kScriptSize = 20223;
constexpr std::uint32_t kScriptHash = 0xdb1f3d7e;
inline std::uint32_t Hash(const std::uint8_t* p, std::size_t n) {
    std::uint32_t h = 2166136261u;
    while (n--) h = (h ^ *p++) * 16777619u;
    return h;
}
// Entry/resume/tracking recovery must see a released trigger before arming.
struct Trigger {
    bool ready{}, down{}, armed{};
    bool Update(float level, bool usable) {
        if (!usable || !std::isfinite(level)) { *this = {}; return false; }
        const bool pressed = down ? level >= 0.32f : level >= 0.62f;
        if (!ready) { ready = level < 0.32f; down = pressed; return false; }
        if (pressed && !down) armed = true;
        const bool release = !pressed && down && armed;
        if (release) armed = false;
        down = pressed;
        return release;
    }
};
constexpr std::size_t kInput = 11087, kLaunch = 11229,
    kSource = 11269, kVelocity = 11474, kDone = 11492, kCatch = 11538;
// Pure routing used by the actual interpreter bridge and host regression test.
inline std::size_t Route(std::size_t ip, bool release) {
    return ip == kInput ? (release ? kLaunch : kCatch) : ip;
}
}
}
