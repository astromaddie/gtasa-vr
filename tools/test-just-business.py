"""Exercise real JustBusiness detection with retail SCM and production gun/camera routes."""
from pathlib import Path
import os
import subprocess,sys,struct,re
R=Path(__file__).resolve().parents[1];O=R/'build/just-business-tests';O.mkdir(parents=True,exist_ok=True)
scm=Path(sys.argv[sys.argv.index('--scm')+1]);b=scm.read_bytes();c=struct.unpack_from('<I',b,3)[0];c=struct.unpack_from('<I',b,c+3)[0];off=struct.unpack_from('<'+'I'*struct.unpack_from('<H',b,c+16)[0],b,c+24)
(O/'smoke4.scm').write_bytes(b[off[30]:off[31]])
code=(R/'native/src/JustBusiness.cpp').read_text(encoding='utf8').replace('#include "Log.h"','').replace('#include <dlfcn.h>','')
fire_path=Path(sys.argv[sys.argv.index('--fire-source')+1]) if '--fire-source' in sys.argv else R/'native/src/VrFire.cpp'
fire=fire_path.read_text(encoding='utf8');drive=(R/'native/src/Driving.cpp').read_text(encoding='utf8')
def fn(s,name):
 m=re.search(r'^(?:void|bool|int) '+name+r'\(',s,re.M);a=m.start();p=s.index('{',a)+1;depth=1
 while depth:depth+=(s[p]=='{')-(s[p]=='}');p+=1
 return s[a:p]
