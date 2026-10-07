#!/usr/bin/env python3
"""Compile the production Frame CPad query hooks against controlled input boundaries."""
from pathlib import Path
import os, subprocess, tempfile
R=Path(__file__).resolve().parents[1]
s=(R/'native/src/VrFire.cpp').read_text()
s=s[s.index('using TargetQueryFn='):s.index('TargetQueryFn InstallFrameTargetQuery')]
pause=(R/'native/src/main.cpp').read_text(); start=pause.index('void OnStartUserPause() {'); end=pause.index('\n}\n',start)+2
s += pause[start:end]
x=(R/'native/src/Xr.h').read_text(); x=x[x.index('struct InputState {'):x.index('// Identifies which VR menu')]
prefix=r"""
#include "Symbols.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#define LOGW(...) ((void)0)
#define CHECK(e) do { if(!(e)){std::fprintf(stderr,"FAIL %d %s\n",__LINE__,#e);std::exit(1);} } while(0)
namespace savr {
GameSymbols g{};
namespace xr {
"""+x+r"""
InputState input{}; bool focus=true,menu=false;
bool IsSessionFocused(){return focus;} bool IsMenuVisible(){return menu;}
void GetInput(InputState& out){out=input;}
}
namespace vrcam { bool tp=true,walk=true; bool IsStereoActive(){return tp;} bool OverShoulderActive(){return tp;} bool GroundWalkControlsActive(){return walk;} }
namespace vrfire {
"""
harness=r"""
}}
using namespace savr; using namespace savr::vrfire;
unsigned char pad[0x200]{},ped[0x600]{},data[0x100]{};
int cleared=0,fallbacks=0; std::uint32_t frame=0;
void* GetPad(int){return pad;} void* GetPed(int){return ped;}
void Clear(void*){++cleared;} int Fallback(void*){++fallbacks;return 7;}
float AimFallback(void*,void*,bool*){return 3.f;} std::int16_t UDFallback(void*,void*,bool*){return 4;}
int main(){
 bool userPause=false;g.CTimer_m_UserPause=&userPause;
 OnStartUserPause();CHECK(!userPause);
 xr::menu=true;OnStartUserPause();CHECK(userPause); // VR settings own a real native pause.
 userPause=false;xr::menu=false;xr::focus=false;OnStartUserPause();CHECK(userPause);
 xr::focus=true;
 g.CPad_GetPad=GetPad;g.FindPlayerPed=GetPed;g.CPlayerPed_ClearWeaponTarget=Clear;g.CTimer_m_FrameCounter=&frame;
 auto* ptr=data;std::memcpy(ped+0x540,&ptr,sizeof(ptr));
 frameEnterBody=frameExitBody=Fallback;frameAimLeftRight=AimFallback;frameAimUpDown=UDFallback;
 xr::input.frameControls=true;
 CHECK(OnFrameEnterTargeting(pad)==0 && OnFrameExitTargeting(pad)==0);
 ++frame;xr::input.triggers[0]=1;
 CHECK(OnFrameEnterTargeting(pad)==1 && OnFrameEnterTargeting(pad)==1 && OnFrameExitTargeting(pad)==0);
 ++frame;CHECK(OnFrameEnterTargeting(pad)==0);
 xr::input.rightStick[0]=.5f;xr::input.rightStick[1]=1.f;bool touch=true;
 CHECK(OnFrameAimLeftRight(pad,ped,&touch)==63.5f && !touch);
 CHECK(OnFrameAimUpDown(pad,ped,&touch)==-127);
 auto* flags=reinterpret_cast<std::uint16_t*>(data+0x48);*flags=0x18;
 ++frame;xr::input.triggers[0]=0;
 CHECK(OnFrameExitTargeting(pad)==1 && cleared==1 && *flags==0x10);
 ++frame;CHECK(OnFrameExitTargeting(pad)==0);
 CHECK(OnFrameAimLeftRight(pad,ped,&touch)==3.f && OnFrameAimUpDown(pad,ped,&touch)==4);
 for(int context=0;context<5;++context){
  xr::menu=context==0;xr::focus=context!=1;vrcam::tp=context!=2;vrcam::walk=context!=3;xr::input.frameControls=context!=4;
  CHECK(OnFrameEnterTargeting(pad)==7 && OnFrameExitTargeting(pad)==7);
  CHECK(OnFrameAimLeftRight(pad,ped,&touch)==3.f && OnFrameAimUpDown(pad,ped,&touch)==4);
 }
 CHECK(fallbacks==10);
 const std::uint16_t disabled=1;std::memcpy(pad+0x110,&disabled,2);
 CHECK(OnFrameEnterTargeting(pad)==0 && OnFrameExitTargeting(pad)==0 && OnFrameEnterTargeting(nullptr)==0);
 std::puts("PASS: actual Frame target press/hold/release queries, native target clearing, aim ABI and values, disabled pad and native menu/focus/FP/vehicle/profile fallbacks");
}
"""
with tempfile.TemporaryDirectory(prefix='savr-target-') as path:
 d=Path(path);(d/'test.cpp').write_text(prefix+s+harness)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-DSAVR_STEAM_FRAME','-I',str(R/'native/src'),str(d/'test.cpp'),'-o',str(d/'test')],check=True)
 subprocess.run([str(d/'test')],check=True)
