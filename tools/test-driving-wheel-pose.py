"""Compile stock wheel and handlebar calibration from Driving.cpp on the host."""

import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "native/src/Driving.cpp").read_text(encoding="utf-8")


def function(signature):
    start = SOURCE.index(signature)
    brace = SOURCE.index("{", start)
    depth, end = 1, brace + 1
    while depth:
        depth += (SOURCE[end] == "{") - (SOURCE[end] == "}")
        end += 1
    return SOURCE[start:end] + "\n"


PRELUDE = r'''
#include "Driving.h"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <map>
#include <mutex>
#include <string>

namespace savr::driving {
int activeModel=411, activeMode=MODE_IMMERSIVE;
int saveCount=0, resetCount=0;
void EnsureInit() {}
void Save() { ++saveCount; }
void ResetInteraction() { ++resetCount; }
int GetActiveVehicleModelId() { return activeModel; }
int GetActiveVehicleType() { return VEHICLE_BIKE; }
std::atomic<bool> g_bikeBlockWheelie{false};
std::atomic<bool> g_planeInvertPitch{false};
std::atomic<bool> g_bikeHandsFollowTilt{true};
std::atomic<int> g_activeBikeAccelerator{BIKE_ACCEL_PHYSICAL_OR_TAP};
struct GameSymbols { struct Vec3 {float x,y,z;}; };
bool ComponentPresent(void*,int) {return true;}
void ComponentPosition(void*,int,GameSymbols::Vec3* p) {*p={1,2,3};}
struct { bool (*CBike_IsComponentPresent)(void*,int)=ComponentPresent;
 void (*CBike_GetComponentWorldPosition)(void*,int,GameSymbols::Vec3*)=ComponentPosition; } g;
#define LOGI(...) ((void)0)

int GetModeForVehicleType(int) { return activeMode; }
int GlobalSeatSideField(int,int) { return F_SIDE; }
int GlobalSeatField(int,int,bool height) { return height?F_HEIGHT:F_DISTANCE; }
bool HasCurrentModelForType(int) { return activeModel>=0; }
std::atomic<int> g_value[F_COUNT]{};
std::atomic<int> g_bikeVisualLeanPercent{50};
int kDefaults[F_COUNT]{};
'''