constants='\n'.join(re.findall(r'^constexpr std::uintptr_t (?:kPed\w+|kWeaponStride|kPlayerWeaponModeOffset|kPadDisableControlsOffset|kPadDisableFireOffset) = .*?;',fire,re.M))
prefix=r'''
#include <algorithm>
#include <atomic>
#include <fstream>
#include <iterator>
#include <vector>
#include <cstdlib>
#include <cmath>
#include "Xr.h"
#include "VrFire.h"
#include "Driving.h"
#define LOGI(...) ((void)0)
#define CHECK(e) do {if(!(e)){std::fprintf(stderr,"FAIL %d: %s\n",__LINE__,#e);std::exit(3);}}while(0)
void* dlsym(void*,const char*){return nullptr;}
'''
stubs=r'''
namespace savr {
GameSymbols g{};
namespace vrcam {int resets{};void RequestRecenter(){++resets;}}
namespace xr {InputState input{};void GetInput(InputState& out){out=input;}}
namespace driving {
bool VehicleWeaponsImmersive(){return false;}
void EnsureInit(){}
constexpr int kRhinoModelId=432;
std::atomic<int> g_activeVehicleAppearance{2},g_activeVehicleModel{581};
std::atomic<int> g_carView{VIEW_THIRD_PERSON},g_bikeView{VIEW_THIRD_PERSON},g_airView{VIEW_THIRD_PERSON},g_boatView{VIEW_THIRD_PERSON};
'''+fn(drive,'ThirdPersonViewActive')+r'''
}
namespace vrfire {
thread_local bool g_insideScriptedFire=false;
std::atomic<PhysicalFireQuery> g_physicalFireQuery{};
'''+constants+'\n'+fn(fire,'SupportedHitscan')+'\n'+fn(fire,'IsScriptedWeaponCamera')+'\n'+fn(fire,'GetPhysicalTrigger')+'\n'+fn(fire,'PlayerFireEnabled')+r'''
}
}
using namespace savr;
using namespace savr::justbusiness;
std::uint8_t thread[0x130]{},missionLocals[2048]{},ped[0xa00]{},bike[0x1000]{},camera[0x1000]{},pad[0x140]{};
void* activeList=thread;bool driver=false,alive=true,inVehicle=true;int appearance=2,selects=0,held=-1;
std::vector<std::uint8_t> bytes;
template<class T>void Put(void* p,std::size_t off,T v){std::memcpy(static_cast<std::uint8_t*>(p)+off,&v,sizeof(v));}
void* Player(int){return ped;}
void* Vehicle(int,bool){return inVehicle?bike:nullptr;}
void* RefVehicle(int ref){return ref==517?bike:nullptr;}
bool Driver(const void*,const void*){return driver;}
bool Alive(void*){return alive;}
int Appearance(const void*){return appearance;}
void Select(void*,int slot){++selects;Put<std::int8_t>(ped,0x8dc,slot);}
void* Pad(int){return pad;}
bool Query(int type,int* hand){*hand=1;return held==4 && type==28;}
struct Vec {float x,y,z;Vec operator*(float f)const{return{x*f,y*f,z*f};}};
struct Basis {Vec right{-1,0,0},forward{0,1,0},up{0,0,1},pos{0,0,2};};
'''
# Compile the actual selected-weapon auto-hold block, with engine/ownership stubs.
phys=(R/'native/src/PhysicalWeapon.cpp').read_text(encoding='utf8')
a=phys.index('        const int selectedSlot = CurrentWeaponSlot(ped);',phys.index('void Update('));z=phys.index('        gWasScriptedWeaponCamera = scriptedGunner;',a)+len('        gWasScriptedWeaponCamera = scriptedGunner;')
stubs+=r'''
constexpr int kHandCount=2;
bool gWasScriptedWeaponCamera=false,gAwaitFirstGrip[2]{};int gLastObservedActiveSlot=-1,gHeldSlot[2]{-1,-1};
struct Drop {int slot=-1;} gDropped[2];
struct DroppedWeapon:Drop{};
bool ValidSlot(int s){return s>0&&s<13;}
int CurrentWeaponSlot(void* p){return Read<std::int8_t>(p,0x8dc);}
int WeaponTypeInSlot(void* p,int s){return Read<int>(p,0x730+s*0x20);}
int HeldHandForSlotLocked(int slot){for(int h=0;h<2;++h)if(gHeldSlot[h]==slot)return h;return -1;}
void ClearHeldLocked(int h){gHeldSlot[h]=-1;}
void GiveToHandLocked(void*,int h,int slot,const char*){gHeldSlot[h]=slot;held=slot;}
void AutoHold(){void* ped=Player(-1);const bool scriptedGunner=vrfire::IsScriptedWeaponCamera();
'''+phys[a:z]+r'''
}
'''
tests=r'''
int main(int argc,char** argv){
 CHECK(argc==2);std::ifstream f(argv[1],std::ios::binary);bytes.assign(std::istreambuf_iterator<char>(f),{});
 CHECK(bytes.size()==detail::kScriptSize && Hash(bytes.data())==detail::kScriptHash);
 CHECK(Read<std::uint16_t>(bytes.data(),18707)==0x1b2 && Read<std::uint16_t>(bytes.data(),18719)==0x713);
 g.FindPlayerPed=Player;g.FindPlayerVehicle=Vehicle;g.CVehicle_IsDriver=Driver;g.CPed_IsAlive=Alive;
 g.CVehicle_GetVehicleAppearance=Appearance;g.CPed_SetCurrentWeaponSlot=Select;g.TheCamera=camera;g.CPad_GetPad=Pad;
 scripts=&activeList;locals=missionLocals;getVehicle=RefVehicle;
 Put(thread,0x18,bytes.data());thread[0x12c]=1;std::memcpy(thread+0x10,"smoke4",6);
 Put<int>(locals,169*4,517);Put<int>(locals,98*4,19);Put<int>(ped,0x730+4*0x20,28);
 Update();CHECK(!Active() && selects==0);CHECK(driving::ThirdPersonViewActive());
 Put<int>(locals,98*4,20);Update();CHECK(Active()&&selects==1&&vrcam::resets==1);
 CHECK(!driving::ThirdPersonViewActive());CHECK(driving::g_bikeView==driving::VIEW_THIRD_PERSON);
 CHECK(vrfire::IsScriptedWeaponCamera());CHECK(Read<void*>(ped,0x150)==nullptr);
 AutoHold();CHECK(gHeldSlot[1]==4 && gAwaitFirstGrip[1]);
 vrfire::g_physicalFireQuery=Query;xr::input.triggers[1]=.85f;xr::input.b=false;
 int type,hand;float level;CHECK(vrfire::GetPhysicalTrigger(ped,type,hand,level));CHECK(type==28&&hand==1&&level==.85f);
 CHECK(vrfire::PlayerFireEnabled());
 Put<std::uint16_t>(pad,vrfire::kPadDisableControlsOffset,1);CHECK(!vrfire::PlayerFireEnabled());
 Put<std::uint16_t>(pad,vrfire::kPadDisableControlsOffset,0);
 for(int i=0;i<30;++i)Update();CHECK(selects==1&&vrcam::resets==1);
 Basis b;detail::FaceRear(b);CHECK(b.forward.y==-1&&b.right.x==1&&b.up.z==1&&b.pos.z==2);
 driver=true;Update();CHECK(!Active()&&driving::ThirdPersonViewActive());driver=false;Update();CHECK(Active());
 appearance=1;Update();CHECK(!Active());appearance=2;Update();CHECK(Active());
 Put<int>(locals,169*4,518);Update();CHECK(!Active());Put<int>(locals,169*4,517);Update();CHECK(Active());
 inVehicle=false;Update();CHECK(!Active());inVehicle=true;Update();CHECK(Active());
 alive=false;Update();CHECK(!Active());alive=true;
 thread[0x16]='x';Update();CHECK(!Active());thread[0x16]=0;
 std::memcpy(thread+0x10,"SMOKE4",6);Update();CHECK(Active());
 activeList=nullptr;Update();CHECK(!Active());activeList=thread;bytes[100]^=1;Update();CHECK(!Active());
 std::puts("PASS: retail SMOKE4 stage/vehicle/passenger isolation, auto-held Micro SMG, physical trigger with no attachment, native fire locks, rear basis, third-person preference restoration");
}
'''
(O/'test.cpp').write_text(prefix+code+stubs+tests,encoding='utf8')
vc=Path(r'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
cmd=O/'run.cmd';cmd.write_text(f'@echo off\ncall "{vc}" >nul\ncl /nologo /std:c++20 /EHsc /W3 /I"{R / "native/src"}" /I"{Path(os.environ["JAVA_HOME"]) / "include"}" /I"{Path(os.environ["JAVA_HOME"]) / "include/win32"}" "{O / "test.cpp"}" /Fe:"{O / "test.exe"}" /Fo:"{O / "test.obj"}"\nif errorlevel 1 exit /b 1\n"{O / "test.exe"}" "{O / "smoke4.scm"}"\n',encoding='utf8')
p=subprocess.run(['cmd','/c',str(cmd)],cwd=O,capture_output=True,text=True,encoding='utf8',errors='replace');print(p.stdout);print(p.stderr);sys.exit(p.returncode)
