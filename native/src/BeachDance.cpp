// Life's a Beach: retain the native dance/score script, replace only VR view/input.
#include "BeachDance.h"
#include "Symbols.h"
#include "VrCamera.h"
#include "Log.h"
#include <atomic>
#include <cstring>
#include <cstdio>
#include <dlfcn.h>
namespace savr::beachdance {
namespace {
void** scripts{};
void* (*localVariable)(void*,unsigned){};
std::atomic<bool> active{};
std::atomic<int> direction{},score{};
template<class T>T Read(const void* p,unsigned off=0) {
    T v{};std::memcpy(&v,static_cast<const std::uint8_t*>(p)+off,sizeof(v));return v;
}
void Trace(const char* event,int a,int b=0) {
    LOGI("[beachdance] %s %d %d",event,a,b);
    if(FILE* f=std::fopen("/sdcard/Android/data/com.rockstargames.gtasa/files/vr_beachdance.log","a")) {
        std::fprintf(f,"%u %s %d %d\n",g.CTimer_m_snTimeInMilliseconds?*g.CTimer_m_snTimeInMilliseconds:0,event,a,b);
        std::fclose(f);
    }
}
bool Name(void* s,const char* name,bool mission) {
    if((Read<std::uint8_t>(s,0x12c)!=0)!=mission)return false;
    const auto* n=static_cast<const unsigned char*>(s)+0x10;
    unsigned i=0;
    for(;name[i];++i)if((n[i]>='A'&&n[i]<='Z'?n[i]+32:n[i])!=name[i])return false;
    return n[i]==0;
}
std::uint32_t Hash(const std::uint8_t* p,unsigned size) {
    std::uint32_t h=2166136261u;
    for(unsigned i=0;i<size;++i)h=(h^p[i])*16777619u;
    return h;
}
struct VerifiedScript {
    void* thread{};std::uint8_t* base{};bool valid{};
    bool Check(void* s,unsigned size,std::uint32_t expected) {
        auto* bytes=s?Read<std::uint8_t*>(s,0x18):nullptr;
        if(s!=thread || bytes!=base) {
            thread=s;base=bytes;valid=base&&Hash(base,size)==expected;
            if(s)Trace("BYTECODE",static_cast<int>(expected),valid);
        }
        return valid;
    }
} parentCache,danceCache;
void SetActive(bool next) {
    if(active.exchange(next,std::memory_order_relaxed)==next)return;
    direction=0;score=0;
    vrcam::RequestRecenter();
    Trace(next?"BEGIN 3D RIGHT STICK":"END",next);
}
}
bool Install(void* h) {
    if(!h)return false;
    scripts=reinterpret_cast<void**>(dlsym(h,"_ZN11CTheScripts14pActiveScriptsE"));
    localVariable=reinterpret_cast<decltype(localVariable)>(dlsym(h,"_ZN14CRunningScript25GetPointerToLocalVariableEj"));
    const bool ok=scripts&&localVariable&&g.CTheScripts_ScriptSpace&&g.FindPlayerPed&&g.CPed_IsAlive;
    if(!ok)scripts=nullptr;
    Trace("INSTALLED",ok);return ok;
}
bool Active(){return active.load(std::memory_order_relaxed);}
void Update() {
    if(!scripts)return;
    void* parent=nullptr;void* dance=nullptr;
    unsigned count=0;
    for(void* s=*scripts;s && count++<128;) {
        if(Name(s,"strap1",true))parent=s;
        if(Name(s,"dance",false))dance=s;
        void* next=Read<void*>(s,0);if(next==s)break;s=next;
    }
    const bool parentOk=parentCache.Check(parent,detail::kParentSize,detail::kParentHash);
    // Only fingerprint the streamed code when its owning mission is present.
    const bool danceOk=danceCache.Check(parentOk?dance:nullptr,detail::kDanceSize,detail::kDanceHash);
    bool next=false;
    if(parentOk && danceOk) {
        const int phase=Read<int>(localVariable(dance,6));
        const int subphase=Read<int>(localVariable(dance,7));
        void* ped=g.FindPlayerPed(-1);
        const auto flags=Read<std::uint32_t>(g.CTheScripts_ScriptSpace,0x685c);
        next=detail::PlayPhase(phase,subphase) && (flags&0x80000000u) && ped && g.CPed_IsAlive(ped);
    }
    SetActive(next);
    if(next)score=Read<int>(g.CTheScripts_ScriptSpace,0x6860);
}
void SetInput(bool enabled,float x,float y) {
    const int next=enabled&&Active()?detail::Direction(x,y):0;
    const int old=direction.exchange(next,std::memory_order_relaxed);
    if(next && next!=old)Trace("INPUT",next,Score());
}
int AxisLeftRight(){const int d=direction.load();return d==3?-127:d==4?127:0;}
int AxisUpDown(){const int d=direction.load();return d==1?-127:d==2?127:0;}
int Score(){return score.load(std::memory_order_relaxed);}
}