HARNESS = r'''
int checks=0;
#define CHECK(c) do { ++checks; if (!(c)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#c); std::exit(1); } } while (0)
bool Near(float a,float b) { return std::abs(a-b)<.00001f; }
void CheckVector(V3 a,V3 b) { CHECK(Near(a.x,b.x)); CHECK(Near(a.y,b.y)); CHECK(Near(a.z,b.z)); }
void CheckBasis(const ModelWheelPose& p) {
    CHECK(Near(Length(p.right),1)); CHECK(Near(Length(p.up),1)); CHECK(Near(Length(p.normal),1));
    CHECK(Near(Dot(p.right,p.up),0)); CHECK(Near(Dot(p.right,p.normal),0)); CHECK(Near(Dot(p.up,p.normal),0));
    CheckVector(Cross(p.right,p.normal),p.up);
}


void TestPose() {
    int preset[F_COUNT]{},delta[WHEEL_CAL_FIELD_COUNT]{};
    preset[F_WHEEL_SIDE]=-47;preset[F_WHEEL_DISTANCE]=37;
    preset[F_WHEEL_HEIGHT]=15;preset[F_WHEEL_RADIUS]=17;
    auto wheel=CalibratedWheelPose({1,2,3},{1,0,0},{0,1,0},{0,0,1},preset,delta);
    CheckVector(wheel.center,{.53f,2.37f,3.15f});CHECK(Near(wheel.radius,.17f));CheckBasis(wheel);
    delta[WHEEL_CAL_SIDE]=2;delta[WHEEL_CAL_FORWARD]=-4;
    delta[WHEEL_CAL_HEIGHT]=7;delta[WHEEL_CAL_RADIUS]=1;
    wheel=CalibratedWheelPose({1,2,3},{1,0,0},{0,1,0},{0,0,1},preset,delta);
    CheckVector(wheel.center,{.55f,2.33f,3.22f});CHECK(Near(wheel.radius,.18f));
    auto turned=CalibratedWheelPose({10,20,30},{0,1,0},{-1,0,0},{0,0,1},preset,delta);
    CheckVector(turned.center,{9.67f,19.55f,30.22f});CheckBasis(turned);
    delta[WHEEL_CAL_RADIUS]=-100;
    CHECK(Near(CalibratedWheelPose({},{1,0,0},{0,1,0},{0,0,1},preset,delta).radius,.06f));
    delta[WHEEL_CAL_RADIUS]=200;
    CHECK(Near(CalibratedWheelPose({},{1,0,0},{0,1,0},{0,0,1},preset,delta).radius,.45f));
    std::fill_n(delta,WHEEL_CAL_FIELD_COUNT,0);
    for(int field=WHEEL_CAL_PITCH;field<=WHEEL_CAL_ROLL;++field) {
        delta[field]=180;
        auto rotated=CalibratedWheelPose({},{1,0,0},{0,1,0},{0,0,1},preset,delta);
        CheckBasis(rotated);
        if(field==WHEEL_CAL_PITCH)CheckVector(rotated.normal,{0,0,1});
        if(field==WHEEL_CAL_YAW)CheckVector(rotated.normal,{-1,0,0});
        if(field==WHEEL_CAL_ROLL)CheckVector(rotated.right,{0,0,-1});
        delta[field]=0;
    }
}
void TestProfiles() {
    g_modelCalibration.clear();
    auto& c=g_modelCalibration[411];c.wheel[WHEEL_CAL_SIDE]=-50;
    CHECK(GetWheelCalibrationValue(WHEEL_CAL_SIDE)==-50);
    AdjustWheelCalibrationValue(WHEEL_CAL_SIDE,-1);
    CHECK(c.wheel[WHEEL_CAL_SIDE]==-51);CHECK(saveCount==1);
    g_modelCalibration[400].wheel[WHEEL_CAL_SIDE]=19;
    ResetVehiclePreset(VEHICLE_CAR);
    CHECK(c.wheel[WHEEL_CAL_SIDE]==0);CHECK(g_modelCalibration[400].wheel[WHEEL_CAL_SIDE]==19);
    c.wheel[WHEEL_CAL_SIDE]=13;activeMode=MODE_DEFAULT;
    ResetVehiclePreset(VEHICLE_CAR);CHECK(c.wheel[WHEEL_CAL_SIDE]==13);
    activeMode=MODE_IMMERSIVE;
    ResetVehiclePreset(VEHICLE_BIKE);CHECK(c.wheel[WHEEL_CAL_SIDE]==13);
    c.wheel[WHEEL_CAL_RADIUS]=200;
    AdjustWheelCalibrationValue(WHEEL_CAL_RADIUS,1);CHECK(c.wheel[WHEEL_CAL_RADIUS]==200);
    const int saves=saveCount;
    AdjustWheelCalibrationValue(-1,1);AdjustWheelCalibrationValue(WHEEL_CAL_SIDE,0);
    activeModel=-1;AdjustWheelCalibrationValue(WHEEL_CAL_SIDE,1);
    CHECK(GetWheelCalibrationValue(WHEEL_CAL_SIDE)==0);CHECK(saveCount==saves);
    activeModel=411;
}
void TestBars() {
    g_modelCalibration.clear();auto& c=g_modelCalibration[411];
    c.control[0][CONTROL_OFFSET_X]=99;
    CHECK(GetControlCalibrationValue(0,CONTROL_OFFSET_X)==99);
    AdjustControlCalibrationValue(0,CONTROL_OFFSET_X,1);
    CHECK(c.control[0][CONTROL_OFFSET_X]==100);
    CHECK(GetControlCalibrationValue(2,CONTROL_OFFSET_X)==0);
    ResetVehiclePreset(VEHICLE_BIKE);CHECK(c.control[0][CONTROL_OFFSET_X]==0);
    WheelVisualState visual{};visual.modelId=411;visual.bike=true;
    visual.center[0]=.02f;visual.center[1]=.2f;visual.center[2]=.7f;
    visual.right[0]=1;visual.up[1]=1;visual.normal[2]=1;visual.radius=.32f;
    visual.physicalAngle=3.14159265358979323846f*.5f;
    FillHandleVisuals(&visual);
    CheckVector({visual.center[0],visual.center[1],visual.center[2]},{.02f,.2f,.7f});
    CheckVector({visual.handlePosition[0][0],visual.handlePosition[0][1],visual.handlePosition[0][2]},{.02f,-.12f,.7f});
    CheckVector({visual.handlePosition[1][0],visual.handlePosition[1][1],visual.handlePosition[1][2]},{.02f,.52f,.7f});
    FillHandleVisuals(&visual);
    CheckVector({visual.handlePosition[0][0],visual.handlePosition[0][1],visual.handlePosition[0][2]},{.02f,-.12f,.7f});
    visual.physicalAngle=0;FillHandleVisuals(&visual);
    CheckVector({visual.handlePosition[0][0],visual.handlePosition[0][1],visual.handlePosition[0][2]},{-.30f,.2f,.7f});
    g_value[F_BIKE_DISTANCE]=30;g_value[F_BIKE_HEIGHT]=82;g_value[F_BIKE_HALF_WIDTH]=32;
    WheelVisualState built{};CHECK(BuildBikeTracking(&built));CHECK(Near(built.radius,.32f));
    CheckVector({built.center[0],built.center[1],built.center[2]},{1,2,3});
    g.CBike_IsComponentPresent=nullptr;CHECK(BuildBikeTracking(&built));
    CheckVector({built.center[0],built.center[1],built.center[2]},{0,.30f,.82f});
    g.CBike_IsComponentPresent=ComponentPresent;
    CHECK(!BuildBikeTracking(nullptr));
}
void TestPersistence() {
    g_modelCalibration.clear();
    ReadWheelLine("WheelCalib.411.0=-47");CHECK(g_modelCalibration[411].wheel[0]==-47);
    ReadWheelLine("WheelCalib.411.4=-15");CHECK(g_modelCalibration[411].wheel[4]==-15);
    ReadWheelLine("WheelCalib.411.999=3");ReadWheelLine("WheelCalib.-1.0=3");
    CHECK(g_modelCalibration.size()==1);
    ReadWheelLine("WheelCalib.411.3=999999");CHECK(g_modelCalibration[411].wheel[3]==200);
    FILE* file=std::tmpfile();CHECK(file!=nullptr);
    WriteWheelLines(file,411,g_modelCalibration[411]);
    std::rewind(file);char line[128];std::string contents;g_modelCalibration.clear();
    while(std::fgets(line,sizeof(line),file)){contents+=line;ReadWheelLine(line);}
    std::fclose(file);
    CHECK(contents.find("WheelCalib.411.0=-47\n")!=std::string::npos);
    CHECK(g_modelCalibration[411].wheel[0]==-47);CHECK(g_modelCalibration[411].wheel[4]==-15);
    CHECK(g_modelCalibration[411].wheel[3]==200);
}
} // namespace savr::driving
int main() {
    savr::driving::TestPose();
    savr::driving::TestProfiles();
    savr::driving::TestPersistence();
    savr::driving::TestBars();
    std::printf("PASS: %d stock wheel, handlebar, calibration isolation and persistence checks\n",savr::driving::checks);
}
'''


