"""Compile production hull selection and boarding against controlled engine callbacks."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

PRELUDE = r'''
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
namespace savr {
struct GameSymbols { struct Vec3 { float x{},y{},z{}; }; };
using V=GameSymbols::Vec3;
alignas(16) char ped[0x1000]{},boat[0x1000]{},pad[0x200]{},intelligence[0x100]{},driveTask[0x38]{};
void* seated=nullptr;
V eye{0,0,0.72f},point{0,1,0};
int appearance=4,seatCalls=0,driveCalls=0,deletedTasks=0,seatDestructed=0;
bool allocationOk=true,ctorArgs=false,driveArgs=false;
bool collision=true,unlocked=true,vehicleHealthy=true,pedHealthy=true,
     nativeSuccess=true,nativeArgsCorrect=false,headValid=true;
struct Symbols {
    void* (*FindPlayerPed)(int)=[](int)->void* { return ped; };
    void* (*FindPlayerVehicle)(int,bool)=[](int,bool) { return seated; };
    void* (*CPad_GetPad)(int)=[](int)->void* { return pad; };
    int (*CVehicle_GetVehicleAppearance)(const void*)=[](const void*) { return appearance; };
    bool (*CWorld_ProcessLineOfSight)(const V*,const V*,void*,void**,bool,bool,bool,bool,bool,bool,bool,bool)=
        [](const V*,const V*,void* out,void** entity,bool,bool,bool,bool,bool,bool,bool,bool) {
            std::memcpy(out,&point,sizeof(point)); *entity=boat; return collision;
        };
} g;
namespace vrcam {
bool GetHeadWorldRay(float p[3],float d[3]) {
    p[0]=eye.x; p[1]=eye.y; p[2]=eye.z; d[1]=1; return headValid;
}
}
}
'''

def main():
    msvc = sorted(Path("C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC").iterdir())[-1]
    sdk = Path("C:/Program Files (x86)/Windows Kits/10")
    version = sorted((sdk / "Include").iterdir())[-1].name
    env = os.environ.copy()
    env["INCLUDE"] = ";".join(str(p) for p in [msvc / "include", *[
        sdk / "Include" / version / name for name in ("ucrt", "shared", "um")]])
    env["LIB"] = ";".join(str(p) for p in [msvc / "lib/x64", *[
        sdk / "Lib" / version / name / "x64" for name in ("ucrt", "um")]])
    compiler = msvc / "bin/Hostx64/x64"
    env["PATH"] = str(compiler) + os.pathsep + env.get("PATH", "")
    output = ROOT / "build/boat-entry-tests"
    output.mkdir(parents=True, exist_ok=True)
    source = (ROOT / "native/src/BoatEntry.cpp").read_text()
    code = source[source.index("namespace savr::boatentry {"):source.index("void Install(void* handle)")]
    code += source[source.index("bool TryEnter()"):]
    code = code.replace("/sdcard/Android/data/com.rockstargames.gtasa/files/vr_boat_entry.log",
                        (output / "boat-entry-test.log").as_posix())
    harness = output / "boat_entry.cpp"
    harness.write_text(PRELUDE + code + (ROOT / "native/tests/boat_entry_test.inc").read_text())
    subprocess.run([str(compiler / "cl.exe"), "/nologo", "/std:c++17", "/EHsc", "/MD",
                    str(harness), "/Fe:" + str(output / "boat_entry.exe"),
                    "/Fo:" + str(output / "boat_entry.obj")], env=env, check=True)
    subprocess.run([str(output / "boat_entry.exe")], check=True)

if __name__ == "__main__":
    main()
