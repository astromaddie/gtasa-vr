#pragma once
#include "Symbols.h"
#include <cmath>
#include <cstring>
namespace savr::vehiclecabin {
// ARM64 2.11: CVehicleModelInfo::SetClump @533508 stores the structure
// at +0x90; CPed::SetPedPositionInCar @590648 reads front dummy +0x30
// and mirrors its X for the driver. Read the loaded model, stock or HD.
inline bool ReadCombineEye(const GameSymbols& symbols, GameSymbols::Vec3* eye) {
    if(!eye || !symbols.CModelInfo_GetModelInfoByName)return false;
    int id=-1;void* model=symbols.CModelInfo_GetModelInfoByName("combine",&id);
    if(!model || id!=532)return false;
    void* structure=nullptr;
    std::memcpy(&structure,static_cast<const char*>(model)+0x90,sizeof(structure));
    if(!structure)return false;
    GameSymbols::Vec3 seat{};
    std::memcpy(&seat,static_cast<const char*>(structure)+0x30,sizeof(seat));
    if(!std::isfinite(seat.x)||!std::isfinite(seat.y)||!std::isfinite(seat.z)||
       std::abs(seat.x)>3.f || std::abs(seat.y)>12.f || seat.z<-.5f || seat.z>5.f ||
       seat.x*seat.x+seat.y*seat.y+seat.z*seat.z<.01f)return false;
    *eye={-seat.x,seat.y,seat.z+.60f};
    return true;
}
// Migrate the recognized legacy seat triple at load; preserve custom values.
inline bool MigrateCombineSeat(int model,int mode,int& side,int& forward,int& height) {
    if(model!=532 || mode!=1 || side!=-98 || forward!=290 || height!=43)return false;
    side=forward=height=0;return true;
}
}
