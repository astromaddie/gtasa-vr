"""Exercise production beach detection, mobile axis hooks, stereo gate and shared beat HUD."""
from pathlib import Path
import os
import subprocess,sys,re
R=Path(__file__).resolve().parents[1];O=R/'build/beach-dance-tests';O.mkdir(parents=True,exist_ok=True)
F=Path(sys.argv[sys.argv.index('--fixtures')+1])
def src(n):return (R/'native/src'/n).read_text(encoding='utf8')
def fn(s,name):
 m=re.search(r'^(?:void|bool|int) '+name+r'\(',s,re.M);a=m.start();p=s.index('{',a)+1;d=1
 while d:d+=(s[p]=='{')-(s[p]=='}');p+=1
 return s[a:p]
def module(n):return src(n).replace('#include "Log.h"','').replace('#include <dlfcn.h>','')
prefix=r'''
#include <algorithm>
#include <atomic>
#include <fstream>
#include <iterator>
#include <vector>
#include <cstdlib>
#include <cmath>
#include "Locomotion.h"
#include "Xr.h"
#define LOGI(...) ((void)0)
#define CHECK(e) do{if(!(e)){std::fprintf(stderr,"FAIL %d: %s\n",__LINE__,#e);std::exit(3);}}while(0)
void* dlsym(void*,const char*){return nullptr;}
'''
code=prefix+module('BeachDance.cpp')+module('Hydraulics.cpp')+r'''
namespace savr {
namespace missionscenes {bool Theater(){return false;}}
GameSymbols g{};
namespace locomotion {int CutsceneMode(){return 0;}int GameCutsceneMode(){return 0;}}
namespace vrcam {
int resets{};bool menu{};double g_scriptedCutsceneLastWideMs=-1;
void RequestRecenter(){++resets;}
bool MobileMenuOpen(){return menu;}
bool FormalCutsceneRunning(){return *g.CCutsceneMgr_ms_running;}
double NowMs(){return 1000;}
'''+fn(src('VrCamera.cpp'),'ShouldRunStereo')+fn(src('VrCamera.cpp'),'ScriptedCutsceneRunning')+r'''
}
namespace xr {void GetInput(InputState& out){out={};}}
namespace driving {
bool VehicleRightStickActive(){return false;}
void ReadMappedGameplaySticks(const xr::InputState&,float&,float&,float&,float&){}
int OrigUD(void*,int,void*,float,int){return 14;}
int OrigLR(void*,int,int){return 13;}
auto g_origCarGunUpDown=OrigUD;auto g_origCarGunLeftRight=OrigLR;
'''+fn(src('Driving.cpp'),'OnGetCarGunUpDown')+fn(src('Driving.cpp'),'OnGetCarGunLeftRight')+r'''
}
}
using namespace savr;
using namespace savr::beachdance;
std::uint8_t mission[0x200]{},danceThread[0x200]{},space[0xab00]{},camera[0x100]{},pad[0x140]{},beat[0xb0]{};
void* list=mission;bool alive=true;int fade=0;bool formal=false;
void* Player(int){return alive?pad:nullptr;}
bool Alive(void*){return alive;}
int Fade(void*){return fade;}
void* Pad(int){return pad;}
void* Local(void* s,unsigned i){return static_cast<std::uint8_t*>(s)+0x6c+i*4;}
template<class T>void Put(void* p,unsigned off,T v){std::memcpy(static_cast<std::uint8_t*>(p)+off,&v,sizeof(v));}
std::vector<std::uint8_t> File(const char* path){std::ifstream f(path,std::ios::binary);CHECK(f.good());return {std::istreambuf_iterator<char>(f),{}};}
int main(int argc,char**argv){
 CHECK(argc==3);auto parent=File(argv[1]),dance=File(argv[2]);
 CHECK(parent.size()==detail::kParentSize && Hash(parent.data(),parent.size())==detail::kParentHash);
 CHECK(dance.size()>=detail::kDanceSize && Hash(dance.data(),detail::kDanceSize)==detail::kDanceHash);
 // Exact retail command: 0494 supplies right axes to $aa28/$aa2c.
 CHECK(Read<std::uint16_t>(dance.data(),17028)==0x494);
 CHECK(Read<std::uint16_t>(dance.data(),17039)==0xaa28 && Read<std::uint16_t>(dance.data(),17042)==0xaa2c);
 g.CTheScripts_ScriptSpace=space;g.FindPlayerPed=Player;g.CPed_IsAlive=Alive;
 g.TheCamera=camera;g.CPad_GetPad=Pad;g.CCutsceneMgr_ms_running=&formal;g.CCamera_GetScreenFadeStatus=Fade;
 scripts=&list;localVariable=Local;
 std::memcpy(mission+0x10,"strap1",6);mission[0x12c]=1;Put(mission,0x18,parent.data());Put<void*>(mission,0,danceThread);
 std::memcpy(danceThread+0x10,"DANCE",5);Put(danceThread,0x18,dance.data());
 Put<std::uint32_t>(space,0x685c,0x80000000u);Put<int>(space,0x6860,720);
 Put<std::uint16_t>(pad,0x110,1);camera[0x43]=1;
 CHECK(!vrcam::ShouldRunStereo());Update();CHECK(!Active());
 Put<int>(Local(danceThread,7),0,2);Update();CHECK(Active() && vrcam::resets==1 && Score()==720);
 CHECK(vrcam::ShouldRunStereo() && !vrcam::ScriptedCutsceneRunning());
 for(int i=0;i<20;++i)Update();CHECK(vrcam::resets==1);
 struct Case{float x,y;int d,lr,ud;};
 for(auto c: {Case{0,1,1,0,-127},Case{0,-1,2,0,127},Case{-1,0,3,-127,0},Case{1,0,4,127,0},Case{.8f,.5f,4,127,0},Case{.3f,.8f,1,0,-127},Case{.1f,.1f,0,0,0}}){
  CHECK(detail::Direction(c.x,c.y)==c.d);SetInput(true,c.x,c.y);
  CHECK(driving::OnGetCarGunUpDown(pad,0,nullptr,2500,0)==c.ud);
  CHECK(driving::OnGetCarGunLeftRight(pad,0,0)==c.lr);
 }
 SetInput(false,1,0);CHECK(AxisLeftRight()==0);SetInput(true,NAN,1);CHECK(AxisUpDown()==0);
 // Read-only beat snapshot; no GetBeatInfo call consumes native beat edges.
 hydraulics::g_beatInfo=beat;Put<int>(beat,0xa0,1);Put<int>(beat,0x50,95);Put<int>(beat,0xa8,10);
 for(auto c:{Case{13,0,1},Case{14,0,2},Case{9,0,3},Case{10,0,4}}){
  Put<int>(beat,0x54,static_cast<int>(c.x));hydraulics::SetStick(false,0,0);int ms=0;
  CHECK(hydraulics::PollBeat(&ms)==c.d && ms==95);CHECK(Read<int>(beat,0xa8)==10);
 }
 fade=2;CHECK(!vrcam::ShouldRunStereo());fade=0;vrcam::menu=true;CHECK(!vrcam::ShouldRunStereo());vrcam::menu=false;
 formal=true;CHECK(!vrcam::ShouldRunStereo());formal=false;
 Put<int>(Local(danceThread,6),0,1);Update();CHECK(Active());
 for(int phase:{2,3,4}){Put<int>(Local(danceThread,6),0,phase);Update();CHECK(!Active());CHECK(!vrcam::ShouldRunStereo());}
 Put<int>(Local(danceThread,6),0,1);Update();CHECK(Active());
 alive=false;Update();CHECK(!Active());alive=true;Update();CHECK(Active());
 Put<std::uint32_t>(space,0x685c,0);Update();CHECK(!Active());Put<std::uint32_t>(space,0x685c,0x80000000u);Update();CHECK(Active());
 // Other missions and nightclub/free-roam DANCE must retain their own view and controls.
 list=danceThread;Update();CHECK(!Active());SetInput(true,1,0);CHECK(AxisLeftRight()==0);
 int ms=0;CHECK(hydraulics::PollBeat(&ms)==0);CHECK(driving::OnGetCarGunLeftRight(pad,0,0)==13);
 CHECK(driving::OnGetCarGunUpDown(pad,0,nullptr,0,0)==14);
 list=mission;Update();CHECK(Active());Put<void*>(mission,0,nullptr);Update();CHECK(!Active());Put<void*>(mission,0,danceThread);
 dance[100]^=1;Update();CHECK(!Active());dance[100]^=1;list=nullptr;Update();list=mission;Update();CHECK(Active());
 list=nullptr;Update();parent[309]^=1;list=mission;Update();CHECK(!Active());
 // Existing LOWGAME gating and scoring stay independent from beach input.
 Put<int>(space,0x1004,1);Put<int>(beat,0x54,10);hydraulics::SetStick(true,0,0);hydraulics::SetStick(true,1,0);
 CHECK(hydraulics::AxisLeftRight()==127);CHECK(hydraulics::PollBeat(&ms)==4);
 Put<std::uint16_t>(pad,0x110,0);CHECK(vrcam::ShouldRunStereo());
 std::puts("PASS: installed SCM hashes, phase/death/mission isolation, mobile axis hooks, cardinal right-stick input, neutral/menu input, stereo gates and restoration, shared read-only beat HUD, lowrider regression");
}
'''
(O/'test.cpp').write_text(code,encoding='utf8')
vc=Path(r'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
cmd=O/'run.cmd';cmd.write_text(f'@echo off\ncall "{vc}" >nul\ncl /nologo /std:c++20 /EHsc /W3 /I"{R / "native/src"}" /I"{Path(os.environ["JAVA_HOME"]) / "include"}" /I"{Path(os.environ["JAVA_HOME"]) / "include/win32"}" "{O / "test.cpp"}" /Fe:"{O / "test.exe"}" /Fo:"{O / "test.obj"}"\nif errorlevel 1 exit /b 1\n"{O / "test.exe"}" "{F / "strap1.scm"}" "{F / "dance.scm"}"\n',encoding='utf8')
p=subprocess.run(['cmd','/c',str(cmd)],cwd=O,capture_output=True,text=True,encoding='utf8',errors='replace');print(p.stdout);print(p.stderr);sys.exit(p.returncode)
