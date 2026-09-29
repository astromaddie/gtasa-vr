// Retail mission camera policy and post-cutscene streaming service.
#include "MissionScenes.h"
#include "Symbols.h"
#include "ModelSets.h"
#include "Log.h"
#include <atomic>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cmath>
#include <dlfcn.h>
namespace savr::missionscenes {
namespace {
void** scripts{};
void (*loadAll)(bool){};
int (*animIndex)(const char*){};
void (*suspendTimer)(){};
void (*resumeTimer)(){};
bool servicing{};
bool (*canStartMission)(void*){};
std::atomic<bool> theater{};
template<class T>T Read(const void* p,unsigned off=0) {
    T v{};std::memcpy(&v,static_cast<const std::uint8_t*>(p)+off,sizeof(v));return v;
}
void Trace(const char* event,int a=0,int b=0,int c=0) {
    LOGI("[mission.scene] %s %d %d %d",event,a,b,c);
    if(FILE* f=std::fopen("/sdcard/Android/data/com.rockstargames.gtasa/files/vr_mission_scenes.log","a")) {
        std::fprintf(f,"%u %s %d %d %d\n",g.CTimer_m_snTimeInMilliseconds?*g.CTimer_m_snTimeInMilliseconds:0,event,a,b,c);
        std::fclose(f);
    }
}
bool Name(void* s,const char* name,bool missionOnly=true) {
    if(missionOnly && !Read<std::uint8_t>(s,0x12c))return false;
    const auto* n=static_cast<const unsigned char*>(s)+0x10;
    unsigned i=0;for(;name[i];++i)if((n[i]>='A'&&n[i]<='Z'?n[i]+32:n[i])!=name[i])return false;
    return n[i]==0;
}
struct Script {
    void* thread{};std::uint8_t* base{};bool valid{};
    bool Check(void* s,unsigned size,std::uint32_t expected) {
        auto* bytes=s?Read<std::uint8_t*>(s,0x18):nullptr;
        if(s!=thread || bytes!=base) {
            thread=s;base=bytes;valid=false;
            if(base) {
                std::uint32_t hash=2166136261u;
                for(unsigned i=0;i<size;++i)hash=(hash^base[i])*16777619u;
                valid=hash==expected;Trace("BYTECODE",expected,valid);
            }
        }
        return valid;
    }
    int Ip() const {
        if(!valid)return -1;
        const auto current=reinterpret_cast<std::uintptr_t>(Read<void*>(thread,0x20));
        const auto begin=reinterpret_cast<std::uintptr_t>(base);
        return current>=begin && current<begin+42218?static_cast<int>(current-begin):-1;
    }
} mansion,burning;
int lastPhase{},attempts{};
void TraceKingMarker(void* cat) {
    auto* space=static_cast<unsigned char*>(g.CTheScripts_ScriptSpace);
    if(!space || !g.FindPlayerCoors || !g.FindPlayerPed || !canStartMission)return;
    const auto now=g.CTimer_m_snTimeInMilliseconds?*g.CTimer_m_snTimeInMilliseconds:0;
    static std::uint32_t last=0;
    if(!now || (now>=last && now-last<2000))return;
    void* ped=g.FindPlayerPed(-1);if(!ped)return;
    last=now;
    static const unsigned char* checked=nullptr;
    static bool verified=false;
    // ScriptSpace is allocated before the SCM/save is loaded. A failed early
    // fingerprint must not be cached forever at that same address.
    if(checked!=space || !verified) {
        checked=space;std::uint32_t hash=2166136261u;
        for(unsigned i=72537;i<73178;++i)hash=(hash^space[i])*16777619u;
        verified=hash==0x94fb56ebu;
        Trace("KING CODE",static_cast<int>(hash),verified,cat!=nullptr);
    }
    if(!verified)return;
    const auto p=g.FindPlayerCoors(-1);
    const float dx=p.x-Read<float>(space,0x7b4),dy=p.y-Read<float>(space,0x7b8),
                dz=p.z-Read<float>(space,0x7bc);
    if(!std::isfinite(dx)||!std::isfinite(dy)||!std::isfinite(dz)||
       std::abs(dx)>20000 || std::abs(dy)>20000 || std::abs(dz)>20000){
        Trace("KING BAD COORD");return;
    }
    const auto ip=cat?reinterpret_cast<std::uintptr_t>(Read<void*>(cat,0x20)):0;
    const auto base=reinterpret_cast<std::uintptr_t>(space);
    const int offset=ip>=base && ip<base+262245?static_cast<int>(ip-base):-1;
    const bool ready=canStartMission(ped);
    // Repair only the legacy, confirmed Body Harvest debug-save combination:
    // CATCUT has really passed, yet First Date is still zero and CAT's caller
    // stage was left pending. Normal progression never needs this migration.
    // The exact retail CAT bytecode was verified above; never run during a
    // mission or before CAT reaches its native idle loop.
    const int stage=Read<int>(space,0xb38);
    if(ready && offset==72559 && Read<int>(space,0x660)==0 &&
       Read<int>(space,0x1818)==32 && Read<int>(space,0x17f0)==84 &&
       Read<int>(space,0x7a8)==1 && Read<int>(space,0x3778)==1 &&
       Read<int>(space,0xfc)==0 && (stage==1 || stage==2)) {
        const int nextDate=1,finishedStage=2;
        std::memcpy(space+0xfc,&nextDate,sizeof(nextDate));
        std::memcpy(space+0xb38,&finishedStage,sizeof(finishedStage));
        Trace("CATALINA DEBUG REPAIR",stage,0,nextDate);
    }
    Trace("KING FLAGS",Read<int>(space,0x7a8),Read<int>(space,0xb38),Read<int>(space,0x3778));
    Trace("KING DIST CM",static_cast<int>(dx*100),static_cast<int>(dy*100),static_cast<int>(dz*100));
    Trace("KING GATES",ready,g.FindPlayerVehicle&&g.FindPlayerVehicle(-1,false)!=nullptr,offset);
    Trace("KING STORY",Read<int>(space,0x660),Read<int>(space,0xfc));
}
std::uint32_t entered{},lastTrace{};
int WaitPhase(int ip) {
    if(ip>=39436 && ip<39468)return 1;
    if(ip>=39468 && ip<39507)return 2;
    if(ip>=39507 && ip<39544)return 3;
    if(ip>=39544 && ip<39586)return 4;
    if(ip>=39586 && ip<39630)return 5;
    if(ip>=39641 && ip<39676)return 6;
    return 0;
}
void ServiceBurning() {
    const int ip=burning.Ip();
    const bool faded=burning.valid && g.TheCamera && g.CCamera_GetScreenFadeStatus &&
        g.CCamera_GetScreenFadeStatus(g.TheCamera)==2;
    const int phase=faded?WaitPhase(ip):0;
    const auto now=g.CTimer_m_snTimeInMilliseconds?*g.CTimer_m_snTimeInMilliseconds:0;
    if(phase!=lastPhase) {lastPhase=phase;attempts=0;entered=now;lastTrace=now;Trace("BURNING PHASE",phase,ip);}
    if(servicing || !faded || !now || (g.CTimer_m_UserPause && *g.CTimer_m_UserPause) ||
       (g.CTimer_m_CodePause && *g.CTimer_m_CodePause))return;
    if(now-lastTrace<2000)return;
    lastTrace=now;
    Trace("BURNING FADE",phase,ip,g.CStreaming_ms_numModelsRequested?*g.CStreaming_ms_numModelsRequested:-1);
    if(!phase || !g.CStreaming_ms_aInfoForModel)return;
    int models[4]{-1,-1,-1,-1};
    if(phase==1){models[0]=412;models[1]=596;}
    if(phase==2){models[0]=108;models[1]=109;models[2]=110;models[3]=195;}
    if(phase==3){models[0]=346;models[1]=344;models[2]=366;}
    if(phase==4){models[0]=3098;models[1]=3097;models[2]=3099;models[3]=3127;}
    if(phase==5){models[0]=3013;models[1]=3064;models[2]=2950;models[3]=3063;}
    if(phase==6 && animIndex) {const int index=animIndex("BD_FIRE");if(index>=0 && index<180)models[0]=25575+index;}
    // Loading after the script's LOAD_ALL_MODELS_NOW can leave dependencies
    // requested by converted HD clumps queued while the fully opaque fade
    // suppresses RenderScene. Service the native queue at this exact wait only.
    // Never skip the script, force loaded flags, remove models, or force a fade.
    const bool hd=modelsets::Applied(modelsets::PROPER_FIXES) ||
        modelsets::Applied(modelsets::HD_WEAPONS);
    const bool retry=hd && attempts<3 && now-entered>=2000 && loadAll && suspendTimer && resumeTimer && g.CStreaming_RequestModel &&
        (!g.CStreaming_ms_disableStreaming || !*g.CStreaming_ms_disableStreaming);
    bool queued=false;
    for(int id:models) {
        if(id<0)continue;
        auto* info=g.CStreaming_ms_aInfoForModel+id*0x14;
        const int state=Read<std::uint32_t>(info,0x10);
        const auto sectors=Read<std::uint32_t>(info,0xc);
        Trace("BURNING MODEL",id,state,sectors);
        Trace("BURNING SOURCE",id,info[7],Read<std::uint32_t>(info,8));
        // A missing directory entry needs an asset fix, not repeated requests.
        if(retry && sectors && state!=1){g.CStreaming_RequestModel(id,0xc);queued=true;}
    }
    if(queued){
        ++attempts;servicing=true;suspendTimer();loadAll(false);resumeTimer();servicing=false;
        Trace("BURNING SERVICE",phase,attempts);
    }
}
}
void Install(void* h) {
    if(!h)return;
    scripts=reinterpret_cast<void**>(dlsym(h,"_ZN11CTheScripts14pActiveScriptsE"));
    loadAll=reinterpret_cast<decltype(loadAll)>(dlsym(h,"_ZN10CStreaming22LoadAllRequestedModelsEb"));
    animIndex=reinterpret_cast<decltype(animIndex)>(dlsym(h,"_ZN12CAnimManager22GetAnimationBlockIndexEPKc"));
    suspendTimer=reinterpret_cast<decltype(suspendTimer)>(dlsym(h,"_ZN6CTimer7SuspendEv"));
    resumeTimer=reinterpret_cast<decltype(resumeTimer)>(dlsym(h,"_ZN6CTimer6ResumeEv"));
    canStartMission=reinterpret_cast<decltype(canStartMission)>(dlsym(h,"_ZN10CPlayerPed21CanPlayerStartMissionEv"));
    Trace("INSTALLED",scripts!=nullptr,loadAll!=nullptr,animIndex!=nullptr);
    Trace("KING DIAG V2",canStartMission!=nullptr,g.FindPlayerCoors!=nullptr,g.CTheScripts_ScriptSpace!=nullptr);
}
bool Theater(){return theater.load(std::memory_order_relaxed);}
void Update() {
    if(!scripts)return;
    void* m=nullptr;void* b=nullptr;void* cat=nullptr;unsigned count=0;
    for(void* s=*scripts;s && count++<128;) {
        if(Name(s,"strap2"))m=s;
        if(Name(s,"crash1"))b=s;
        if(Name(s,"cat",false))cat=s;
        void* next=Read<void*>(s);if(next==s)break;s=next;
    }
    const bool verified=mansion.Check(m,10840,0x5861cb0cu);
    const bool next=verified && g.TheCamera && Read<std::uint8_t>(g.TheCamera,0x43)!=0;
    if(theater.exchange(next)!=next)Trace("MANSION THEATER",next);
    burning.Check(b,42218,0xfc3eeacfu);
    ServiceBurning();
    TraceKingMarker(cat);
}
}
