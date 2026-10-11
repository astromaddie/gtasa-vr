"""Production control migration/toggle and seated camera branch regression harness."""
from pathlib import Path
import os
import subprocess,sys,re
R=Path(__file__).resolve().parents[1];O=R/'build/standard-controls-tests';O.mkdir(parents=True,exist_ok=True)
loc=(R/'native/src/Locomotion.cpp').read_text(encoding='utf8').replace('#include "Log.h"','').replace('#include "StoragePaths.h"', '#include <string>\nnamespace savr::storage { inline const char* FilesPath(const char*) { return "test-locomotion.ini"; } }').replace('/sdcard/Android/data/com.rockstargames.gtasa/files/vr_locomotion.ini','test-locomotion.ini')
cam=(R/'native/src/VrCamera.cpp').read_text(encoding='utf8');a=cam.index('                    const int seatedAppearance =');z=cam.index('                    // Suspension steps over kerbs',a)
def fn(s,name):
 m=re.search(r'^bool '+name+r'\(',s,re.M);a=m.start();p=s.index('{',a)+1;d=1
 while d:d+=(s[p]=='{')-(s[p]=='}');p+=1
 return s[a:p]
sprint=fn((R/'native/src/Driving.cpp').read_text(encoding='utf8'),'OnGetSprint')
assert 'ApplyWalkLimit' not in cam and 'ApplyWalkLimit' not in loc
assert 'ApplyWalkLimit' not in (R/'native/src/main.cpp').read_text(encoding='utf8')
code=r'''
#include <cstdlib>
#include <atomic>
#include <cstring>
#include "Symbols.h"
#include "TrackingRecovery.h"
#include "VehicleCabin.h"
#include "FrameViewButton.h"
#include <limits>
#define LOGI(...) ((void)0)
#define LOGW(...) ((void)0)
#define CHECK(e) do{if(!(e)){std::fprintf(stderr,"FAIL %d %s\n",__LINE__,#e);std::exit(3);}}while(0)
'''+loc+r'''
using namespace savr;
using namespace savr::locomotion;
namespace savr {GameSymbols g{};
namespace vrcam {bool stereo=true,crouched=false;bool IsStereoActive(){return stereo;}bool IsCrouched(){return crouched;}}
namespace driving {
std::atomic<bool> g_inputBlocked{};bool vehicle=false;int fallbackCalls=0;
bool HasPlayerVehicle(){return vehicle;}
bool Original(void*,int){++fallbackCalls;return true;}
auto g_origSprint=Original;
'''+sprint+r'''
}}

struct V3{float x{},y{},z{};};
V3 operator+(V3 a,V3 b){return{a.x+b.x,a.y+b.y,a.z+b.z};}
V3 operator-(V3 a,V3 b){return{a.x-b.x,a.y-b.y,a.z-b.z};}
V3 operator*(V3 a,float f){return{a.x*f,a.y*f,a.z*f};}
float Dot(V3 a,V3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
bool Finite(V3 a){return std::isfinite(a.x)&&std::isfinite(a.y)&&std::isfinite(a.z);}
void TraceTracking(const char*,V3){}
double now=0;double NowMs(){return now;}
unsigned char bike[0x100]{};V3 liveHead{},cachedSeatLocal{},result{};
tracking::SeatLatch seatLatch;bool& cachedSeatLocalValid=seatLatch.valid;
int boneCalls=0;
int appearance=2;
int Appearance(const void*){return appearance;}
unsigned char combineModel[0x100]{},combineStructure[0x100]{};int foundModel=532;bool modelPresent=true;
void* Lookup(const char* name,int* id){CHECK(!std::strcmp(name,"combine"));*id=foundModel;return modelPresent?combineModel:nullptr;}
void SetSeat(V3 value){void* structure=combineStructure;std::memcpy(combineModel+0x90,&structure,sizeof(structure));std::memcpy(combineStructure+0x30,&value,sizeof(value));}

void Bone(void*,GameSymbols::Vec3* out,unsigned,bool){++boneCalls;*out={liveHead.x,liveHead.y,liveHead.z};}
V3 Sample(V3 vehiclePosition,V3 vehicleRight,V3 vehicleForward,V3 vehicleUp,bool rearPassenger=false){
 void* vehicle=bike;void* ped=bike;bool vehicleBasisValid=true,usedSeatedHead=false;
 V3 anchorPosition{};const char* anchorSource="";constexpr float kVehicleFallbackEyeHeight=.85f;
'''+cam[a:z]+r'''
 return anchorPosition;
}
void Write(const char* text){FILE* f=std::fopen("test-locomotion.ini","w");CHECK(f);std::fputs(text,f);std::fclose(f);Load();}
int main(){
 Write("BindA=1\nBindB=3\nBindX=2\nBindY=4\nBindL3=5\nBindR3=0\nMovementMode=2\nGestureSwim=0\n");
 // Exercise the production View release classifier and route through the real
 // persistent locomotion toggle; ordinary vehicle play uses this same global mode.
 frameview::Button viewButton;
 CHECK(viewButton.Update(true,true,frameview::Context::Gameplay,100)==frameview::Event::None);
 CHECK(viewButton.Update(false,true,frameview::Context::Gameplay,200)==frameview::Event::ShortPress);
 CHECK(frameview::Button::Route(frameview::Event::ShortPress,frameview::Context::Gameplay)==frameview::Action::ToggleGameplayView);
 int viewBefore=ViewMode();CycleViewMode(+1);CHECK(ViewMode()!=viewBefore);
 CHECK(viewButton.Update(true,true,frameview::Context::Menu,300)==frameview::Event::None);
 CHECK(viewButton.Update(false,true,frameview::Context::Menu,400)==frameview::Event::ShortPress);
 CHECK(frameview::Button::Route(frameview::Event::ShortPress,frameview::Context::Menu)==frameview::Action::Back);
 CHECK(GetButtonBinding(BIND_SRC_L3)==BIND_ACT_SPRINT && GetButtonBinding(BIND_SRC_R3)==BIND_ACT_CROUCH);
 CHECK(GetButtonBinding(BIND_SRC_A)==BIND_ACT_NONE && GetButtonBinding(BIND_SRC_X)==BIND_ACT_JUMP);
 CHECK(GetMovementMode()==2 && !GestureSwimEnabled());
 CHECK(ActionHeld(BIND_ACT_SPRINT,true,false,false,false,false,false,false)); // vehicle A unchanged
 CHECK(!ActionHeld(BIND_ACT_SPRINT,false,false,false,false,true,false,false));
 CHECK(ControlsLayout()==CONTROLS_LAYOUT_DEFAULT);
 Write("BindA=3\nBindB=1\nBindX=2\nBindY=4\nBindL3=0\nBindR3=5\n");CHECK(GetButtonBinding(BIND_SRC_A)==3 && GetButtonBinding(BIND_SRC_B)==1); // custom unchanged
 Write("BindA=2\nBindB=4\nBindX=1\nBindY=3\nBindL3=5\nBindR3=0\n");CHECK(ControlsLayout()==CONTROLS_LAYOUT_SWAPPED_HANDS);
 ApplyControlsLayout(CONTROLS_LAYOUT_DEFAULT);CHECK(GetButtonBinding(BIND_SRC_R3)==5);
 UpdateRunToggle(true,false,false,false,false);CHECK(!RunEnabled());
 UpdateRunToggle(true,true,false,true,false);CHECK(RunEnabled());
 for(int i=0;i<50;++i)UpdateRunToggle(true,true,false,true,false);CHECK(RunEnabled());
 UpdateRunToggle(true,false,false,false,false);CHECK(RunEnabled());
 UpdateRunToggle(true,true,false,true,false);CHECK(!RunEnabled());
 UpdateRunToggle(true,false,false,false,false);UpdateRunToggle(true,true,false,true,false);CHECK(RunEnabled());
 UpdateRunToggle(true,true,false,true,true);CHECK(!RunEnabled());
 UpdateRunToggle(true,true,false,true,false);CHECK(!RunEnabled()); // asymmetric chord release
 UpdateRunToggle(true,false,false,false,false);UpdateRunToggle(true,true,false,true,false);CHECK(RunEnabled());
 UpdateRunToggle(true,false,true,false,true);CHECK(!RunEnabled());
 UpdateRunToggle(false,true,false,true,false);UpdateRunToggle(true,true,false,true,false);CHECK(!RunEnabled()); // held through pause
 // Exercise the actual mobile CPad hook, not just the toggle state helper.
 UpdateRunToggle(true,false,false,false,false);CHECK(!driving::OnGetSprint(nullptr,0));
 UpdateRunToggle(true,true,false,true,false);CHECK(driving::OnGetSprint(nullptr,0));
 UpdateRunToggle(true,false,false,false,false);
 for(int i=0;i<100;++i)CHECK(driving::OnGetSprint(nullptr,0)); // survives physical release
 UpdateRunToggle(true,true,false,true,false);CHECK(!driving::OnGetSprint(nullptr,0));
 CHECK(!ActionHeld(BIND_ACT_SPRINT,true,false,false,false,false,false,true)); // A has no sprint
 UpdateRunToggle(true,false,false,false,false);UpdateRunToggle(true,true,false,true,false);
 vrcam::crouched=true;CHECK(!driving::OnGetSprint(nullptr,0));vrcam::crouched=false;
 driving::vehicle=true;CHECK(!driving::OnGetSprint(nullptr,0));driving::vehicle=false;
 driving::g_inputBlocked=true;CHECK(!driving::OnGetSprint(nullptr,0));driving::g_inputBlocked=false;
 vrcam::stereo=false;CHECK(driving::OnGetSprint(nullptr,0) && driving::fallbackCalls==1);vrcam::stereo=true;
 // Exercise the actual seated camera branch with stale and animated bones, turns,
 // resets, and a moving vehicle. Sanchez must never sample those bone positions.
 g.CVehicle_GetVehicleAppearance=Appearance;g.CPed_GetBonePosition=Bone;
 std::uint16_t model=468;std::memcpy(bike+0x32,&model,2);
 for(int frame=0;frame<100;++frame){
  now=frame*50.;seatLatch.Begin(bike,frame/15,now);
  liveHead={float(frame%3),float(frame%7),float(frame%5)};
  V3 position{float(frame),float(frame*2),3};
  auto p=Sample(position,{1,0,0},{0,1,0},{0,0,1});
  CHECK(std::abs(p.x-position.x)<.0001f && std::abs(p.y-position.y+.14f)<.0001f && std::abs(p.z-3.95f)<.0001f);
 }
 CHECK(boneCalls==0);
 auto turn=Sample({0,0,0},{0,-1,0},{1,0,0},{0,0,1});CHECK(std::abs(turn.x+.14f)<.0001f && turn.y==0);
 // Other bikes and Just Business retain their native passenger/seat path.
 seatLatch.Begin(nullptr,0,0);liveHead={0,-.5f,1.2f};Sample({0,0,0},{1,0,0},{0,1,0},{0,0,1},true);CHECK(boneCalls==1);
 // Combine seat coordinates cover lateral, forward and vertical offsets.
 g.CModelInfo_GetModelInfoByName=Lookup;appearance=1;model=532;std::memcpy(bike+0x32,&model,2);
 for(V3 seat:{V3{1.006000f,2.997006f,.591899f},V3{-.028021f,2.540719f,2.210999f}}){
  SetSeat(seat);GameSymbols::Vec3 eye{};CHECK(vehiclecabin::ReadCombineEye(g,&eye));
  CHECK(std::abs(eye.x+seat.x)<.0001f && std::abs(eye.z-seat.z-.6f)<.0001f);
  const int oldBoneCalls=boneCalls;
  for(int frame=0;frame<90;++frame){
   now=frame*50.;seatLatch.Begin(bike,100+frame/15,now);
   liveHead={-900.f,float(frame),-300.f};V3 pos{float(frame*2),float(frame),13};
   auto p=Sample(pos,{1,0,0},{0,1,0},{0,0,1});
   CHECK(std::abs(p.x-pos.x-eye.x)<.0001f && std::abs(p.y-pos.y-eye.y)<.0001f && std::abs(p.z-pos.z-eye.z)<.0001f);
  }
  CHECK(boneCalls==oldBoneCalls); // stale / animated head never displaces the cab
  auto p=Sample({0,0,0},{0,-1,0},{.8f,0,.6f},{-.6f,0,.8f});
  CHECK(std::abs(p.x-(eye.y*.8f-eye.z*.6f))<.0001f && std::abs(p.y+eye.x)<.0001f && std::abs(p.z-(eye.y*.6f+eye.z*.8f))<.0001f);
 }
 GameSymbols::Vec3 eye{};foundModel=531;CHECK(!vehiclecabin::ReadCombineEye(g,&eye));foundModel=532;
 modelPresent=false;CHECK(!vehiclecabin::ReadCombineEye(g,&eye));modelPresent=true;
 void* nullStructure=nullptr;std::memcpy(combineModel+0x90,&nullStructure,sizeof(nullStructure));CHECK(!vehiclecabin::ReadCombineEye(g,&eye));
 SetSeat({0,0,std::numeric_limits<float>::quiet_NaN()});CHECK(!vehiclecabin::ReadCombineEye(g,&eye));
 SetSeat({0,20,2});CHECK(!vehiclecabin::ReadCombineEye(g,&eye));SetSeat({0,0,0});CHECK(!vehiclecabin::ReadCombineEye(g,&eye));
 int side=-98,forward=290,height=43;
 CHECK(!vehiclecabin::MigrateCombineSeat(531,1,side,forward,height));
 CHECK(!vehiclecabin::MigrateCombineSeat(532,0,side,forward,height));
 CHECK(vehiclecabin::MigrateCombineSeat(532,1,side,forward,height) && side==0 && forward==0 && height==0);
 CHECK(!vehiclecabin::MigrateCombineSeat(532,1,side,forward,height)); // idempotent
 side=-97;forward=290;height=43;CHECK(!vehiclecabin::MigrateCombineSeat(532,1,side,forward,height));CHECK(side==-97 && forward==290 && height==43);
 std::puts("PASS: legacy/custom bindings, L3 toggle/hold/release/chord/menu/crouch, normal movement axes unchanged; actual mobile sprint hook after button release, vehicle A retained, Sanchez motion/turn/recenter invariant, passenger camera preserved; combine cab, movement/tilt/recenter/stale bones, invalid model/dummy guards, exact shipped-preset migration");
}
'''
(O/'test.cpp').write_text(code,encoding='utf8')
if os.name == 'nt':
 vc=Path(r'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
 cmd=O/'run.cmd';cmd.write_text(f'@echo off\ncall "{vc}" >nul\ncl /nologo /std:c++20 /EHsc /W3 /I"{R / "native/src"}" "{O / "test.cpp"}" /Fe:"{O / "test.exe"}" /Fo:"{O / "test.obj"}"\nif errorlevel 1 exit /b 1\n"{O / "test.exe"}"\n',encoding='utf8')
 command=['cmd','/c',str(cmd)]
else:
 compiler=os.environ.get('CXX','c++')
 subprocess.run([compiler,'-std=c++20','-I',str(R/'native/src'),str(O/'test.cpp'),'-o',str(O/'test')],check=True)
 command=[str(O/'test')]
p=subprocess.run(command,cwd=O,capture_output=True,text=True,encoding='utf8',errors='replace');print(p.stdout);print(p.stderr);sys.exit(p.returncode)
