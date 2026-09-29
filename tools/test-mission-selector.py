"""Exercise the production selector functions in a Windows C++ host harness."""
from pathlib import Path
import os, re, subprocess
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build' / 'mission-selector-tests'
OUT.mkdir(parents=True, exist_ok=True)
source = (ROOT / 'native/src/Cheats.cpp').read_text(encoding='utf8')
def function(signature):
    start = source.index(signature)
    pos = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[pos] == '{') - (source[pos] == '}')
        pos += 1
    return source[start:pos]
prelude = r'''
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <cassert>
#include <string>
#include "MissionCatalog.h"
#include "DirectMission.h"
using namespace savr::cheats;
enum class Kind { Plain, MissionSelect, MissionLaunch, GodMode, SpawnByButton };
struct Entry { const char* label; Kind kind; };
Entry g_cheats[] = {{"MISSION GROUP",Kind::MissionSelect},
    {"MISSION NUMBER",Kind::MissionSelect},{"LAUNCH MISSION",Kind::MissionLaunch},
    {"UNCHANGED",Kind::Plain},{"GOD MODE",Kind::GodMode}};
int Count() { return 5; }
int* g_numMissions = nullptr;
std::atomic<int> g_missionPageSel{0}, g_missionNumberSel{0};
std::atomic<bool> g_godMode{false}, g_spawnByButton{false};
std::atomic<const char*> g_directMissionBlock{nullptr};
constexpr int kMissionPageCount = missioncatalog::kPageCount;
'''
main = r'''

bool fakeOnMission=false, fakeRunning=false, fakePack=false, fakeLoadFailure=false;
int initCalls=0, processCalls=0, launchedId=-1;
bool OnMission() { return fakeOnMission; }
void ScriptInit(void* ptr) {
    ++initCalls;
    std::memset(ptr,0,0x130);
    std::memcpy(static_cast<unsigned char*>(ptr)+0x10,"noname",7);
}
int Process(void* ptr,int opcode) {
    ++processCalls;
    assert(opcode==0x0417);
    unsigned char* ip=nullptr;
    std::memcpy(&ip,static_cast<unsigned char*>(ptr)+0x20,sizeof(ip));
    assert(ip && ip[0]==4);
    assert(ip[1]==45 || ip[1]==71);
    launchedId=ip[1];
    fakeRunning=!fakeLoadFailure;
    return 0;
}
void TestDirectLauncher() {
    using directmission::Api;
    Api api;
    assert(!api.Launch(0,false,false));
    int idleSlot=0, area=0, kingStage=1, catProgress=0;void* idle=&idleSlot;
    std::uint16_t count=135, exclusive=0;
    api={ScriptInit,Process,OnMission,&fakeRunning,&idle,&count,&exclusive,&fakePack,&area,&kingStage,&catProgress};
    assert(api.Available());
    assert(api.Launch(0,false,false));assert(launchedId==45 && initCalls==1);
    assert(kingStage==2 && catProgress==1); // native CAT caller's post-launch stage
    assert(!api.Launch(1,false,false)); // The mission buffer is already occupied.
    fakeRunning=false;
    kingStage=1;catProgress=0;
    assert(api.Launch(1,false,false));assert(launchedId==71 && initCalls==2);
    assert(kingStage==1 && catProgress==0); // Back to School must not touch CAT
    fakeRunning=false;
    assert(!api.Launch(-1,false,false) && !api.Launch(2,false,false));
    assert(!api.Launch(0,true,false) && !api.Launch(0,false,true));
    fakeOnMission=true;assert(!api.Launch(0,false,false));fakeOnMission=false;
    area=3;assert(!api.Launch(0,false,false));area=0;
    fakePack=true;assert(!api.Launch(0,false,false));fakePack=false;
    exclusive=2;assert(!api.Launch(0,false,false));exclusive=0;
    count=71;assert(!api.Launch(0,false,false));count=135;
    idle=nullptr;assert(!api.Launch(0,false,false));idle=&idleSlot;
    assert(processCalls==2 && initCalls==2);
    assert(kingStage==1 && catProgress==0); // every rejected launch preserved it
    fakeLoadFailure=true;assert(!api.Launch(0,false,false));assert(kingStage==1 && catProgress==0);
    fakeLoadFailure=false;
    for(int existing : {1,2,3,4}) {
        fakeRunning=false;catProgress=existing;
        assert(api.Launch(0,false,false));assert(catProgress==existing && kingStage==2);
    }
    fakeRunning=false;
    std::puts("PASS: King prepares missing First Date prerequisite only on successful launch; later dates, School, blocked and failed launches preserved");
    g_missionPageSel=6;g_missionNumberSel=0;
    g_directMissionBlock="FINISH CURRENT MISSION";
    assert(std::strcmp(Name(2),"FINISH CURRENT MISSION")==0);
    assert(std::strstr(Name(1),"KING IN EXILE"));
    g_directMissionBlock=nullptr;
}
int main() {
    TestDirectLauncher();
    const int expected[] = {84,16,83,84,75,23,2};
    int counts[6]{};
    int visited = 0;
    for (int mode=0;mode<4;++mode) {
        g_numMissions = mode ? counts : nullptr;
        for (int p=0;p<7;++p) {
            if (p<6) counts[p] = mode==2 ? -1 : (mode==3 ? 513 : 0);
            g_missionPageSel=p; g_missionNumberSel=0;
            assert(MissionCountForPage(p)==expected[p]);
            for (int i=0;i<expected[p];++i) {
                assert(g_missionNumberSel==i);
                const char* title=missioncatalog::Name(p,i);
                assert(title && title[0]);
                assert(std::strcmp(title,"UNNAMED RETAIL ENTRY")!=0);
                std::string selection=Name(1), launch=Name(2), group=Name(0);
                assert(selection.find(title)!=std::string::npos);
                assert(launch.find(title)!=std::string::npos);
                assert(group.find(missioncatalog::kPageNames[p])!=std::string::npos);
                // PanelTextFit at minimum scale must fit all labels in 512px.
                assert(selection.size()*6<=504 && launch.size()*6<=504);
                ++visited; StepMissionSelection(false,+1);
            }
            assert(g_missionNumberSel==0);
            StepMissionSelection(false,-1); assert(g_missionNumberSel==expected[p]-1);
            StepMissionSelection(false,+1); assert(g_missionNumberSel==0);
        }
    }
    g_numMissions=nullptr;
    g_missionPageSel=0;g_missionNumberSel=83;
    StepMissionSelection(true,+1);assert(g_missionPageSel==1 && g_missionNumberSel==15);
    StepMissionSelection(true,-1);assert(g_missionPageSel==0 && g_missionNumberSel==15);
    StepMissionSelection(true,-1);assert(g_missionPageSel==6 && g_missionNumberSel==1);
    StepMissionSelection(true,+1);assert(g_missionPageSel==0);
    assert(std::strcmp(missioncatalog::Name(0,22),"CATALYST")==0);
    assert(std::strcmp(missioncatalog::Name(0,23),"ROBBING UNCLE SAM")==0);
    assert(std::strcmp(missioncatalog::Name(1,8),"VERTICAL BIRD")==0);
    assert(std::strcmp(missioncatalog::Name(3,39),"KING IN EXILE (CUTSCENE)")==0);
    assert(std::strcmp(Name(3),"UNCHANGED")==0);
    assert(std::strcmp(Name(-1),"")==0 && std::strcmp(Name(5),"")==0);
    assert(missioncatalog::Count(-1)==0 && missioncatalog::Count(7)==0);
    assert(std::strcmp(missioncatalog::Name(0,84),"UNNAMED RETAIL ENTRY")==0);
    // Proper runtime counts, short initialization and invalid retail buffer sizes.
    for(int p=0;p<7;++p) {
        assert(missioncatalog::Count(p,expected[p])==expected[p]);
        assert(missioncatalog::Count(p,1)==expected[p]);
        assert(missioncatalog::Count(p,257)==expected[p]);
        assert(missioncatalog::Count(p,512)==expected[p]);
    }
    std::printf("PASS: %d selectable entries across missing/zero/negative/invalid retail counts; labels, wrapping, page clamp, panel width.\n",visited);
}
'''
cpp = OUT/'selector-test.cpp'
cpp.write_text(prelude+'\n'.join(function(s) for s in ['int MissionCountForPage(', 'void StepMissionSelection(', 'const char* Name(int index)'])+'\n'+main,encoding='utf8')
vcvars = Path(os.environ.get('VS_VCVARS64', r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'))
assert vcvars.is_file(), 'Set VS_VCVARS64 to the Visual Studio environment batch file'
exe=OUT/'selector-test.exe'
cmd=OUT/'run-test.cmd'
cmd.write_text(f'@echo off\ncall "{vcvars}" >nul\nif errorlevel 1 exit /b %errorlevel%\ncl /nologo /std:c++17 /EHsc /W4 /I"{ROOT / "native/src"}" /Fe:"{exe}" /Fo:"{OUT / "selector-test.obj"}" "{cpp}"\nif errorlevel 1 exit /b %errorlevel%\n"{exe}"\n',encoding='utf8')
subprocess.run(['cmd.exe','/d','/c',str(cmd)],check=True)
