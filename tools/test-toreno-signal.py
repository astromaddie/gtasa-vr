"""Exercise retail counter decoding and the production stereo gauge draw calls."""
from pathlib import Path
import os,re,subprocess
R=Path(__file__).resolve().parents[1];O=R/'build/toreno-tests';O.mkdir(parents=True,exist_ok=True)
xr=(R/'native/src/Xr.cpp').read_text(encoding='utf8')
a=xr.index('    if (signal>=0) {');i=xr.index('{',a)+1;depth=1
while depth:depth+=(xr[i]=='{')-(xr[i]=='}');i+=1
draw=xr[a:i]
code=r'''
#include "MissionHud.h"
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <initializer_list>
int checks=0;
#define CHECK(x) do{++checks;if(!(x)){printf("FAIL %d: %s\n",__LINE__,#x);exit(1);}}while(0)
struct {int hudCompositeSourceRectUniform=1,hudCompositeDestinationRectUniform=2,hudCompositeHighlightUniform=3;}s;
struct{bool visible=true;int texture=7;}g_signalTextTexture;
struct Draw{float x,y,w,h,fraction,mode;};Draw next{};std::vector<Draw> draws;
constexpr int GL_TEXTURE_2D=1,GL_TRIANGLES=4;
void glBindTexture(int,int){}
void glUniform4f(int uniform,float x,float y,float w,float h){if(uniform==1)next.fraction=x;else{next.x=x;next.y=y;next.w=w;next.h=h;}}
void glUniform1f(int,float mode){next.mode=mode;}
void glDrawArrays(int,int,int){draws.push_back(next);}
namespace perf {double MonotonicMs(){return -1;}}
void Render(int signal,float hudDepthShiftUv,unsigned sourceTexture=0){
 int eye=0;
'''+draw+r'''
}
int main(){
 using savr::missionhud::TorenoSignal;
 unsigned char timer[0x154]{};
 unsigned char script[0x31c0]{};
 auto Read=[&](){return TorenoSignal(timer,script);};
 auto Value=[&](int value){memcpy(script+0x31bc,&value,4);};
 CHECK(TorenoSignal(nullptr,script)==-1);CHECK(TorenoSignal(timer,nullptr)==-1);CHECK(Read()==-1);
 for(int slot=0;slot<4;++slot){
  memset(timer,0,sizeof(timer)); // mobile display flags and text never populated
  auto* entry=timer+0x40+slot*0x44;
  unsigned variable=0x31bc;memcpy(entry,&variable,4);memcpy(entry+8,"DRI2_17",8);
  entry[0x12]=1;entry[0x3f]=1;entry[0x40]=3; // actual AddCounter writes
  for(int value=0;value<=100;++value){Value(value);CHECK(Read()==value);}
  Value(999999);CHECK(Read()==100);Value(-2147483647);CHECK(Read()==0);
  Value(67);strcpy((char*)entry+0x14,"0");CHECK(Read()==67); // stale display text
  entry[0x3e]=1;timer[0x150]=1;CHECK(Read()==67);
  entry[0x12]=0;CHECK(Read()==-1);entry[0x12]=1;
  entry[8]='X';CHECK(Read()==-1);entry[8]='D';
  memset(entry,0,4);CHECK(Read()==-1);memcpy(entry,&variable,4);
  variable=0xffffffff;memcpy(entry,&variable,4);CHECK(Read()==-1);
 }
 draws.clear();Render(-1,0);CHECK(draws.empty());
 for(unsigned source: {0u,77u})for(float eyeShift: {-.01f,.01f})for(int value: {0,1,50,99,100}){
  draws.clear();Render(value,eyeShift,source);CHECK(draws.size()==2);
  CHECK(draws[0].mode==0);CHECK(draws[1].mode==5);
  CHECK(std::abs(draws[1].fraction-value/100.f)<.00001f);
  CHECK(std::abs(draws[1].x-(.4f+eyeShift))<.00001f);
  CHECK(draws[1].w==.20f&&draws[1].h==.018f);
 }
 printf("PASS: %d native signal and stereo drawing checks\n",checks);
}
'''
base=Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC');msvc=sorted(base.iterdir())[-1]
sdk=Path('C:/Program Files (x86)/Windows Kits/10');version=sorted((sdk/'Include').iterdir())[-1].name
env=os.environ.copy();env['INCLUDE']=';'.join(str(p) for p in [msvc/'include',*[sdk/'Include'/version/n for n in ('ucrt','shared','um')]])
env['LIB']=';'.join(str(p) for p in [msvc/'lib/x64',*[sdk/'Lib'/version/n/'x64' for n in ('ucrt','um')]])
compiler=msvc/'bin/Hostx64/x64';env['PATH']=str(compiler)+os.pathsep+env['PATH']
p=O/'signal.cpp';p.write_text(code,encoding='utf8')
subprocess.run([str(compiler/'cl.exe'),'/nologo','/std:c++17','/EHsc','/MD','/I'+str(R/'native/src'),str(p),'/Fe:'+str(O/'signal.exe'),'/Fo:'+str(O/'signal.obj')],env=env,check=True)
subprocess.run([str(O/'signal.exe')],check=True)
vr=(R/'native/src/VrCamera.cpp').read_text(encoding='utf8')
pad=vr[vr.index('void OnUpdatePads()'):vr.index('    beachdance::SetInput(',vr.index('void OnUpdatePads()'))]
assert 'g.CUserDisplay_OnscnTimer,g.CTheScripts_ScriptSpace' in pad
assert 'xr::PublishTorenoSignal(torenoSignal)' in pad
assert 'if (hudSource||g_signalPercent.load(std::memory_order_relaxed)>=0)' in xr
assert '(!sourceTexture&&g_signalPercent.load(std::memory_order_relaxed)<0)' in xr
assert 'entry+0x14' in vr and 'entry[0x3e]!=0' in vr
assert 'uHighlight > 4.5 ? vec3(0.25,1.0,0.35)' in xr
print('PASS: native publication, counter offsets and signal shader wired')
