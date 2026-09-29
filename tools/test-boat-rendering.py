"""Run production boat alpha routing with a two-eye list and material-pass recorder."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PRELUDE = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
struct AlphaListNode {
    void* object; void* callback; float distance; std::uint32_t padding;
    AlphaListNode* previous; AlphaListNode* next;
};
int g_renderingStereoEyeIndex=0,pluginOffset=0x80,nativeCalls=0,draws=0;
bool skipBlend=false,skipNonblend=false,stateValid=true,admit=true;
std::uintptr_t depthWrite=1;
struct Draw { bool skipBlend,skipNonblend; std::uintptr_t write; } draw[8]{};
AlphaListNode list[2]{},nodes[20]{};
int nodeCount=0;
void Render(void*,float) { draw[draws++]={skipBlend,skipNonblend,depthWrite}; }
struct Symbols {
    void* CVisibilityPlugins_m_alphaBoatAtomicList=list;
    void (*CVisibilityPlugins_RenderAtomic)(void*,float)=Render;
    int* CVisibilityPlugins_ms_atomicPluginOffset=&pluginOffset;
    bool* skipBlendRender=&skipBlend; bool* skipNonblendRender=&skipNonblend;
    void (*rpSkipBlendRender)(bool)=[](bool x) { skipBlend=x; };
    void (*rpSkipNonblendRender)(bool)=[](bool x) { skipNonblend=x; };
    int (*RwRenderStateGet)(int,void*)=[](int state,void* out) {
        if (!stateValid||state!=8) return 0;
        *static_cast<std::uintptr_t*>(out)=depthWrite; return 1;
    };
    int (*RwRenderStateSet)(int,void*)=[](int state,void* value) {
        if (state!=8) std::abort();
        depthWrite=reinterpret_cast<std::uintptr_t>(value); return 1;
    };
} g;
void* Native(void* atomic) {
    ++nativeCalls;
    auto* flags=reinterpret_cast<std::uint16_t*>(static_cast<char*>(atomic)+pluginOffset+2);
    *flags|=0x2000; // Native LOD update must survive temporary alpha tagging.
    if (!admit) return atomic;
    if ((*flags&0x40)&&nodeCount<20) {
        auto* n=&nodes[nodeCount++];
        *n={atomic,reinterpret_cast<void*>(&Render),1,0,list[1].previous,&list[1]};
        n->previous->next=n; list[1].previous=n;
    } else Render(atomic,1);
    return atomic;
}
void* (*g_origRenderBoatHiDetailAlpha)(void*)=Native;
int checks=0;
void Check(bool ok,const char* message) {
    ++checks; if (!ok) { std::fprintf(stderr,"FAIL: %s\n",message); std::exit(1); }
}
void Reset() {
    list[0].next=&list[1]; list[1].previous=&list[0];
    nodeCount=nativeCalls=draws=0; depthWrite=1;
    skipBlend=skipNonblend=false; stateValid=admit=true; g_renderingStereoEyeIndex=0;
}
void DrawList() {
    for(auto* n=list[1].previous;n!=&list[0];n=n->previous)
        reinterpret_cast<void(*)(void*,float)>(n->callback)(n->object,n->distance);
}
'''
TESTS = r'''
int main() {
    alignas(8) char atomic[0x100]{};
    auto& flags=*reinterpret_cast<std::uint16_t*>(atomic+pluginOffset+2);
    Reset(); flags=0;
    OnRenderBoatHiDetailAlpha(atomic);
    Check(nodeCount==1&&draws==0,"untagged glass queues after world geometry");
    Check(flags==0x2000,"temporary alpha bit restored while native LOD bit retained");
    DrawList();
    Check(draws==2&&draw[0].skipBlend&&!draw[0].skipNonblend&&draw[0].write==1,
          "solid hull keeps its depth pass");
    Check(!draw[1].skipBlend&&draw[1].skipNonblend&&draw[1].write==0,
          "glass pass cannot occlude later foliage");
    Check(depthWrite==1&&!skipBlend&&!skipNonblend,"render states restored");
    g_renderingStereoEyeIndex=1;
    OnRenderBoatHiDetailAlpha(atomic); DrawList();
    Check(nativeCalls==1&&nodeCount==1&&draws==4,"right eye reuses one list entry");
    Check(draw[2].write==draw[0].write&&draw[3].write==draw[1].write,
          "both eyes receive identical material passes");
    Reset(); flags=0x40; OnRenderBoatHiDetailAlpha(atomic);
    Check((flags&0x40)!=0,"authored alpha flag preserved");
    skipBlend=true; skipNonblend=true; depthWrite=0; DrawList();
    Check(skipBlend&&skipNonblend&&depthWrite==0,"nondefault incoming states restored");
    Reset(); flags=0; admit=false; OnRenderBoatHiDetailAlpha(atomic);
    Check(nodeCount==0&&draws==0,"native LOD culling preserved");
    Reset(); flags=0; g_renderingStereoEyeIndex=-1;
    OnRenderBoatHiDetailAlpha(atomic);
    Check(nativeCalls==1&&draws==1&&nodeCount==0,"flat and reflection calls retain native behavior");
    Reset(); flags=0; OnRenderBoatHiDetailAlpha(atomic); stateValid=false; DrawList();
    Check(draws==1&&depthWrite==1&&!skipBlend&&!skipNonblend,"failed state query uses retail draw");
    list[0].next=nullptr;
    Check(FindBoatAlphaNode(atomic)==nullptr,"broken list is not dereferenced");
    std::printf("PASS: %d production boat rendering checks\n",checks);
}
'''

def main():
    msvc = sorted(Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC').iterdir())[-1]
    sdk = Path('C:/Program Files (x86)/Windows Kits/10')
    ver = sorted((sdk/'Include').iterdir())[-1].name
    env = os.environ.copy()
    env['INCLUDE'] = ';'.join(str(p) for p in [msvc/'include', *[sdk/'Include'/ver/n for n in ('ucrt','shared','um')]])
    env['LIB'] = ';'.join(str(p) for p in [msvc/'lib/x64', *[sdk/'Lib'/ver/n/'x64' for n in ('ucrt','um')]])
    compiler = msvc/'bin/Hostx64/x64'
    env['PATH'] = str(compiler)+os.pathsep+env.get('PATH','')
    out = ROOT/'build/boat-render-tests'
    out.mkdir(parents=True,exist_ok=True)
    source = (ROOT/'native/src/VrCamera.cpp').read_text()
    core = source[source.index('AlphaListNode* FindBoatAlphaNode('):source.index('void* OnRenderVehicleHiDetailAlpha(')]
    harness = out/'boat_render.cpp'
    harness.write_text(PRELUDE+core+TESTS)
    subprocess.run([str(compiler/'cl.exe'),'/nologo','/std:c++17','/EHsc','/MD',str(harness),
                    '/Fe:'+str(out/'boat_render.exe'),'/Fo:'+str(out/'boat_render.obj')],env=env,check=True)
    subprocess.run([str(out/'boat_render.exe')],check=True)

if __name__ == '__main__':
    main()
