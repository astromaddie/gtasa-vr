"""Production comfort policy, native RC isolation, live cabin publication tests."""
from pathlib import Path
import subprocess,re,sys
R=Path(__file__).resolve().parents[1];O=R/'build/zero-comfort-tests';O.mkdir(parents=True,exist_ok=True)
def fn(name):
 s=(R/'native/src/Driving.cpp').read_text();m=re.search(r'^(?:bool|void) '+name+r'\(',s,re.M);assert m,name
 a=m.start();i=s.index('{',a)+1;d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
code=r"""
#include "MissionComfort.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <limits>
int checks=0;
#define CHECK(x) do{++checks;if(!(x)){std::printf("FAIL: %d %s\n",__LINE__,#x);std::exit(1);}}while(0)
namespace rc {
alignas(16) char vehicle[0x500]{},other[0x500]{};float handling[22]{};
bool allowed=true;int modelId=464;void* remote=vehicle;
bool VrGameplayInputAllowed(){return allowed;}
void* GetRemoteControlledVehicle(){return remote;}
int ControlledVehicleModel(){return modelId;}
using FlyingControlFn=void(*)(void*,int,float,float,float,float);
FlyingControlFn g_origFlyingControl=nullptr;thread_local bool g_insideRcFlying=false;
"""+fn('IsRemoteBaron')+fn('OnFlyingControl')+r"""
bool expected=false;int calls=0;
void Original(void* v,int,float a,float b,float c,float d){
 ++calls;CHECK(a==.1f&&b==.2f&&c==.3f&&d==.4f);
 float* p=*reinterpret_cast<float**>(static_cast<char*>(v)+0x4b0);
 CHECK((p!=handling)==expected);
 if(expected){CHECK(p[6]==handling[6]*.5f);CHECK(p[7]==handling[7]*3);CHECK(p[8]==handling[8]*.7f);
 for(int i=0;i<22;++i)if(i!=6&&i!=7&&i!=8)CHECK(p[i]==handling[i]);}
}
void Test(){
 *reinterpret_cast<float**>(vehicle+0x4b0)=handling;*reinterpret_cast<float**>(other+0x4b0)=handling;
 for(int i=0;i<22;++i)handling[i]=float(i);handling[6]=.015f;handling[7]=-.005f;handling[8]=.005f;
 float before[22];std::memcpy(before,handling,sizeof(before));g_origFlyingControl=Original;
 for(int model:{1,3}){expected=true;OnFlyingControl(vehicle,model,.1f,.2f,.3f,.4f);CHECK(*reinterpret_cast<float**>(vehicle+0x4b0)==handling);CHECK(!g_insideRcFlying);CHECK(std::memcmp(before,handling,sizeof(before))==0);}
 expected=false;
 OnFlyingControl(other,3,.1f,.2f,.3f,.4f);modelId=465;OnFlyingControl(vehicle,3,.1f,.2f,.3f,.4f);modelId=464;
 allowed=false;OnFlyingControl(vehicle,3,.1f,.2f,.3f,.4f);allowed=true;
 remote=nullptr;OnFlyingControl(vehicle,3,.1f,.2f,.3f,.4f);remote=vehicle;
 OnFlyingControl(vehicle,6,.1f,.2f,.3f,.4f);
 g_insideRcFlying=true;OnFlyingControl(vehicle,3,.1f,.2f,.3f,.4f);g_insideRcFlying=false;
 CHECK(std::memcmp(before,handling,sizeof(before))==0);
 std::puts("PASS: RC Baron only, both native flight modes, private handling copy, exact restore, blocked/NPC/other RC/recursive calls unchanged");
}
}
namespace cabin {
bool stereo=true,third=false,remote=false,seated=true,cutscene=false,entering=false;
unsigned char cam[0x100]{};bool Entering(){return entering;}
struct{bool* CCutsceneMgr_ms_running=&cutscene;void* TheCamera=cam;bool(*PlayerIsEnteringCar)()=Entering;}g;
namespace vrcam{bool IsStereoActive(){return stereo;}}
bool ThirdPersonViewActive(){return third;}void* GetRemoteControlledVehicle(){return remote?cam:nullptr;}bool HasPlayerVehicle(){return seated;}
struct WheelVisualState{bool active{},dashAnchorValid{},grabbed[2]{};};
WheelVisualState g_visual{};std::mutex g_stateMutex;
void ClearInteractionLocked(){g_visual={};}
"""+fn('CabinVisualContext')+fn('GetWheelVisualState')+r"""
void Test(){
 WheelVisualState out{};
 g_visual={true,true,{true,true}};CHECK(GetWheelVisualState(&out)&&out.active&&out.grabbed[0]);
 for(bool* gate:{&third,&remote,&cutscene,&entering}){*gate=true;g_visual={true,true,{true,true}};CHECK(!GetWheelVisualState(&out)&&!out.active&&!out.dashAnchorValid&&!g_visual.active);*gate=false;}
 for(bool* gate:{&stereo,&seated}){*gate=false;g_visual={true,true,{true,true}};CHECK(!GetWheelVisualState(&out)&&!out.active&&!out.dashAnchorValid);*gate=true;}
 cam[0x43]=1;g_visual={true,true,{true,true}};CHECK(!GetWheelVisualState(&out)&&!out.active);cam[0x43]=0;
 CHECK(!GetWheelVisualState(nullptr));g_visual={true,true,{true,true}};CHECK(GetWheelVisualState(&out));
 std::puts("PASS: cabin hidden and stale grabs cleared for formal/scripted cutscene, external camera, exit, entry, RC and theater; live cockpit restored");
}
}
int main(){
 using namespace savr::missioncomfort;
 CHECK(CameraAtEye(.30f,.28f,-.06f,.04f,.99f,false));
 CHECK(!CameraAtEye(.6f,.55f,-.06f,.04f,.99f,false));
 CHECK(!CameraAtEye(.30f,.28f,-.06f,.04f,.8f,false));
 CHECK(!CameraAtEye(.30f,.28f,-.25f,.04f,.99f,false));
 CHECK(!CameraAtEye(.40f,.30f,-.10f,.04f,.92f,false));
 CHECK(CameraAtEye(.40f,.30f,-.10f,.04f,.92f,true));
 CHECK(!CameraAtEye(.5f,.30f,-.10f,.04f,.92f,true));
 CHECK(!CameraAtEye(.30f,.28f,-.06f,.04f,std::numeric_limits<float>::quiet_NaN(),false));
 for(float side:{-.17f,.17f})CHECK(CameraAtEye(.34f,.28f,-.06f,side,.99f,false));
 float last=-2;
 for(int i=-100;i<=100;i++){float x=i/100.f;float y=RcAxis(x);CHECK(std::isfinite(y)&&y>=last&&std::abs(y)<=1);CHECK(std::abs(y+RcAxis(-x))<.00001f);last=y;}
 CHECK(RcAxis(.1f)==0&&RcAxis(-.1f)==0&&RcAxis(1)==1&&RcAxis(-1)==-1);
 CHECK(RcAxis(.5f)<.3f&&RcAxis(std::numeric_limits<float>::quiet_NaN())==0);
 std::puts("PASS: close intentional photo pose, both hands, retention hysteresis; monotonic RC curve with deadzone and full authority");
 rc::Test();cabin::Test();std::printf("PASS: %d checks\n",checks);
}
"""
(O/'test.cpp').write_text(code)
vc=Path(r'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
p=O/'run.cmd';p.write_text(f'@echo off\ncall "{vc}" >nul\ncl /nologo /std:c++20 /EHsc /W3 /I"{R / "native/src"}" "{O / "test.cpp"}" /Fe:"{O / "test.exe"}" /Fo:"{O / "test.obj"}"\nif errorlevel 1 exit /b 1\n"{O / "test.exe"}"\n')
p=subprocess.run(['cmd','/c',str(p)],cwd=O,capture_output=True,text=True,encoding='utf8',errors='replace');print(p.stdout);print(p.stderr);sys.exit(p.returncode)
