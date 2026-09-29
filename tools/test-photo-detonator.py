"""Production tests for native photo FOV/frame and detonator lifetime."""
from pathlib import Path
import re,subprocess,sys
R=Path(__file__).resolve().parents[1];O=R/'build/photo-detonator-tests';O.mkdir(parents=True,exist_ok=True)
def fn(file,name):
 s=(R/'native/src'/file).read_text();m=re.search(r'^(?:bool|void|int|float|CamBasis) '+name+r'\(',s,re.M);assert m,name
 a=m.start();i=s.index('{',a)+1;d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
code=r"""
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <vector>
#define LOGI(...) ((void)0)
#define CHECK(e) do{if(!(e)){std::fprintf(stderr,"FAIL %d %s\n",__LINE__,#e);std::exit(3);}}while(0)
struct V3{float x{},y{},z{};V3 operator+(V3 b)const{return {x+b.x,y+b.y,z+b.z};}};
struct Q{float x{},y{},z{},w{1};};
V3 Rotate(Q q,V3 v){V3 t{2*(q.y*v.z-q.z*v.y),2*(q.z*v.x-q.x*v.z),2*(q.x*v.y-q.y*v.x)};return {v.x+q.w*t.x+q.y*t.z-q.z*t.y,v.y+q.w*t.y+q.z*t.x-q.x*t.z,v.z+q.w*t.z+q.x*t.y-q.y*t.x};}
V3 Cross(V3 a,V3 b){return {a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
float Dot(V3 v,V3 b){return v.x*b.x+v.y*b.y+v.z*b.z;}
V3 Normalized(V3 v){float n=std::sqrt(Dot(v,v));return n>1e-8f?V3{v.x/n,v.y/n,v.z/n}:V3{};}
bool Finite(V3 v){return std::isfinite(v.x)&&std::isfinite(v.y)&&std::isfinite(v.z);}
struct CamBasis{V3 right,forward,up,pos;};
V3 TrackingToGame(const CamBasis& b,V3 v){return {-b.right.x*v.x+b.up.x*v.y-b.forward.x*v.z,-b.right.y*v.x+b.up.y*v.y-b.forward.y*v.z,-b.right.z*v.x+b.up.z*v.y-b.forward.z*v.z};}
struct GameSymbols{using Vec3=V3;};
namespace scopeaim {struct VisualState{bool active=true;int hand=1,weaponType=43;float zoom=8;};VisualState state;VisualState Snapshot(){return state;}
float RenderFovX(float f){return state.active?2*std::atan(std::tan(f*3.14159265359f/360)/state.zoom)*180/3.14159265359f:f;}}
namespace xr {bool tracked=true;float yaw=0;int published=0;bool GetHeadPose(float*p,float*q){p[0]=.2f;p[1]=1.5f;p[2]=-.3f;q[0]=q[2]=0;q[1]=std::sin(yaw/2);q[3]=std::cos(yaw/2);return tracked;}void SetRenderHeadPose(float*,float*){++published;}}
namespace photo {
std::atomic<bool> g_stereoActive{true};bool g_vrBaseValid=true;struct{bool valid=true;}g_origin;
CamBasis g_vrBase{{-1,0,0},{0,1,0},{0,0,1},{100,200,30}};
void RelativePose(V3 p,Q q,V3& rp,Q& rq){rp=p;rq=q;}
constexpr float kVrFovX=105;
alignas(16) unsigned char camera[0x1200]{},placeable[0x40]{};float drawFov=70;int fireCalls=0,derivedCalls=0;bool fireResult=true;
template<class T>void Put(void*p,unsigned off,T v){std::memcpy(static_cast<unsigned char*>(p)+off,&v,sizeof(v));}
template<class T>T Read(void*p,unsigned off){T v;std::memcpy(&v,static_cast<unsigned char*>(p)+off,sizeof(v));return v;}
CamBasis ReadCam(std::uintptr_t p){return {Read<V3>((void*)p,0x970),Read<V3>((void*)p,0x980),Read<V3>((void*)p,0x990),Read<V3>((void*)p,0x9a0)};}
void WriteCam(std::uintptr_t p,const CamBasis& b){Put((void*)p,0x970,b.right);Put((void*)p,0x980,b.forward);Put((void*)p,0x990,b.up);Put((void*)p,0x9a0,b.pos);}
void SetFov(float f,bool){drawFov=f;}void Derived(void*,bool,bool){++derivedCalls;}
bool NativeFire(void*,void*,V3*,V3*,void*,V3*,V3*);
struct{void* TheCamera=camera;bool(*CWeapon_Fire)(void*,void*,V3*,V3*,void*,V3*,V3*)=NativeFire;void(*CCamera_CalculateDerivedValues)(void*,bool,bool)=Derived;void(*CDraw_SetFOV)(float,bool)=SetFov;float* CDraw_ms_fFOV=&drawFov;}g;
float observedFov=0;
int NativeCommand(void*,int){unsigned a=camera[0x5f];observedFov=a<3?Read<float>(camera,a*0x228+0x204):-1;return 17;}
int(*g_origPhotoCommands)(void*,int)=NativeCommand;
"""+fn('VrCamera.cpp','BuildVrCamera')+fn('VrCamera.cpp','PhotoViewActive')+fn('VrCamera.cpp','BuildPhotoView')+fn('VrCamera.cpp','OnPhotoCommands')+fn('VrCamera.cpp','FirePhotograph').replace('/sdcard/Android/data/com.rockstargames.gtasa/files/vr_photo.log','photo-test.log')+r"""
bool NativeFire(void*,void*,V3*,V3*,void*,V3*,V3*){
 ++fireCalls;unsigned a=camera[0x5f];CHECK(Read<std::uint16_t>(camera,a*0x228+0x186)==46);
 float f=Read<float>(camera,a*0x228+0x204);CHECK(f<20&&std::abs(f-drawFov)<1e-5f);
 CamBasis want;CHECK(BuildPhotoView(want,false));auto actual=ReadCam((std::uintptr_t)camera);
 CHECK(std::memcmp(&actual,&want,sizeof(want))==0);
 CHECK(std::memcmp(placeable+0x10,&want.forward,12)==0&&std::memcmp(placeable+0x30,&want.pos,12)==0);
 return fireResult;
}
void Test(){
 Put(camera,0x18,static_cast<void*>(placeable));CamBasis native{{-1,0,0},{0,1,0},{0,0,1},{400,500,600}};WriteCam((std::uintptr_t)camera,native);
 std::memset(placeable,0x42,sizeof(placeable));int dummy=0;float flash[3]{1,2,3};
 for(unsigned active=0;active<3;++active){camera[0x5f]=active;Put<float>(camera,active*0x228+0x204,70);Put<std::uint16_t>(camera,active*0x228+0x186,4);
  const std::vector<unsigned char> before(camera,camera+sizeof(camera));const std::vector<unsigned char> beforeP(placeable,placeable+sizeof(placeable));
  for(float z:{1.0f,1.8f,4.0f,8.0f}){scopeaim::state.zoom=z;CHECK(OnPhotoCommands(&dummy,0x801)==17);CHECK(std::abs(observedFov-scopeaim::RenderFovX(105))<1e-5f);CHECK((observedFov<20)==(z==8));CHECK(std::memcmp(camera,before.data(),before.size())==0);}
  scopeaim::state.zoom=8;
  for(float yaw:{0.0f,1.5707963f,3.1415926f,-1.5707963f})for(bool ok:{false,true}){
   xr::yaw=yaw;fireResult=ok;CHECK(FirePhotograph(&dummy,&dummy,flash)==ok);
   CHECK(std::memcmp(camera,before.data(),before.size())==0&&std::memcmp(placeable,beforeP.data(),beforeP.size())==0&&drawFov==70);
   CamBasis low,high;scopeaim::state.zoom=1;CHECK(BuildPhotoView(low,true));scopeaim::state.zoom=8;CHECK(BuildPhotoView(high,true));CHECK(std::memcmp(&low,&high,sizeof(low))==0); // zoom cannot change head anchor or direction
  }
  CHECK(OnPhotoCommands(&dummy,0x800)==17&&observedFov==70);
  scopeaim::state.weaponType=34;OnPhotoCommands(&dummy,0x801);CHECK(observedFov==70);scopeaim::state.weaponType=43;
  scopeaim::state.active=false;OnPhotoCommands(&dummy,0x801);CHECK(observedFov==70);scopeaim::state.active=true;
 }
 int n=fireCalls;xr::tracked=false;CHECK(!FirePhotograph(&dummy,&dummy,flash));xr::tracked=true;camera[0x5f]=3;CHECK(!FirePhotograph(&dummy,&dummy,flash));CHECK(fireCalls==n);
 std::puts("PASS: native 0801 sees actual zoom and original 20-degree gate; all 3 cameras, other opcodes/optics preserved; head frame invariant across zoom/yaw; shutter success/failure restores matrices/mode/FOV; invalid tracking rejected");
}
}
namespace charges {
constexpr int kProjectileCount=32,kHandCount=2,kWeaponSlotCount=13,kOffWeapons=0x730,kWeaponStride=0x20;
unsigned char info[32*0x38]{},ped[0xa00]{};struct{unsigned char* gaProjectileInfo=info;}g;
namespace throwable {
"""+fn('Throwable.cpp','HasLiveSatchels')+r"""
}
bool ValidSlot(int s){return s>0&&s<13;}
"""+fn('PhysicalWeapon.cpp','WeaponTypeInSlot')+r"""
int gHeldSlot[2]{12,12};struct DroppedWeapon{int slot=-1;};DroppedWeapon gDropped[2];
void ClearHeldLocked(int h){gHeldSlot[h]=-1;}bool OwnedConfiguredSlot(void*p,int s){return ValidSlot(s)&&WeaponTypeInSlot(p,s)!=0;}
"""+fn('PhysicalWeapon.cpp','ValidateInventoryLocked')+r"""
void Test(){
 int remote=40;std::memcpy(ped+0x730+12*0x20,&remote,4);int charge=39;
 CHECK(!throwable::HasLiveSatchels()&&WeaponTypeInSlot(ped,12)==0);
 for(int i:{0,7,31}){std::memcpy(info+i*0x38,&charge,4);info[i*0x38+0x1c]=1;CHECK(throwable::HasLiveSatchels()&&WeaponTypeInSlot(ped,12)==40);}
 ValidateInventoryLocked(ped);CHECK(gHeldSlot[0]==12&&gHeldSlot[1]==12);
 info[0x1c]=0;info[7*0x38+0x1c]=0;ValidateInventoryLocked(ped);CHECK(gHeldSlot[0]==12&&gHeldSlot[1]==12);
 info[31*0x38+0x1c]=0;gDropped[0].slot=12;ValidateInventoryLocked(ped);CHECK(gHeldSlot[0]==-1&&gHeldSlot[1]==-1&&gDropped[0].slot==-1&&WeaponTypeInSlot(ped,12)==0);
 info[0x1c]=1;CHECK(WeaponTypeInSlot(ped,12)==40); // new throw re-enables remote
 int grenade=16;std::memcpy(info,&grenade,4);CHECK(!throwable::HasLiveSatchels());
 g.gaProjectileInfo=nullptr;CHECK(throwable::HasLiveSatchels()); // unknown build fails open
 std::puts("PASS: zero/one/multiple live C4, first/middle/last slots, both hands and dropped remote removed only after last charge; spare inventory/stale projectile pointer cannot retain remote; new charge restores availability");
}
}
int main(){photo::Test();charges::Test();}
"""
(O/'test.cpp').write_text(code)
vc=Path(r'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
c=O/'run.cmd';c.write_text(f'@echo off\ncall "{vc}" >nul\ncl /nologo /std:c++20 /EHsc /W3 /D_CRT_SECURE_NO_WARNINGS "{O / "test.cpp"}" /Fe:"{O / "test.exe"}" /Fo:"{O / "test.obj"}"\nif errorlevel 1 exit /b 1\n"{O / "test.exe"}"\n')
p=subprocess.run(['cmd','/c',str(c)],cwd=O,capture_output=True,text=True,encoding='utf8',errors='replace');print(p.stdout);print(p.stderr);sys.exit(p.returncode)
