#include "Swimming.h"
#include "SwimMotion.h"
#include "Locomotion.h"
#include "Log.h"
#include "MissionControls.h"
#include "Symbols.h"
#include "VrCamera.h"
#include "Xr.h"

#include <chrono>
#include <cstdint>
#include <cstring>
#include <dlfcn.h>
#include <sys/mman.h>
#include <unistd.h>

namespace savr::swimming {
namespace {
using motion::Vec;
using TaskFn=void (*)(void*,void*);
using WaterFn=bool (*)(float,float,float,float*,bool,Vec*);
TaskFn g_control{},g_resistance{};
WaterFn g_water{};
float (*g_maxBreath)(int){};
void (*g_setOrientation)(void*,float,float,float){};
bool g_installed{},g_enabled{},g_underwater{};
void* g_ped{};
void* g_controlTask{};
motion::Strokes g_strokes;
Vec g_impulse{},g_direction{};
float g_support{},g_vertical{};
double g_sampleTime{};

template<class T> T Read(const void* p,int offset) {
    T out{}; std::memcpy(&out,static_cast<const char*>(p)+offset,sizeof(out)); return out;
}
template<class T> void Write(void* p,int offset,T value) {
    std::memcpy(static_cast<char*>(p)+offset,&value,sizeof(value));
}
double Now() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
void Reset() {
    g_strokes.Reset(); g_impulse={}; g_support=g_vertical=0;
    g_sampleTime=0; g_underwater=false; g_ped=nullptr; g_controlTask=nullptr; g_enabled=false;
}
bool Water(void* ped,Vec& pos,float& level) {
    if (!ped||!g_water) return false;
    void* matrix=Read<void*>(ped,0x18);
    pos=matrix ? Read<Vec>(matrix,0x30) : Read<Vec>(ped,0x8);
    return motion::Finite(pos)&&g_water(pos.x,pos.y,pos.z,&level,true,nullptr)&&std::isfinite(level);
}
bool Controlled(void* ped) {
    return g_installed&&g_enabled&&ped==g_ped&&locomotion::GestureSwimEnabled()&&
           Now()-g_sampleTime<0.15;
}
bool Blended(void* task) {
    // ARM64 2.11.311: ProcessControlInput's original animation readiness gate.
    return Read<std::uint8_t>(task,0x10)==1&&(Read<std::uint8_t>(task,0x11)&1);
}
void UpdateDepth(void* task,void* ped,const Vec& pos,float level) {
    float eye[3]{},direction[3]{};
    // Camera height is normally ped+0.72. Use the actual tracked eye where
    // available so physically lowering the head consumes air at the waterline.
    float headZ=pos.z+0.72f;
    if (vrcam::GetHeadWorldRay(eye,direction)&&std::abs(eye[2]-pos.z)<1.6f)
        headZ=eye[2];
    const float mouth=headZ-0.10f;
    if (mouth<level-0.025f) g_underwater=true;
    else if (mouth>level+0.025f) g_underwater=false;
    const std::uint16_t state=g_underwater?4:(g_support>0.18f?1:0);
    Write(task,0x12,state);
    // Remove native automatic nose-up/surface attraction. Animations and the
    // retail ProcessPed breath/drowning call still run normally after control.
    Write(task,0x40,0.0f);
    Write(task,0x30,g_underwater?std::asin(std::clamp(g_direction.z,-0.98f,0.98f)):0.0f);
}
void OnControl(void* task,void* ped) {
    if (Controlled(ped)&&Blended(task)&&g_setOrientation&&
        missioncontrols::TouchDoubleTapped(168)) {
        Vec pos{}; float level{};
        // Native climb probes use CJ's matrix forward, not the tracked gaze.
        // Keep the real launch/climb task and its collision checks, but face
        // the visible ledge/boat before it tests for a handhold.
        if (Water(ped,pos,level)&&level-pos.z<=0.90f&&
            g_direction.x*g_direction.x+g_direction.y*g_direction.y>0.01f&&
            Read<std::uint16_t>(task,0x12)!=5) {
            const float yaw=std::atan2(-g_direction.x,g_direction.y);
            g_setOrientation(ped,0.0f,0.0f,yaw);
            // Current/aim rotation, verified in retail ProcessControlInput.
            Write(ped,0x6c4,yaw); Write(ped,0x6c8,yaw);
            // Waves/physical head height can put the eyes just underwater at
            // a reachable ledge. Allow the stock jump test there, not at depth.
            Write(task,0x12,std::uint16_t{0});
        }
    }
    g_control(task,ped);
    if (!Controlled(ped)||!Blended(task)||Read<std::uint16_t>(task,0x12)==5) return;
    Vec pos{}; float level{};
    if (Water(ped,pos,level)) {
        g_controlTask=task;
        UpdateDepth(task,ped,pos,level);
    }
}
void OnResistance(void* task,void* ped) {
    const Vec before=Read<Vec>(ped,0x68);
    const bool active=Controlled(ped)&&g_controlTask==task&&Blended(task)&&
                      Read<std::uint16_t>(task,0x12)!=5;
    if (ped==g_ped) g_controlTask=nullptr;
    g_resistance(task,ped); // retain retail state transitions and world-depth floor
    if (!active) { if (ped==g_ped) { g_impulse={}; g_vertical=0; } return; }
    Vec pos{}; float level{};
    if (!Water(ped,pos,level)) { g_impulse={}; return; }
    const float dt=g.CTimer_ms_fTimeStep?*g.CTimer_ms_fTimeStep/50.0f:0;
    if (!(dt>0&&dt<=0.1f)||!motion::Finite(before)) { g_impulse={}; return; }
    Vec velocity=motion::Advance(before*50.0f,g_impulse,g_vertical,
                                  motion::SupportForGaze(g_support,g_direction.z),dt,
                                  level-0.55f-pos.z,pos.z<=-69.0f);
    g_impulse={};
    Write(ped,0x68,velocity*(1.0f/50.0f));
    // ProcessSwimAnims may initialise underwater pitch on entry; reapply the
    // measured depth after the stock resistance's automatic surfacing branch.
    UpdateDepth(task,ped,pos,level);
}

// Both prologues are checked before enabling physical swimming. These first
// four instructions only allocate/save registers (no PC-relative operands).
bool Hook(void* target,const std::uint32_t (&expected)[4],TaskFn hook,TaskFn& original) {
    if (!target||std::memcmp(target,expected,16)) return false;
    const long size=sysconf(_SC_PAGESIZE);
    if (size<=0) return false;
    void* trampoline=mmap(nullptr,size,PROT_READ|PROT_WRITE|PROT_EXEC,
                          MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if (trampoline==MAP_FAILED) return false;
    auto* t=static_cast<std::uint32_t*>(trampoline);
    std::memcpy(t,target,16); t[4]=0x58000051; t[5]=0xd61f0220;
    const auto resume=reinterpret_cast<std::uintptr_t>(target)+16;
    std::memcpy(t+6,&resume,sizeof(resume));
    __builtin___clear_cache(static_cast<char*>(trampoline),static_cast<char*>(trampoline)+32);
    const auto address=reinterpret_cast<std::uintptr_t>(target);
    const auto start=address&~(static_cast<std::uintptr_t>(size)-1);
    const auto end=(address+16+size-1)&~(static_cast<std::uintptr_t>(size)-1);
    if (mprotect(reinterpret_cast<void*>(start),end-start,PROT_READ|PROT_WRITE|PROT_EXEC)) {
        munmap(trampoline,size); return false;
    }
    original=reinterpret_cast<TaskFn>(trampoline);
    auto* code=static_cast<std::uint32_t*>(target);
    std::memcpy(code+2,&hook,sizeof(hook)); code[1]=0xd61f0220;
    __atomic_store_n(code,0x58000051u,__ATOMIC_RELEASE);
    __builtin___clear_cache(static_cast<char*>(target),static_cast<char*>(target)+16);
    return true;
}
} // namespace

void Install(void* handle) {
    if (!handle||g_installed) return;
    g_water=reinterpret_cast<WaterFn>(dlsym(handle,"_ZN11CWaterLevel13GetWaterLevelEfffPfbP7CVector"));
    g_maxBreath=reinterpret_cast<float (*)(int)>(dlsym(handle,"_ZN6CStats23GetFatAndMuscleModifierE17eStatModAbilities"));
    g_setOrientation=reinterpret_cast<void (*)(void*,float,float,float)>(
        dlsym(handle,"_ZN10CPlaceable14SetOrientationEfff"));
    void* control=dlsym(handle,"_ZN15CTaskSimpleSwim19ProcessControlInputEP10CPlayerPed");
    void* resistance=dlsym(handle,"_ZN15CTaskSimpleSwim25ProcessSwimmingResistanceEP4CPed");
    constexpr std::uint32_t cp[]={0xd10283ff,0xfd0013ee,0x6d0333ed,0x6d042beb};
    constexpr std::uint32_t rp[]={0xd10303ff,0xfd0033ec,0x6d06abeb,0x6d07a3e9};
    if (g_water&&g_maxBreath&&control&&resistance&&
        !std::memcmp(control,cp,16)&&!std::memcmp(resistance,rp,16))
        g_installed=Hook(control,cp,OnControl,g_control)&&Hook(resistance,rp,OnResistance,g_resistance);
    if (!g_installed) LOGE("[swim] physical swimming hooks unavailable; retaining retail swimming");
}

void UpdateInput(bool enabled) {
    g_controlTask=nullptr;
    void* ped=enabled&&g.FindPlayerPed?g.FindPlayerPed(-1):nullptr;
    void* pad=g.CPad_GetPad?g.CPad_GetPad(0):nullptr;
    const bool swimming=ped&&missioncontrols::IsSwimming();
    // Breath display also works with the physical swimming toggle disabled.
    void* data=swimming?Read<void*>(ped,0x540):nullptr;
    const float maximum=data&&g_maxBreath?g_maxBreath(8):0;
    xr::PublishBreath(data&&maximum>0?Read<float>(data,0x58)/maximum:-1.0f);
    if (!swimming||!g_installed||!locomotion::GestureSwimEnabled()||
        !pad||Read<std::uint16_t>(pad,0x110)) { Reset(); return; }
    if (ped!=g_ped) Reset();
    g_ped=ped;
    const double now=Now();
    const float dt=g_sampleTime>0?static_cast<float>(now-g_sampleTime):0;
    g_sampleTime=now;
    float head[3]{},q[4]{},eye[3]{},dir[3]{};
    if (!xr::GetHeadPose(head,q)||!vrcam::GetHeadWorldRay(eye,dir)) { Reset(); return; }
    g_enabled=true; g_direction=motion::Unit({dir[0],dir[1],dir[2]});
    // Rotate OpenXR -Z by the head quaternion; use horizontal heading only
    // for recognising a pull. Pitch affects the resulting world-space thrust.
    const Vec forward{-2*(q[0]*q[2]+q[3]*q[1]),
                      -2*(q[1]*q[2]-q[3]*q[0]),
                      -(1-2*(q[0]*q[0]+q[1]*q[1]))};
    xr::HandPose hands[2]{}; xr::GetHandPoses(hands);
    Vec relative[2]{}; bool valid[2]{};
    for (int i=0;i<2;++i) {
        relative[i]={hands[i].gripPos[0]-head[0],hands[i].gripPos[1]-head[1],hands[i].gripPos[2]-head[2]};
        valid[i]=hands[i].valid;
    }
    const auto effort=g_strokes.Update(relative,valid,forward,dt);
    if (dt>0&&dt<=0.1f) {
        g_support+=(effort.support-g_support)*(1-std::exp(-dt/0.22f));
        g_impulse=g_impulse+g_direction*effort.impulse;
    } else { g_support=0; g_impulse={}; }
}
} // namespace savr::swimming
