#pragma once
#include <algorithm>
#include <cmath>
namespace savr::locomotion::detail {
struct RunToggle {
    bool running{},wasHeld{},chordGuard{};
    bool Update(bool enabled,bool held,bool crouch,bool l3,bool r3) {
        if(l3 && r3)chordGuard=true;
        if(!l3 && !r3)chordGuard=false;
        if(!enabled || crouch || chordGuard)running=false;
        else if(held && !wasHeld)running=!running;
        wasHeld=held;
        return running;
    }
};
}
