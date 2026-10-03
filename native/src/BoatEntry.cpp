#include "BoatEntry.h"
#include "Symbols.h"
#include "VrCamera.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <initializer_list>
#include "StoragePaths.h"

namespace savr::boatentry {
namespace {
using Vec=GameSymbols::Vec3;
void (*g_seatCtor)(void*,void*,void*){};
bool (*g_seatProcess)(void*,void*){};
void (*g_seatDtor)(void*){};
void* (*g_taskAlloc)(std::size_t){};
void (*g_driveCtor)(void*,void*){};
void (*g_driveDelete)(void*){};
void (*g_setTask)(void*,void*,int,bool){};
bool (*g_vehicleHealthy)(void*){};
bool (*g_pedHealthy)(void*){};
bool (*g_canOpenLocks)(void*,void*){};

template<class T> T Read(const void* p,int offset) {
    T value{}; std::memcpy(&value,static_cast<const char*>(p)+offset,sizeof(value)); return value;
}
bool Finite(Vec v) { return std::isfinite(v.x)&&std::isfinite(v.y)&&std::isfinite(v.z); }
Vec Position(void* entity) {
    void* matrix=Read<void*>(entity,0x18);
    return matrix?Read<Vec>(matrix,0x30):Read<Vec>(entity,0x8);
}
float DistanceSquared(Vec a,Vec b) {
    return (a.x-b.x)*(a.x-b.x)+(a.y-b.y)*(a.y-b.y)+(a.z-b.z)*(a.z-b.z);
}
void Report(const char* result,void* boat,float distance) {
    // One bounded record per explicit boarding attempt, also in player builds.
    // A failed headset test then identifies target/gate/native-result failures.
    static const char* const path=savr::storage::FilesPath("vr_boat_entry.log");
    if (FILE* f=std::fopen(path,"a+")) {
        std::fseek(f,0,SEEK_END);
        if (std::ftell(f)>32768) {
            std::fclose(f); f=std::fopen(path,"w");
            if (!f) return;
        }
        const double seconds=std::chrono::duration<double>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        std::fprintf(f,"%.3f boat-entry-v2 %s model=%d distance=%.2f\n",seconds,result,
                     boat?int(Read<std::uint16_t>(boat,0x32)):-1,distance);
        std::fclose(f);
    }
}

// A small ray fan covers hull/deck height from water or a bank. A boat must
// itself be the first collision: no selecting a hull behind a wall or pier.
void* FindReachableBoat(void* ped,Vec eye,Vec gaze,float& distance) {
    const Vec pedPos=Position(ped);
    if (!Finite(pedPos)||!Finite(eye)||!Finite(gaze)||DistanceSquared(eye,pedPos)>6.25f)
        return nullptr;
    void* closest=nullptr;
    float best=2.5f*2.5f;
    const auto probe=[&](Vec direction) {
        const float length=std::sqrt(DistanceSquared(direction,{}));
        if (!(length>0.01f)) return;
        const Vec end{eye.x+direction.x*2.5f/length,
                      eye.y+direction.y*2.5f/length,
                      eye.z+direction.z*2.5f/length};
        alignas(8) std::uint8_t col[0x2c]{};
        void* hit=nullptr;
        if (!g.CWorld_ProcessLineOfSight(&eye,&end,col,&hit,
                true,true,false,true,true,false,false,false)||!hit) return;
        if ((Read<std::uint8_t>(hit,0x5a)&7)!=2) return;
        // Vortex is the second craft in the boat cheat menu, but its retail
        // class is CAutomobile. Do not broaden this to other automobiles.
        if (g.CVehicle_GetVehicleAppearance(hit)!=4&&
            Read<std::uint16_t>(hit,0x32)!=539) return;
        const Vec point=Read<Vec>(col,0);
        if (!Finite(point)||std::abs(point.z-pedPos.z)>1.6f) return;
        const float d=DistanceSquared(eye,point);
        if (d<best) { closest=hit; best=d; }
    };
    probe(gaze);
    probe({0,0,-1}); // already on a deck, looking towards its helm
    float horizontal=std::hypot(gaze.x,gaze.y);
    if (horizontal<0.1f) {
        if (void* matrix=Read<void*>(ped,0x18)) gaze=Read<Vec>(matrix,0x10);
        horizontal=std::hypot(gaze.x,gaze.y);
    }
    if (horizontal>=0.1f) {
        const float x=gaze.x/horizontal,y=gaze.y/horizontal;
        for (const float yaw:{-0.35f,0.0f,0.35f}) {
            const float dx=x*std::cos(yaw)-y*std::sin(yaw);
            const float dy=x*std::sin(yaw)+y*std::cos(yaw);
            for (const float pitch:{-1.05f,-0.52f,0.0f,0.35f})
                probe({dx*std::cos(pitch),dy*std::cos(pitch),std::sin(pitch)});
        }
    }
    distance=std::sqrt(best);
    return closest;
}
} // namespace

void Install(void* handle) {
    if (!handle) return;
    // Use the native seating task but not SetPedInCarDirect: its driver branch
    // always assigns CarDriveWander, which takes over the helm with AI inputs.
    g_seatCtor=reinterpret_cast<void (*)(void*,void*,void*)>(dlsym(handle,
        "_ZN30CTaskSimpleCarSetPedInAsDriverC1EP8CVehicleP28CTaskUtilityLineUpPedWithCar"));
    g_seatProcess=reinterpret_cast<bool (*)(void*,void*)>(dlsym(handle,
        "_ZN30CTaskSimpleCarSetPedInAsDriver10ProcessPedEP4CPed"));
    g_seatDtor=reinterpret_cast<void (*)(void*)>(dlsym(handle,
        "_ZN30CTaskSimpleCarSetPedInAsDriverD1Ev"));
    g_taskAlloc=reinterpret_cast<void* (*)(std::size_t)>(dlsym(handle,"_ZN5CTasknwEm"));
    g_driveCtor=reinterpret_cast<void (*)(void*,void*)>(dlsym(handle,
        "_ZN20CTaskComplexCarDriveC1EP8CVehicle"));
    g_driveDelete=reinterpret_cast<void (*)(void*)>(dlsym(handle,
        "_ZN20CTaskComplexCarDriveD0Ev"));
    g_setTask=reinterpret_cast<void (*)(void*,void*,int,bool)>(dlsym(handle,
        "_ZN12CTaskManager7SetTaskEP5CTaskib"));
    g_vehicleHealthy=reinterpret_cast<bool (*)(void*)>(
        dlsym(handle,"_ZN13CCarEnterExit16IsVehicleHealthyERK8CVehicle"));
    g_pedHealthy=reinterpret_cast<bool (*)(void*)>(
        dlsym(handle,"_ZN13CCarEnterExit12IsPedHealthyERK4CPed"));
    g_canOpenLocks=reinterpret_cast<bool (*)(void*,void*)>(
        dlsym(handle,"_ZNK8CVehicle15CanPedOpenLocksEPK4CPed"));
}

bool TryEnter() {
    if (!g_seatCtor||!g_seatProcess||!g_seatDtor||!g_taskAlloc||
        !g_driveCtor||!g_driveDelete||!g_setTask||
        !g_vehicleHealthy||!g_pedHealthy||!g_canOpenLocks||
        !g.CWorld_ProcessLineOfSight||!g.CVehicle_GetVehicleAppearance||
        !g.FindPlayerPed||!g.FindPlayerVehicle||!g.CPad_GetPad) {
        Report("missing-symbol",nullptr,0); return false;
    }
    void* ped=g.FindPlayerPed(-1);
    void* pad=g.CPad_GetPad(0);
    if (!ped||!pad||g.FindPlayerVehicle(-1,false)) return false;
    if (Read<std::uint16_t>(pad,0x110)||Read<std::uint8_t>(pad,0x12d)) {
        Report("controls-disabled",nullptr,0); return false;
    }
    if (!g_pedHealthy(ped)) { Report("ped-unhealthy",nullptr,0); return false; }
    float origin[3]{},forward[3]{};
    if (!vrcam::GetHeadWorldRay(origin,forward)) {
        Report("no-head-pose",nullptr,0); return false;
    }
    float distance{};
    void* boat=FindReachableBoat(ped,{origin[0],origin[1],origin[2]},
                                    {forward[0],forward[1],forward[2]},distance);
    if (!boat) { Report("no-reachable-hull",nullptr,0); return false; }
    // CVehicle::m_pDriver +0x5a0, also verified by TrafficCensus. The native
    // direct-seat helper must not displace an occupant or bypass mission locks.
    if (Read<void*>(boat,0x5a0)) { Report("occupied",boat,distance); return true; }
    if (!g_vehicleHealthy(boat)) { Report("damaged",boat,distance); return true; }
    if (!g_canOpenLocks(boat,ped)) { Report("locked",boat,distance); return true; }
    // Layouts verified in retail ARM64: seat task 0x38 bytes / warp byte +0x30,
    // CarDrive 0x38 bytes, ped intelligence +0x538, task manager +0x8.
    void* intelligence=Read<void*>(ped,0x538);
    if (!intelligence) { Report("no-intelligence",boat,distance); return true; }
    void* drive=g_taskAlloc(0x38);
    if (!drive) { Report("task-pool-full",boat,distance); return true; }
    g_driveCtor(drive,boat);
    alignas(16) std::uint8_t seat[0x38]{};
    g_seatCtor(seat,boat,nullptr);
    seat[0x30]=1;
    g_seatProcess(seat,ped);
    g_seatDtor(seat);
    const bool seated=g.FindPlayerVehicle(-1,false)==boat;
    if (seated) g_setTask(static_cast<char*>(intelligence)+0x8,drive,3,false);
    else g_driveDelete(drive);
    Report(seated?"seated-player-control":"native-seat-failed",boat,distance);
    return true;
}
} // namespace savr::boatentry
