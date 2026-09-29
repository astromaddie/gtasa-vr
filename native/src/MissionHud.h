#pragma once
#include <cstdint>
#include <cstring>

namespace savr::missionhud {
// Android 2.11.311 ProcessForDisplay @3f89f0 / ClearCounter @3f8e1c:
// four 0x44-byte entries start at +0x40; type +0x12, text +0x14,
// enabled +0x3e. PC enum layout must not be used for these offsets.
inline bool IsTorenoSignal(const std::uint8_t* entry) {
    std::uint32_t variable{};
    std::uint16_t type{};
    std::memcpy(&variable,entry,sizeof(variable));
    std::memcpy(&type,entry+0x12,sizeof(type));
    // DRIV3 registers this key as a percentage bar while searching for Mike.
    // Registration is authoritative even when mobile display flags/text have
    // never been populated. ClearCounter zeroes variable, type and key.
    return variable==0x31bc && type==1 &&
        std::memcmp(entry+8,"DRI2_17",8)==0;
}
inline int TorenoSignal(const void* source,const void* scriptSpace) {
    if(!source||!scriptSpace)return -1;
    const auto* timer=static_cast<const std::uint8_t*>(source);
    for(int slot=0;slot<4;++slot) {
        const auto* entry=timer+0x40+slot*0x44;
        if(!IsTorenoSignal(entry))continue;
        // DRIV3 opcode 03C4 registers $31bc; 0090 writes its distance-derived
        // strength. Read the same int32 as the native counter renderer.
        std::int32_t value{};
        std::memcpy(&value,static_cast<const std::uint8_t*>(scriptSpace)+0x31bc,4);
        return value<0?0:(value>100?100:value);
    }
    return -1;
}
}
