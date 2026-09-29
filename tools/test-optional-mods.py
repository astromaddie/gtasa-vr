"""Exercise production pack parsing, routing and restart state."""
import importlib.util
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import proper_world_effects as worldfx

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('builder', ROOT / 'tools/build_optional_mods.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PayloadTests(unittest.TestCase):
    def test_world_effect_records(self):
        particle = worldfx.fountain()[0]
        self.assertEqual(struct.unpack_from('<II', particle, 12), (1, 24))
        self.assertEqual(particle[20:].rstrip(b'\0'), b'water_fountain')
        lights = worldfx.neon()
        self.assertEqual(len(lights), 8)
        self.assertEqual(len(set(lights)), 8)
        for light in lights:
            self.assertEqual(struct.unpack_from('<II', light, 12), (0, 80))
            self.assertEqual(light[44], 0x41) # LOS + night, never day-only
            self.assertEqual(light[45:69].rstrip(b'\0'), b'coronastar')

    def test_effect_chunk_preserves_existing_plugins(self):
        version = 0x1803ffff
        cover = worldfx.effect((0, 0, 0), 9, bytes(12))
        existing = worldfx.chunk(worldfx.FX, struct.pack('<I', 1)+cover, version)
        unrelated = worldfx.chunk(1234, b'keep exactly', version)
        geom = worldfx.chunk(1, b'original geometry', version) + worldfx.chunk(3, existing+unrelated, version)
        result = worldfx.patch_geometry(geom, worldfx.fountain(), False)
        parts = list(worldfx.chunks(result))
        self.assertEqual(parts[0][1], b'original geometry')
        plugins = list(worldfx.chunks(parts[1][1]))
        self.assertEqual(plugins[0][1], struct.pack('<I',2)+cover+worldfx.fountain()[0])
        self.assertEqual(plugins[1], (1234,b'keep exactly',version))
        with self.assertRaises(ValueError):
            list(worldfx.chunks(result[:-1]))

    def test_img_append_and_unknown_revision(self):
        version = 0x1803ffff
        # Fill the original sector so adding the emitter must relocate it.
        geom = worldfx.chunk(1,b'x'*1940,version)+worldfx.chunk(3,b'',version)
        original = worldfx.chunk(16,worldfx.chunk(26,worldfx.chunk(15,geom,version),version),version).ljust(2048,b'\0')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'test.img'
            directory=struct.pack('<4sI',b'VER2',2)+struct.pack('<IHH24s',1,1,0,b'graveyard01_lawn.dff')+struct.pack('<IHH24s',2,1,0,b'other.dff')
            path.write_bytes(directory.ljust(2048,b'\0')+original+b'y'*2048)
            before=path.read_bytes()
            self.assertIn('unchanged',worldfx.apply(path)[0]['status'])
            self.assertEqual(path.read_bytes(),before)
            with patch.dict(worldfx.MODELS,{'graveyard01_lawn.dff':worldfx.hashlib.sha256(original).hexdigest()}):
                self.assertEqual(worldfx.apply(path)[0]['effects_added'],1)
            self.assertEqual(builder.validate_img(path),2)
            after=path.read_bytes()
            self.assertEqual(after[2048:6144],before[2048:6144])
            self.assertEqual(after[40:72],before[40:72])
            offset,sectors=struct.unpack_from('<IH',after,8)
            self.assertEqual((offset,sectors),(3,2))

    def test_paths(self):
        self.assertEqual(builder.safe_path('Data\\MAPS\\test.ipl'), 'data/maps/test.ipl')
        for path in ('../x', '/x', 'c:/x', 'data/../x', 'data//x', 'data/./x', 'data/x\n'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                builder.safe_path(path)

    def test_proper_allowlist(self):
        for path in ('texdb/gta3/gta3.dxt.dat', 'data/maps/la/lae.ide', 'anim/cuts.img'):
            self.assertTrue(builder.proper_allowed(path))
        for path in ('main.scm', 'data/script/main.scm', 'gta_sa.set', 'scripts/cheat.csa', 'libGame.so'):
            self.assertFalse(builder.proper_allowed(path))

    def test_img_bounds(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'test.img'
            good = b'VER2' + struct.pack('<I', 1) + struct.pack('<IHH24s', 1, 1, 0, b'test.dff')
            path.write_bytes(good.ljust(4096, b'\0'))
            self.assertEqual(builder.validate_img(path), 1)
            path.write_bytes(good)
            with self.assertRaises(ValueError):
                builder.validate_img(path)

    def test_manifest_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out/'data').mkdir()
            (out/'data/water.dat').write_bytes(b'water')
            report = builder.seal_payload(out, 'properfixes', {'files': 1})
            self.assertEqual(len(report['generation']), 24)
            for name in ('manifest.tsv', 'SHA256SUMS'):
                self.assertNotIn(b'\r', (out/name).read_bytes())
            self.assertEqual((out/'manifest.tsv').read_text(), 'SAVR_OPTIONAL_V1 properfixes\n5\tdata/water.dat\n')


PRELUDE = r'''
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <fstream>
#include <map>
#include <mutex>
#include <sstream>
#include <set>
#include <sys/stat.h>
#include <io.h>
#include <filesystem>
#include <iostream>
#include <vector>
#define NOMINMAX
#include <windows.h>
#include "OptionalAssetPaths.h"
#include "ModelSets.h"
#include "NativeLodSort.h"
#include "CoronaTextures.h"
#define R_OK 4
#define access _access
#define S_ISREG(m) (((m)&_S_IFMT)==_S_IFREG)
#define LOGI(...) ((void)0)
#define LOGE(...) ((void)0)
int ReplaceSettings(const char* source,const char* target) {
    // Windows rename does not replace an existing target; emulate Android's
    // POSIX rename for the production persistence state-machine test.
    return MoveFileExA(source,target,MOVEFILE_REPLACE_EXISTING)?0:-1;
}
namespace savr {
struct {
    void** CModelInfo_ms_modelInfoPtrs=nullptr;
    void* (*TextureDatabaseRuntime_GetDatabase)(const char*)=nullptr;
    void* (*CModelInfo_GetModelInfoByName)(const char*,int*)=nullptr;
    int (*CStreaming_AddImageToList)(const char*,bool)=nullptr;
    std::uint8_t* CStreaming_ms_aInfoForModel=nullptr;
    std::uint8_t* CStreaming_ms_files=nullptr;
    std::int32_t* CStreaming_ms_streamingBufferSize=nullptr;
} g;
namespace hdweapons {
bool Available(){return true;} bool Applied(){return false;}

}
namespace vrcam {bool hd=false; bool IsHdWeaponsEnabled(){return hd;} void SetHdWeaponsEnabled(bool v){hd=v;} }
}
'''

HARNESS = r'''
    struct Model {
        std::array<char, 0x28> entity{};
        std::array<char, 0x38> atomic{};
        std::array<char, 0xa0> geometry{};
        std::array<char, 0x8c> entry{};
        void* ptr = entity.data();
        void put(void* base, size_t offset, auto value) {
            std::memcpy(static_cast<char*>(base)+offset, &value, sizeof(value));
        }
        Model(std::uint64_t separate, std::uint64_t combined) {
            put(entity.data(),0x20,atomic.data()); atomic[0]=1;
            put(atomic.data(),0x30,geometry.data());
            put(geometry.data(),0x98,entry.data());
            put(entry.data(),0x32,std::uint16_t(1));
            put(entry.data(),0x5c,separate);put(entry.data(),0x4c,combined);
        }
    };

int main() {
    using namespace savr::modelsets;
    int checks=0;
    auto check=[&](bool ok){++checks; if(!ok){std::cerr<<"check "<<checks<<" failed\n";std::exit(1);}};
    check(AssetKey("DATA\\MAPS\\la\\lae.ide")=="data/maps/la/lae.ide");
    check(AssetKey("/storage/emulated/0/Android/data/com.rockstargames.gtasa/files/texdb/gta3.img")=="texdb/gta3.img");
    for(auto p:{"../data/x", "data/../../save", "/other/data/x", "vr_graphics.ini", "data//x", "data/./x", "data/x/", "gtasa1.b", "optionalmods/test"}) check(AssetKey(p).empty());
    for(auto m:{"rb", "r", "re"}) check(ReadOnlyMode(m));
    for(auto m:{"r+", "rb+", "w", "a", "w+b", ""}) check(!ReadOnlyMode(m));
    check(!ReadOnlyMode(nullptr));

    const std::string root=std::string(kFiles)+"optionalmods/properfixes/";
    std::filesystem::create_directories(root+"0123456789abcdef01234567/texdb/gta3");
    std::filesystem::create_directories(root+"0123456789abcdef01234567/anim");
    std::ofstream(root+"active.txt")<<"0123456789abcdef01234567\n";
    std::string files[]={"texdb/gta3.img","texdb/gta_int.img","texdb/cutscene.img","anim/cuts.img","texdb/gta3/gta3.dxt.dat"};
    std::ofstream manifest(root+"0123456789abcdef01234567/manifest.tsv");
    manifest<<"SAVR_OPTIONAL_V1 properfixes\n";
    for(auto& p:files){std::ofstream(root+"0123456789abcdef01234567/"+p)<<"x";manifest<<"1\t"<<p<<"\n";} manifest.close();
    check(LoadPack(PROPER_FIXES));
    packs[PROPER_FIXES].available=true;
    session[PROPER_FIXES]=true;
    check(Redirect("texdb\\gta3.img")!=nullptr);
    check(Redirect("data/missing.ide")==nullptr);
    check(Redirect("gtasa1.b")==nullptr);
    static std::string opened;
    origFopen=[](const char* p,const char*)->FILE*{opened=p;return nullptr;};
    OnFopen("texdb/gta3.img","rb"); check(opened.starts_with(root));
    OnFopen("texdb/gta3.img","r+b"); check(opened=="texdb/gta3.img");
    session[PROPER_FIXES]=false;
    check(!Redirect("texdb/gta3.img"));
    SetEnabled(PROPER_FIXES,true);check(Enabled(PROPER_FIXES));check(!session[PROPER_FIXES]);check(std::string(Status(PROPER_FIXES))=="RESTART");
    packs[PROPER_FIXES].available=false;
    SetEnabled(PROPER_FIXES,false);check(!Enabled(PROPER_FIXES));
    SetEnabled(PROPER_FIXES,true);check(!Enabled(PROPER_FIXES));
    packs[PROPER_FIXES]=Pack{};
    std::ofstream(root+"0123456789abcdef01234567/texdb/gta3.img")<<"corrupt size";
    check(!LoadPack(PROPER_FIXES));
    packs[PROPER_FIXES]=Pack{};
    std::ofstream(root+"active.txt")<<"../escape\n";
    check(!LoadPack(PROPER_FIXES));

    // Existing stock cache must never be read/written for a changed map pack.
    const char* stockCache = "CINFO.BIN";
    const char* selectedCache = stockCache;
    session[PROPER_FIXES]=false;
    check(SelectCollisionCache(&selectedCache));check(selectedCache==stockCache);
    packs[PROPER_FIXES].generation="0123456789abcdef01234567";
    session[PROPER_FIXES]=true;
    check(SelectCollisionCache(&selectedCache));
    const std::string firstCache=selectedCache;
    check(firstCache=="CINFO_SAVR_PROPER_V1_0123456789abcdef01234567.BIN");
    check(std::string(stockCache)=="CINFO.BIN");
    SetEnabled(PROPER_FIXES,false);check(firstCache==selectedCache); // choice latched until restart
    selectedCache=stockCache;
    check(SelectCollisionCache(&selectedCache));check(firstCache==selectedCache);
    selectedCache=stockCache;
    packs[PROPER_FIXES].generation="abcdef0123456789abcdef01";
    check(SelectCollisionCache(&selectedCache));check(firstCache!=selectedCache);
    selectedCache=stockCache;
    packs[PROPER_FIXES].generation="../invalid";
    check(!SelectCollisionCache(&selectedCache));check(selectedCache==stockCache);
    packs[PROPER_FIXES].generation="0123456789abcdef01234567";
    selectedCache="another-mod.bin";
    check(!SelectCollisionCache(&selectedCache));check(std::string(selectedCache)=="another-mod.bin");
    check(!SelectCollisionCache(nullptr));
    selectedCache=nullptr;check(!SelectCollisionCache(&selectedCache));
    session[PROPER_FIXES]=false;selectedCache=stockCache;
    check(SelectCollisionCache(&selectedCache));check(selectedCache==stockCache);

    static int formatSeen=-1;
    origLoadDb=[](const char*,bool,int format)->void*{formatSeen=format;return nullptr;};
    session[PROPER_FIXES]=true;
    OnLoadDb("gta3",false,6);check(formatSeen==1);
    OnLoadDb("hdweapons",false,0);check(formatSeen==0);
    session[PROPER_FIXES]=false;
    OnLoadDb("gta3",false,6);check(formatSeen==6);

    WriteStatus(PROPER_FIXES, "diagnostic test");
    std::ifstream status(std::string(kFiles)+"vr_modelset_properfixes_status.txt");
    std::string first;std::getline(status,first);check(first=="diagnostic test");
    check(!std::filesystem::exists(root+"status.txt"));

    // Meshes may use only the combined array handle.
    Model split(30,99), combined(0,20), empty(0,0), high(UINT64_MAX,0);
    static int idCalls=0;
    arraysId=[](std::uint64_t handle)->std::uint64_t {
        if(!handle) std::abort(); // emu_ArraysGetID dereferences its argument.
        ++idCalls; return handle;
    };
    static void* clumpAtomic=nullptr;
    firstAtomic=[](void*)->void* {return clumpAtomic;};
    session[PROPER_FIXES]=true;
    check(OnSortLods(&split.ptr,&combined.ptr)==-1);
    check(OnSortLods(&combined.ptr,&split.ptr)==1);
    check(OnSortLods(&combined.ptr,&combined.ptr)==0);
    check(OnSortLods(&high.ptr,&split.ptr)==-1); // unsigned, no subtract/overflow
    check(OnSortLods(&empty.ptr,&combined.ptr)==1);
    check(OnSortLods(&empty.ptr,&empty.ptr)==0);
    // Resource header without any mesh: no access beyond its 0x34 bytes.
    std::array<char,0x34> zeroMeshes{};
    empty.put(empty.geometry.data(),0x98,zeroMeshes.data());
    check(OnSortLods(&empty.ptr,&combined.ptr)==1);
    void* missing=nullptr;
    int beforeCalls=idCalls;
    check(OnSortLods(&empty.ptr,&missing)==0);check(idCalls==beforeCalls);
    combined.atomic[0]=2;clumpAtomic=nullptr;
    check(OnSortLods(&combined.ptr,&missing)==0);
    clumpAtomic=split.atomic.data();
    check(OnSortLods(&combined.ptr,&split.ptr)==0);
    combined.atomic[0]=1;
    void* objects[]={empty.ptr,combined.ptr,high.ptr,split.ptr};
    std::qsort(objects,4,sizeof(void*),OnSortLods);
    check(objects[0]==high.ptr && objects[1]==split.ptr && objects[2]==combined.ptr && objects[3]==empty.ptr);
    split.put(split.geometry.data(),0x98,static_cast<void*>(nullptr));
    check(OnSortLods(&split.ptr,&missing)==0);
    split.put(split.atomic.data(),0x30,static_cast<void*>(nullptr));
    check(OnSortLods(&split.ptr,&missing)==0);
    split.put(split.entity.data(),0x20,static_cast<void*>(nullptr));
    check(OnSortLods(&split.ptr,&missing)==0);
    origSortLods=[](const void*,const void*){return 42;};session[PROPER_FIXES]=false;
    check(OnSortLods(&split.ptr,&missing)==42);
    savr::graphicsfx::CoronaTextures<64> textures;
    int textureObjects[64]{};
    textures.Add(nullptr);
    for (int& object : textureObjects) { textures.Add(&object); textures.Add(&object); }
    check(textures.end()-textures.begin()==64);
    int slot=0;
    for (void* texture : textures) check(texture==&textureObjects[slot++]);
    std::cout<<checks<<" production runtime checks passed\n";
}
'''


def runtime_tests():
    msvc = sorted(Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC').iterdir())[-1]
    sdk = Path('C:/Program Files (x86)/Windows Kits/10')
    version = sorted((sdk/'Include').iterdir())[-1].name
    env = os.environ.copy()
    env['INCLUDE'] = ';'.join(str(p) for p in [msvc/'include', *[sdk/'Include'/version/n for n in ('ucrt','shared','um')]])
    env['LIB'] = ';'.join(str(p) for p in [msvc/'lib/x64', *[sdk/'Lib'/version/n/'x64' for n in ('ucrt','um')]])
    compiler = msvc/'bin/Hostx64/x64'
    env['PATH'] = str(compiler) + os.pathsep + env.get('PATH','')
    with tempfile.TemporaryDirectory(prefix='savr-modelsets-') as temp:
        out = Path(temp)
        header = (ROOT/'native/src/OptionalAssetPaths.h').read_text().replace(
            '"/sdcard/Android/data/com.rockstargames.gtasa/files/"', '"'+out.as_posix()+'/files/"')
        (out/'OptionalAssetPaths.h').write_text(header)
        (out/'ModelSets.h').write_text((ROOT/'native/src/ModelSets.h').read_text())
        (out/'NativeLodSort.h').write_text((ROOT/'native/src/NativeLodSort.h').read_text())
        (out/'CoronaTextures.h').write_text((ROOT/'native/src/CoronaTextures.h').read_text())
        source = (ROOT/'native/src/ModelSets.cpp').read_text()
        source = source[source.index('namespace savr::modelsets {'):]
        source = source[:source.index('// Only relocation-free')] + source[source.index('void* OnLoadDb'):]
        source = source[:source.index('void Install(void* handle)')] + source[source.index('bool Enabled(int set)'):]
        source = source.replace('/sdcard/Android/data/com.rockstargames.gtasa/files/vr_modelsets.ini',out.as_posix()+'/files/vr_modelsets.ini')
        source = source.replace('std::rename(', 'ReplaceSettings(')
        (out/'test.cpp').write_text(PRELUDE+source+HARNESS)
        subprocess.run([str(compiler/'cl.exe'),'/nologo','/std:c++20','/EHsc','/MD',str(out/'test.cpp'),
                        '/Fe:'+str(out/'test.exe'),'/Fo:'+str(out/'test.obj')], env=env, check=True)
        subprocess.run([str(out/'test.exe')],check=True)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PayloadTests))
    if not result.wasSuccessful(): raise SystemExit(1)
    runtime_tests()
