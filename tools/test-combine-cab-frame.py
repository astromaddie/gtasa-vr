"""Exercise production camera post-processing and late wheel reprojection on slopes."""
from pathlib import Path
import subprocess
import sys

R = Path(__file__).resolve().parents[1]
O = R / 'build/combine-cab-tests'
O.mkdir(parents=True, exist_ok=True)
cam = (R / 'native/src/VrCamera.cpp').read_text(encoding='utf8')
drive = (R / 'native/src/Driving.cpp').read_text(encoding='utf8')


def function(source, signature):
    start = source.index(signature)
    p = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[p] == '{') - (source[p] == '}')
        p += 1
    return source[start:p]


def between(source, start, end):
    a = source.index(start)
    return source[a:source.index(end, a)]


predicate = between(cam, '                const bool rigidCombineCabin =',
                    '                constexpr float kEyeHeightStanding')
smoothing = between(cam, '                    // Suspension steps over kerbs',
                    '                    anchorReady = true;')
tilt = between(cam, '                        const bool carTilt =',
               '                        } else if (vehicleIsBike') + '\n}\n'
offset = between(cam, '                        const V3 heightAxis =',
                 '                        static void* loggedVehicle')
projection = between(drive, '    const V3 worldCenter=wheel.center;',
                     '    static int loggedModel=-1;')
# The production call must follow publication of the current camera frame.
assert 'g_vrBase = base; g_vrBaseValid = true;\n                        driving::RefreshVisualTracking();' in cam

