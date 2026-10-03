// SMOKE4/Just Business: CJ is a passenger, not an AttachPedToEntity gunner.
// Retail mission bytecode and vehicle reference are verified; SCM is untouched.
#include "JustBusiness.h"
#include "Symbols.h"
#include "VrCamera.h"
#include "Log.h"
#include <atomic>
#include <cstring>
#include <cstdio>
#include <dlfcn.h>
#include "StoragePaths.h"
namespace savr::justbusiness {
namespace {
void** scripts{};
std::uint8_t* locals{};
void* (*getVehicle)(int){};
void* script{};std::uint8_t* base{};
bool verified{};int lastStage=-1;int lastRideGate=-1;
std::atomic<bool> active{};
template<class T>T Read(const void* p,std::size_t off){T v{};std::memcpy(&v,static_cast<const std::uint8_t*>(p)+off,sizeof(v));return v;}
void Trace(const char* event,int value,int extra=0) {
    LOGI("[justbusiness] %s value=%d extra=%d",event,value,extra);
    if(FILE* f=std::fopen(savr::storage::Files("vr_justbusiness.log").c_str(),"a")) {
        const unsigned time=g.CTimer_m_snTimeInMilliseconds?*g.CTimer_m_snTimeInMilliseconds:0;
        std::fprintf(f,"%u %s value=%d extra=%d\n",time,event,value,extra);std::fclose(f);
    }
}
bool NameMatches(void* s) {
    if(!s || !Read<std::uint8_t>(s,0x12c))return false;
    const auto* n=static_cast<const unsigned char*>(s)+0x10;
    constexpr char name[]="smoke4";
    for(int i=0;i<6;++i) {
        const auto c=n[i]>='A'&&n[i]<='Z'?n[i]+32:n[i];
        if(c!=name[i])return false;
    }
    return n[6]==0;
}
std::uint32_t Hash(const std::uint8_t* p) {
    std::uint32_t h=2166136261u;
    for(std::size_t i=0;i<detail::kScriptSize;++i)h=(h^p[i])*16777619u;
    return h;
}
void SetActive(bool next,void* ped=nullptr) {
    if(active.exchange(next,std::memory_order_relaxed)==next)return;
    if(next) {
        // The script gives MICRO_UZI (type 28, slot 4) at 18707 before stage 20.
        // Select its existing inventory entry; PhysicalWeapon's mission entry
        // path then puts it in a free hand and waits for the first grip.
        if(ped && Read<int>(ped,0x730+4*0x20)==28)
            g.CPed_SetCurrentWeaponSlot(ped,4);
    }
    vrcam::RequestRecenter();
    Trace(next?"BEGIN rear passenger":"END",next?1:0);
}
}
bool Install(void* h) {
    if(!h)return false;
    scripts=reinterpret_cast<void**>(dlsym(h,"_ZN11CTheScripts14pActiveScriptsE"));
    locals=reinterpret_cast<std::uint8_t*>(dlsym(h,"_ZN11CTheScripts31LocalVariablesForCurrentMissionE"));
    getVehicle=reinterpret_cast<decltype(getVehicle)>(dlsym(h,"_ZN6CPools10GetVehicleEi"));
    const bool ok=scripts&&locals&&getVehicle&&g.FindPlayerPed&&g.FindPlayerVehicle&&
        g.CVehicle_IsDriver&&g.CVehicle_GetVehicleAppearance&&g.CPed_IsAlive&&
        g.CPed_SetCurrentWeaponSlot&&g.TheCamera;
    if(!ok)scripts=nullptr;
    Trace("INSTALLED",ok);return ok;
}
bool Active(){return active.load(std::memory_order_relaxed);}
void Update() {
    if(!scripts)return;
    void* found=nullptr;
    unsigned count=0;
    for(void* s=*scripts;s && count++<128;) {
        if(NameMatches(s)){found=s;break;}
        void* next=Read<void*>(s,0);if(next==s)break;s=next;
    }
    if(!found) {script=nullptr;base=nullptr;verified=false;lastStage=-1;lastRideGate=-1;SetActive(false);return;}
    auto* bytes=Read<std::uint8_t*>(found,0x18);
    if(found!=script || bytes!=base) {
        script=found;base=bytes;
        const auto hash=base?Hash(base):0;
        verified=base && hash==detail::kScriptHash;
        Trace("BYTECODE hash",static_cast<int>(hash),static_cast<int>(detail::kScriptHash));
        Trace("BYTECODE verified",verified);
    }
    if(!verified){SetActive(false);return;}
    const int stage=Read<int>(locals,98*4);
    if(stage!=lastStage){lastStage=stage;Trace("STAGE",stage);}
    void* ped=g.FindPlayerPed(-1);
    void* vehicle=g.FindPlayerVehicle(-1,false);
    // Stage 20 owns all gunplay sections. Scripted jumps keep their native
    // control locks/cinematic cameras; leaving the seat ends this override.
    const int gate=(stage!=20?1:0) | ((!ped || !g.CPed_IsAlive(ped))?2:0) |
        (!vehicle?4:0) | ((vehicle && vehicle!=getVehicle(Read<int>(locals,169*4)))?8:0) |
        ((vehicle && g.CVehicle_GetVehicleAppearance(vehicle)!=2)?16:0) |
        ((vehicle && ped && g.CVehicle_IsDriver(vehicle,ped))?32:0);
    if(gate!=lastRideGate){lastRideGate=gate;Trace("RIDE gate (0=ready)",gate,stage);}
    SetActive(gate==0,ped);
}
void RecordShot(int type,int hand) {
    static unsigned shots=0;
    if(Active() && (++shots<=16 || shots%120==0))Trace("SHOT",type,hand);
}
}
