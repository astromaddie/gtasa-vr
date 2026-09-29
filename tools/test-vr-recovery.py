"""Production melee + tracking recovery regression harness, with only engine APIs mocked."""
from pathlib import Path
import os
import subprocess,sys,re
R=Path(__file__).resolve().parents[1];O=R/'build/recovery-tests';O.mkdir(parents=True,exist_ok=True)
p=Path(sys.argv[sys.argv.index('--source')+1]) if '--source' in sys.argv else R/'native/src/Melee.cpp'
s=p.read_text(encoding='utf8').replace('#include "Log.h"','')
s=re.sub(r'double NowSeconds\(\) \{.*?\n\}', 'double NowSeconds() { return fakeNow; }',s,flags=re.S)
prefix=r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include "TrackingRecovery.h"
#define LOGI(...) ((void)0)
#define LOGW(...) ((void)0)
#define CHECK(e) do {if(!(e)){std::fprintf(stderr,"FAIL %d: %s\n",__LINE__,#e);std::exit(3);}}while(0)
double fakeNow=10;
'''
tests=r'''
namespace savr {
GameSymbols g{};
namespace xr {HandPose hands[2]{};}
namespace physicalweapon {
int slot=1;TrackingPose pose{};
bool GetHandPosesSnapshot(xr::HandPose h[2]) {std::memcpy(h,xr::hands,sizeof(xr::hands));return true;}
int HeldSlot(int hand){return hand==1?slot:-1;}
bool GetHeldVisualPoseTracking(int hand,int,TrackingPose* out){*out=pose;return hand==1;}
bool IsSupportHand(int){return false;}
}
namespace vrcam {bool TrackingPointToWorld(const float p[3],float w[3]){std::memcpy(w,p,12);return true;}}
}
using namespace savr;
unsigned char ped[0x1000]{},victim[0x1000]{},info[128]{},col[0x2c]{};
void* ignore{};int hits{},lastDamage{},expectedType=5;bool collides=true,ducked=false,unaware=true;
unsigned char intelligence[0x100]{},targetIntel[0x100]{},targetMatrix[0x40]{};
void* Duck(const void*,bool){return ducked?intelligence:nullptr;}
bool Stealth(void* i,void* t,bool basic){CHECK(i==intelligence && t==victim && !basic);return unaware;}
void* Player(int){return ped;}
void* Vehicle(int,bool){return nullptr;}
bool Alive(void*){return true;}
void* Info(int,signed char){return info;}
bool Line(const GameSymbols::Vec3*,const GameSymbols::Vec3*,void*,void**,bool,bool,bool,bool,bool,bool,bool,bool){return false;}
void* Sphere(GameSymbols::Vec3 c,float,void*,bool,bool,bool,bool,bool,bool){std::memcpy(col,&c,12);col[0x24]=3;return collides?victim:nullptr;}
bool Damage(void* v,void* creator,int type,int damage,int,int){CHECK(v==victim&&creator==ped&&type==expectedType&&damage>0);lastDamage=damage;++hits;return true;}
void CarDamage(void*,void*,int,float,GameSymbols::Vec3){}
int Dir(void*,const GameSymbols::Vec2*){return 0;}
void Centre(void*,GameSymbols::Vec3* p){*p={1,0,1};}
void Seed(){
    melee::Reset();hits=0;fakeNow+=1;physicalweapon::pose={};xr::hands[1].valid=true;
    xr::hands[1].grip=1;xr::hands[1].trigger=0;melee::Update(false);
}
void Move(float distance,double dt=.014){fakeNow+=dt;physicalweapon::pose.position[0]+=distance;melee::Update(false);}
int main(){
    g.FindPlayerPed=Player;g.FindPlayerVehicle=Vehicle;g.CPed_IsAlive=Alive;
    g.CWeaponInfo_GetWeaponInfo=Info;g.CWorld_ProcessLineOfSight=Line;
    g.CWorld_TestSphereAgainstWorld=Sphere;g.gaTempSphereColPoints=col;g.CWorld_pIgnoreEntity=&ignore;
    g.CWeapon_GenerateDamageEvent=Damage;g.CVehicle_InflictDamage=CarDamage;
    g.CPed_GetLocalDirection=Dir;g.CEntity_GetBoundCentre=Centre;
    const int bat=5;std::memcpy(ped+0x730+0x20,&bat,4);victim[0x5a]=3;
    Seed();Move(.03f);CHECK(hits==1); // immediate draw-and-swing, no stillness ritual or trigger
    for(int i=0;i<8;++i)Move(.025f);CHECK(hits==1); // same swing cannot repeatedly damage
    for(int i=0;i<20;++i)Move(0.f);Move(.03f);CHECK(hits==2);
    Seed();Move(.08f,.06);CHECK(hits==1); // real 16.7 Hz gameplay sample
    Seed();Move(2.f);CHECK(hits==0); // tracking jump is not a strike
    Seed();fakeNow+=.014;physicalweapon::pose.position[0]=.04f;melee::Update(true);CHECK(hits==0);
    Seed();xr::hands[1].valid=false;Move(.03f);CHECK(hits==0);
    Seed();collides=false;Move(.03f);CHECK(hits==0);collides=true;
    // The actual physical knife strike reaches native lethal damage only when crouched/unseen.
    void* pi=intelligence;void* ti=targetIntel;void* tm=targetMatrix;
    std::memcpy(ped+0x538,&pi,sizeof(pi));std::memcpy(victim+0x538,&ti,sizeof(ti));std::memcpy(victim+0x18,&tm,sizeof(tm));
    g.CPedIntelligence_GetTaskDuck=Duck;g.CPedIntelligence_TestForStealthKill=Stealth;
    expectedType=4;std::memcpy(ped+0x750,&expectedType,4);ducked=true;
    Seed();Move(.03f);CHECK(hits==1 && lastDamage==10000);
    ducked=false;Seed();Move(.03f);CHECK(hits==1 && lastDamage<10000);
    ducked=true;unaware=false;Seed();Move(.03f);CHECK(hits==1 && lastDamage<10000);
    unaware=true;g.CPedIntelligence_TestForStealthKill=nullptr;Seed();Move(.03f);CHECK(hits==1 && lastDamage<10000);
    g.CPedIntelligence_TestForStealthKill=Stealth;expectedType=5;std::memcpy(ped+0x750,&expectedType,4);
    Seed();Move(.03f);CHECK(hits==1 && lastDamage<10000);
    tracking::Recovery recovery;
    for(int i=0;i<7;++i)CHECK(!recovery.Sample(true));
    CHECK(recovery.Sample(true)&&recovery.epoch==1);
    CHECK(!recovery.Sample(false)); // valid bit/focus/pose failure
    for(int i=0;i<4;++i)CHECK(!recovery.Sample(true));
    recovery.Invalidate(); // runtime recenter interrupts settling
    for(int i=0;i<7;++i)CHECK(!recovery.Sample(true));
    CHECK(recovery.Sample(true)&&recovery.epoch==2);
    for(int i=0;i<100;++i)CHECK(recovery.Sample(true)&&recovery.epoch==2);
    tracking::SeatLatch seat;
    CHECK(seat.Begin(ped,1,0));CHECK(seat.Capture(0));seat.valid=true;
    CHECK(seat.Capture(1500));CHECK(!seat.Capture(2001));
    CHECK(!seat.Begin(ped,1,3000));CHECK(!seat.Capture(3000));
    CHECK(seat.Begin(ped,2,3100)&&!seat.valid);CHECK(seat.Capture(3100)); // same-car recenter
    CHECK(seat.Begin(nullptr,2,3200));CHECK(seat.Begin(ped,2,5000)); // entry animation completes
    seat.valid=true;CHECK(seat.Capture(6500));CHECK(!seat.Capture(7001));
    std::puts("PASS: knife crouch/awareness lethal damage gating; immediate bat swing reaches native damage; cooldown, low FPS, tracking jumps, blocked/lost pose; focus/reference recovery and same-car seat reset");
}
'''
(O/'test.cpp').write_text(prefix+s+tests,encoding='utf8')
vc=Path(r'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
cmd=O/'run.cmd';cmd.write_text(f'@echo off\ncall "{vc}" >nul\ncl /nologo /std:c++20 /EHsc /W3 /I"{R / "native/src"}" /I"{Path(os.environ["JAVA_HOME"]) / "include"}" /I"{Path(os.environ["JAVA_HOME"]) / "include/win32"}" "{O / "test.cpp"}" /Fe:"{O / "test.exe"}" /Fo:"{O / "test.obj"}"\nif errorlevel 1 exit /b 1\n"{O / "test.exe"}"\n',encoding='utf8')
p=subprocess.run(['cmd','/c',str(cmd)],cwd=O,capture_output=True,text=True,encoding='utf8',errors='replace');print(p.stdout);print(p.stderr);sys.exit(p.returncode)
