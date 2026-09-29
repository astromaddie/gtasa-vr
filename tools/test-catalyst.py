"""Compile the production Catalyst bridge on Windows with mocked engine/platform boundaries.
Optional --scm is a local retail mainV1.scm; retail bytes are never committed.
"""
from pathlib import Path
import os
import subprocess,sys,struct
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/catalyst-tests';OUT.mkdir(parents=True,exist_ok=True)
source_path=Path(sys.argv[sys.argv.index('--source')+1]) if '--source' in sys.argv else ROOT/'native/src/Catalyst.cpp'
source=source_path.read_text(encoding='utf8')
legacy='OnConditions(' not in source
for name in ['"Log.h"','<dlfcn.h>','<sys/mman.h>','<unistd.h>']:
 source=source.replace('#include '+name,'')
prelude=r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <vector>
#include <cstdint>
#undef assert
#define assert(e) do { if(!(e)) { std::fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#e); std::exit(3); } } while(0)
#define LOGI(...) ((void)0)
#define PROT_READ 1
#define PROT_WRITE 2
#define PROT_EXEC 4
#define MAP_PRIVATE 2
#define MAP_ANONYMOUS 32
#define MAP_FAILED ((void*)-1)
#define _SC_PAGESIZE 1
#define __builtin___clear_cache(a,b) ((void)0)
void* dlsym(void*,const char*) {return nullptr;}
long sysconf(int) {return 4096;}
void* mmap(void*,long n,int,int,int,int) {return std::calloc(1,n);}
int mprotect(void*,std::size_t,int) {return 0;}
int munmap(void* p,long) {std::free(p);return 0;}
'''
stubs=r'''
namespace savr {
GameSymbols g{};
namespace xr {
InputState fakeInput{};
HandPose fakeHands[2]{};
int arcCount=0;float arcPoints[41][3]{};
void GetInput(InputState& out){out=fakeInput;}
void SetThrowableTrajectory(int hand,const float points[][3],int count,bool hit){assert(hand==1);arcCount=count;if(count)std::memcpy(arcPoints,points,count*3*sizeof(float));}
}
namespace physicalweapon {
int resets=0;
bool GetHandPosesSnapshot(xr::HandPose out[2]){out[0]=xr::fakeHands[0];out[1]=xr::fakeHands[1];return true;}
void ResetTransient(){++resets;}
}
namespace vrcam {
bool TrackingPointToWorld(const float p[3],float w[3]){std::memcpy(w,p,12);return true;}
bool WorldPointToTracking(const float p[3],float w[3]){std::memcpy(w,p,12);return true;}
}
}
using namespace savr;
using namespace savr::catalyst;
std::uint8_t gs[0x9000]{},ls[1024]{},thread[0x130]{},other[0x130]{};
std::uint8_t pool[32]{},objects[0x220]{},refs[1]{7},matrix[64]{},models[28*154]{};
std::uint8_t train[0x100]{},modelInfo[64]{};
void* modelPtrs[20000]{};
std::vector<std::uint8_t> bytecode(detail::kScriptSize);
void* poolPtr=pool,*scriptList=thread;
int creates=0,deletes=0,removes=0,originalCalls=0,nativeThrows=0;
bool emulate=false,comparison=false;
V projectileSource[10]{},projectileVelocity[10]{};
bool projectiles[10]{};
std::size_t originalOffset=0;
// Small engine-boundary interpreter consumes the REAL retail operands. The
// production bridge is reached only through Process()'s prefetched group ABI.
struct Param {
    std::uint8_t* ref{};std::int32_t value{};
    int Int()const{return ref?Read<int>(ref,0):value;}
    float Float()const{return Read<float>(ref?ref:reinterpret_cast<const std::uint8_t*>(&value),0);}
    void Set(int v){assert(ref);Write<int>(ref,0,v);}
    void Set(float v){assert(ref);Write<float>(ref,0,v);}
};
Param Operand(std::uint8_t*& ip) {
    Param p;const int type=*ip++;
    switch(type) {
    case 1:case 6:p.value=Read<int>(ip,0);ip+=4;break;
    case 4:p.value=Read<std::int8_t>(ip,0);++ip;break;
    case 5:p.value=Read<std::int16_t>(ip,0);ip+=2;break;
    case 2:p.ref=gs+Read<std::uint16_t>(ip,0);ip+=2;break;
    case 3:p.ref=ls+4*Read<std::uint16_t>(ip,0);ip+=2;break;
    case 8:{const int start=Read<std::uint16_t>(ip,0),index=Read<std::uint16_t>(ip,2);
        assert(ip[4]==10 && ip[5]==0);assert(Local(index)>=0 && Local(index)<10);
        p.ref=ls+4*(start+Local(index));ip+=6;break;}
    default:assert(false);
    }return p;
}
std::int8_t Original(void* s,int op) {
    ++originalCalls;auto* ip=Read<std::uint8_t*>(s,0x20);originalOffset=ip-base;
    if(!emulate)return 7;
    auto a=Operand(ip);Param b,c,d,e;
    switch(op) {
    case 0xd6:break; // IF operand, comparisons below set the result
    case 0x8f:b=Operand(ip);a.Set(float(b.Int()));break;
    case 0x17:b=Operand(ip);a.Set(a.Float()/b.Float());break;
    case 0x68d:case 0x68e:b=Operand(ip);c=Operand(ip);a.Set(0.f);b.Set(0.f);c.Set(0.f);break;
    case 0x3ca:comparison=a.Int()>0 && projectiles[a.Int()-1];break;
    case 0x4d:if(!comparison)ip=base-a.Int();break;
    case 0x108:assert(a.Int()>0);projectiles[a.Int()-1]=false;break;
    case 0x29b:
        b=Operand(ip);c=Operand(ip);d=Operand(ip);e=Operand(ip);
        assert(a.Int()==-153 || a.Int()==-137);
        projectileSource[Local(117)]={b.Float(),c.Float(),d.Float()};
        projectiles[Local(117)]=true;e.Set(Local(117)+1);break;
    case 0x4d9:case 0x392:case 0x382:b=Operand(ip);assert(a.Int()>0 && b.Int()==1);break;
    case 0x85:b=Operand(ip);a.Set(b.Int());break;
    case 0x65:b=Operand(ip);a.Set(a.Float()-b.Float());break;
    case 0x6b:b=Operand(ip);a.Set(a.Float()*b.Float());break;
    case 0x6a2:b=Operand(ip);c=Operand(ip);d=Operand(ip);b.Set(.1f*50);c.Set(0.f);d.Set(0.f);break;
    case 0x89:b=Operand(ip);a.Set(b.Float());break;
    case 0x5b:b=Operand(ip);a.Set(a.Float()+b.Float());break;
    case 0x381:
        b=Operand(ip);c=Operand(ip);d=Operand(ip);assert(a.Int()>0 && projectiles[a.Int()-1]);
        projectileVelocity[a.Int()-1]={b.Float()/50,c.Float()/50,d.Float()/50};++nativeThrows;break;
    case 0xa:b=Operand(ip);a.Set(a.Int()+b.Int());break;
    case 0x39:b=Operand(ip);comparison=a.Int()==b.Int();break;
    case 0x6:case 0x4:b=Operand(ip);a.Set(b.Int());break;
    default:assert(false);
    }
    Write(s,0x20,ip);return 0;
}
#ifdef LEGACY_BRIDGE
// Reproduce retail's bypass of ProcessOneCommand: neither group calls it.
std::int8_t OldOriginal(void*){return 0;}
std::int8_t OnConditions(void* s,int op){return Original(s,op);}
std::int8_t OnObjects(void* s,int op){return Original(s,op);}
#endif
std::int8_t DispatchOne(void* s) {
    auto* ip=Read<std::uint8_t*>(s,0x20);
    const auto instruction=Read<std::uint16_t>(ip,0);
    Write(s,0x20,ip+2);Write<std::uint8_t>(s,0x122,instruction>>15);
    const int opcode=instruction&0x7fff;
    switch(opcode/100) {
    case 2:return OnConditions(s,opcode);
    case 8:return OnObjects(s,opcode);
    default:return Original(s,opcode);
    }
}
void ThrowBlock() {
    emulate=true;Write(thread,0x20,base+detail::kInput);
    assert(DispatchOne(thread)==0);
    assert(!pending && launching && !held); // The release is consumed before launch.
    assert(Read<std::uint8_t*>(thread,0x20)==base+detail::kLaunch);
    int steps=0;
    while(Read<std::uint8_t*>(thread,0x20)!=base+detail::kCatch) {
        assert(++steps<64);assert(DispatchOne(thread)==0);
    }
    assert(!launching && !pending);emulate=false;
}
void* Player(int){return thread;}
void* Train(int handle){return handle==256?train:nullptr;}
void* Create(int model,bool){assert(model==3014);++creates;std::memset(objects,0,sizeof(objects));refs[0]=7;Write(objects,0x18,(void*)matrix);return objects;}
void Add(void*){}
void Remove(void* p){assert(p==objects);++removes;}
void Delete(void* p){assert(p==objects);++deletes;refs[0]|=0x80;}
void Static(void*,bool b){assert(b);}
void Rw(void* p){Write(p,0x20,(void*)matrix);}
void Teleport(void* p,float x,float y,float z,unsigned char){Write<V>(matrix,0x30,{x,y,z});}
void Setup(){
    #ifdef LEGACY_BRIDGE
    original=OldOriginal;
#else
    originalConditions=originalObjects=Original;installed=true;
#endif
    activeScripts=&scriptList;locals=ls;usedObjects=models;objectPool=&poolPtr;
    createObject=Create;worldAdd=Add;worldRemove=Remove;deleteObject=Delete;createRw=Rw;teleport=Teleport;getVehicle=Train;
    g.FindPlayerPed=Player;g.CTheScripts_ScriptSpace=gs;g.CObject_SetIsStatic=Static;g.CModelInfo_ms_modelInfoPtrs=modelPtrs;
    modelPtrs[3014]=modelInfo;Write<int>(models,153*28+24,3014);
    Write(pool,0,(void*)objects);Write(pool,8,(void*)refs);Write<int>(pool,0x10,1);
    std::memcpy(thread+0x10,"ryder3",6);thread[0x12c]=1;Write(thread,0x18,bytecode.data());
    Write<int>(ls,97*4,10);Write<int>(ls,135*4,-153);Write<int>(ls,171*4,256);
    Write<int>(gs,0x80c0,90000);Write<V>(train,0x68,{0.1f,0,0});
    xr::fakeHands[1].valid=xr::fakeHands[1].aimValid=true;
}
void CommandAt(std::size_t off){Write(thread,0x20,base+off);DispatchOne(thread);}
int main(int argc,char** argv){
    detail::Trigger t;
    assert(!t.Update(1,true));assert(!t.Update(0,true));assert(!t.armed);
    for(int i=0;i<1000;++i){
        assert(!t.Update(0.61f,true));assert(!t.Update(0.63f,true));assert(t.armed);
        for(int j=0;j<4;++j)assert(!t.Update(0.4f,true));
        assert(t.Update(0.31f,true));assert(!t.Update(0,true));
    }
    for(bool blocked: {false,true}) {
        t={};t.Update(0,true);t.Update(1,true);
        t.Update(blocked?1.0f:NAN,!blocked);
        assert(!t.Update(0,true));assert(!t.armed);
    }
    assert(detail::Route(11087,false)==11538 && detail::Route(11087,true)==11229);
    assert(detail::Route(11704,true)==11704); // Ryder catch task untouched
    if(argc>1){std::ifstream f(argv[1],std::ios::binary);bytecode.assign(std::istreambuf_iterator<char>(f),{});assert(bytecode.size()==detail::kScriptSize);assert(detail::Hash(bytecode.data(),bytecode.size())==detail::kScriptHash);}
    Setup();
    // With zero air drag, adding the same train speed to player and crate must
    // leave the displayed relative arc identical. Release stays in world space.
    script=thread;base=bytecode.data();verified=true;
    Write<V>(train,0x68,{});Preview({0,0,2},{0,.46f,.1f});
    float still[41][3]{};std::memcpy(still,xr::arcPoints,sizeof(still));
    Write<V>(train,0x68,{.15f,-.40f,0});Preview({0,0,2},{.15f,.06f,.1f});
    assert(xr::arcCount==41);
    for(int i=0;i<41;++i)for(int j=0;j<3;++j)assert(std::abs(still[i][j]-xr::arcPoints[i][j])<0.0002f);
    script=nullptr;base=nullptr;verified=false;Write<V>(train,0x68,{.1f,0,0});
    // Retail 03A4 names are case-insensitive.
    assert(NameMatches(thread));
    std::memcpy(thread+0x10,"RYDER3",6);assert(NameMatches(thread));
    std::memcpy(thread+0x10,"RyDeR3",6);assert(NameMatches(thread));
    thread[0x16]='X';assert(!NameMatches(thread));thread[0x16]=0;
    thread[0x12c]=0;assert(!NameMatches(thread));thread[0x12c]=1;
    std::memcpy(thread+0x10,"ryder2",6);assert(!NameMatches(thread));
    std::memcpy(thread+0x10,"ryder3",6);
    if(argc>1) {
        Update(false);assert(active && verified && HeldValid() && creates==1 && !pending);
        xr::fakeInput.triggers[1]=1;Update(false);assert(trigger.armed && xr::arcCount>1);
        Update(true);assert(!pending && !trigger.armed && !held && xr::arcCount==0);
        // Resume while held: releasing cannot accidentally throw.
        Update(false);xr::fakeInput.triggers[1]=0;Update(false);assert(!pending);
        xr::fakeInput.triggers[1]=1;Update(false);
        xr::fakeHands[1].valid=false;Update(false);assert(!pending && !held);
        xr::fakeHands[1].valid=true;xr::fakeInput.triggers[1]=0;Update(false);
        xr::fakeInput.triggers[1]=1;Update(false);xr::fakeInput.triggers[1]=0;Update(false);
        assert(pending && !trigger.armed);
        assert(std::abs(releaseVelocity.x-0.1f)<1e-6 && std::abs(releaseVelocity.z+0.46f)<1e-6);
    } else {script=thread;base=bytecode.data();verified=active=true;pending=true;releaseSource={1,2,3};releaseVelocity={.1f,.2f,.3f};}
    assert(argc>1); // Run the real retail bytecode, never a zero-filled stand-in.
    for(int n=0;n<25;++n) {
        const int index=Local(117);const V expectedSource=releaseSource,expectedVelocity=releaseVelocity;
        ThrowBlock();assert(nativeThrows==n+1 && Local(117)==(index+1)%10);
        const auto p=projectileSource[index],v=projectileVelocity[index];
        assert(p.x==expectedSource.x && p.y==expectedSource.y && p.z==expectedSource.z);
        assert(std::abs(v.x-expectedVelocity.x)<1e-6 && std::abs(v.z-expectedVelocity.z)<1e-6);
        Update(false);assert(HeldValid() && !pending);
        const int calls=originalCalls;
        CommandAt(detail::kInput);assert(originalCalls==calls); // do not parse next opcode as IF operand
        assert(Read<std::uint8_t*>(thread,0x20)==base+detail::kCatch);
        xr::fakeInput.triggers[1]=1;Update(false);assert(xr::arcCount>1);
        xr::fakeInput.triggers[1]=0;Update(false);assert(pending);
    }
#ifndef LEGACY_BRIDGE
    // A stopped dispatcher cannot permanently latch input or throw a stale request.
    for(int n=0;n<90;++n)Update(false);
    assert(!pending && !launching && HeldValid());
    xr::fakeInput.triggers[1]=1;Update(false);assert(xr::arcCount>1);
    xr::fakeInput.triggers[1]=0;Update(false);assert(pending);
    ThrowBlock();assert(nativeThrows==26);
#endif
    // Unrelated scripts/stages and unsupported bytecode retain the prefetched ABI.
    Write(other,0x20,base+detail::kInput);DispatchOne(other);assert(originalOffset==detail::kInput+2);
    Write<int>(ls,97*4,9);CommandAt(detail::kInput);assert(originalOffset==detail::kInput+2);
    Write<int>(ls,97*4,10);verified=false;CommandAt(detail::kInput);assert(originalOffset==detail::kInput+2);verified=true;
    if(argc>1) {
        Update(false);assert(HeldValid());
        const int before=deletes;refs[0]=8; // recycled slot must never be deleted
        Reset();assert(deletes==before && !active && !held);
        Update(false);assert(active && HeldValid());
        Write<int>(gs,0x80b8,10);Update(false);assert(!active && !held && !pending);
        Write<int>(gs,0x80b8,0);Update(false);assert(active && held);
        scriptList=nullptr;Update(false);assert(!active && !held);
        scriptList=thread;bytecode[100]^=1;Update(false);assert(!verified && !active);
    }
#ifndef LEGACY_BRIDGE
    // Both exact retail prologues must pass before either function is patched.
    alignas(16) std::uint32_t ct[4],ot[4];
    std::memcpy(ct,conditionsPrologue,16);std::memcpy(ot,objectsPrologue,16);
    ot[0]=0;assert(!HookGroups(ct,ot));assert(!std::memcmp(ct,conditionsPrologue,16));
    std::memcpy(ot,objectsPrologue,16);assert(HookGroups(ct,ot));
    for(auto item: {std::make_pair((void*)ct,originalConditions),std::make_pair((void*)ot,originalObjects)}) {
        auto* tramp=reinterpret_cast<std::uint32_t*>(item.second);
        assert(tramp[4]==0x58000051 && tramp[5]==0xd61f0220);
        assert(Read<std::uintptr_t>(tramp,24)==reinterpret_cast<std::uintptr_t>(item.first)+16);
    }
#endif
    std::puts("PASS: prefetched retail group dispatch, 26 complete throw blocks, ring wrap, repeat trajectory, pending recovery, 1000 input cycles, cancellation, script isolation, pool lifetime, group trampolines");
}
'''
(OUT/'test.cpp').write_text(('#define LEGACY_BRIDGE 1\n' if legacy else '')+prelude+source+stubs,encoding='utf8')
scm=None
if '--scm' in sys.argv:
 p=Path(sys.argv[sys.argv.index('--scm')+1]);b=p.read_bytes();c=struct.unpack_from('<I',b,3)[0];c=struct.unpack_from('<I',b,c+3)[0]
 offsets=struct.unpack_from('<'+'I'*struct.unpack_from('<H',b,c+16)[0],b,c+24)
 scm=OUT/'catalyst.scm';scm.write_bytes(b[offsets[25]:offsets[26]])
 # Versioned hook sites must be exact instruction boundaries in the local retail mission.
 expected={11087:0x00d6,11229:0x008f,11269:0x00d6,11474:0x0381,11492:0x000a,11538:0x0006,11704:0x070a}
 for offset,opcode in expected.items():assert struct.unpack_from('<H',scm.read_bytes(),offset)[0]==opcode
vc=Path(r'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
cmd=OUT/'run.cmd'
cmd.write_text(f'@echo off\ncall "{vc}" >nul\ncl /nologo /std:c++20 /EHsc /W3 /I"{ROOT / "native/src"}" /I"{Path(os.environ["JAVA_HOME"]) / "include"}" /I"{Path(os.environ["JAVA_HOME"]) / "include/win32"}" "{OUT / "test.cpp"}" /Fe:"{OUT / "test.exe"}" /Fo:"{OUT / "test.obj"}"\nif errorlevel 1 exit /b 1\n"{OUT / "test.exe"}" '+(f'"{scm}"' if scm else '')+'\n',encoding='utf8')
r=subprocess.run(['cmd','/c',str(cmd)],cwd=OUT,capture_output=True,text=True,encoding='utf8',errors='replace');print(r.stdout);print(r.stderr);sys.exit(r.returncode)