code = r'''
#include "Driving.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
using namespace savr;
#define CHECK(e) do{if(!(e)){std::fprintf(stderr,"FAIL %d %s\n",__LINE__,#e);std::exit(3);}}while(0)
struct V3{float x{},y{},z{};};
V3 operator+(V3 a,V3 b){return{a.x+b.x,a.y+b.y,a.z+b.z};}
V3 operator-(V3 a,V3 b){return{a.x-b.x,a.y-b.y,a.z-b.z};}
V3 operator*(V3 a,float f){return{a.x*f,a.y*f,a.z*f};}
float Dot(V3 a,V3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
V3 Cross(V3 a,V3 b){return{a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
float Length(V3 a){return std::sqrt(Dot(a,a));}
V3 Normalized(V3 a){return a*(1.f/Length(a));}
bool Near(V3 a,V3 b){return Length(a-b)<.0004f;}
struct Q{float x{},y{},z{},w{1};};
V3 Rotate(Q q,V3 v){V3 xyz{q.x,q.y,q.z};V3 t=Cross(xyz,v)*2;return v+t*q.w+Cross(xyz,t);}
struct Basis{V3 right,forward,up,pos;} g_vrBase;
struct{V3 pos;Q ori;}g_origin;
double clockMs{};double NowMs(){return clockMs;}
int appearance=1;
int Appearance(const void*){return appearance;}
void* PlayerVehicle(int,bool);void* PlayerPed(int);bool Entering();bool IsDriver(const void*,const void*);
struct{
 int(*CVehicle_GetVehicleAppearance)(const void*)=Appearance;
 void*(*FindPlayerVehicle)(int,bool)=PlayerVehicle;
 void*(*FindPlayerPed)(int)=PlayerPed;
 bool(*PlayerIsEnteringCar)()=Entering;
 bool(*CVehicle_IsDriver)(const void*,const void*)=IsDriver;
}g;
namespace savr::vrcam{bool stereo=true;bool IsStereoActive(){return stereo;}}
namespace savr::driving {
bool tiltEnabled=false;
bool thirdPerson=false;
bool ThirdPersonViewActive(){return thirdPerson;}
bool CarCameraTiltEnabled(){return tiltEnabled;}
bool BoatCameraTiltEnabled(){return false;}
}
''' + function(cam, 'V3 GameVectorToTracking(') + r'''
bool WorldPointToTracking(V3 p,V3* out){*out=g_origin.pos+GameVectorToTracking(p-g_vrBase.pos);return true;}
unsigned char entity[0x900]{},chassis[0x100]{},otherFrame[0x100]{};
bool entering=false,driver=true;void* playerVehicle=entity;
void* PlayerVehicle(int,bool){return playerVehicle;}void* PlayerPed(int){return entity;}
bool Entering(){return entering;}bool IsDriver(const void*,const void*){return driver;}
V3 vr,vf,vu,vp;
V3 World(V3 p){return vp+vr*p.x+vf*p.y+vu*p.z;}
Basis Camera(V3 eye,V3 calibration,bool thirdPersonView=false,bool enteringVehicle=false,bool valid=true){
 void* vehicle=entity;bool vehicleBasisValid=valid;
 V3 vehicleRight=vr,vehicleForward=vf,vehicleUp=vu;
 V3 anchorPosition=World(eye);
 float yaw=std::atan2(-vf.x,vf.y);
 V3 fwd{-std::sin(yaw),std::cos(yaw),0},right{std::cos(yaw),std::sin(yaw),0};
 Basis base{right*-1,fwd,{0,0,1},{}};
 bool aircraftTilt=false,rearPassenger=false;
 float seatSide=calibration.x,seatDistance=calibration.y,seatHeight=calibration.z;
 constexpr float kEyeForward=.12f;
''' + predicate + smoothing + tilt + offset + r'''
 return base;
}
struct Wheel{V3 center,right,up,normal;float radius;};
namespace savr::driving {
float appliedAngle=0;int rotationCalls=0;
void NativeComponentRotation(void*,void* frame,int axis,float angle,bool reset){
 ++rotationCalls;appliedAngle=angle;
 if(!frame||axis!=1||!reset)return;
 // Retail SetRotateY(angle), followed by restoring the frame translation.
 V3 r{std::cos(angle),0,-std::sin(angle)},u{std::sin(angle),0,std::cos(angle)};
 std::memcpy(static_cast<char*>(frame)+0x20,&r,sizeof(r));
 std::memcpy(static_cast<char*>(frame)+0x40,&u,sizeof(u));
}
auto g_origComponentRotation=NativeComponentRotation;
void TraceCombineCabin(float,const void*){}
''' + function(drive, 'void OnComponentRotation(') + r'''
std::mutex g_stateMutex;WheelVisualState g_visual;
bool available=true;int wheelCalls=0,bikeCalls=0;bool g_wheelVisible=true;
bool BuildWheelTracking(WheelVisualState* visual){
 ++wheelCalls;if(!available)return false;
 int modelId=532;
 V3 worldNormal=vr*.0000001f+vf*.3818912f+vu*-.9242073f;
 V3 worldRight=vr,worldUp=Normalized(Cross(worldRight,worldNormal));
 Wheel wheel{World({.0252865f,3.2100763f,2.4369435f}),worldRight,worldUp,worldNormal,.2177257f};
''' + projection.replace('g_wheelVisible.load()', 'g_wheelVisible') + r'''
 return true;
}
bool BuildBikeTracking(WheelVisualState* visual){++bikeCalls;return true;}
void FillHandleVisuals(WheelVisualState* v){
 for(int h=0;h<2;++h)for(int a=0;a<3;++a)v->handlePosition[h][a]=v->center[a]+v->right[a]*(h?1:-1)*v->radius;
}
''' + 'bool CabinVisualContext(){return true;} void ClearInteractionLocked(){g_visual={};}\n'+function(drive, 'void RefreshVisualTracking()') + r'''
}
void Frame(float yaw,float pitch,float roll,V3 pos){
 // Independent rigid-body composition Rz(yaw) Rx(pitch) Ry(roll).
 auto rot=[&](V3 v){
  V3 r{std::cos(roll)*v.x+std::sin(roll)*v.z,v.y,-std::sin(roll)*v.x+std::cos(roll)*v.z};
  V3 p{r.x,std::cos(pitch)*r.y-std::sin(pitch)*r.z,std::sin(pitch)*r.y+std::cos(pitch)*r.z};
  return V3{std::cos(yaw)*p.x-std::sin(yaw)*p.y,std::sin(yaw)*p.x+std::cos(yaw)*p.y,p.z};
 };
 vr=rot({1,0,0});vf=rot({0,1,0});vu=rot({0,0,1});vp=pos;
}
int main(){
 using namespace savr::driving;
 std::uint16_t id=532;std::memcpy(entity+0x32,&id,2);
 void* chassisPtr=chassis;std::memcpy(entity+0x808,&chassisPtr,sizeof(chassisPtr));
 const V3 wheelLocal{.0252865f,3.2100763f,2.4369435f};
 int frames=0;float nativeCabRoll=0,maxUnfixedDrift=0;
 for(V3 eye:{V3{-1.006f,2.997006f,1.191899f},V3{.028021f,2.540719f,2.810999f}})
 for(V3 cal:{V3{0,-.04f,0},V3{.37f,-.65f,.42f}})
 for(bool setting:{false,true}) {
  tiltEnabled=setting;
  g_visual={};g_visual.active=true;g_visual.modelId=532;
  g_visual.grabbed[0]=true;g_visual.markerVisible[1]=true;
  g_visual.physicalAngle=.25f;g_visual.steering=-.4f;
  for(int f=0;f<240;++f){
   ++frames;clockMs+=13.89;
   if(f%40==0){float a=.15f*f;g_origin={{.2f,1.6f,-.3f},{0,std::sin(a/2),0,std::cos(a/2)}};}
   Frame(f*.021f,.48f*std::sin(f*.17f),.36f*std::cos(f*.23f),{100+f*.1f,-55+f*.07f,20+.4f*std::sin(f*.7f)});
   // Input used the old camera, exactly as in the production ordering.
   if(f)CHECK(BuildWheelTracking(&g_visual));
   Basis base=Camera(eye,cal);
   CHECK(Near(base.right,vr*-1)&&Near(base.forward,vf)&&Near(base.up,vu));
   CHECK(Near(base.pos,World(eye+cal+V3{0,.12f,0})));
   g_vrBase=base;
   RefreshVisualTracking();
   // CAutomobile::PreRender applies chassis self-level rotation after camera update.
   nativeCabRoll=.95f*nativeCabRoll+.05f*std::asin(vr.z);
   OnComponentRotation(entity,chassis,1,nativeCabRoll,true);
   CHECK(appliedAngle==0);
   V3 chassisRight{},chassisUp{};
   std::memcpy(&chassisRight,chassis+0x20,sizeof(V3));
   std::memcpy(&chassisUp,chassis+0x40,sizeof(V3));
   V3 drawnWheel=World(chassisRight*wheelLocal.x+V3{0,1,0}*wheelLocal.y+chassisUp*wheelLocal.z);
   V3 drawnTracking{};CHECK(WorldPointToTracking(drawnWheel,&drawnTracking));
   CHECK(Near(drawnTracking,{g_visual.center[0],g_visual.center[1],g_visual.center[2]}));
   V3 oldDrawnWheel=World({std::cos(nativeCabRoll)*wheelLocal.x+std::sin(nativeCabRoll)*wheelLocal.z,
      wheelLocal.y,-std::sin(nativeCabRoll)*wheelLocal.x+std::cos(nativeCabRoll)*wheelLocal.z});
   maxUnfixedDrift=std::max(maxUnfixedDrift,Length(oldDrawnWheel-World(wheelLocal)));
   V3 delta=wheelLocal-eye-cal-V3{0,.12f,0};
   V3 expected=g_origin.pos+Rotate(g_origin.ori,{delta.x,delta.z,-delta.y});
   CHECK(Near({g_visual.center[0],g_visual.center[1],g_visual.center[2]},expected));
   CHECK(g_visual.grabbed[0]&&g_visual.markerVisible[1]);
   CHECK(g_visual.physicalAngle==.25f&&g_visual.steering==-.4f);
   V3 n=Rotate(g_origin.ori,{.0000001f,-.9242073f,-.3818912f});
   CHECK(Near({g_visual.normal[0],g_visual.normal[1],g_visual.normal[2]},n));
  }
 }
 CHECK(maxUnfixedDrift>.2f);
 // Native animation is retained for every other component/context.
 auto forwards=[&](void* v,void* f,int axis,bool reset){int before=rotationCalls;OnComponentRotation(v,f,axis,.3f,reset);CHECK(rotationCalls==before+1&&appliedAngle==.3f);};
 forwards(entity,otherFrame,1,true);forwards(entity,chassis,0,true);forwards(entity,chassis,1,false);
 vrcam::stereo=false;forwards(entity,chassis,1,true);vrcam::stereo=true;
 thirdPerson=true;forwards(entity,chassis,1,true);thirdPerson=false;
 entering=true;forwards(entity,chassis,1,true);entering=false;
 driver=false;forwards(entity,chassis,1,true);driver=true;
 playerVehicle=nullptr;forwards(entity,chassis,1,true);playerVehicle=entity;
 id=531;std::memcpy(entity+0x32,&id,2);forwards(entity,chassis,1,true);
 id=532;std::memcpy(entity+0x32,&id,2);
 forwards(nullptr,chassis,1,true);forwards(entity,nullptr,1,true);
 // Switching back from a banked external view must neutralize old rotation.
 NativeComponentRotation(entity,chassis,1,.4f,true);
 OnComponentRotation(entity,chassis,1,.4f,true);CHECK(appliedAngle==0);
 // Existing car horizon choice, entry and chase paths must remain available.
 Frame(0,.3f,.2f,{0,0,0});tiltEnabled=false;
 id=411;std::memcpy(entity+0x32,&id,2);
 CHECK(Near(Camera({0,0,1},{}).up,{0,0,1}));
 id=532;std::memcpy(entity+0x32,&id,2);
 CHECK(Near(Camera({0,0,1},{},true).up,{0,0,1}));
 CHECK(Near(Camera({0,0,1},{},false,true).up,{0,0,1}));
 CHECK(Near(Camera({0,0,1},{},false,false,false).up,{0,0,1}));
 int before=wheelCalls;g_visual.modelId=411;RefreshVisualTracking();CHECK(wheelCalls==before);
 g_visual.bike=true;RefreshVisualTracking();CHECK(bikeCalls==1);
 g_visual.active=false;RefreshVisualTracking();CHECK(bikeCalls==1);
 std::printf("PASS: %d production camera/wheel/render frames; native chassis self-level reproduced %.3fm of drift and removed by actual callback; NPC/other component/entry/chase/non-VR preserved; pitch/roll/bumps/turns, seat offsets, custom calibration, recenter and held-wheel state\n",frames,maxUnfixedDrift);
}
'''
(O / 'test.cpp').write_text(code, encoding='utf8')
vc = Path(r'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
cmd = O / 'run.cmd'
cmd.write_text(f'@echo off\ncall "{vc}" >nul\ncl /nologo /std:c++20 /EHsc /W3 /I"{R / "native/src"}" "{O / "test.cpp"}" /Fe:"{O / "test.exe"}" /Fo:"{O / "test.obj"}"\nif errorlevel 1 exit /b 1\n"{O / "test.exe"}"\n', encoding='utf8')
p = subprocess.run(['cmd', '/c', str(cmd)], cwd=O, capture_output=True, text=True, encoding='utf8', errors='replace')
print(p.stdout)
print(p.stderr)
sys.exit(p.returncode)
