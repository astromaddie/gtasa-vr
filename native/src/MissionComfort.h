#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace savr::missioncomfort {
// Metres in the head frame. Retention is slightly wider than entry so a
// deliberate raise does not flicker when the player's hand trembles.
inline bool CameraAtEye(float distance,float forward,float height,float lateral,
                        float alignment,bool active) {
    return std::isfinite(distance)&&std::isfinite(forward)&&
        std::isfinite(height)&&std::isfinite(lateral)&&std::isfinite(alignment)&&
        distance>=0.04f&&distance<=(active?0.43f:0.38f)&&
        forward>=-0.03f&&forward<=(active?0.39f:0.34f)&&
        height>=(active?-0.22f:-0.18f)&&height<=0.12f&&
        std::abs(lateral)<=(active?0.21f:0.18f)&&
        alignment>=(active?0.90f:0.94f);
}

// Soft centre for RC aim, full travel remains available for take-off/landing.
inline float RcAxis(float value) {
    if(!std::isfinite(value)) return 0;
    const float x=std::clamp((std::abs(value)-0.12f)/0.88f,0.0f,1.0f);
    return std::copysign(x*(0.35f+0.65f*x),value);
}

} // namespace savr::missioncomfort
