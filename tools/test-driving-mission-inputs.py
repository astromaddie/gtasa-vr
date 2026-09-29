"""Compile the production mission input callbacks in a small Windows host harness."""

import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "native/src/Driving.cpp").read_text(encoding="utf-8")


def function(name):
    # These functions contain no braces in string literals. Keep the production
    # bodies verbatim so the harness exercises their real routing and ABI values.
    match = re.search(r"^(?:void\*|void|bool|int) " + re.escape(name) + r"\(", SOURCE, re.MULTILINE)
    if not match:
        raise ValueError("Missing production function: " + name)
    start = match.start()
    brace = SOURCE.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (SOURCE[end] == "{") - (SOURCE[end] == "}")
        end += 1
    return SOURCE[start:end] + "\n"


PRELUDE = r"""
#include "MissionComfort.h"
namespace missioncomfort=savr::missioncomfort;
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <cstdlib>
namespace xr {
struct InputState { float triggers[2]{}, leftStick[2]{}, rightStick[2]{}, grip[2]{}; bool b{}; };
InputState input;
void GetInput(InputState& out) { out=input; }
}
namespace savr::beachdance {
bool Active(){return false;}
int AxisUpDown(){return 0;}
int AxisLeftRight(){return 0;}
}
namespace savr::hydraulics {
bool active=false;
bool IsActive() { return active; }
int AxisUpDown() { return -87; }
int AxisLeftRight() { return 91; }
}
void* seated=nullptr;
int appearance=0;
bool allowed=true, immersive=false;
void* FindVehicle(int, bool) { return seated; }
int Appearance(const void*) { return appearance; }
void* activePad=nullptr;
void* GetPad(int) { return activePad; }
struct Symbols {
    void* (*CPad_GetPad)(int)=GetPad;
    void* CWorld_Players{};
    std::uint8_t* CWorld_PlayerInFocus{};
    std::int32_t* CRopes_PlayerControlsCrane{};
    std::uintptr_t LoadBase{};
    void* (*FindPlayerVehicle)(int,bool)=FindVehicle;
    int (*CVehicle_GetVehicleAppearance)(const void*)=Appearance;
} g;
namespace vrcam { bool IsStereoActive() { return allowed; } }
namespace vrfire { bool scripted=false; bool IsScriptedWeaponCamera() { return scripted; } }
std::atomic<bool> g_inputBlocked{false};
bool HasPlayerVehicle() { return seated!=nullptr; }
void EnsureInit() {}
std::atomic<bool> g_planeInvertPitch{false};
std::atomic<bool> g_bikeBlockWheelie{false};
int saveCalls=0;void Save(){++saveCalls;}
constexpr int MODE_IMMERSIVE=1, MODE_MOTION=2, kRhinoModelId=432;
constexpr int BICYCLE_MOTION=1, BIKE_ACCEL_HOLD_TRIGGER=1;
int GetActiveVehicleAppearance() { return appearance; }
bool IsBicycleModel(int model) { return model==481; }
std::atomic<int> g_activeVehicleModel{452},g_activeBikeAccelerator{0},g_bicycleMode{0};
std::atomic<int> g_activeVehicleAppearance{4};
std::atomic<float> g_motionSteering{0};
float g_bicyclePedalPulse=0,g_bikeThrottle=0,g_bicycleSteering=0;
struct { bool active=true; float steering=0; } g_visual;
#define LOGI(...) ((void)0)
int ModeForAppearance(int) { return immersive?MODE_IMMERSIVE:0; }
std::mutex g_stateMutex;
float g_bikeLean=0;
std::atomic<float> g_planePitch{0};
std::atomic<bool> g_vehicleActionEdge{false};
void ReadMappedGameplaySticks(const xr::InputState& in, float& mx,float& my,float& tx,float& ty) {
    mx=in.leftStick[0]; my=in.leftStick[1]; tx=in.rightStick[0]; ty=in.rightStick[1];
}
int Fallback(void*) { return 71; }
int GunFallback(void*,int,int) { return 72; }
int UpDownFallback(void*,int,void*,float,int) { return 73; }
int (*g_origBrake)(void*)=Fallback;
int (*g_origAccelerate)(void*)=Fallback;
int (*g_origSteering)(void*)=Fallback;
int (*g_origSteeringUpDown)(void*)=Fallback;
int (*g_origTurretLeft)(void*)=Fallback;
int (*g_origTurretRight)(void*)=Fallback;
int (*g_origCraneReleaseJustDown)(void*)=Fallback;
int (*g_origUseBomb)(void*)=Fallback;
int (*g_origUseRocket)(void*)=Fallback;
int (*g_origCarGunFired)(void*,int,int)=GunFallback;
int (*g_origCarGunLeftRight)(void*,int,int)=GunFallback;
int (*g_origCarGunUpDown)(void*,int,void*,float,int)=UpDownFallback;
int checks=0;
void Check(bool condition,const char* text) {
    ++checks;
    if (!condition) { std::fprintf(stderr,"FAIL: %s\n",text); std::exit(1); }
}
"""

