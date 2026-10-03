#include "Tbone.h"
#include "Symbols.h"
#include "Xr.h"
#include "Log.h"
#include <cstdint>
#include <cstdio>
#include "StoragePaths.h"
namespace savr::tbone {
namespace {
bool enabled{},previousA{},pressed{},consumed{},claimHeld{},hasPoll{},pending{};
std::uint32_t readyUntil{},pressUntil{};
std::uint32_t Now(){return g.CTimer_m_snTimeInMilliseconds?*g.CTimer_m_snTimeInMilliseconds:0;}
void Trace(const char* text) {
    LOGI("[tbone] %s",text);
    if(FILE* f=std::fopen(savr::storage::Files("vr_snatch.log").c_str(),"a")) {
        std::fprintf(f,"%u %s\n",Now(),text);std::fclose(f);
    }
}
}
void Install(void*) { Trace("native snatch widget 66 -> A installed"); }
bool Active(){return enabled&&hasPoll;}
bool Ready(){return enabled&&hasPoll&&static_cast<std::int32_t>(readyUntil-Now())>=0;}
bool ClaimsA(){return enabled&&(Ready()||claimHeld);}
void UpdateInput(bool allow,bool a) {
    enabled=allow;consumed=false;
    pressed=a&&!previousA;
    if(pressed&&Ready()){pending=true;pressUntil=Now()+180;}
    previousA=a;
    if(!a)claimHeld=false;
    if(!enabled){hasPoll=false;claimHeld=false;pending=false;pressed=false;}
    if(pending&&static_cast<std::int32_t>(pressUntil-Now())<0)pending=false;
    if(Ready()&&a)claimHeld=true;
    xr::SetPackageHint(Ready());
}
bool WidgetReleased(bool original) {
    if(!enabled)return original;
    // The native mobile snatch query is itself the authority: DRIV2 only
    // polls it after live/uncollected package, 2m XYZ and bike/on-foot tests.
    // Do not reject a valid action because of unrelated mission-list metadata.
    if(!Ready())Trace("snatch in range");
    hasPoll=true;readyUntil=Now()+120;xr::SetPackageHint(true);
    if(original)return true;
    if((!pressed&&!pending)||consumed)return false;
    consumed=true;pending=false;claimHeld=true;hasPoll=false;
    xr::SetPackageHint(false);Trace("A -> native package snatch");
    return true;
}
}
