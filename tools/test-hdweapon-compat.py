"""Exercise the production HD-weapon Apply loop using the installed weapon IMG."""
from pathlib import Path
import os
import subprocess,sys,re,struct
R=Path(__file__).resolve().parents[1];O=R/'build/hdweapon-compat-tests';O.mkdir(parents=True,exist_ok=True)
img=Path(sys.argv[sys.argv.index('--img')+1]);b=img.read_bytes();assert b[:4]==b'VER2'
entries={}
for i in range(struct.unpack_from('<I',b,4)[0]):
 off,size,archive,name=struct.unpack_from('<IHH24s',b,8+i*32);entries[name.split(b'\0')[0].decode().lower()]=(off,size)
assert entries['fire_ex.dff']==(815,43), 'fixture does not match the expected fire_extinguisher entry'
s=(R/'native/src/HdWeapons.cpp').read_text(encoding='utf8');a=s.index('void Apply() {');p=s.index('{',a)+1;depth=1
while depth:depth+=(s[p]=='{')-(s[p]=='}');p+=1
apply=s[a:p]
code=r'''
#include <atomic>
#include <initializer_list>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include "Symbols.h"
#define LOGI(...) ((void)0)
#define LOGE(...) ((void)0)
#define CHECK(e) do{if(!(e)){std::fprintf(stderr,"FAIL %d %s\n",__LINE__,#e);std::exit(3);}}while(0)
namespace savr {GameSymbols g{};}
using namespace savr;
const char* kFilesDir="test-files";const char* kImgPath="hdweapons\\hdweapons.img";const char* kImgPathReal;
constexpr int kFilesStride=0x30,kInfoStride=0x14;
std::atomic<bool> g_applied{};bool g_attemptFailed{};char status[1024]{};
struct DirEntry {std::uint32_t posn;std::uint16_t sizeSectors,sizeArchive;char name[24];};
char* getcwd(char* b,std::size_t){std::strcpy(b,kFilesDir);return b;}
int chdir(const char*){return 0;}
bool InstallSortEntriesHook(){return true;}
void* LoadLooseDatabase(const char*,bool){return status;}
void WriteStatus(const char* s){std::snprintf(status,sizeof(status),"%s",s);}
'''+apply+r'''
std::uint8_t infos[400*0x14]{},files[8*0x30]{};int buffer=512,flushes=0,removes=0;
int Add(const char*,bool){return 3;}
void* Find(const char* name,int* out){
 int id=!std::strcmp(name,"fire_ex")?366:!std::strcmp(name,"colt45")?346:!std::strcmp(name,"molotov")?344:-1;
 *out=id;return id>=0?infos+id*0x14:nullptr;
}
void Flush(){++flushes;}
void Remove(int id){CHECK(id!=366);++removes;}
template<class T>void Put(void* p,int offset,T v){std::memcpy(static_cast<char*>(p)+offset,&v,sizeof(v));}
int main(int argc,char** argv){
 CHECK(argc==2);kImgPathReal=argv[1];g.CStreaming_ms_files=files;g.CStreaming_ms_aInfoForModel=infos;
 g.CStreaming_ms_streamingBufferSize=&buffer;g.CStreaming_AddImageToList=Add;g.CModelInfo_GetModelInfoByName=Find;
 g.CStreaming_FlushChannels=Flush;g.CStreaming_RemoveModel=Remove;Put<int>(files,3*0x30+0x2c,1<<24);
 for(int state:{0,1,2,3,4}){
  std::memset(infos,0,sizeof(infos));g_applied=false;g_attemptFailed=false;flushes=removes=0;
  auto* fire=infos+366*0x14;Put<std::uint16_t>(fire,4,367);fire[6]=12;fire[7]=0;
  Put<std::uint32_t>(fire,8,68174);Put<std::uint32_t>(fire,12,5);Put<std::uint32_t>(fire,16,state);
  std::uint8_t before[0x14];std::memcpy(before,fire,sizeof(before));Apply();
  CHECK(g_applied && !g_attemptFailed && !std::memcmp(before,fire,sizeof(before)));
  CHECK(flushes==0 && removes==0 && std::strstr(status,"compat=1"));
  for(int id:{344,346}){auto* weapon=infos+id*0x14;CHECK(weapon[7]==3);std::uint32_t size;std::memcpy(&size,weapon+12,4);CHECK(size== (id==344?20:84));}
 }
 std::puts("PASS: real installed IMG; production Apply preserves all 20 bytes of fire_ex streaming record for unloaded/loaded/queued/reading/finishing states; no flush/remove; Colt and Molotov still use HD entries");
}
'''
(O/'test.cpp').write_text(code,encoding='utf8');vc=Path(r'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
cmd=O/'run.cmd';cmd.write_text(f'@echo off\ncall "{vc}" >nul\ncl /nologo /std:c++20 /EHsc /W3 /D_CRT_SECURE_NO_WARNINGS /I"{R / "native/src"}" /I"{Path(os.environ["JAVA_HOME"]) / "include"}" /I"{Path(os.environ["JAVA_HOME"]) / "include/win32"}" "{O / "test.cpp"}" /Fe:"{O / "test.exe"}" /Fo:"{O / "test.obj"}"\nif errorlevel 1 exit /b 1\n"{O / "test.exe"}" "{img}"\n',encoding='utf8')
p=subprocess.run(['cmd','/c',str(cmd)],cwd=O,capture_output=True,text=True,encoding='utf8',errors='replace');print(p.stdout);print(p.stderr);sys.exit(p.returncode)
