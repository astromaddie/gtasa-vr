#pragma once
#include <cstdint>
namespace savr::tracking {
struct Recovery {
    bool pending{true};
    unsigned stable{};
    std::uint64_t epoch{};
    void Invalidate() { pending=true;stable=0; }
    bool Sample(bool usable) {
        if(!usable) { Invalidate();return false; }
        if(pending) {
            if(++stable<8)return false;
            pending=false;++epoch;
        }
        return true;
    }
};
struct SeatLatch {
    void* vehicle{};
    std::uint64_t resetSerial{~std::uint64_t{0}};
    double captureUntil{};
    bool valid{};
    bool Begin(void* current, std::uint64_t serial, double nowMs) {
        if(current==vehicle && serial==resetSerial)return false;
        vehicle=current;resetSerial=serial;captureUntil=nowMs+2000.0;valid=false;
        return true;
    }
    bool Capture(double nowMs)const{return !valid || nowMs<captureUntil;}
};
}
