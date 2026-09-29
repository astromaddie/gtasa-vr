"""Run the production swimming motion policy on the host using synthetic strokes."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

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
    output = ROOT / "build/swim-tests"
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(compiler / "cl.exe"), "/nologo", "/std:c++17", "/EHsc", "/MD",
                    str(ROOT / "native/tests/swim_motion_test.cpp"),
                    "/Fe:" + str(output / "swim_motion.exe"),
                    "/Fo:" + str(output / "swim_motion.obj")], env=env, check=True)
    subprocess.run([str(output / "swim_motion.exe")], check=True)

    source = (ROOT / "native/src/Swimming.cpp").read_text()
    core = source[source.index("namespace savr::swimming {"):source.index("// Both prologues")]
    update = source[source.index("void UpdateInput(bool enabled)"):]
    prelude = r'''
#include "SwimMotion.h"
#include <chrono>
#include <cstdint>
#include <cstring>
#include <cstdio>
namespace savr {
void* fakePed{}; void* fakePad{}; float fakeStep=1.0f; int nativeControls{},nativeResistance{};
struct Symbols {
    void* (*FindPlayerPed)(int)=[](int) { return fakePed; };
    void* (*CPad_GetPad)(int)=[](int) { return fakePad; };
    float* CTimer_ms_fTimeStep{};
} g;
namespace locomotion { bool enabled=true; bool GestureSwimEnabled() { return enabled; } }
namespace missioncontrols {
bool swim=true,climb=false;
bool IsSwimming() { return swim; }
bool TouchDoubleTapped(int id) { return climb&&id==168; }
}
namespace xr {
struct HandPose { bool valid{}; float gripPos[3]{}; };
float breath{}; bool headValid=true;
void PublishBreath(float value) { breath=value; }
bool GetHeadPose(float p[3],float q[4]) { p[0]=p[1]=p[2]=0; q[3]=1; return headValid; }
void GetHandPoses(HandPose[2]) {}
}
namespace vrcam {
float eyeZ=0.2f;
bool GetHeadWorldRay(float eye[3],float dir[3]) { eye[2]=eyeZ; dir[1]=1; return true; }
}
}
'''
    harness = output / "swim_callbacks.cpp"
    harness.write_text(prelude + core + "}\n" + update +
                       (ROOT / "native/tests/swim_callbacks_test.inc").read_text())
    subprocess.run([str(compiler / "cl.exe"), "/nologo", "/std:c++17", "/EHsc", "/MD",
                    "/I" + str(ROOT / "native/src"), str(harness),
                    "/Fe:" + str(output / "swim_callbacks.exe"),
                    "/Fo:" + str(output / "swim_callbacks.obj")], env=env, check=True)
    subprocess.run([str(output / "swim_callbacks.exe")], check=True)

if __name__ == "__main__":
    main()
