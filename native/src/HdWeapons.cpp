// HD weapon model set. The payload built by tools/build_hdweapons.py lives
// under the app files dir:
//   files/hdweapons/gta3.img            VER2 image with replacement DFFs
//   files/texdb/hdweapons/hdweapons.txt loose-PNG texture database (format 0)
//   files/texdb/hdweapons/src/*.png
// When the option is ON, the image is registered as an extra streaming CD
// image (CStreaming::AddImageToList) and each weapon model's streaming-info
// entry is repointed at it, so the very next stream-in reads the HD model.
// The texture database is the engine's own text format: registered via
// TextureDatabaseRuntime::Load with format 0, where every texture loads from
// src/<name>.png through the engine's PNG reader, and GetTexture resolves
// names across all registered databases. Nothing in the stock APK changes;
// removing the files restores the original look.
#include "HdWeapons.h"
#include "PngRasterUpload.h"
#include <dlfcn.h>

#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include "Log.h"
#include "Symbols.h"
#include "StoragePaths.h"

namespace savr::hdweapons {
namespace {

const char* const kFilesDir = savr::storage::FilesDir().c_str();
// Registered RELATIVE to the files dir (Apply chdirs there first): the
// ms_files name field is only 40 bytes and an absolute /sdcard path aborts
// the engine's fortified strcpy. The engine lowercases + converts '\'->'/'
// before fopen (OS_NormalizeFilename), so this opens files/hdweapons/... .
//
// The BACKSLASH is load-bearing: for every streamed DFF the engine derives a
// texture-database key from the archive name = strip ".img", then take the
// tail after the FIRST '\' (ConvertBufferToObject @0x3b1690 strchr('\\')+1,
// with NO null guard). A forward-slash-only name made strchr return NULL and
// the +1 produced 0x1, crashing GetDatabase's strcmp. Naming it so the tail
// equals "hdweapons" both fixes that AND makes GetDatabase("hdweapons") match
// our loose-PNG texture database, so the HD textures actually bind.
constexpr char kImgPath[] = "hdweapons\\hdweapons.img";
const char* const kImgPathReal =
    savr::storage::FilesPath("hdweapons/hdweapons.img");
const char* const kTexDbListing =
    savr::storage::FilesPath("texdb/hdweapons/hdweapons.txt");

constexpr int kInfoStride = 0x14;      // CStreamingInfo on arm64
constexpr int kFilesStride = 0x30;     // CStreaming::ms_files entry

std::atomic<bool> g_applied{false};
// The choice is latched once per session the moment the engine could apply
// it (Vice City semantics: flipping the menu row later shows RESTART and
// takes effect on the next start, so weapon models never swap mid-combat).
std::atomic<int> g_sessionChoice{-1};
bool g_attemptFailed = false;

struct DirEntry {
    std::uint32_t posn;
    std::uint16_t sizeSectors;
    std::uint16_t sizeArchive;
    char name[24];
};

bool PayloadPresent() {
    struct stat st{};
    const int imgRc = stat(kImgPathReal, &st);
    const int imgErr = errno;
    const int txtRc = stat(kTexDbListing, &st);
    const int txtErr = errno;
    const bool ok = imgRc == 0 && txtRc == 0;
    if (!ok) {
        static int logged = 0;
        if (logged < 5) {
            ++logged;
            LOGE("[hdweapons] payload NOT visible to the game: "
                 "img rc=%d errno=%d(%s) [%s] | txt rc=%d errno=%d(%s) [%s]",
                 imgRc, imgErr, std::strerror(imgErr), kImgPathReal,
                 txtRc, txtErr, std::strerror(txtErr), kTexDbListing);
        }
    }
    return ok;
}

// On-device breadcrumb: the boot-time apply races the logcat ring buffer, so
// the outcome also lands in a file the next debugging session can read.
void WriteStatus(const char* text) {
    if (FILE* f = std::fopen(
            savr::storage::Files("hdweapons/status.txt").c_str(), "w")) {
        std::fputs(text, f);
        std::fclose(f);
    }
}

bool EngineReady() {
    return g.CStreaming_AddImageToList && g.CStreaming_ms_aInfoForModel &&
        g.CStreaming_ms_files && g.CModelInfo_GetModelInfoByName &&
        g.TextureDatabaseRuntime_Load && g.TextureDatabaseRuntime_GetDatabase &&
        g.TextureDatabaseRuntime_SortEntries &&
        g.CStreaming_RemoveModel && g.CStreaming_FlushChannels &&
        // The stock databases register in CGame::InitialiseRenderWare; until
        // gta3 exists the texture runtime is not ready for a new database.
        g.TextureDatabaseRuntime_GetDatabase("gta3") != nullptr &&
        // CStreaming::InitImageList populates ms_files[0] with the retail
        // gta3.img later in boot. Registering before it runs is doubly wrong:
        // the retail init overwrites our slot 0, and a slot-0 CdStream handle
        // (slot << 24) is indistinguishable from the open-failure zero.
        g.CStreaming_ms_files[0] != 0;
}

// SortEntries(db, bool) also reorders the per-format thumbnail records loaded
// from the database's .tmb file; our database ships no thumbnails (they only
// feed the mobile menu galleries), and with the bool false the reorder walks a
// null thumbnail array — the engine never hits this because every stock
// database has its .tmb. The bool true skips both thumbnail passes, so the
// hook forces it for the one Load call that registers our database.
using SortEntriesFn = void (*)(void*, bool);
SortEntriesFn g_origSortEntries = nullptr;
std::atomic<bool> g_loadingOurDb{false};

void OnSortEntries(void* db, bool skipThumbs) {
    if (g_loadingOurDb.load(std::memory_order_relaxed)) skipThumbs = true;
    if (g_origSortEntries) g_origSortEntries(db, skipThumbs);
}

bool InstallSortEntriesHook() {
    if (g_origSortEntries) return true;
    void* target = g.TextureDatabaseRuntime_SortEntries;
    constexpr std::uint32_t kExpected[4] = {
        0xd10203ffu, 0xa9027bfdu, 0xa9036ffcu, 0xa90467fau};
    std::uint32_t observed[4]{};
    std::memcpy(observed, target, sizeof(observed));
    if (std::memcmp(observed, kExpected, sizeof(observed)) != 0) {
        LOGE("[hdweapons] SortEntries prologue mismatch: %08x %08x %08x %08x",
             observed[0], observed[1], observed[2], observed[3]);
        return false;
    }
    const auto pageSize =
        static_cast<std::uintptr_t>(sysconf(_SC_PAGESIZE));
    void* trampoline = mmap(nullptr, pageSize, PROT_READ | PROT_WRITE |
                            PROT_EXEC, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (trampoline == MAP_FAILED) return false;
    auto* t = reinterpret_cast<std::uint32_t*>(trampoline);
    std::memcpy(t, target, 16);
    t[4] = 0x58000051u;   // LDR X17, resume literal
    t[5] = 0xD61F0220u;   // BR X17
    *reinterpret_cast<void**>(t + 6) = reinterpret_cast<void*>(
        reinterpret_cast<std::uintptr_t>(target) + 16);
    __builtin___clear_cache(reinterpret_cast<char*>(t),
                            reinterpret_cast<char*>(t) + 32);
    auto* code = reinterpret_cast<std::uint32_t*>(target);
    const std::uintptr_t start =
        reinterpret_cast<std::uintptr_t>(code) & ~(pageSize - 1);
    const std::uintptr_t end =
        (reinterpret_cast<std::uintptr_t>(code) + 16 + pageSize - 1) &
        ~(pageSize - 1);
    if (mprotect(reinterpret_cast<void*>(start), end - start,
                 PROT_READ | PROT_WRITE | PROT_EXEC) != 0) {
        munmap(trampoline, pageSize);
        return false;
    }
    code[0] = 0x58000051u;
    code[1] = 0xD61F0220u;
    *reinterpret_cast<void**>(code + 2) =
        reinterpret_cast<void*>(&OnSortEntries);
    __builtin___clear_cache(reinterpret_cast<char*>(code),
                            reinterpret_cast<char*>(code) + 16);
    g_origSortEntries = reinterpret_cast<SortEntriesFn>(trampoline);
    LOGI("[hdweapons] SortEntries hook installed");
    return true;
}

void Apply() {
    // Texture databases and loose PNGs resolve as "texdb/..." relative to the
    // process cwd (the APK asset layer is consulted first and misses them).
    // The audio deployment already chdirs here when present; make it
    // unconditional so the HD set works without the audio packs too.
    char cwd[256]{};
    if (getcwd(cwd, sizeof(cwd)) == nullptr ||
        std::strcmp(cwd, kFilesDir) != 0) {
        if (chdir(kFilesDir) != 0) {
            LOGE("[hdweapons] chdir(%s) failed", kFilesDir);
            WriteStatus("failed: chdir\n");
            g_attemptFailed = true;
            return;
        }
        LOGI("[hdweapons] cwd -> %s", kFilesDir);
    }

    if (!InstallSortEntriesHook()) {
        WriteStatus("failed: SortEntries hook\n");
        g_attemptFailed = true;
        return;
    }
    // The optional database has only 89 entries and is registered during the
    // startup/loading window.  Loading it lazily caused the first appearance
    // of each weapon to decode PNGs synchronously on the GameThread (11-42 ms
    // per texture, with several often landing in one frame).  Preload this
    // small database once here; the large retail gta3/txd databases retain
    // their original streaming policy and the 128 MiTex cache keeps the HD
    // set resident afterwards.
    void* db = LoadLooseDatabase("hdweapons", true);
    if (db == nullptr) {
        LOGE("[hdweapons] texture database load failed");
        WriteStatus("failed: texture database load\n");
        g_attemptFailed = true;
        return;
    }

    const int imgIdx = g.CStreaming_AddImageToList(kImgPath, true);
    const std::uint8_t* fileSlot = g.CStreaming_ms_files +
        static_cast<std::size_t>(imgIdx) * kFilesStride;
    const std::int32_t handle =
        *reinterpret_cast<const std::int32_t*>(fileSlot + 0x2c);
    if (imgIdx < 0 || imgIdx >= 8 || handle == 0) {
        LOGE("[hdweapons] image registration failed idx=%d handle=%d",
             imgIdx, handle);
        char status[96];
        std::snprintf(status, sizeof(status),
                      "failed: image registration idx=%d handle=%d\n",
                      imgIdx, handle);
        WriteStatus(status);
        g_attemptFailed = true;
        return;
    }

    FILE* img = std::fopen(kImgPathReal, "rb");
    if (img == nullptr) {
        LOGE("[hdweapons] cannot read %s", kImgPathReal);
        WriteStatus("failed: image unreadable\n");
        g_attemptFailed = true;
        return;
    }
    char magic[4]{};
    std::uint32_t count = 0;
    if (std::fread(magic, 1, 4, img) != 4 ||
        std::memcmp(magic, "VER2", 4) != 0 ||
        std::fread(&count, 4, 1, img) != 1 || count > 4096) {
        LOGE("[hdweapons] bad image header");
        std::fclose(img);
        WriteStatus("failed: bad image header\n");
        g_attemptFailed = true;
        return;
    }

    int repointed = 0, missing = 0, flushed = 0, outOfRange = 0, oversized = 0;
    int compatibilityFallbacks = 0;
    char missingNames[512]{};
    int missingLen = 0;
    bool channelsFlushed = false;
    for (std::uint32_t i = 0; i < count; ++i) {
        DirEntry entry{};
        if (std::fread(&entry, sizeof(entry), 1, img) != 1) break;
        entry.name[23] = 0;
        char base[24];
        std::snprintf(base, sizeof(base), "%s", entry.name);
        if (char* dot = std::strrchr(base, '.')) *dot = 0;

        int modelId = -1;
        void* modelInfo = g.CModelInfo_GetModelInfoByName(base, &modelId);
        if (modelInfo == nullptr) {
            char upper[24];
            for (int c = 0; c < 24; ++c) {
                upper[c] = static_cast<char>(
                    base[c] >= 'a' && base[c] <= 'z' ? base[c] - 32 : base[c]);
                if (base[c] == 0) break;
            }
            modelId = -1;
            modelInfo = g.CModelInfo_GetModelInfoByName(upper, &modelId);
        }
        if (modelInfo == nullptr || modelId < 0) {
            ++missing;
            if (missingLen < static_cast<int>(sizeof(missingNames)) - 32) {
                missingLen += std::snprintf(missingNames + missingLen,
                                            sizeof(missingNames) - missingLen,
                                            " %s", base);
            }
            continue;
        }
        // Strictly the weapon/pickup model range. Names such as parachute or
        // cellphone can also match DYNAMIC special slots (the cutscene system
        // reuses those ids per scene); hijacking one hands a cutscene actor
        // our weapon DFF and corrupts the stream.
        if (modelId < 321 || modelId > 373) {
            ++outOfRange;
            if (missingLen < static_cast<int>(sizeof(missingNames)) - 40) {
                missingLen += std::snprintf(missingNames + missingLen,
                                            sizeof(missingNames) - missingLen,
                                            " %s=%d!", base, modelId);
            }
            continue;
        }
        // On-device CRASH1 trace: HD fire_ex (366, 43 sectors) remains in
        // READING with an empty request queue; the script waits at IP 39537.
        // Re-request/LoadAllRequestedModels does not recover it. Preserve the
        // main archive's fire extinguisher before any flush/remove/repoint.
        // Other weapons keep their HD entries; no archive/settings edits.
        if (modelId == 366) {
            ++compatibilityFallbacks;
            LOGI("[hdweapons] fire_ex=366 compatibility: main archive retained");
            continue;
        }
        // SA streams a model across BOTH halves of the double buffer, so the
        // largest single model it can load is 2 * ms_streamingBufferSize. A DFF
        // bigger than that cannot be read and corrupts adjacent engine memory
        // (crash surfaces later, e.g. CWorld::Process / AddEventsToPed). Keep
        // the ORIGINAL model for any such oversized HD DFF. Models up to the 2x
        // limit stream fine (double-buffered), matching what the engine does
        // for the base archive.
        if (g.CStreaming_ms_streamingBufferSize &&
            entry.sizeSectors > 2 * *g.CStreaming_ms_streamingBufferSize) {
            ++oversized;
            if (missingLen < static_cast<int>(sizeof(missingNames)) - 48) {
                missingLen += std::snprintf(missingNames + missingLen,
                                            sizeof(missingNames) - missingLen,
                                            " %s=%dsec>buf%d", base,
                                            entry.sizeSectors,
                                            *g.CStreaming_ms_streamingBufferSize);
            }
            continue;
        }
        std::uint8_t* info = g.CStreaming_ms_aInfoForModel +
            static_cast<std::size_t>(modelId) * kInfoStride;
        if (*reinterpret_cast<std::uint32_t*>(info + 0x10) != 0) {
            // Already loaded or in flight: settle the channels once, then
            // drop the object so the next request streams from our image.
            if (!channelsFlushed) {
                g.CStreaming_FlushChannels();
                channelsFlushed = true;
            }
            g.CStreaming_RemoveModel(modelId);
            ++flushed;
        }
        info[0x7] = static_cast<std::uint8_t>(imgIdx);
        *reinterpret_cast<std::uint32_t*>(info + 0x8) = entry.posn;
        *reinterpret_cast<std::uint32_t*>(info + 0xC) = entry.sizeSectors;
        *reinterpret_cast<std::uint16_t*>(info + 0x4) = 0xFFFF;
        ++repointed;
    }
    std::fclose(img);

    g_applied.store(true, std::memory_order_release);
    LOGI("[hdweapons] active img=%d models=%d flushed=%d unknown=%d skip=%d "
         "oversized=%d compat=%d bufsec=%d", imgIdx, repointed, flushed, missing,
         outOfRange, oversized, compatibilityFallbacks,
         g.CStreaming_ms_streamingBufferSize
             ? *g.CStreaming_ms_streamingBufferSize : -1);
    char status[768];
    const bool anySkip = missing || outOfRange || oversized;
    std::snprintf(status, sizeof(status),
                  "applied img=%d handle=%d entries=%u models=%d flushed=%d "
                  "unknown=%d skipped=%d oversized=%d compat=%d bufsec=%d%s%s\n",
                  imgIdx, handle, count, repointed, flushed, missing,
                  outOfRange, oversized, compatibilityFallbacks,
                  g.CStreaming_ms_streamingBufferSize
                      ? *g.CStreaming_ms_streamingBufferSize : -1,
                  anySkip ? " names:" : "",
                  anySkip ? missingNames : "");
    WriteStatus(status);
}

}  // namespace

namespace {
using RasterCopy = void* (*)(void*, void*);
using ImageResample = void* (*)(const void*, int, int);
using ImageDestroy = int (*)(void*);
RasterCopy pngRasterCopy{};
ImageResample pngResample{};
ImageDestroy pngDestroy{};

void* OnPngRasterCopy(void* raster, void* image) {
    // Only TextureDatabaseEntry::LoadPNG omits the resize after FindRasterFormat.
    // Its destination is rounded DOWN to powers of two, unlike the source PNG.
    const auto caller = reinterpret_cast<std::uintptr_t>(__builtin_return_address(0));
    if (caller != g.LoadBase + 0x7954a0) return pngRasterCopy(raster, image);
    return pngupload::Copy(raster, image, pngRasterCopy, pngResample, pngDestroy);
}

bool InstallPngRasterCopy() {
    if (pngRasterCopy) return true;
    if (!g.LoadBase || reinterpret_cast<std::uintptr_t>(g.implOnDrawFrame) != g.LoadBase + 0x7d28d4)
        return false;
    auto** slot = reinterpret_cast<void**>(g.LoadBase + 0x849398);
    auto copy = reinterpret_cast<RasterCopy>(g.LoadBase + 0x76b144);
    // Guard the retail call site and GOT target; no instruction relocation.
    if (*slot != reinterpret_cast<void*>(copy) ||
        *reinterpret_cast<const std::uint32_t*>(g.LoadBase + 0x79549c) != 0x9401cf85)
        return false;
    const auto page = static_cast<std::uintptr_t>(sysconf(_SC_PAGESIZE));
    if (mprotect(reinterpret_cast<void*>(reinterpret_cast<std::uintptr_t>(slot) & ~(page-1)),
                 page, PROT_READ | PROT_WRITE)) return false;
    pngResample = reinterpret_cast<ImageResample>(g.LoadBase + 0x76c048);
    pngDestroy = reinterpret_cast<ImageDestroy>(g.LoadBase + 0x7694a8);
    pngRasterCopy = copy;
    __atomic_store_n(slot, reinterpret_cast<void*>(&OnPngRasterCopy), __ATOMIC_RELEASE);
    LOGI("[hdweapons] safe PNG raster upload installed (resample to destination size)");
    return true;
}
} // namespace

void* LoadLooseDatabase(const char* name, bool preload) {
    if (!name || !g.TextureDatabaseRuntime_Load || !g.TextureDatabaseRuntime_GetDatabase ||
        !g.TextureDatabaseRuntime_SortEntries ||
        !g.TextureDatabaseRuntime_GetDatabase("gta3") ||
        chdir(kFilesDir) != 0 || !InstallSortEntriesHook() || !InstallPngRasterCopy()) return nullptr;
    if (void* existing = g.TextureDatabaseRuntime_GetDatabase(name)) return existing;
    // Both callers run on GameThread during loading. Scope this flag to our
    // database; stock database sorting still processes its thumbnail records.
    g_loadingOurDb.store(true, std::memory_order_relaxed);
    void* db = g.TextureDatabaseRuntime_Load(name, preload, 0);
    g_loadingOurDb.store(false, std::memory_order_relaxed);
    return db;
}

bool Available() {
    // Re-check until the payload appears, then latch it for the process. This
    // supports installing the optional files while GTA is paused in the Quest.
    static std::atomic<bool> present{false};
    if (!present.load(std::memory_order_relaxed) && PayloadPresent())
        present.store(true, std::memory_order_relaxed);
    return present.load(std::memory_order_relaxed);
}

bool Applied() { return g_applied.load(std::memory_order_acquire); }

void Tick(bool enabled) {
    if (g_attemptFailed || g_applied.load(std::memory_order_relaxed)) return;
    int choice = g_sessionChoice.load(std::memory_order_relaxed);
    if (choice == -1) {
        if (!EngineReady()) return;
        choice = enabled ? 1 : 0;
        g_sessionChoice.store(choice, std::memory_order_relaxed);
    }
    if (choice != 1 || !Available()) return;
    Apply();
}

}  // namespace savr::hdweapons
