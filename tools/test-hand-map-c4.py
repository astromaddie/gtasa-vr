"""Exercise actual ownership, controller-ray, throw routing and modal input code."""
from pathlib import Path
import re,subprocess,sys
R=Path(__file__).resolve().parents[1];O=R/'build/hand-map-c4-tests';O.mkdir(parents=True,exist_ok=True)
def fn(file,name):
 s=(R/'native/src'/file).read_text();m=re.search(r'^(?:bool|void|int|float) '+name+r'\(',s,re.M);assert m,name
 a=m.start();i=s.index('{',a)+1;d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
code=r"""
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include "FrontendPointer.h"
#define CHECK(x) do {if(!(x)){std::fprintf(stderr,"FAIL %d %s\n",__LINE__,#x);std::exit(3);}}while(0)
namespace ownership {
constexpr int kHandCount=2;int gHeldSlot[2]{-1,-1},gPreferredHand=-1,active=4,calls=0;
struct Hand{bool valid=true;float trigger=0;};Hand gHands[2];
bool ValidHand(int h){return h>=0&&h<2;}bool ValidSlot(int s){return s>0&&s<13;}
int CurrentWeaponSlot(void*){return active;}int WeaponTypeInSlot(void*,int s){return s==11?46:s==0?0:31;}
void Set(void*,int s){active=s;++calls;}struct{void(*CPed_SetCurrentWeaponSlot)(void*,int)=Set;}g;
void SelectCurrentSlot(void* p,int s){if(active!=s)Set(p,s);}
"""+fn('PhysicalWeapon.cpp','AnyHeldHandLocked')+fn('PhysicalWeapon.cpp','ChooseFiringHandLocked')+r"""
void Test(){
 int ped=0;ChooseFiringHandLocked(&ped);CHECK(active==0&&calls==1); // initial load with empty hands
 for(int s:{1,2,4,8,12}){active=s;ChooseFiringHandLocked(&ped);CHECK(active==0);} // native reselects later
 int before=calls;ChooseFiringHandLocked(&ped);CHECK(calls==before);
 gHeldSlot[1]=4;ChooseFiringHandLocked(&ped);CHECK(active==4);gHeldSlot[0]=2;
 gHands[0].trigger=1;ChooseFiringHandLocked(&ped);CHECK(active==2);
 gHeldSlot[0]=-1;ChooseFiringHandLocked(&ped);CHECK(active==4);
 gHeldSlot[1]=-1;ChooseFiringHandLocked(&ped);CHECK(active==0);
 active=11;ChooseFiringHandLocked(&ped);CHECK(active==11); // preserve native parachute owner
 gHeldSlot[1]=4;ChooseFiringHandLocked(&ped);CHECK(active==4);
 std::puts("PASS: empty-hand load/reselection/release use fists; held and dual-hand selection and parachute preserved");
}
}
struct V3 {float x{},y{},z{};};struct Q{float x{},y{},z{},w{1};};
float Dot(V3 a,V3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
bool Finite(V3 a){return std::isfinite(a.x)&&std::isfinite(a.y)&&std::isfinite(a.z);}
V3 Normalized(V3 a){float n=std::sqrt(Dot(a,a));return n>1e-8f?V3{a.x/n,a.y/n,a.z/n}:V3{};}
V3 Rotate(Q q,V3 v){
 V3 t{2*(q.y*v.z-q.z*v.y),2*(q.z*v.x-q.x*v.z),2*(q.x*v.y-q.y*v.x)};
 return {v.x+q.w*t.x+q.y*t.z-q.z*t.y,v.y+q.w*t.y+q.z*t.x-q.x*t.z,v.z+q.w*t.z+q.x*t.y-q.y*t.x};
}
namespace xr {struct HandPose{bool valid=true,aimValid=true;float gripPos[3]{},aimOri[4]{0,0,0,1};};HandPose poses[2];int fallbackCalls=0;void GetHandPoses(HandPose* h){++fallbackCalls;std::memcpy(h,poses,sizeof(poses));}}
namespace physicalweapon {bool snapshot=true;bool GetHandPosesSnapshot(xr::HandPose* h){std::memcpy(h,xr::poses,sizeof(xr::poses));return snapshot;}int FiringHand(){return 1;}}
namespace vrcam {
std::atomic<bool> g_stereoActive{true};bool g_vrBaseValid=true;struct{bool valid=true;}g_origin;
float bodyYaw=0;
V3 TrackingVectorToGame(V3 v){return {v.x*std::cos(bodyYaw)+v.z*std::sin(bodyYaw),v.x*std::sin(bodyYaw)-v.z*std::cos(bodyYaw),v.y};}
V3 TrackingPointToGame(V3 v){v=TrackingVectorToGame(v);return {v.x+100,v.y-20,v.z+30};}
"""+fn('VrCamera.cpp','GetControllerThrowRay')+r"""
int modelRayCalls=0;bool GetWeaponFireRay(int,int,float* p,float* d){++modelRayCalls;p[0]=10;p[1]=20;p[2]=30;d[0]=-1;d[1]=d[2]=0;return true;}
bool TrackingPointToWorld(const float*,float*){return false;}
}
namespace xr {bool GetHeadPose(float*,float*){return false;}}
namespace throws {
using Vec3=V3;int player,heldType=39;
void* Player(int){return &player;}void* Vehicle(int,bool){return nullptr;}
struct {void*(*FindPlayerPed)(int)=Player;void*(*FindPlayerVehicle)(int,bool)=Vehicle;bool(*CWorld_ProcessLineOfSight)(...)=nullptr;void** CWorld_pIgnoreEntity=nullptr;}g;
constexpr float kQuestVcThrowSpeed=0.46f;constexpr int kColPointSize=0x2c;
float LengthSquared(Vec3 v){return Dot(v,v);}int WeaponTypeInHeldSlot(void*,int){return heldType;}
"""+fn('Throwable.cpp','BuildLaunch')+r"""
void Test(){
 for(int h:{0,1})for(int body:{0,1,2,3})for(int yaw:{0,1,2,3}){
  float a=yaw*1.57079632679f;vrcam::bodyYaw=body*1.57079632679f;
  xr::poses[h].aimOri[1]=std::sin(a/2);xr::poses[h].aimOri[3]=std::cos(a/2);
  xr::poses[h].gripPos[0]=h?0.3f:-0.3f;xr::poses[h].gripPos[1]=1.2f;xr::poses[h].gripPos[2]=-0.5f;
  Vec3 p{},v{};int hand=-1;heldType=39;int before=vrcam::modelRayCalls;
  CHECK(BuildLaunch(&player,39,p,v,hand,h)&&hand==h&&vrcam::modelRayCalls==before);
  // Independent analytic expectation for controller yaw + body yaw, in GTA XY.
  float total=a+vrcam::bodyYaw;
  CHECK(std::abs(v.x+0.46f*std::sin(total))<1e-5f&&std::abs(v.y-0.46f*std::cos(total))<1e-5f&&std::abs(v.z)<1e-5f);
  auto expected=vrcam::TrackingPointToGame({h?0.3f:-0.3f,1.2f,-0.5f});
  CHECK(std::abs(p.x-expected.x)<1e-5f&&std::abs(p.y-expected.y)<1e-5f&&std::abs(p.z-expected.z)<1e-5f);
  Vec3 p2{},v2{};CHECK(BuildLaunch(&player,39,p2,v2,hand,h));CHECK(std::memcmp(&v,&v2,sizeof(v))==0); // preview/release
 }
 Vec3 p{},v{};int hand=-1;
 for(int type:{16,17,18}){heldType=type;CHECK(BuildLaunch(&player,type,p,v,hand,1));CHECK(std::abs(v.x+0.46f)<1e-6f&&p.x==10);}
 heldType=39;xr::poses[1].aimValid=false;CHECK(!BuildLaunch(&player,39,p,v,hand,1));xr::poses[1].aimValid=true;
 vrcam::g_origin.valid=false;CHECK(!BuildLaunch(&player,39,p,v,hand,1));vrcam::g_origin.valid=true;
 CHECK(!BuildLaunch(&player,39,p,v,hand,2));physicalweapon::snapshot=false;CHECK(BuildLaunch(&player,39,p,v,hand,1)&&xr::fallbackCalls>0);
 std::puts("PASS: C4 controller direction across 64 hand/body/yaw cases, hand origin, preview/release parity, invalid tracking; grenade/molotov routes preserved");
}
}
namespace maptest {
std::atomic<bool> g_blocked{false};std::atomic<float> g_gripL{0},g_gripR{0};unsigned char memory[256]{};unsigned char* g_mobileMenu=memory;
int nativeCalls=0;void Native(float){++nativeCalls;}void(*g_origMapUpdate)(float)=Native;
constexpr float kGripOn=.6f,kMinSize=152,kMaxSize=800,kZoomSpeed=1.1f;
float ReadF(std::size_t o){float f;std::memcpy(&f,memory+o,4);return f;}void WriteF(std::size_t o,float f){std::memcpy(memory+o,&f,4);}
"""+fn('MapZoom.cpp','ClampCentre')+fn('MapZoom.cpp','OnMapUpdate')+r"""
void Test(){g_gripR=1;WriteF(0x78,400);g_blocked=true;OnMapUpdate(.016f);CHECK(nativeCalls==0&&ReadF(0x78)==400);g_blocked=false;OnMapUpdate(.016f);CHECK(nativeCalls==1&&ReadF(0x78)>400);}
}
int main(){
 ownership::Test();throws::Test();maptest::Test();
 using namespace savr::frontendpointer;State s;
 auto tick=[&](bool blocked,bool press,float u=.5f,float v=.5f){return s.Update(blocked,press,true,u,v,1000,500);};
 CHECK(tick(false,true).action==Action::Down);CHECK(tick(false,true,.51f).action==Action::None);
 auto up=tick(false,false,.51f);CHECK(up.action==Action::Up&&up.x==500);
 CHECK(tick(false,true).action==Action::Down);CHECK(tick(false,true,.8f).action==Action::Move);
 CHECK(tick(true,true).action==Action::Cancel);for(int i=0;i<10;++i)CHECK(tick(true,true).action==Action::None);
 CHECK(tick(false,true).action==Action::None);CHECK(tick(false,false).action==Action::None);
 CHECK(tick(false,true).action==Action::Down);CHECK(tick(false,false).action==Action::Up);
 tick(true,false);CHECK(tick(false,true).action==Action::None);tick(false,false);CHECK(tick(false,true).action==Action::Down);
 std::puts("PASS: map update/zoom blocked behind overlay; tap jitter and drag preserved; one cancellation, held-through-close and fresh-press rearm");
}
"""
(O/'test.cpp').write_text(code)
vc=Path(r'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
c=O/'run.cmd';c.write_text(f'@echo off\ncall "{vc}" >nul\ncl /nologo /std:c++20 /EHsc /W3 /I"{R / "native/src"}" "{O / "test.cpp"}" /Fe:"{O / "test.exe"}" /Fo:"{O / "test.obj"}"\nif errorlevel 1 exit /b 1\n"{O / "test.exe"}"\n')
p=subprocess.run(['cmd','/c',str(c)],cwd=O,capture_output=True,text=True,encoding='utf8',errors='replace');print(p.stdout);print(p.stderr);sys.exit(p.returncode)
