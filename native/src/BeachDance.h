#pragma once
#include <cmath>
#include <cstdint>
namespace savr::beachdance {
bool Install(void* gameHandle);
void Update();
bool Active();
void SetInput(bool enabled,float rightX,float rightY);
int AxisLeftRight();
int AxisUpDown();
int Score();
namespace detail {
constexpr unsigned kParentSize=15962,kDanceSize=17436;
constexpr std::uint32_t kParentHash=0x3b08c58e,kDanceHash=0x4e6b6b3c;
// Directions match the existing lowrider VR arrow renderer. Snap diagonals:
// DANCE interprets raw diagonals as separate, incorrect answers (11/12/15/16).
inline int Direction(float x,float y) {
    if(!std::isfinite(x)||!std::isfinite(y) || x*x+y*y<0.25f)return 0;
    if(std::fabs(x)>=std::fabs(y))return x>0?4:3;
    return y>0?1:2;
}
inline bool PlayPhase(int phase,int subphase) {
    return (phase==0 && subphase>=2 && subphase<=3) || phase==1;
}
}
}
