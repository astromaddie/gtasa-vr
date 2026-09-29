"""Run production weapon routing functions against synthetic retail memory."""

import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "native/src/VrFire.cpp").read_text(encoding="utf-8")


def function(name):
    match = re.search(r"^(?:void|bool) " + name + r"\(", SOURCE, re.MULTILINE)
    if not match:
        raise ValueError("Missing production function: " + name)
    start = match.start()
    end = SOURCE.index("{", start) + 1
    depth = 1
    while depth:
        depth += (SOURCE[end] == "{") - (SOURCE[end] == "}")
        end += 1
    return SOURCE[start:end]


PRELUDE = r"""
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <initializer_list>
struct Vec3 { float x{}, y{}, z{}; };
alignas(16) std::uint8_t ped[0xa00]{}, camera[0x1000]{}, pad[0x140]{};
void* FindPed(int) { return ped; }
void* GetPad(int) { return pad; }
bool FakeFire(void*,void*,Vec3*,Vec3*,void*,Vec3*,Vec3*);
namespace vrcam {bool FirePhotograph(void*,void*,const float*){return true;}}
struct Symbols {
    void* TheCamera=camera;
    void* (*FindPlayerPed)(int)=FindPed;
    void* (*CPad_GetPad)(int)=GetPad;
    bool (*CWeapon_Fire)(void*,void*,Vec3*,Vec3*,void*,Vec3*,Vec3*)=FakeFire;
} g;
namespace justbusiness { bool active=false; bool Active(){return active;} }
thread_local bool g_insideScriptedFire=false;
std::atomic<bool> g_directTriggerDown[2]{};
bool g_detonatorReleaseRequired[2]{true,true};
std::uint32_t g_directNextFireMs[2]{};
int g_directWeaponType[2]{-1,-1};
int checks=0;
void Check(bool condition,const char* name) {
    ++checks;
    if (!condition) { std::fprintf(stderr,"FAIL: %s\n",name); std::exit(1); }
}
template<class T> void Put(std::uint8_t* p,std::size_t offset,T value) {
    std::memcpy(p+offset,&value,sizeof(value));
}
"""

