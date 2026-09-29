#pragma once
#include <cmath>
#include <cstdint>
#include <cstring>
namespace savr::playerlife {
// Retail 2.11: health +0x6ac (JetPack::MakeAbortable), state +0x54c
// (CPed::IsAlive). IsAlive alone misses lethal health before the death task.
inline bool Dead(const void* ped) {
    if(!ped)return false;
    float health{};std::uint32_t state{};
    std::memcpy(&health,static_cast<const char*>(ped)+0x6ac,sizeof(health));
    std::memcpy(&state,static_cast<const char*>(ped)+0x54c,sizeof(state));
    return (std::isfinite(health)&&health<=0)||state==54||state==55;
}
inline bool HideBody(bool dead,bool scene,bool inVehicle,bool immersive) {
    return !dead&&!scene&&(!inVehicle||immersive);
}
}
