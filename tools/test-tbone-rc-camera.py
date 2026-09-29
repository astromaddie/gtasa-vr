"""Exercise production T-Bone input bridge and RC camera on a host fixture."""
from pathlib import Path
import os,re,subprocess
R=Path(__file__).resolve().parents[1];O=R/'build/tbone-tests';O.mkdir(parents=True,exist_ok=True)
body=(R/'native/src/Tbone.cpp').read_text(encoding='utf8')
body='\n'.join(x for x in body.splitlines() if not x.startswith('#include'))
vr=(R/'native/src/VrCamera.cpp').read_text(encoding='utf8')
pad_call=re.search(r'    tbone::UpdateInput\([^\n]+',vr).group(0)
a=vr.index('bool StabilizeRemoteCamera(');end=vr.index('\nvoid OnCopyCameraMatrixToRWCam',a);camera=vr[a:end]
code=r'''
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <limits>
#include <initializer_list>
int checks=0;
#define CHECK(x) do{++checks;if(!(x)){std::printf("FAIL %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
#define LOGI(...) ((void)0)
void* head=nullptr;
void* dlsym(void*,const char*){return &head;}
namespace savr {
std::uint32_t clockMs=1000;
struct{std::uint32_t* CTimer_m_snTimeInMilliseconds=&clockMs;}g;
namespace xr{bool hint=false;void SetPackageHint(bool value){hint=value;}}
}
'''+body+'''
void UpdateFromPad(bool stereo,bool inputBlocked,bool bothGrips,bool openChord,bool actionControls,bool a){
 using namespace savr;
 struct {bool a;} in{a};
'''+pad_call+'''
}
'''+r'''
struct V3{float x{},y{},z{};};
V3 operator+(V3 a,V3 b){return {a.x+b.x,a.y+b.y,a.z+b.z};}
V3 operator-(V3 a,V3 b){return {a.x-b.x,a.y-b.y,a.z-b.z};}
V3 operator*(V3 a,float b){return {a.x*b,a.y*b,a.z*b};}
float Dot(V3 a,V3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
V3 Cross(V3 a,V3 b){return {a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
bool Finite(V3 a){return std::isfinite(a.x)&&std::isfinite(a.y)&&std::isfinite(a.z);}
struct CamBasis{V3 pos,right,forward,up;};
namespace driving{void* remote=nullptr;void* GetRemoteControlledVehicle(){return remote;}}
V3 remotePosition{30,60,90};
bool ReadEntityWorldPosition(const void*,V3* out){*out=remotePosition;return Finite(*out);}
'''+camera+r'''
int main(){
 using namespace savr;
 tbone::Install(nullptr);tbone::UpdateInput(true,false);
 CHECK(!tbone::Ready());CHECK(!tbone::ClaimsA());CHECK(!xr::hint);
 // Native action works without a named/hashed entry in the mission list.
 CHECK(!tbone::WidgetReleased(false));CHECK(tbone::Ready());CHECK(xr::hint);
 tbone::UpdateInput(true,true);CHECK(tbone::ClaimsA());
 // A second pad update before script evaluation must not lose this press.
 tbone::UpdateInput(true,true);CHECK(tbone::WidgetReleased(false));
 CHECK(!tbone::WidgetReleased(false));
 tbone::UpdateInput(true,true);CHECK(!tbone::WidgetReleased(false));CHECK(tbone::ClaimsA());
 tbone::UpdateInput(true,false);CHECK(!tbone::WidgetReleased(false));
 tbone::UpdateInput(true,true);CHECK(tbone::WidgetReleased(false));
 clockMs+=121;tbone::UpdateInput(true,false);CHECK(!tbone::Ready());CHECK(!xr::hint);CHECK(!tbone::ClaimsA());
 tbone::UpdateInput(true,true);tbone::UpdateInput(true,true);CHECK(!tbone::WidgetReleased(false));
 tbone::UpdateInput(false,true);CHECK(!tbone::WidgetReleased(false));CHECK(!tbone::Ready());CHECK(!tbone::ClaimsA());
 CHECK(tbone::WidgetReleased(true));
 tbone::UpdateInput(true,true);CHECK(!tbone::WidgetReleased(false));
 tbone::UpdateInput(true,false);tbone::UpdateInput(true,true);
 clockMs+=181;tbone::UpdateInput(true,true);CHECK(!tbone::WidgetReleased(false));
 // Exercise the real OnUpdatePads call, including the grip/menu gate.
 for(bool grips: {false,true}) {
  UpdateFromPad(true,false,grips,false,true,false);
  CHECK(!tbone::WidgetReleased(false));CHECK(tbone::Ready());
  UpdateFromPad(true,false,grips,false,true,true);
  CHECK(tbone::ClaimsA());CHECK(tbone::WidgetReleased(false));
  UpdateFromPad(true,false,grips,false,true,true);
  CHECK(!tbone::WidgetReleased(false));
 }
 UpdateFromPad(true,false,true,false,true,false);
 UpdateFromPad(true,false,true,true,true,true); // actual menu-opening chord
 CHECK(!tbone::WidgetReleased(false));CHECK(!tbone::Ready());
 UpdateFromPad(true,false,true,false,true,true); // still held after closing
 CHECK(!tbone::WidgetReleased(false));
 UpdateFromPad(true,true,true,false,true,false); // open menu
 UpdateFromPad(true,true,true,false,true,true);
 CHECK(!tbone::WidgetReleased(false));
 UpdateFromPad(true,false,true,false,false,false); // native controls disabled
 UpdateFromPad(true,false,true,false,false,true);
 CHECK(!tbone::WidgetReleased(false));
 alignas(8) unsigned char vehicle[0x40]{};
 *reinterpret_cast<std::uint16_t*>(vehicle+0x32)=501;driving::remote=vehicle;
 const V3 target=remotePosition+V3{0,0,.35f};
 for(int i=0;i<1000;++i){
  const float angle=i*.1f;const float radius=.5f+i*.02f;
  CamBasis c{};c.pos=target+V3{std::cos(angle)*radius,std::sin(angle)*radius,1+radius*.2f};
  CHECK(StabilizeRemoteCamera(c));const V3 delta=c.pos-target;
  CHECK(std::abs(std::sqrt(Dot(delta,delta))-6)<.0001f);
  CHECK(std::abs(Dot(c.right,c.forward))<.0001f);
  CHECK(std::abs(Dot(c.up,c.forward))<.0001f);
  CHECK(std::abs(Dot(c.up,c.up)-1)<.0001f);CHECK(c.up.z>0);
 }
 CamBasis c{};c.pos=target;CHECK(!StabilizeRemoteCamera(c));
 c.pos.x=std::numeric_limits<float>::quiet_NaN();CHECK(!StabilizeRemoteCamera(c));
 *reinterpret_cast<std::uint16_t*>(vehicle+0x32)=464;CHECK(!StabilizeRemoteCamera(c));
 driving::remote=nullptr;CHECK(!StabilizeRemoteCamera(c));
 std::printf("PASS: %d production mission input and fixed-distance camera checks\n",checks);
}
'''
(O/'tbone.cpp').write_text(code,encoding='utf8')
base=Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC');msvc=sorted(base.iterdir())[-1]
sdk=Path('C:/Program Files (x86)/Windows Kits/10');version=sorted((sdk/'Include').iterdir())[-1].name
env=os.environ.copy();env['INCLUDE']=';'.join(str(p) for p in [msvc/'include',*[sdk/'Include'/version/n for n in ('ucrt','shared','um')]])
env['LIB']=';'.join(str(p) for p in [msvc/'lib/x64',*[sdk/'Lib'/version/n/'x64' for n in ('ucrt','um')]])
compiler=msvc/'bin/Hostx64/x64';env['PATH']=str(compiler)+os.pathsep+env.get('PATH','')
subprocess.run([str(compiler/'cl.exe'),'/nologo','/std:c++17','/EHsc','/MD',str(O/'tbone.cpp'),'/Fe:'+str(O/'tbone.exe'),'/Fo:'+str(O/'tbone.obj')],env=env,check=True)
subprocess.run([str(O/'tbone.exe')],check=True)
assert 'input.a&&!tbone::ClaimsA()?255:0' in (R/'native/src/Driving.cpp').read_text()
assert 'if (widgetId==66)' in vr
assert 'Press A to snatch the package.' in vr
assert '!cutsceneRunning && !ScriptedCutsceneRunning() && StabilizeRemoteCamera(base)' in vr
assert 'PRESS A TO STEAL PACKAGE' in (R/'native/src/Xr.cpp').read_text()
print('PASS: widget routing, contextual handbrake, cutscene isolation and prompt wired')