FUNCTIONS = [
    "GetRemoteControlledVehicle", "IsCraneControlActive",
    "VrGameplayInputAllowed",
    "GetControlledVehicle", "ControlledVehicleAppearance", "ControlledVehicleModel",
    "IsPlanePitchInverted", "TogglePlanePitchInversion",
    "IsRemoteBaron", "OnGetAccelerate", "OnGetSteering", "OnGetBrake", "OnGetSteeringUpDown", "VehicleRightStickActive",
    "OnGetCarGunUpDown", "OnGetCarGunLeftRight", "OnGetCarGunFired",
    "MissionActionAllowed", "OnCraneReleaseJustDown", "OnUseBomb", "OnUseRocket",
    "OnGetTurretLeft", "OnGetTurretRight",
    "IsRemoteCargoControlActive", "RemoteCargoActionPressed",
]

TESTS = r"""
int main() {
    alignas(8) unsigned char players[2*0x1d8]{}, vehicle[0x40]{}, pad[0x130]{};
    std::uint8_t focus=0;
    std::int32_t crane=0;
    g.CWorld_Players=players; g.CWorld_PlayerInFocus=&focus;
    g.CRopes_PlayerControlsCrane=&crane;
    g.LoadBase=reinterpret_cast<std::uintptr_t>(g.FindPlayerVehicle)-0x4afb0c;
    void* remote=vehicle;
    Check(GetRemoteControlledVehicle()==nullptr,"no remote vehicle");
    std::memcpy(players+0xe0,&remote,sizeof(remote));
    Check(GetRemoteControlledVehicle()==remote,"remote without seated player");
    focus=1;
    Check(GetRemoteControlledVehicle()==nullptr,"respect selected player slot");
    std::memcpy(players+0x1d8+0xe0,&remote,sizeof(remote));
    Check(GetRemoteControlledVehicle()==remote,"verified player-info stride");
    focus=2;
    Check(GetRemoteControlledVehicle()==nullptr,"reject invalid focus");
    focus=0;
    ++g.LoadBase;
    Check(GetRemoteControlledVehicle()==nullptr,"reject unknown retail layout");
    --g.LoadBase;
    activePad=pad;
    *reinterpret_cast<std::uint16_t*>(vehicle+0x32)=501;
    Check(IsRemoteCargoControlActive(),"RC Goblin cargo context without seated CJ");
    g_vehicleActionEdge=true;
    Check(RemoteCargoActionPressed(),"B feeds New Model Army magnet command");
    Check(RemoteCargoActionPressed(),"script repeated query sees same press");
    g_vehicleActionEdge=false;
    Check(!RemoteCargoActionPressed(),"held B cannot repeat cargo action");
    g_vehicleActionEdge=true;
    g_inputBlocked=true;Check(!RemoteCargoActionPressed(),"menu blocks cargo");g_inputBlocked=false;
    allowed=false;Check(!RemoteCargoActionPressed(),"non VR blocks cargo");allowed=true;
    xr::input.grip[0]=xr::input.grip[1]=1;
    Check(!RemoteCargoActionPressed(),"menu chord blocks cargo");xr::input={};
    *reinterpret_cast<std::uint16_t*>(pad+0x110)=1;
    Check(!RemoteCargoActionPressed(),"script-disabled controls block cargo");
    *reinterpret_cast<std::uint16_t*>(pad+0x110)=0;
    activePad=nullptr;Check(!RemoteCargoActionPressed(),"missing pad blocks cargo");activePad=pad;
    *reinterpret_cast<std::uint16_t*>(vehicle+0x32)=464;
    Check(!IsRemoteCargoControlActive()&&!RemoteCargoActionPressed(),"RC Baron unaffected");
    *reinterpret_cast<std::uint16_t*>(vehicle+0x32)=501;
    std::memset(players,0,sizeof(players));seated=vehicle;
    Check(!IsRemoteCargoControlActive(),"seated vehicle is not remote cargo");
    seated=nullptr;std::memcpy(players+0xe0,&remote,sizeof(remote));
    *reinterpret_cast<std::uint16_t*>(vehicle+0x32)=0;
    appearance=2;immersive=true;g_bikeLean=-.75f;
    Check(OnGetSteeringUpDown(pad)==96,"wheelie enabled preserves raised-hands input");
    g_bikeBlockWheelie=true;
    Check(OnGetSteeringUpDown(pad)==0,"wheelie disabled blocks raised-hands input");
    g_bikeLean=.5f;Check(OnGetSteeringUpDown(pad)==-64,"forward braking lean preserved");
    immersive=false;Check(OnGetSteeringUpDown(pad)==71,"default riding unaffected by wheelie option");
    g_bikeBlockWheelie=false;immersive=false;
    appearance=5;
    xr::input.b=true;
    Check(OnGetCarGunFired(pad,1,1)==2,"RC secondary gun button code");
    xr::input.grip[0]=xr::input.grip[1]=1.0f;
    Check(!VrGameplayInputAllowed(),"menu chord blocks remote controls");
    Check(OnGetCarGunFired(pad,1,1)==72,"menu chord does not force gun fire");
    xr::input.grip[0]=xr::input.grip[1]=0.0f;
    Check(OnGetCarGunFired(pad,0,0)==1,"primary gun button code");
    xr::input.b=false;
    Check(OnGetCarGunFired(pad,1,1)==0,"released gun");
    xr::input.triggers[0]=0.5f;
    Check(OnGetBrake(pad)==127,"remote brake analog");
    xr::input.leftStick[1]=0.75f;
    immersive=true; g_planePitch=-0.5f;
    Check(OnGetSteeringUpDown(pad)==96,"RC plane ignores cockpit yoke setting");
    Check(!IsPlanePitchInverted(),"default preserves existing pitch");
    TogglePlanePitchInversion();Check(IsPlanePitchInverted()&&saveCalls==1,"menu toggle persists inversion");
    Check(OnGetSteeringUpDown(pad)==-96,"RC plane inverted pitch");
    *reinterpret_cast<std::uint16_t*>(vehicle+0x32)=464;
    const int rcPitch=static_cast<int>(savr::missioncomfort::RcAxis(.75f)*128);
    Check(OnGetSteeringUpDown(pad)==-rcPitch,"RC Baron inversion after comfort curve");
    xr::input.leftStick[1]=-.75f;
    Check(OnGetSteeringUpDown(pad)==rcPitch,"RC Baron opposite direction");
    xr::input.leftStick[1]=0;
    Check(OnGetSteeringUpDown(pad)==0,"RC Baron neutral pitch");
    xr::input.leftStick[1]=.75f;*reinterpret_cast<std::uint16_t*>(vehicle+0x32)=0;
    appearance=3;
    Check(OnGetSteeringUpDown(pad)==-96,"RC helicopter ignores plane inversion");
    TogglePlanePitchInversion();Check(!IsPlanePitchInverted()&&saveCalls==2,"second toggle saves original mapping");
    Check(OnGetSteeringUpDown(pad)==-96,"RC helicopter pitch axis");
    xr::input.rightStick[0]=-0.6f;
    Check(OnGetTurretLeft(pad)==1&&OnGetTurretRight(pad)==0,"RC helicopter yaw left");
    xr::input.rightStick[0]=0.6f;
    Check(OnGetTurretLeft(pad)==0&&OnGetTurretRight(pad)==1,"RC helicopter yaw right");
    g_vehicleActionEdge=true;
    Check(OnCraneReleaseJustDown(pad)==1,"RC magnet release");
    Check(OnCraneReleaseJustDown(pad)==1,"repeated query sees same edge");
    appearance=5;
    Check(OnUseRocket(pad)==1,"aircraft missile edge");
    g_vehicleActionEdge=false;
    Check(OnUseRocket(pad)==0,"held button does not repeat edge");
    g_vehicleActionEdge=true;
    *reinterpret_cast<std::uint16_t*>(pad+0x110)=1;
    Check(OnUseRocket(pad)==71,"script-disabled rocket follows retail");
    Check(OnGetCarGunFired(pad,1,1)==72,"script-disabled aircraft gun follows retail");
    *reinterpret_cast<std::uint16_t*>(pad+0x110)=0;
    allowed=false;
    Check(OnGetCarGunFired(pad,1,1)==72,"blocked gun follows retail");
    Check(OnGetSteeringUpDown(pad)==71,"blocked aircraft steering follows retail");
    allowed=true;
    vrfire::scripted=true;
    Check(!VrGameplayInputAllowed(),"scripted gunner does not drive");
    vrfire::scripted=false;
    g_inputBlocked=true;
    Check(!VrGameplayInputAllowed(),"blocked input does not drive");
    g_inputBlocked=false;
    std::memset(players,0,sizeof(players)); seated=vehicle;
    appearance=4; immersive=true; xr::input={};
    Check(OnGetAccelerate(pad)==0&&OnGetBrake(pad)==0,"boat has no thrust at released triggers");
    xr::input.triggers[1]=0.5f;
    Check(OnGetAccelerate(pad)==127,"boat R2 gives proportional thrust");
    xr::input.triggers[1]=0; xr::input.triggers[0]=0.75f;
    Check(OnGetBrake(pad)==191,"boat L2 gives proportional brake/reverse");
    g_visual.steering=0.5f; xr::input.leftStick[0]=-1;
    Check(OnGetSteering(pad)==-64,"boat physical helm drives retail steering despite stick drift");
    g_visual.steering=-0.5f;
    Check(OnGetSteering(pad)==64,"opposite helm rotation reverses boat steering");
    g_visual.steering=0;
    Check(OnGetSteering(pad)==0,"centered immersive helm has no steering");
    immersive=false;
    Check(OnGetSteering(pad)==-128,"default boat retains stick steering");
    xr::input.leftStick[1]=0.75f; immersive=true;
    appearance=5;
    Check(OnGetSteeringUpDown(pad)==-64,"seated immersive plane retains yoke");
    immersive=false;
    Check(OnGetSteeringUpDown(pad)==96,"seated default plane has direct pitch");
    TogglePlanePitchInversion();
    Check(OnGetSteeringUpDown(pad)==-96,"seated plane inversion");
    immersive=true;
    Check(OnGetSteeringUpDown(pad)==-64,"physical yoke unaffected by stick inversion");
    immersive=false;
    appearance=3;Check(OnGetSteeringUpDown(pad)==-96,"seated helicopter unaffected");
    TogglePlanePitchInversion();
    appearance=1;
    *reinterpret_cast<std::uint16_t*>(vehicle+0x32)=530;
    xr::input.rightStick[1]=0.75f;
    Check(OnGetCarGunUpDown(pad,1,vehicle,0,0)==96,"forklift arm axis");
    xr::input.rightStick[1]=0.1f;
    Check(OnGetCarGunUpDown(pad,1,vehicle,0,0)==0,"forklift deadzone");
    *reinterpret_cast<std::uint16_t*>(vehicle+0x32)=400;
    Check(OnGetCarGunUpDown(pad,1,vehicle,0,0)==73,"ordinary vehicle keeps retail axis");
    Check(OnGetCarGunFired(pad,1,1)==72,"ordinary vehicle keeps retail gun");
    Check(OnUseBomb(pad)==1,"car bomb edge");
    seated=nullptr;
    Check(OnUseBomb(pad)==71,"on foot bomb query keeps retail");
    for (crane=1;crane<=4;++crane) {
        Check(IsCraneControlActive(),"all four crane contexts");
        Check(OnCraneReleaseJustDown(pad)==1,"crane release without seated player");
    }
    crane=1;
    xr::input.grip[0]=xr::input.grip[1]=1.0f;
    Check(!VrGameplayInputAllowed(),"menu chord blocks crane controls");
    xr::input.grip[0]=xr::input.grip[1]=0.0f;
    crane=5;
    Check(!IsCraneControlActive(),"reject invalid crane context");
    crane=0;
    Check(!IsCraneControlActive(),"inactive crane");
    crane=-1;
    Check(!IsCraneControlActive(),"reject negative crane context");
    savr::hydraulics::active=true;
    Check(OnGetCarGunUpDown(pad,1,nullptr,0,0)==-87,"preserve hydraulics pitch override");
    Check(OnGetCarGunLeftRight(pad,1,0)==91,"preserve hydraulics roll override");
    std::printf("PASS: %d production driving input checks\n",checks);
}
"""


