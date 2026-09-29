"""Run production boat alpha routing with a two-eye list and material-pass recorder."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PRELUDE = r'''#include <initializer_list>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
struct AlphaListNode {
    void* object; void* callback; float distance; std::uint32_t padding;
    AlphaListNode* previous; AlphaListNode* next;
};
int g_renderingStereoEyeIndex=0,pluginOffset=0x80,nativeCalls=0,draws=0,solidCalls=0;
bool skipBlend=false,skipNonblend=false,stateValid=true,admit=true,full=false,far=false;
bool lighting=true,paint=true;
std::uintptr_t depthWrite=1;
struct Draw { bool hull,glass,lit,painted; std::uintptr_t write; } draw[128]{};
AlphaListNode list[2]{},nodes[20]{};
int nodeCount=0;
struct Material { char prefix[0xb]{}; std::uint8_t alpha=255; bool glass=false,blend=true; };
struct Geometry { Material* materials[130]{}; int count=0; };
void Render(void* atomic,float) {
    auto* geometry=*reinterpret_cast<Geometry**>(static_cast<char*>(atomic)+0x30);
    bool hull=!skipNonblend,glass=!skipBlend;
    if (geometry) {
        hull=glass=false;
        for (int i=0;i<geometry->count;++i) {
            auto& m=*geometry->materials[i];
            if (!m.alpha||(m.blend?skipBlend:skipNonblend)) continue;
            if (m.glass) glass=true; else hull=true;
        }
    }
    draw[draws++]={hull,glass,lighting,paint,depthWrite};
}
struct Symbols {
    void* CVisibilityPlugins_m_alphaBoatAtomicList=list;
    void (*CVisibilityPlugins_RenderAtomic)(void*,float)=Render;
    int* CVisibilityPlugins_ms_atomicPluginOffset=&pluginOffset;
    bool* skipBlendRender=&skipBlend; bool* skipNonblendRender=&skipNonblend;
    void (*rpSkipBlendRender)(bool)=[](bool x) { skipBlend=x; };
    // Verified ARM64 2.11 setter ignores its argument (STRB WZR).
    void (*rpSkipNonblendRender)(bool)=[](bool) { skipNonblend=false; };
    int (*RwRenderStateGet)(int,void*)=[](int state,void* out) {
        if (!stateValid||state!=8) return 0;
        *static_cast<std::uintptr_t*>(out)=depthWrite; return 1;
    };
    int (*RwRenderStateSet)(int,void*)=[](int state,void* value) {
        if (state!=8) std::abort();
        depthWrite=reinterpret_cast<std::uintptr_t>(value); return 1;
    };
    void* (*RpGeometryForAllMaterials)(void*,void*(*)(void*,void*),void*)=
        [](void* ptr,void*(*cb)(void*,void*),void* data)->void* {
            auto* geometry=static_cast<Geometry*>(ptr);
            for(int i=0;i<geometry->count;++i) cb(geometry->materials[i],data);
            return ptr;
        };
} g;
void* Native(void* atomic) {
    ++nativeCalls;
    if (!admit) return atomic;
    auto* flags=reinterpret_cast<std::uint16_t*>(static_cast<char*>(atomic)+pluginOffset+2);
    if (far) *flags|=0x2000; else *flags&=~0x2000;
    if ((*flags&0x40)&&!full&&nodeCount<20) {
        auto* n=&nodes[nodeCount++];
        *n={atomic,reinterpret_cast<void*>(&Render),1,0,list[1].previous,&list[1]};
        n->previous->next=n; list[1].previous=n;
    } else Render(atomic,1);
    return atomic;
}
void* (*g_origRenderBoatHiDetailAlpha)(void*)=Native;
void* (*g_origRenderBoatHiDetail)(void*)=[](void* atomic)->void* {
    ++solidCalls; Render(atomic,1); return atomic;
};
int checks=0;
void Check(bool ok,const char* message) {
    ++checks; if (!ok) { std::fprintf(stderr,"FAIL: %s\n",message); std::exit(1); }
}
void Reset() {
    list[0].next=&list[1]; list[1].previous=&list[0];
    nodeCount=nativeCalls=solidCalls=draws=0; depthWrite=1;
    skipBlend=skipNonblend=full=far=false;
    stateValid=admit=lighting=paint=true; g_renderingStereoEyeIndex=0;
}
void DrawList() {
    // CRenderer ends vehicle lighting and resets editable materials before this list.
    lighting=paint=false;
    for(auto* n=list[1].previous;n!=&list[0];n=n->previous)
        reinterpret_cast<void(*)(void*,float)>(n->callback)(n->object,n->distance);
}
'''
TESTS = r'''
int main() {
    alignas(8) char atomic[0x100]{};
    auto& flags=*reinterpret_cast<std::uint16_t*>(atomic+pluginOffset+2);
    for (bool distant:{false,true}) {
        Reset(); flags=0; far=distant;
        OnRenderBoatHiDetailAlpha(atomic);
        Check(nodeCount==1&&draws==1,"solid hull draws before vehicle paint/lights reset");
        Check(draw[0].hull&&!draw[0].glass&&draw[0].lit&&draw[0].painted&&draw[0].write==1,
              "near and distant hull keep their original colour and depth");
        Check(flags==(distant?0x2000:0),"native distance/reflection flag survives alpha tagging");
        DrawList();
        Check(draws==2&&!draw[1].hull&&draw[1].glass&&draw[1].write==0,
              "deferred glass cannot redraw the dark hull or occlude foliage");
        Check(depthWrite==1&&!skipBlend&&!skipNonblend,"exact render states restored");
        g_renderingStereoEyeIndex=1; lighting=paint=true;
        OnRenderBoatHiDetailAlpha(atomic); DrawList();
        Check(nativeCalls==2&&nodeCount==1&&draws==4,"each eye draws solid and shares one glass entry");
        Check(draw[2].hull&&draw[2].lit&&draw[2].painted&&!draw[2].glass&&
              !draw[3].hull&&draw[3].glass&&draw[3].write==0,"right eye matches left eye passes");
    }
    Reset(); flags=0x40; OnRenderBoatHiDetailAlpha(atomic);
    Check((flags&0x40)!=0,"authored alpha flag preserved");
    g_renderingStereoEyeIndex=1; far=true; OnRenderBoatHiDetailAlpha(atomic);
    Check(flags==0x2040,"second eye still runs native distance update");
    skipBlend=true; skipNonblend=true; depthWrite=0; DrawList();
    Check(skipBlend&&skipNonblend&&depthWrite==0&&!draw[draws-1].hull&&!draw[draws-1].glass,
          "nondefault incoming filters and depth are respected and restored");
    Reset(); flags=0; admit=false; OnRenderBoatHiDetailAlpha(atomic);
    Check(nodeCount==0&&draws==0,"native LOD culling preserved");
    Reset(); flags=0x40; full=true; OnRenderBoatHiDetailAlpha(atomic);
    Check(nodeCount==0&&draws==2&&draw[0].hull&&!draw[0].glass&&
          !draw[1].hull&&draw[1].glass&&draw[1].write==0,"full list retains both material passes");
    Check(flags==0x40&&depthWrite==1&&!skipBlend&&!skipNonblend,"overflow restores flags and render state");
    Reset(); flags=0; g_renderingStereoEyeIndex=-1; OnRenderBoatHiDetailAlpha(atomic);
    Check(nativeCalls==1&&draws==1&&nodeCount==0&&draw[0].hull&&draw[0].glass,
          "flat and reflection calls retain native behaviour");
    Reset(); flags=0; stateValid=false; OnRenderBoatHiDetailAlpha(atomic);
    Check(draws==1&&nodeCount==0&&flags==0,"failed admission state query leaves retail path intact");
    Reset(); flags=0; OnRenderBoatHiDetailAlpha(atomic); stateValid=false; DrawList();
    Check(draws==1&&depthWrite==1&&!skipBlend&&!skipNonblend,
          "failed deferred state query cannot repaint hull without its lights");
    Reset(); flags=0;
    Material hull{},window1{},window2{},invisible{};
    window1.alpha=168; window2.alpha=128; invisible.alpha=0;
    window1.glass=window2.glass=true;
    Geometry geometry{{&hull,&window1,&window2,&hull,&invisible},5};
    *reinterpret_cast<void**>(atomic+0x30)=&geometry;
    OnRenderBoatHiDetail(atomic);
    Check(nodeCount==1&&solidCalls==0&&draw[0].hull&&!draw[0].glass,
          "Reefer boat_hi mixed materials enter the corrected split path");
    DrawList(); Check(!draw[1].hull&&draw[1].glass&&draw[1].write==0,"Reefer windows retain depth fix");
    Check(draw[0].lit&&draw[0].painted&&draw[0].write==1,"blended Reefer hull keeps lighting, paint and depth");
    Check(hull.alpha==255&&window1.alpha==168&&window2.alpha==128&&invisible.alpha==0,
          "shared and invisible materials restore original alpha after both passes");
    g_renderingStereoEyeIndex=1; lighting=paint=true; far=true;
    OnRenderBoatHiDetail(atomic); DrawList();
    Check(nodeCount==1&&draws==4&&flags==0x2000&&draw[2].hull&&!draw[2].glass&&
          draw[2].lit&&draw[2].write==1&&!draw[3].hull&&draw[3].glass,
          "Reefer second eye preserves native distance update and material split");
    Reset(); flags=0x40; full=true; OnRenderBoatHiDetail(atomic);
    Check(draws==2&&nodeCount==0&&draw[0].hull&&!draw[0].glass&&!draw[1].hull&&
          draw[1].glass&&draw[1].write==0&&flags==0x40,"Reefer list overflow draws both isolated passes");
    Check(hull.alpha==255&&window1.alpha==168&&window2.alpha==128&&depthWrite==1,
          "Reefer overflow restores materials and depth");
    Reset(); flags=0; admit=false; OnRenderBoatHiDetail(atomic);
    Check(draws==0&&nodeCount==0&&hull.alpha==255&&window1.alpha==168,"Reefer respects native LOD rejection");
    Reset(); flags=0; OnRenderBoatHiDetail(atomic); stateValid=false; DrawList();
    Check(draws==1&&hull.alpha==255&&window1.alpha==168,"failed deferred state query cannot redraw Reefer hull");
    Reset(); flags=0; skipBlend=skipNonblend=true; OnRenderBoatHiDetail(atomic); DrawList();
    Check(skipBlend&&skipNonblend&&draw[0].hull&&!draw[0].glass&&!draw[1].hull&&draw[1].glass,
          "material passes do not inherit blend classification and restore incoming filters");
    Material many[129]{};
    Geometry large{}; large.count=129; many[128].alpha=128;
    for(int i=0;i<129;++i) large.materials[i]=&many[i];
    Reset(); *reinterpret_cast<void**>(atomic+0x30)=&large; OnRenderBoatHiDetail(atomic);
    Check(solidCalls==1&&nodeCount==0&&many[0].alpha==255&&many[128].alpha==128,
          "material capacity overflow falls back before changing any alpha");
    *reinterpret_cast<void**>(atomic+0x30)=&geometry;
    Reset(); geometry.count=1; OnRenderBoatHiDetail(atomic);
    Check(solidCalls==1&&nativeCalls==0&&nodeCount==0,"opaque boat parts retain retail callback");
    Reset(); geometry.count=5; g_renderingStereoEyeIndex=-1; OnRenderBoatHiDetail(atomic);
    Check(solidCalls==1&&nativeCalls==0,"Reefer flat/reflection callback unchanged");
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
