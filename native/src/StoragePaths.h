#pragma once

#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#include <deque>
#include <mutex>
#include <string>
#include <string_view>

#include "Log.h"

// One central place for every on-device path the VR layer reads or writes.
//
// Quest builds keep the original locations exactly:
//   files    /sdcard/Android/data/com.rockstargames.gtasa/files
//   data_main /sdcard/savr/data_main
//
// Steam Frame builds (SAVR_STEAM_FRAME) keep everything under one root that
// survives a Lepton app-data reset (only /sdcard/Documents does):
//   /sdcard/Documents/GTASAVR/files      (vr_*.ini, logs, audio/, vrhands/, mods)
//   /sdcard/Documents/GTASAVR/data_main  (game data pack)
// The root is created on first use. If it cannot be created or written, the
// old locations are used instead and the fallback is logged.
namespace savr::storage {

inline constexpr char kLegacyFilesDir[] =
    "/sdcard/Android/data/com.rockstargames.gtasa/files";
inline constexpr char kLegacyDataMainDir[] = "/sdcard/savr/data_main";

#ifdef SAVR_STEAM_FRAME
inline constexpr bool kPreferRelocatedRoot = true;
inline constexpr char kPreferredRoot[] = "/sdcard/Documents/GTASAVR";
#else
inline constexpr bool kPreferRelocatedRoot = false;
inline constexpr char kPreferredRoot[] = "";
#endif

struct Roots {
    std::string files;      // no trailing slash
    std::string dataMain;   // no trailing slash
    bool relocated = false; // true when the Frame root is in use
};

namespace detail {

inline bool MakeDirs(const std::string& path) {
    if (path.empty()) return false;
    std::string partial;
    std::size_t start = 0;
    while (start <= path.size()) {
        const auto slash = path.find('/', start);
        const auto end = slash == std::string::npos ? path.size() : slash;
        partial = path.substr(0, end);
        if (!partial.empty()) {
            if (mkdir(partial.c_str(), 0777) != 0 && errno != EEXIST) {
                struct stat st{};
                if (stat(partial.c_str(), &st) != 0 || !S_ISDIR(st.st_mode)) return false;
            }
        }
        if (slash == std::string::npos) break;
        start = slash + 1;
    }
    return true;
}

inline bool Writable(const std::string& dir) {
    const std::string probe = dir + "/.savr_write_test";
    const int fd = open(probe.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0666);
    if (fd < 0) return false;
    close(fd);
    unlink(probe.c_str());
    return true;
}

inline Roots Compute() {
    Roots roots;
    roots.files = kLegacyFilesDir;
    roots.dataMain = kLegacyDataMainDir;
    if (!kPreferRelocatedRoot) return roots;

    const std::string root = kPreferredRoot;
    const std::string files = root + "/files";
    const std::string data = root + "/data_main";
    if (MakeDirs(files) && MakeDirs(data) && Writable(files)) {
        roots.files = files;
        roots.dataMain = data;
        roots.relocated = true;
        LOGW("[savr-frame] storage root %s (files=%s data_main=%s)",
             root.c_str(), files.c_str(), data.c_str());
    } else {
        const int error = errno;
        LOGE("[savr-frame] storage root %s is not writable (errno=%d %s); "
             "falling back to %s and %s",
             root.c_str(), error, std::strerror(error),
             kLegacyFilesDir, kLegacyDataMainDir);
    }
    return roots;
}

} // namespace detail

inline const Roots& GetRoots() {
    static const Roots roots = detail::Compute();
    return roots;
}

inline const std::string& FilesDir() { return GetRoots().files; }
inline const std::string& DataMainDir() { return GetRoots().dataMain; }

// FilesDir() + "/" + leaf. The returned pointer stays valid for the process
// lifetime, so it is safe to keep in file-scope `const char*` path variables.
inline const char* FilesPath(std::string_view leaf) {
    static std::mutex mutex;
    static std::deque<std::string> interned;
    std::string full = FilesDir();
    full += '/';
    full.append(leaf);
    std::lock_guard<std::mutex> lock(mutex);
    interned.push_back(std::move(full));
    return interned.back().c_str();
}

// FilesDir() + "/" + leaf as an owned string.
inline std::string Files(std::string_view leaf) {
    std::string full = FilesDir();
    full += '/';
    full.append(leaf);
    return full;
}

} // namespace savr::storage
