#include "ModelSets.h"
#include "LoadingTrace.h"
#include "NativeLodSort.h"
#include "OptionalAssetPaths.h"
#include "HdWeapons.h"
#include "Log.h"
#include "Symbols.h"
#include "VrCamera.h"

#include <array>
#include <atomic>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <fstream>
#include <map>
#include <mutex>
#include <sstream>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

namespace savr::modelsets {
namespace {
constexpr const char* kNames[COUNT] = {"hdweapons", "properfixes"};
constexpr char kSettings[] = "/sdcard/Android/data/com.rockstargames.gtasa/files/vr_modelsets.ini";
struct Pack {
    std::string root;
    std::string generation;
    std::map<std::string, std::string, std::less<>> files;
    bool available = false;
};
Pack packs[COUNT];
std::atomic<bool> desired[COUNT]{};
std::atomic<bool> applied[COUNT]{};
std::atomic<bool> failed[COUNT]{};
bool session[COUNT]{};
std::mutex saveMutex;
std::string collisionCacheName;
using NvOpen = void* (*)(const char*);
using FileOpen = FILE* (*)(const char*, const char*);
using LoadDb = void* (*)(const char*, bool, int);
NvOpen origNvOpen = nullptr;
FileOpen origFopen = nullptr;
LoadDb origLoadDb = nullptr;
using SortLods = int (*)(const void*, const void*);
SortLods origSortLods = nullptr;
lodsort::FirstAtomic firstAtomic = nullptr;
lodsort::ArraysId arraysId = nullptr;
int OnSortLods(const void* a, const void* b) {
    if (!session[PROPER_FIXES]) return origSortLods(a, b);
    return lodsort::Compare(a, b, firstAtomic, arraysId);
}

void WriteStatus(int set, const char* status) {
    const auto path = std::string(kFiles) + "vr_modelset_" + kNames[set] + "_status.txt";
    if (FILE* f = std::fopen(path.c_str(), "w")) {
        std::fprintf(f, "%s\ngeneration=%s\nrequested=%d\nsession=%d\ncollision_cache=%s\n", status, packs[set].root.c_str(), desired[set].load(), session[set], collisionCacheName.empty() ? "CINFO.BIN" : collisionCacheName.c_str());
        std::fclose(f);
    }
    LOGI("[modelsets] %s: %s", kNames[set], status);
}

bool LoadPack(int set) {
    auto& pack = packs[set];
    std::string base = std::string(kFiles) + "optionalmods/" + kNames[set] + "/";
    std::ifstream active(base + "active.txt");
    std::string generation;
    if (!std::getline(active, generation)) return false;
    if (!generation.empty() && generation.back() == '\r') generation.pop_back();
    if (generation.size() != 24 || generation.find_first_not_of("0123456789abcdef") != generation.npos) return false;
    pack.generation = generation;
    pack.root = base + generation + "/";
    std::ifstream manifest(pack.root + "manifest.tsv");
    std::string line;
    if (!std::getline(manifest, line)) return false;
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line != std::string("SAVR_OPTIONAL_V1 ") + kNames[set]) return false;
    while (std::getline(manifest, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        const auto tab = line.find('\t');
        if (tab == line.npos || tab == 0 || line.substr(0, tab).find_first_not_of("0123456789") != line.npos) return false;
        const std::string path = line.substr(tab + 1);
        if (!SafeRelative(path) || pack.files.contains(path) || pack.files.size() >= 8192) return false;
        const auto absolute = pack.root + path;
        struct stat st{};
        const auto size = std::strtoull(line.c_str(), nullptr, 10);
        if (!size || size > 2147483647u || stat(absolute.c_str(), &st) || !S_ISREG(st.st_mode) ||
            static_cast<unsigned long long>(st.st_size) != size || access(absolute.c_str(), R_OK)) return false;
        if (set == PROPER_FIXES && AssetKey(path.c_str()) != path) return false;
        pack.files.emplace(path, absolute);
    }
    return pack.files.contains("texdb/gta3.img") && pack.files.contains("texdb/gta_int.img") &&
           pack.files.contains("texdb/cutscene.img") && pack.files.contains("anim/cuts.img") &&
           pack.files.contains("texdb/gta3/gta3.dxt.dat");
}

const char* Redirect(const char* name) {
    const auto key = AssetKey(name);
    if (key.empty()) return nullptr;
    for (int set : {PROPER_FIXES}) {
        if (!session[set]) continue;
        const auto it = packs[set].files.find(key);
        if (it != packs[set].files.end()) return it->second.c_str();
    }
    return nullptr;
}

void* OnNvOpen(const char* name) {
    if (const char* replacement = Redirect(name)) return origNvOpen(replacement);
    return origNvOpen(name);
}
FILE* OnFopen(const char* name, const char* mode) {
    if (ReadOnlyMode(mode))
        if (const char* replacement = Redirect(name)) return origFopen(replacement, mode);
    return origFopen(name, mode);
}

// CINFO caches model/LOD collision links, not just file offsets. An IDE type
// change can invalidate links even when every model ID and IMG name is intact.
// Use the native cache builder with a per-generation filename in its usual
// writable app directory. Never reuse or overwrite stock CINFO for a map mod.
bool SelectCollisionCache(const char** cacheName) {
    if (!session[PROPER_FIXES]) return true;
    const auto& generation = packs[PROPER_FIXES].generation;
    if (!cacheName || !*cacheName || std::strcmp(*cacheName, "CINFO.BIN") ||
        generation.size() != 24 || generation.find_first_not_of("0123456789abcdef") != generation.npos)
        return false;
    collisionCacheName = "CINFO_SAVR_PROPER_V1_" + generation + ".BIN";
    *cacheName = collisionCacheName.c_str();
    return true;
}

// Only relocation-free, exact retail 2.11 prologues may use this trampoline.
template<class Fn>
bool Hook(void* target, const std::array<std::uint32_t, 4>& expected, Fn replacement, Fn& original) {
    if (!target || std::memcmp(target, expected.data(), 16)) return false;
    const auto pageSize = static_cast<std::uintptr_t>(sysconf(_SC_PAGESIZE));
    auto* code = static_cast<std::uint32_t*>(mmap(nullptr, pageSize, PROT_READ | PROT_WRITE | PROT_EXEC,
                                                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
    if (code == MAP_FAILED) return false;
    std::memcpy(code, target, 16);
    code[4] = 0x58000051u; code[5] = 0xd61f0220u;
    *reinterpret_cast<void**>(code + 6) = static_cast<char*>(target) + 16;
    __builtin___clear_cache(reinterpret_cast<char*>(code), reinterpret_cast<char*>(code) + 32);
    const auto begin = reinterpret_cast<std::uintptr_t>(target) & ~(pageSize - 1);
    const auto end = (reinterpret_cast<std::uintptr_t>(target) + 16 + pageSize - 1) & ~(pageSize - 1);
    if (mprotect(reinterpret_cast<void*>(begin), end - begin, PROT_READ | PROT_WRITE | PROT_EXEC)) {
        munmap(code, pageSize); return false;
    }
    original = reinterpret_cast<Fn>(code);
    auto* patch = static_cast<std::uint32_t*>(target);
    patch[0] = 0x58000051u; patch[1] = 0xd61f0220u;
    *reinterpret_cast<Fn*>(patch + 2) = replacement;
    __builtin___clear_cache(static_cast<char*>(target), static_cast<char*>(target) + 16);
    return true;
}

bool FixLegacyCollisionAllocation(void* handle) {
    auto* loader = static_cast<char*>(dlsym(handle, "_ZN11CFileLoader18LoadCollisionModelEPhR9CColModelPKc"));
    if (!loader || reinterpret_cast<std::uintptr_t>(loader) != g.LoadBase + 0x49038c) return false;
    // Retail 2.11 allocates 6*N bytes for COLL vertices, then copies 12*N.
    // Guard both allocation and copy before changing LSL #1 to LSL #2.
    constexpr std::array<std::uint32_t, 15> expected = {
        0x8b1606c8, 0xd37ff900, 0x940d9385, 0xaa1f03e8, 0xf9001280,
        0x8b0802a9, 0xf940128a, 0xf10006d6, 0xb940092b, 0xf9400129,
        0x8b08014a, 0x91003108, 0xb900094b, 0xf9000149, 0x54fffee1
    };
    auto* code = reinterpret_cast<std::uint32_t*>(loader + 0x218);
    if (std::memcmp(code, expected.data(), sizeof(expected))) return false;
    const auto pageSize = static_cast<std::uintptr_t>(sysconf(_SC_PAGESIZE));
    const auto page = reinterpret_cast<std::uintptr_t>(code + 1) & ~(pageSize - 1);
    if (mprotect(reinterpret_cast<void*>(page), pageSize, PROT_READ | PROT_WRITE | PROT_EXEC)) return false;
    code[1] = 0xd37ef500; // 3*N << 2 = N*sizeof(CVector).
    __builtin___clear_cache(reinterpret_cast<char*>(code + 1), reinterpret_cast<char*>(code + 2));
    LOGI("[modelsets] COLL vertex allocation corrected: 12 bytes per vertex");
    return true;
}

bool FileHooks(void* handle) {
    // This import belongs only to libGame; our own manifest/settings I/O never
    // enters it. Exact offset is guarded by the supported build AND libc target.
    auto** slot = reinterpret_cast<void**>(g.LoadBase + 0x8483e0);
    auto* libcFopen = dlsym(RTLD_DEFAULT, "fopen");
    if (*slot != libcFopen) return false;
    const auto page = static_cast<std::uintptr_t>(sysconf(_SC_PAGESIZE));
    if (mprotect(reinterpret_cast<void*>(reinterpret_cast<std::uintptr_t>(slot) & ~(page-1)),
                 page, PROT_READ | PROT_WRITE)) return false;
    if (!Hook(dlsym(handle, "_Z7NvFOpenPKc"), {0xa9bd7bfd,0xf9000bf5,0xa9024ff4,0x910003fd}, &OnNvOpen, origNvOpen)) return false;
    origFopen = reinterpret_cast<FileOpen>(libcFopen);
    __atomic_store_n(slot, reinterpret_cast<void*>(&OnFopen), __ATOMIC_RELEASE);
    return true;
}

void* OnLoadDb(const char* name, bool preload, int format) {
    // Proper's supplied GPU payload is DXT (enum 1 in retail 2.11). Do not let
    // auto-detection pair its listing with a stock ETC/PVR data file.
    if (session[PROPER_FIXES] && name &&
        (!std::strcmp(name,"gta3") || !std::strcmp(name,"gta_int") || !std::strcmp(name,"cutscene"))) format = 1;
    const bool trace = session[PROPER_FIXES] && name &&
        (!std::strcmp(name,"gta3") || !std::strcmp(name,"gta_int") || !std::strcmp(name,"cutscene"));
    char status[160];
    if (trace) {
        std::snprintf(status, sizeof(status), "loading database=%s format=%d", name, format);
        WriteStatus(PROPER_FIXES, status);
    }
    void* db = origLoadDb(name, preload, format);
    if (trace) {
        std::snprintf(status, sizeof(status), "%s database=%s format=%d",
                      db ? "loaded" : "failed", name, format);
        WriteStatus(PROPER_FIXES, status);
        if (!db) failed[PROPER_FIXES] = true;
    }
    return db;
}

} // namespace

void Install(void* handle) {
    { std::ifstream settings(kSettings); std::string line;
      while (std::getline(settings, line)) {
          if (!line.empty() && line.back() == '\r') line.pop_back();
          if (line == "ProperFixes=1") desired[PROPER_FIXES] = true;
      }
    }
    for (int set : {PROPER_FIXES}) {
        packs[set].available = LoadPack(set);
        session[set] = desired[set] && packs[set].available;
        if (!session[set]) WriteStatus(set, desired[set] ? "inactive: incomplete or unreadable payload" : "off: original assets");
    }
    if (!session[PROPER_FIXES]) return;
    const bool known = g.LoadBase && reinterpret_cast<std::uintptr_t>(g.implOnDrawFrame) - g.LoadBase == 0x7d28d4u;
    if (!known || !FileHooks(handle)) {
        for (int set : {PROPER_FIXES}) {
            if (session[set]) { failed[set] = true; WriteStatus(set, "failed: unsupported file hooks"); }
            session[set] = false;
        }
        return;
    }
    if (!FixLegacyCollisionAllocation(handle)) {
        for (int set : {PROPER_FIXES}) {
            if (session[set]) {
                failed[set] = true; session[set] = false;
                WriteStatus(set, "failed: unsupported legacy collision allocator");
            }
        }
        return;
    }
    if (!session[PROPER_FIXES]) return;
    if (!Hook(reinterpret_cast<void*>(g.TextureDatabaseRuntime_Load),
              {0xa9bb7bfd,0xf9000bf9,0xa9025ff8,0xa90357f6}, &OnLoadDb, origLoadDb)) {
        failed[PROPER_FIXES] = true; session[PROPER_FIXES] = false;
        WriteStatus(PROPER_FIXES, "failed: unsupported collision or texture loader");
        return;
    }
    firstAtomic = reinterpret_cast<lodsort::FirstAtomic>(dlsym(handle, "_Z14GetFirstAtomicP7RpClump"));
    arraysId = reinterpret_cast<lodsort::ArraysId>(dlsym(handle, "_Z15emu_ArraysGetIDy"));
    if (!firstAtomic || !arraysId ||
        !Hook(dlsym(handle, "_Z8sortLODsPKvS0_"),
              {0xa9be7bfd,0xa9014ff4,0x910003fd,0xf9400008}, &OnSortLods, origSortLods)) {
        session[PROPER_FIXES] = false;
        failed[PROPER_FIXES] = true;
        WriteStatus(PROPER_FIXES, "failed: unsupported LOD sorting; original assets selected");
        return;
    }
    auto** cacheName = reinterpret_cast<const char**>(dlsym(handle, "_ZN9CColAccel13mp_cCacheNameE"));
    if (!SelectCollisionCache(cacheName)) {
        session[PROPER_FIXES] = false;
        failed[PROPER_FIXES] = true;
        WriteStatus(PROPER_FIXES, "failed: unsupported collision cache; original assets selected");
        return;
    }
    loadingtrace::Start();
    applied[PROPER_FIXES] = session[PROPER_FIXES];
    if (session[PROPER_FIXES]) WriteStatus(PROPER_FIXES, "active: read-only asset overlay; DXT databases");

}

bool Enabled(int set) {
    return set == HD_WEAPONS ? vrcam::IsHdWeaponsEnabled() : set > HD_WEAPONS && set < COUNT && desired[set];
}
void SetEnabled(int set, bool enabled) {
    if (set < 0 || set >= COUNT || (enabled && !Available(set))) return;
    if (set == HD_WEAPONS) { vrcam::SetHdWeaponsEnabled(enabled); return; }
    std::lock_guard lock(saveMutex);
    const auto temp = std::string(kSettings) + ".tmp";
    FILE* file = std::fopen(temp.c_str(), "w");
    if (!file) { LOGE("[modelsets] cannot save settings"); return; }
    const bool proper = set == PROPER_FIXES ? enabled : desired[PROPER_FIXES].load();
    const bool written = std::fprintf(file,"ProperFixes=%d\n",proper) > 0;
    const bool closed = std::fclose(file) == 0;
    if (written && closed && std::rename(temp.c_str(), kSettings) == 0) desired[set] = enabled;
    else LOGE("[modelsets] settings write failed");
}
bool Available(int set) {
    return set == HD_WEAPONS ? hdweapons::Available() : set > HD_WEAPONS && set < COUNT && packs[set].available;
}
bool Applied(int set) {
    return set == HD_WEAPONS ? hdweapons::Applied() : set > HD_WEAPONS && set < COUNT && applied[set];
}
const char* Status(int set) {
    if (!Available(set)) return "NO FILES";
    if (set != HD_WEAPONS && failed[set]) return "LOAD FAILED";
    const bool boot = set == HD_WEAPONS ? Applied(set) : session[set];
    return Enabled(set) != boot ? "RESTART" : "";
}
} // namespace savr::modelsets