def main():
    # Compile production bodies, including the exact save/load snippets. Stubs
    # replace only the game/Quest API and unrelated seat settings.
    math = SOURCE[SOURCE.index("struct V3 {"):SOURCE.index("double MonotonicSeconds()")]
    math += function("V3 RotateAroundAxis(")
    pose = SOURCE[SOURCE.index("struct ModelCalibration {"):SOURCE.index("int ClampField(")]
    accessors = function("int GetWheelCalibrationValue(")
    accessors += function("void AdjustWheelCalibrationValue(")
    accessors += function("void ResetVehiclePreset(")
    save_start = SOURCE.index("            for (int field = 0; field < WHEEL_CAL_FIELD_COUNT; ++field) {")
    save_end = SOURCE.index("\n        }", save_start)
    persistence = "void WriteWheelLines(FILE* file,int model,const ModelCalibration& calibration) {\n"
    persistence += SOURCE[save_start:save_end] + "\n}\n"
    load_start = SOURCE.index('} else if (std::sscanf(line, "WheelCalib.') + 2
    load_end = SOURCE.index("} else {", load_start)
    persistence += "void ReadWheelLine(const char* line) { int model=0,mode=0,value=0,hand=0; if(false) {} "
    persistence += SOURCE[load_start:load_end] + "}\n}\n"
    source = PRELUDE + math + pose + r"""
bool IsBicycleModel(int) {return false;}
bool GetActivePlayerBike(void** vehicle,void*) {static char fake[2048]{};std::uint16_t model=411;std::memcpy(fake+0x32,&model,2);*vehicle=fake;return true;}
bool ReadScaledBikeLeanFrame(void*,V3* right,V3* forward,V3* up,V3* origin) {*right={1,0,0};*forward={0,1,0};*up={0,0,1};*origin={0,0,0};return true;}
bool WorldPointToTracking(V3 p,V3* out) {*out=p;return true;}
""" + function("bool BuildBikeTracking(") + function("int ClampControlValue(") + function("void FillHandleVisuals(") + function("bool IsControlCalibrationAvailable(") + function("int GetControlCalibrationValue(") + function("void AdjustControlCalibrationValue(") + accessors + persistence + HARNESS

    msvc = sorted(Path("C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC").iterdir())[-1]
    sdk = Path("C:/Program Files (x86)/Windows Kits/10")
    version = sorted((sdk / "Include").iterdir())[-1].name
    env = os.environ.copy()
    env["INCLUDE"] = ";".join(str(p) for p in [msvc / "include", *[sdk / "Include" / version / n for n in ("ucrt", "shared", "um")]])
    env["LIB"] = ";".join(str(p) for p in [msvc / "lib/x64", *[sdk / "Lib" / version / n / "x64" for n in ("ucrt", "um")]])
    compiler = msvc / "bin/Hostx64/x64"
    env["PATH"] = str(compiler) + os.pathsep + env.get("PATH", "")
    with tempfile.TemporaryDirectory(prefix="savr-wheel-pose-") as temp:
        out = Path(temp)
        (out / "test.cpp").write_text(source, encoding="utf-8")
        subprocess.run([str(compiler / "cl.exe"), "/nologo", "/std:c++20", "/EHsc", "/MD",
                        "/I" + str(ROOT / "native/src"), str(out / "test.cpp"),
                        "/Fe:" + str(out / "test.exe"), "/Fo:" + str(out / "test.obj")], env=env, check=True)
        subprocess.run([str(out / "test.exe")], check=True)


if __name__ == "__main__":
    main()