TESTS = r"""
int expectedDuringFire=0;
bool expectedScripted=false, nativeResult=true;
bool FakeFire(void*,void*,Vec3*,Vec3*,void*,Vec3*,Vec3*) {
    Check(*reinterpret_cast<std::uint16_t*>(camera+kPlayerWeaponModeOffset)==expectedDuringFire,
          "native fire sees intended mode");
    Check(IsScriptedWeaponCamera()==expectedScripted,
          "nested physical-ray query retains scripted ownership");
    return nativeResult;
}
int main() {
    Put(ped,kPedActiveSlotOffset,std::int8_t{5});
    Put(ped,kPedWeaponsOffset+5*kWeaponStride,std::int32_t{31});
    Put(camera,kPlayerWeaponModeOffset,std::uint16_t{45});
    justbusiness::active=true;
    Check(IsScriptedWeaponCamera(),"Just Business passenger needs no attachment/mode");
    Put(camera,kPlayerWeaponModeOffset,std::uint16_t{0});
    Check(IsScriptedWeaponCamera(),"passenger remains gunner in ordinary camera mode");
    expectedDuringFire=0;expectedScripted=true;
    Check(CallProductionFire(28),"ordinary passenger reaches native Micro SMG fire");
    Check(*reinterpret_cast<std::uint16_t*>(camera+kPlayerWeaponModeOffset)==0,
          "passenger camera mode restored after native shot");
    expectedScripted=false;
    justbusiness::active=false;
    Put(camera,kPlayerWeaponModeOffset,std::uint16_t{45});
    Check(!IsScriptedWeaponCamera(),"ordinary ped cannot become attached gunner");
    Put(ped,kPedAttachedToOffset,static_cast<void*>(camera));
    Check(IsScriptedWeaponCamera(),"attached M4 helicannon mode");
    Put(camera,kPlayerWeaponModeOffset,std::uint16_t{65});
    Check(IsScriptedWeaponCamera(),"attached aiming mode with gun");
    Put(ped,kPedWeaponsOffset+5*kWeaponStride,std::int32_t{7});
    Check(!IsScriptedWeaponCamera(),"attached pool cue cannot become gunner");
    Put(ped,kPedWeaponsOffset+5*kWeaponStride,std::int32_t{31});
    for (int mode : {0,4,7,34,46,53,55}) {
        Put(camera,kPlayerWeaponModeOffset,static_cast<std::uint16_t>(mode));
        Check(!IsScriptedWeaponCamera(),"ordinary rifle/sniper/photo modes excluded");
    }
    Put(camera,kPlayerWeaponModeOffset,std::uint16_t{45});
    for (int slot : {-1,0,13,127}) {
        Put(ped,kPedActiveSlotOffset,static_cast<std::int8_t>(slot));
        Check(!IsScriptedWeaponCamera(),"invalid inventory slot rejected");
    }
    Put(ped,kPedActiveSlotOffset,std::int8_t{5});
    for (bool result : {false,true}) {
        nativeResult=result; expectedDuringFire=0; expectedScripted=true;
        Check(CallProductionFire(31)==result,"native success/failure preserved");
        Check(*reinterpret_cast<std::uint16_t*>(camera+kPlayerWeaponModeOffset)==45,
              "native weapon mode restored after success/failure");
        Check(!g_insideScriptedFire,"temporary ownership flag restored");
    }
    Put(camera,kPlayerWeaponModeOffset,std::uint16_t{34});
    nativeResult=true; expectedDuringFire=34; expectedScripted=false;
    Check(CallProductionFire(31),"ordinary rifle fire mode left untouched");
    Check(PlayerFireEnabled(),"enabled pad accepts physical fire");
    for (std::uint16_t bits : {1,2,128,256,32768}) {
        Put(pad,kPadDisableControlsOffset,bits);
        Check(!PlayerFireEnabled(),"every tested native control lock blocks fire");
    }
    Put(pad,kPadDisableControlsOffset,std::uint16_t{0});
    pad[kPadDisableFireOffset]=1;
    Check(!PlayerFireEnabled(),"native fire lock blocks fire");
    pad[kPadDisableFireOffset]=0;
    Check(PlayerFireEnabled(),"native locks restored");
    for (int hand : {0,1}) {
        ResetDirectTrigger();
        Check(!DetonatorTriggerReady(40,hand,1.0f),"held trigger after block cannot detonate");
        Check(!DetonatorTriggerReady(40,hand,0.5f),"partial release cannot rearm detonator");
        Check(!DetonatorTriggerReady(40,hand,std::numeric_limits<float>::quiet_NaN()),
              "invalid trigger cannot rearm detonator");
        Check(!DetonatorTriggerReady(40,hand,0.0f),"release rearms without firing");
        Check(DetonatorTriggerReady(40,hand,1.0f),"new press after release allowed");
        ResetDirectTrigger();
        Check(!DetonatorTriggerReady(40,hand,1.0f),"next menu requires another release");
    }
    Check(DetonatorTriggerReady(31,1,1.0f),"automatic gun behavior unchanged");
    Check(DetonatorTriggerReady(43,1,1.0f),"camera behavior unchanged");
    std::printf("PASS: %d production mission weapon checks\n",checks);
}
"""


def main():
    constants = "\n".join(re.findall(
        r"^constexpr (?:std::uintptr_t|float) (?:kPadDisableControlsOffset|"
        r"kPadDisableFireOffset|kPedWeaponsOffset|kPedActiveSlotOffset|"
        r"kWeaponStride|kPedAttachedToOffset|kPlayerWeaponModeOffset|"
        r"kTriggerRelease) = .*?;", SOURCE, re.MULTILINE))
    names = ["PlayerFireEnabled", "SupportedHitscan", "ResetDirectTrigger",
             "DetonatorTriggerReady", "IsScriptedWeaponCamera"]
    begin = SOURCE.index("    std::uint16_t* playerWeaponMode = nullptr;")
    end = SOURCE.index("    if (!fired) {", begin)
    fire = ("bool CallProductionFire(int weaponType) {\n"
            "void* weapon=nullptr; Vec3 origin{}; Vec3* target=nullptr;\n" +
            SOURCE[begin:end] + "\nreturn fired;\n}\n")
    output = ROOT / "build/mission-weapon-tests"
    output.mkdir(parents=True, exist_ok=True)
    source = output / "mission_weapons.cpp"
    source.write_text(PRELUDE + constants + "\n" +
                      "\n".join(function(n) for n in names) + fire + TESTS,
                      encoding="utf-8")
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
    subprocess.run([str(compiler_dir / "cl.exe"), "/nologo", "/std:c++17", "/EHsc", "/MD",
                    str(source), "/Fe:" + str(output / "mission_weapons.exe"),
                    "/Fo:" + str(output / "mission_weapons.obj")], env=env, check=True)
    subprocess.run([str(output / "mission_weapons.exe")], check=True)


if __name__ == "__main__":
    main()