def main():
    vr=(ROOT/'native/src/VrCamera.cpp').read_text(encoding='utf8')
    main=(ROOT/'native/src/main.cpp').read_text(encoding='utf8')
    xr=(ROOT/'native/src/Xr.cpp').read_text(encoding='utf8')
    assert 'const bool frontendBlocked = inGameplay || anyMenu || menuWasOpen;' in main
    assert 'formalScene' not in main and 'skipHold' not in vr
    assert 'SetCutsceneSkipProgress' not in xr and 'HOLD A TO SKIP' not in xr
    assert 'if (!stereo || g.CPad_GetPad == nullptr || inputBlocked)' in vr
    assert 'PlaneInvertPitch=%d' in SOURCE and 'g_planeInvertPitch.store(value==1)' in SOURCE
    for table in ('kDefaultPlaneItems','kImmersivePlaneItems'):
        items=SOURCE.split('constexpr int '+table+'[] = {',1)[1].split('};',1)[0]
        assert 'MENU_PLANE_INVERT_PITCH' in items
    assert 'MENU_PLANE_INVERT_PITCH&&(enter||step)' in main
    assert 'PLANE STICK INVERT Y' in xr
    released=vr.split('bool OnWidgetReleased(',1)[1]
    assert released.index('widgetId == 67 && driving::IsRemoteCargoControlActive()') < released.index('PromptAnswerableWidget(widgetId)')
    assert 'driving::RemoteCargoActionPressed()' in released


    msvc = Path(os.environ.get("VCToolsInstallDir", ""))
    if not (msvc / "include").is_dir():
        base = Path("C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC")
        msvc = sorted(base.iterdir())[-1]
    sdk = Path("C:/Program Files (x86)/Windows Kits/10")
    version = sorted((sdk / "Include").iterdir())[-1].name
    env = os.environ.copy()
    env["INCLUDE"] = ";".join(str(p) for p in [msvc / "include", *[
        sdk / "Include" / version / name for name in ("ucrt", "shared", "um")]])
    env["LIB"] = ";".join(str(p) for p in [msvc / "lib/x64", *[
        sdk / "Lib" / version / name / "x64" for name in ("ucrt", "um")]])
    compiler_dir = msvc / "bin/Hostx64/x64"
    env["PATH"] = str(compiler_dir) + os.pathsep + env.get("PATH", "")
    output = ROOT / "build/driving-mission-tests"
    output.mkdir(parents=True, exist_ok=True)
    source = output / "driving_callbacks.cpp"
    source.write_text(PRELUDE + "\n".join(function(n) for n in FUNCTIONS) + TESTS,
                      encoding="utf-8")
    subprocess.run([str(compiler_dir / "cl.exe"), "/nologo", "/std:c++17", "/EHsc", "/MD",
                    "/I" + str(ROOT / "native/src"), str(source), "/Fe:" + str(output / "driving_callbacks.exe"),
                    "/Fo:" + str(output / "driving_callbacks.obj")], env=env, check=True)
    subprocess.run([str(output / "driving_callbacks.exe")], check=True)


if __name__ == "__main__":
    main()
