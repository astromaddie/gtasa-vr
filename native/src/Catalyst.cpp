// Catalyst (RYDER3), retail Android 2.11.311. Never edits SCM files.
// Keep the stock ring of ten projectiles, catcher, timer and mission cleanup.
// Only bypass its desktop charge input; feed controller source/velocity into
// the existing CREATE_OBJECT_NO_OFFSET and SET_OBJECT_VELOCITY instructions.
#include "Catalyst.h"
#include "Log.h"
#include "PhysicalWeapon.h"
#include "Symbols.h"
#include "VrCamera.h"
#include "Xr.h"
#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <sys/mman.h>
#include <unistd.h>
#include "StoragePaths.h"

namespace savr::catalyst {
namespace {
using V = GameSymbols::Vec3;
using GroupCommand = std::int8_t (*)(void*, int);
GroupCommand originalConditions{}, originalObjects{};
bool installed{};
unsigned pendingFrames{};
void** activeScripts{};
std::uint8_t* locals{};
std::uint8_t* usedObjects{};
void** objectPool{};
void* (*createObject)(int, bool){};
void (*worldAdd)(void*){}, (*worldRemove)(void*){}, (*deleteObject)(void*){};
void (*teleport)(void*, float, float, float, unsigned char){};
void (*createRw)(void*){};
void* (*getVehicle)(int){};
void* script{};
std::uint8_t* base{};
bool verified{}, active{}, pending{}, launching{};
void* held{};
void* heldPool{};
int heldSlot{-1}, heldModel{-1}, lastCaught{-1};
std::uint8_t heldRef{};
detail::Trigger trigger;
V releaseSource{}, releaseVelocity{};
int lastStage{-1}, lastGate{-1};
// Keep transition/error evidence after logcat's short ring buffer wraps.
void Trace(const char* format, ...) {
    char line[384]{};
    va_list args; va_start(args,format);
    std::vsnprintf(line,sizeof(line),format,args); va_end(args);
    LOGI("[catalyst] %s",line);
    if(FILE* f=std::fopen(savr::storage::Files("vr_catalyst.log").c_str(),"a")) {
        const unsigned time=g.CTimer_m_snTimeInMilliseconds?*g.CTimer_m_snTimeInMilliseconds:0;
        std::fprintf(f,"%u %s\n",time,line);std::fclose(f);
    }
}

template<class T> T Read(const void* p, std::size_t off) {
    T v{}; std::memcpy(&v, static_cast<const std::uint8_t*>(p) + off, sizeof(v)); return v;
}
template<class T> void Write(void* p, std::size_t off, T v) {
    std::memcpy(static_cast<std::uint8_t*>(p) + off, &v, sizeof(v));
}
bool Finite(V v) { return std::isfinite(v.x) && std::isfinite(v.y) && std::isfinite(v.z); }
int Local(int i) { return Read<int>(locals, i * 4); }
int Global(int offset) { return Read<int>(g.CTheScripts_ScriptSpace, offset); }
bool NameMatches(void* s) {
    if(!s || Read<std::uint8_t>(s,0x12c)==0) return false;
    // Retail opcode 03A4 lowercases all 8 name bytes before copying them to
    // script+0x10 (ARM64 41dd9c..41de8c). SCM text itself stays uppercase.
    // Match both forms, with a terminator; never match RYDER30 or RYDER3X.
    const auto* name=static_cast<const std::uint8_t*>(s)+0x10;
    constexpr char expected[]="ryder3";
    for(int i=0;i<6;++i) {
        const auto c=name[i]>='A' && name[i]<='Z' ? name[i]+('a'-'A') : name[i];
        if(c!=expected[i])return false;
    }
    return name[6]==0;
}
void ClearArc() { xr::SetThrowableTrajectory(1, nullptr, 0, false); }

bool HeldValid() {
    if (!held || !objectPool || !*objectPool || *objectPool != heldPool || heldSlot < 0)
        return false;
    const int count = Read<int>(heldPool, 0x10);
    auto* refs = Read<std::uint8_t*>(heldPool, 8);
    auto* objects = Read<std::uint8_t*>(heldPool, 0);
    return refs && objects && heldSlot < count && refs[heldSlot] == heldRef &&
        !(heldRef & 0x80) && objects + heldSlot * 0x220 == held;
}
void DeleteHeld() {
    if (HeldValid()) { worldRemove(held); deleteObject(held); }
    held = heldPool = nullptr; heldSlot = heldModel = -1;
}
// Quaternion rotation in controller LOCAL space.
V Rotate(const float q[4], V v) {
    V t{2*(q[1]*v.z-q[2]*v.y), 2*(q[2]*v.x-q[0]*v.z), 2*(q[0]*v.y-q[1]*v.x)};
    return {v.x+q[3]*t.x+q[1]*t.z-q[2]*t.y,
            v.y+q[3]*t.y+q[2]*t.x-q[0]*t.z,
            v.z+q[3]*t.z+q[0]*t.y-q[1]*t.x};
}
bool HandPose(V& source, V& velocity, V basis[3]) {
    xr::HandPose hands[2]{};
    if (!physicalweapon::GetHandPosesSnapshot(hands) || !hands[1].valid || !hands[1].aimValid)
        return false;
    const auto& h = hands[1];
    // Centre ahead of the palm; aim comes from the controller, independent of
    // weapon calibration, inventory and the player's scripted fixed camera.
    V f = Rotate(h.gripOri, {0,0,-1});
    float centre[3]{h.gripPos[0]+f.x*0.24f, h.gripPos[1]+f.y*0.24f, h.gripPos[2]+f.z*0.24f};
    float w[3]{};
    if (!vrcam::TrackingPointToWorld(centre,w)) return false;
    source = {w[0],w[1],w[2]};
    const V axes[3]{{1,0,0},{0,0,-1},{0,1,0}};
    for (int i=0;i<3;++i) {
        V a=Rotate(h.gripOri,axes[i]);
        float end[3]{centre[0]+a.x,centre[1]+a.y,centre[2]+a.z}, ew[3]{};
        if (!vrcam::TrackingPointToWorld(end,ew)) return false;
        basis[i]={ew[0]-w[0],ew[1]-w[1],ew[2]-w[2]};
    }
    V aim=Rotate(h.aimOri,{0,0,-1});
    float end[3]{centre[0]+aim.x,centre[1]+aim.y,centre[2]+aim.z}, ew[3]{};
    if (!vrcam::TrackingPointToWorld(end,ew)) return false;
    V dir{ew[0]-w[0],ew[1]-w[1],ew[2]-w[2]};
    const float len=std::sqrt(dir.x*dir.x+dir.y*dir.y+dir.z*dir.z);
    if (!Finite(source) || !std::isfinite(len) || len<0.1f) return false;
    void* train=getVehicle(Local(171));
    if (!train) return false;
    V carry=Read<V>(train,0x68);
    if (!Finite(carry)) return false;
    // Same 0.46 units/tick as grenades; inherit the moving train, as SCM does.
    velocity={dir.x/len*0.46f+carry.x,dir.y/len*0.46f+carry.y,dir.z/len*0.46f+carry.z};
    return Finite(velocity);
}
bool ShowHeld(V source, const V basis[3]) {
    const int index=Local(135);
    if (index!=-153 && index!=-137) return false;
    const int model=Read<int>(usedObjects,(-index)*28+24);
    if (model<=0 || model>=20000 || !g.CModelInfo_ms_modelInfoPtrs ||
        !g.CModelInfo_ms_modelInfoPtrs[model]) return false;
    if (!HeldValid() || model!=heldModel) {
        DeleteHeld();
        Write<std::uint8_t>(g.CModelInfo_ms_modelInfoPtrs[model],0x26,255);
        held=createObject(model,false);
        if (!held) return false;
        heldPool=*objectPool;
        auto* objects=Read<std::uint8_t*>(heldPool,0);
        auto* refs=Read<std::uint8_t*>(heldPool,8);
        const auto delta=reinterpret_cast<std::uintptr_t>(held)-reinterpret_cast<std::uintptr_t>(objects);
        if (delta%0x220 || delta/0x220>=static_cast<unsigned>(Read<int>(heldPool,0x10))) {
            deleteObject(held); held=nullptr; return false;
        }
        heldSlot=static_cast<int>(delta/0x220); heldRef=refs[heldSlot]; heldModel=model;
        Write<std::uint8_t>(held,0x1a0,6); // mission-owned; explicitly removed on every exit
        Write<std::uint64_t>(held,0x28,Read<std::uint64_t>(held,0x28)&~std::uint64_t{1});
        g.CObject_SetIsStatic(held,true);
        worldAdd(held);
        if (!Read<void*>(held,0x20)) createRw(held);
        Trace("AUTO BOX model=%d slot=%d",model,heldSlot);
    }
    Write<V>(held,0x68,{}); Write<V>(held,0x74,{});
    // Teleport allocates/synchronises the native matrix and updates world sectors.
    teleport(held,source.x,source.y,source.z,0);
    if (void* m=Read<void*>(held,0x18)) {
        for (int i=0;i<3;++i) Write<V>(m,i*16,basis[i]);
        teleport(held,source.x,source.y,source.z,0);
    }
    return HeldValid();
}
void Preview(V source, V velocity) {
    float points[41][3]{};
    V previous=source, p=source;
    void* train=getVehicle(Local(171));
    const V carry=train?Read<V>(train,0x68):V{};
    float elapsed=0.0f;
    // Crates have their own drag, unlike grenade projectiles. Reproduce the
    // native gravity -> drag -> integration order (ApplyAirResistance @4a2680,
    // CPhysical::m_fAirResistance +0xbc) using this frame's game timestep.
    const float drag=HeldValid()?Read<float>(held,0xbc):0.0f;
    const float frameStep=g.CTimer_ms_fTimeStep && std::isfinite(*g.CTimer_ms_fTimeStep)
        ? std::clamp(*g.CTimer_ms_fTimeStep,0.1f,2.0f) : 1.0f;
    bool hit=false;
    int count=0;
    void* saved=g.CWorld_pIgnoreEntity?*g.CWorld_pIgnoreEntity:nullptr;
    // The train moves with the viewer; its current static collision hull is
    // not a future obstacle. Exclude it and peds from the terrain/prop preview.
    if(g.CWorld_pIgnoreEntity) *g.CWorld_pIgnoreEntity=train;
    for(int i=0;i<41;++i) {
        if(i) for(float remaining=2.0f;remaining>0.0001f;) {
            const float dt=std::min(remaining,frameStep);
            velocity.z-=0.008f*dt;
            float factor=1.0f;
            if(std::isfinite(drag) && drag>=0.0f && drag<=1.0f) {
                const float speed=std::sqrt(velocity.x*velocity.x+velocity.y*velocity.y+velocity.z*velocity.z);
                factor=std::pow(drag>0.1f?drag:std::max(0.0f,1.0f-speed*drag),dt);
            }
            velocity.x*=factor;velocity.y*=factor;velocity.z*=factor;
            p.x+=velocity.x*dt;p.y+=velocity.y*dt;p.z+=velocity.z*dt;
            elapsed+=dt;remaining-=dt;
        }
        if(i && g.CWorld_ProcessLineOfSight) {
            alignas(4) std::uint8_t col[0x2c]{}; void* entity{};
            hit=g.CWorld_ProcessLineOfSight(&previous,&p,col,&entity,true,true,false,true,true,false,false,false);
            if(hit) std::memcpy(&p,col,sizeof(p));
        }
        // Native crates inherit train speed. Plot relative to the future train
        // position, otherwise a backwards throw appears to collapse underfoot
        // as its world speed cancels the train's forward speed.
        const float world[3]{p.x-carry.x*elapsed,p.y-carry.y*elapsed,p.z-carry.z*elapsed};
        if(!vrcam::WorldPointToTracking(world,points[count])) {count=0;break;}
        ++count;previous=p;if(hit)break;
    }
    if(g.CWorld_pIgnoreEntity)*g.CWorld_pIgnoreEntity=saved;
    xr::SetThrowableTrajectory(1,points,count,hit);
}

// Process() in retail ARM64 inlines opcode fetch and group dispatch; it does
// NOT call the exported ProcessOneCommand(). At group entry IP is already
// past the two-byte opcode. Hook the actual handlers used by both dispatchers.
bool At(void* s, int opcode, int expectedOpcode, std::size_t offset) {
    return s==script && verified && base && opcode==expectedOpcode &&
        Local(97)==10 && Global(0x80b8)<10 &&
        Read<std::uint8_t*>(s,0x20)==base+offset+2;
}
std::int8_t OnConditions(void* s, int opcode) {
    if(At(s,opcode,0x00d6,detail::kInput)) {
        const bool release=active && pending;
        // Return to the dispatch loop with the next OPCODE address. Calling
        // the original IF handler here would parse that opcode as an operand.
        Write(s,0x20,base+detail::Route(detail::kInput,release));
        Write<int>(locals,172*4,0);
        Write<int>(g.CTheScripts_ScriptSpace,0x80c4,release ? 46 : 0);
        launching=release;pending=false;pendingFrames=0;
        if(release) {DeleteHeld();Trace("CONSUMED release index=%d",Local(117));}
        return 0;
    }
    if(launching && At(s,opcode,0x00d6,detail::kSource)) {
        // Camera query has completed. The original IF still parses its operand.
        Write<V>(locals,52*4,releaseSource);
    }
    return originalConditions(s,opcode);
}
std::int8_t OnObjects(void* s, int opcode) {
    const bool release=launching && At(s,opcode,0x0381,detail::kVelocity);
    if(release) {
        // Opcode 0381 divides SCM metres/sec by 50 (retail @41cb54).
        Write<V>(locals,55*4,{releaseVelocity.x*50,releaseVelocity.y*50,releaseVelocity.z*50});
    }
    const auto result=originalObjects(s,opcode);
    if(release) {
        Trace("NATIVE RELEASE index=%d src=(%.2f %.2f %.2f) vel=(%.3f %.3f %.3f) result=%d",
            Local(117),releaseSource.x,releaseSource.y,releaseSource.z,
            releaseVelocity.x,releaseVelocity.y,releaseVelocity.z,int(result));
        launching=false;
    }
    return result;
}
constexpr std::uint32_t conditionsPrologue[]{0xd102c3ff,0xfd0023ec,0x6d04abeb,0x6d05a3e9};
constexpr std::uint32_t objectsPrologue[]{0xd107c3ff,0x6d172beb,0x6d1823e9,0xa9197bfd};
bool Matches(void* target,const std::uint32_t expected[4]) {
    return target && std::memcmp(target,expected,16)==0;
}
void* PrepareHook(void* target) {
    // Both version-checked prologues contain only stack operations; no
    // PC-relative relocation. Prepare BOTH trampolines before patching either.
    const long size=sysconf(_SC_PAGESIZE);if(size<=0)return nullptr;
    auto* t=static_cast<std::uint32_t*>(mmap(nullptr,size,PROT_READ|PROT_WRITE|PROT_EXEC,MAP_PRIVATE|MAP_ANONYMOUS,-1,0));
    if(t==MAP_FAILED)return nullptr;
    std::memcpy(t,target,16);
    t[4]=0x58000051;t[5]=0xd61f0220;
    Write(t,24,reinterpret_cast<std::uintptr_t>(target)+16);
    __builtin___clear_cache(reinterpret_cast<char*>(t),reinterpret_cast<char*>(t)+32);
    const auto start=reinterpret_cast<std::uintptr_t>(target)&~(static_cast<std::uintptr_t>(size)-1);
    const auto end=(reinterpret_cast<std::uintptr_t>(target)+16+size-1)&~(static_cast<std::uintptr_t>(size)-1);
    if(mprotect(reinterpret_cast<void*>(start),end-start,PROT_READ|PROT_WRITE|PROT_EXEC)) {munmap(t,size);return nullptr;}
    return t;
}
void PatchHook(void* target,GroupCommand callback) {
    const std::uint32_t jump[]{0x58000051,0xd61f0220};
    std::memcpy(target,jump,8);Write(target,8,callback);
    __builtin___clear_cache(static_cast<char*>(target),static_cast<char*>(target)+16);
}
bool HookGroups(void* conditions,void* objects) {
    if(!Matches(conditions,conditionsPrologue) || !Matches(objects,objectsPrologue)) {
        Trace("DISABLED command group prologue mismatch");return false;
    }
    void* c=PrepareHook(conditions);if(!c)return false;
    void* o=PrepareHook(objects);
    if(!o){munmap(c,sysconf(_SC_PAGESIZE));return false;}
    originalConditions=reinterpret_cast<GroupCommand>(c);
    originalObjects=reinterpret_cast<GroupCommand>(o);
    PatchHook(conditions,OnConditions);PatchHook(objects,OnObjects);
    return true;
}
}

bool Install(void* h) {
    if(installed)return true;
    if(!h)return false;
#define RESOLVE(var,sym) var=reinterpret_cast<decltype(var)>(dlsym(h,sym))
    RESOLVE(activeScripts,"_ZN11CTheScripts14pActiveScriptsE");
    RESOLVE(locals,"_ZN11CTheScripts31LocalVariablesForCurrentMissionE");
    RESOLVE(usedObjects,"_ZN11CTheScripts15UsedObjectArrayE");
    RESOLVE(objectPool,"_ZN6CPools14ms_pObjectPoolE");
    RESOLVE(createObject,"_ZN7CObject6CreateEib");
    RESOLVE(worldAdd,"_ZN6CWorld3AddEP7CEntity");
    RESOLVE(worldRemove,"_ZN6CWorld6RemoveEP7CEntity");
    RESOLVE(deleteObject,"_ZN7CObjectD0Ev");
    RESOLVE(teleport,"_ZN7CObject8TeleportE7CVectorh");
    RESOLVE(createRw,"_ZN7CObject14CreateRwObjectEv");
    RESOLVE(getVehicle,"_ZN6CPools10GetVehicleEi");
#undef RESOLVE
    const bool required[]{activeScripts!=nullptr,locals!=nullptr,usedObjects!=nullptr,objectPool!=nullptr,
        createObject!=nullptr,worldAdd!=nullptr,worldRemove!=nullptr,deleteObject!=nullptr,
        teleport!=nullptr,createRw!=nullptr,getVehicle!=nullptr,g.CTheScripts_ScriptSpace!=nullptr,
        g.CObject_SetIsStatic!=nullptr,g.FindPlayerPed!=nullptr};
    unsigned missing=0;
    for(unsigned i=0;i<sizeof(required)/sizeof(required[0]);++i) if(!required[i])missing|=1u<<i;
    if(missing){Trace("DISABLED required symbols missingMask=%04x",missing);return false;}
    installed=HookGroups(dlsym(h,"_ZN14CRunningScript23ProcessCommands200To299Ei"),
        dlsym(h,"_ZN14CRunningScript23ProcessCommands800To899Ei"));
    Trace("controller crate bridge r3 command groups installed=%d",installed);
    return installed;
}
bool Active() { return active; }
void Reset() {
    if(active || held) {DeleteHeld();ClearArc();Trace("END");}
    active=pending=launching=verified=false;script=nullptr;base=nullptr;
    pendingFrames=0;trigger={};lastCaught=-1;lastStage=-1;lastGate=-1;
}
void Update(bool blocked) {
    if(!installed)return;
    void* found=nullptr;
    int visited=0;
    for(void* s=*activeScripts, *next=nullptr; s && visited++<128; s=next) {
        next=Read<void*>(s,0);
        if(NameMatches(s)){found=s;break;}
        if(next==s)break;
    }
    if(!found){Reset();return;}
    auto* candidate=Read<std::uint8_t*>(found,0x18);
    if(found!=script || candidate!=base) {
        Reset();script=found;base=candidate;
        const auto hash=base?detail::Hash(base,detail::kScriptSize):0;
        verified=base && hash==detail::kScriptHash;
        Trace("RYDER3 name=%.8s bytecode verified=%d hash=%08x expected=%08x",
            static_cast<const char*>(found)+0x10,verified,hash,detail::kScriptHash);
    }
    if(verified && Local(97)!=lastStage) {
        lastStage=Local(97);
        Trace("STAGE %d caught=%d time=%d",lastStage,Global(0x80b8),Global(0x80c0));
    }
    const bool stage=verified && Local(97)==10 && Global(0x80b8)<10 &&
        Global(0x80c0)>0 && g.FindPlayerPed(-1);
    if(!stage) {
        if(active){DeleteHeld();ClearArc();Trace("throwing stage ended");}
        active=pending=launching=false;pendingFrames=0;trigger={};return;
    }
    if(!active) {
        active=true;physicalweapon::ResetTransient();trigger={};
        Trace("BEGIN right trigger: hold aim / release throw");
    }
    const int caught=Global(0x80b8);
    if(caught!=lastCaught){Trace("CAUGHT %d/10",caught);lastCaught=caught;}
    xr::InputState input{};xr::GetInput(input);
    V source{},velocity{},basis[3]{};
    const bool pose=HandPose(source,velocity,basis);
    const int gate=(blocked?1:0) | (input.menu?2:0) |
        ((input.grip[0]>=0.75f && input.grip[1]>=0.75f)?4:0) |
        ((g.CTimer_m_UserPause && *g.CTimer_m_UserPause)?8:0) |
        ((g.CTimer_m_CodePause && *g.CTimer_m_CodePause)?16:0) | (!pose?32:0);
    if(gate!=lastGate){Trace("INPUT gate=%d (0=ready,32=pose/train unavailable)",gate);lastGate=gate;}
    const bool usable=gate==0;
    if(!usable) {trigger.Update(0,false);pending=launching=false;pendingFrames=0;DeleteHeld();ClearArc();return;}
    if(pending && ++pendingFrames>=90) {
        Trace("CANCEL unconsumed release after %u frames",pendingFrames);
        pending=launching=false;pendingFrames=0;trigger={};
    }
    const bool box=ShowHeld(source,basis);
    const bool released=trigger.Update(input.triggers[1],box && !pending);
    if(released) {releaseSource=source;releaseVelocity=velocity;pending=true;pendingFrames=0;Trace("QUEUED release index=%d",Local(117));ClearArc();}
    else if(trigger.armed && trigger.down) Preview(source,velocity);
    else ClearArc();
}
}
