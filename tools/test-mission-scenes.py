"""Compile production mission policy and run against extracted retail bytecode."""
from pathlib import Path
import os
import subprocess,sys,re
R=Path(__file__).resolve().parents[1];O=R/'build/mission-scenes-tests';O.mkdir(parents=True,exist_ok=True)
F=Path(sys.argv[sys.argv.index('--fixtures')+1])
K=Path(sys.argv[sys.argv.index('--king')+1]) if '--king' in sys.argv else None
s=(R/'native/src/MissionScenes.cpp').read_text(encoding='utf8').replace('#include "Log.h"','').replace('#include <dlfcn.h>','').replace('/sdcard/Android/data/com.rockstargames.gtasa/files/vr_mission_scenes.log','mission-test.log')
code=r'''
#include <cstdlib>
#include <fstream>
#include <vector>
#include <iterator>
#define LOGI(...) ((void)0)
#define CHECK(e) do{if(!(e)){std::fprintf(stderr,"FAIL %d %s\n",__LINE__,#e);std::exit(3);}}while(0)
void* dlsym(void*,const char*){return nullptr;}
'''+s+r'''
namespace savr {GameSymbols g{};namespace modelsets {bool hd=true;bool Applied(int){return hd;}}}
using namespace savr;using namespace savr::missionscenes;
unsigned char m[0x200]{},b[0x200]{},camera[0x100]{},info[26400*0x14]{};
void* list{};std::uint32_t now=1000;int fade=0,loads=0,requests=0,depth=0;bool pause=false,disabled=false,stubborn=false;
template<class T>void Put(void* p,unsigned o,T value){std::memcpy(static_cast<unsigned char*>(p)+o,&value,sizeof(value));}
int Fade(void*){return fade;}
void Request(int id,int flags){CHECK(flags==0xc);++requests;if(!stubborn)Put<std::uint32_t>(info,id*0x14+0x10,1);}
void Load(bool priority){CHECK(!priority && depth==1);++loads;Update();} // nested tick must not retry
void Suspend(){CHECK(depth==0);++depth;}void Resume(){CHECK(depth==1);--depth;}
int Anim(const char* n){CHECK(!std::strcmp(n,"BD_FIRE"));return 23;}
std::vector<unsigned char> Bytes(const char* f){std::ifstream in(f,std::ios::binary);return {std::istreambuf_iterator<char>(in),{}};}
int canChecks=0;bool can=true;GameSymbols::Vec3 playerPos{-2043.34f,-2525.99f,29.62f};
void* Player(int){return m;}void* Vehicle(int,bool){return nullptr;}
GameSymbols::Vec3 Position(int){return playerPos;}bool CanStart(void*){++canChecks;return can;}
void Thread(void* t,const char* name,std::vector<unsigned char>& bytes){std::strcpy(static_cast<char*>(t)+0x10,name);Put(t,0x18,bytes.data());Put(t,0x20,bytes.data());Put<unsigned char>(t,0x12c,1);}
void Ip(std::vector<unsigned char>& bytes,int offset){Put(b,0x20,bytes.data()+offset);}
void Step(unsigned ms){now+=ms;Update();}
void Model(int id,int state=0,int size=10){Put<std::uint32_t>(info,id*0x14+0x10,state);Put<std::uint32_t>(info,id*0x14+0xc,size);}
int main(int argc,char** argv){
 CHECK(argc==3||argc==4);auto mb=Bytes(argv[1]),bb=Bytes(argv[2]);CHECK(mb.size()==10840 && bb.size()==42218);
 g.TheCamera=camera;g.CCamera_GetScreenFadeStatus=Fade;g.CTimer_m_snTimeInMilliseconds=&now;
 g.CTimer_m_UserPause=&pause;g.CStreaming_ms_aInfoForModel=info;g.CStreaming_RequestModel=Request;g.CStreaming_ms_disableStreaming=&disabled;
 scripts=&list;loadAll=Load;animIndex=Anim;suspendTimer=Suspend;resumeTimer=Resume;
 Thread(m,"STRAP2",mb);Thread(b,"CRASH1",bb);list=m;
 camera[0x43]=1;Update();CHECK(Theater());camera[0x43]=0;Update();CHECK(!Theater());
 camera[0x43]=1;Put<unsigned char>(m,0x12c,0);Update();CHECK(!Theater());Put<unsigned char>(m,0x12c,1);
 mb[500]^=1;Update();CHECK(!Theater());mb[500]^=1;list=nullptr;Update();list=m;Update();CHECK(Theater());
 list=b;fade=2;Ip(bb,39448);Model(412);Model(596,1);Update();CHECK(!Theater() && loads==0);
 Step(1999);CHECK(loads==0);Step(1);CHECK(loads==1 && requests==1);Step(2000);CHECK(loads==1); // loaded models untouched
 Ip(bb,39512);Model(346);Model(344);Model(366);Update();stubborn=true;
 for(int i=0;i<5;++i)Step(2000);CHECK(loads==4 && requests==10); // three bounded retries; no false loaded flag
 CHECK(Read<std::uint32_t>(info,346*0x14+0x10)==0);
 Ip(bb,39556);for(int id:{3098,3097,3099,3127})Model(id,0,0);Update();Step(2000);CHECK(loads==4); // absent archive entry
 Ip(bb,39655);Model(25598);Update();modelsets::hd=false;Step(2000);CHECK(loads==4);
 modelsets::hd=true;pause=true;Step(2000);CHECK(loads==4);pause=false;
 disabled=true;Step(2000);CHECK(loads==4);disabled=false;
 fade=0;Step(2000);CHECK(loads==4);fade=2;Update();stubborn=false;Step(2000);CHECK(loads==5 && requests==11);
 Ip(bb,39300);Update();Step(5000);CHECK(loads==5); // outside validated wait range
 list=nullptr;Update();bb[100]^=1;list=b;Ip(bb,39448);Model(412);Update();Step(5000);CHECK(loads==5 && !burning.valid);
 CHECK(depth==0);
 if(argc==4){
  auto marker=Bytes(argv[3]);CHECK(marker.size()==641);
  std::vector<unsigned char> main(262245);
  Put(main.data(),0x7b4,playerPos.x);Put(main.data(),0x7b8,playerPos.y);Put(main.data(),0x7bc,playerPos.z);
  Put<int>(main.data(),0x7a8,1);Put<int>(main.data(),0xb38,1);
  g.CTheScripts_ScriptSpace=main.data();g.FindPlayerCoors=Position;g.FindPlayerPed=Player;g.FindPlayerVehicle=Vehicle;
  canStartMission=CanStart;std::memset(m,0,sizeof(m));std::strcpy(reinterpret_cast<char*>(m)+0x10,"cat");
  Put(m,0x20,main.data()+72559);list=m;
  // Actual boot order: ScriptSpace exists before SCM bytes are loaded.
  Step(2001);CHECK(canChecks==0);
  std::memcpy(main.data()+72537,marker.data(),marker.size());auto before=main;
  CHECK(Name(m,"cat",false)&&!Name(m,"cat"));
  Step(2001);CHECK(canChecks==1&&main==before);
  Step(1);CHECK(canChecks==1);playerPos.x+=30;Step(2001);CHECK(canChecks==2);
  playerPos.x-=30;can=false;Step(2001);CHECK(canChecks==3&&main==before);
  g.CTheScripts_ScriptSpace=nullptr;Step(2001);CHECK(canChecks==3);
  g.CTheScripts_ScriptSpace=main.data();can=true;
  Put<int>(main.data(),0x3778,1);Put<int>(main.data(),0x1818,32);Put<int>(main.data(),0x17f0,84);
  const auto legacy=main;
  // Each unrelated/unfinished/active state must remain byte-for-byte intact.
  for(auto guard : {std::pair<unsigned,int>{0x3778,0},{0x1818,31},{0x17f0,83},
                    {0x7a8,0},{0x7a8,2},{0xfc,1},{0xfc,4},{0xb38,0},{0xb38,3},{0x660,1}}) {
      main=legacy;Put<int>(main.data(),guard.first,guard.second);const auto unchanged=main;
      Step(2001);CHECK(main==unchanged);
  }
  main=legacy;can=false;Step(2001);CHECK(main==legacy);can=true;
  list=nullptr;Step(2001);CHECK(main==legacy);list=m;
  Put(m,0x20,main.data()+73051);Step(2001);CHECK(main==legacy);Put(m,0x20,main.data()+72559);
  Step(2001);
  auto expected=legacy;Put<int>(expected.data(),0xfc,1);Put<int>(expected.data(),0xb38,2);
  CHECK(main==expected);Step(2001);CHECK(main==expected); // exactly two globals, once
  main=legacy;Put<int>(main.data(),0xb38,2);Step(2001);CHECK(main==expected);
  // Reload changed code at another buffer: no state migration without fingerprint.
  auto changed=legacy;changed[72537]^=1;g.CTheScripts_ScriptSpace=changed.data();
  Put(m,0x20,changed.data()+72559);const auto intact=changed;Step(2001);CHECK(changed==intact);
  std::puts("PASS: same-address SCM retry, native gates and throttle; exact legacy debug-state repair changes only Catalina/caller stages, is idempotent, and preserves unrelated/active/unpassed states and unknown scripts");
 }
 std::puts("PASS: actual STRAP2/CRASH1 fingerprints, theater enter/exit, unrelated/changed scripts rejected; native streaming retry, loaded/missing entries, 3-attempt bound, fade/pause/HD/streaming gates and reentrancy");
}
'''
(O/'test.cpp').write_text(code,encoding='utf8')
vc=Path(r'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
cmd=O/'run.cmd';cmd.write_text(f'@echo off\ncall "{vc}" >nul\ncl /nologo /std:c++20 /EHsc /W3 /D_CRT_SECURE_NO_WARNINGS /I"{R / "native/src"}" /I"{Path(os.environ["JAVA_HOME"]) / "include"}" /I"{Path(os.environ["JAVA_HOME"]) / "include/win32"}" "{O / "test.cpp"}" /Fe:"{O / "test.exe"}" /Fo:"{O / "test.obj"}"\nif errorlevel 1 exit /b 1\n"{O / "test.exe"}" "{F / "strap2.scm"}" "{F / "crash1.scm"}"\n',encoding='utf8')
if K:cmd.write_text(cmd.read_text(encoding='utf8').replace(f'"{F / "crash1.scm"}"', f'"{F / "crash1.scm"}" "{K}"'),encoding='utf8')
p=subprocess.run(['cmd','/c',str(cmd)],cwd=O,capture_output=True,text=True,encoding='utf8',errors='replace');print(p.stdout);print(p.stderr);sys.exit(p.returncode)

