#pragma once
#include <algorithm>
#include <string>
#include <string_view>

namespace savr::modelsets {
inline constexpr char kFiles[] = "/sdcard/Android/data/com.rockstargames.gtasa/files/";

inline bool SafeRelative(std::string_view path) {
    if (path.empty() || path.size() > 240 || path.front() == '/') return false;
    for (char c : path)
        if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
              c == '/' || c == '_' || c == '-' || c == '.')) return false;
    std::size_t start = 0;
    do {
        const auto end = path.find('/', start);
        const auto part = path.substr(start, end == path.npos ? end : end - start);
        if (part.empty() || part == "." || part == "..") return false;
        if (end == path.npos) break;
        start = end + 1;
    } while (true);
    return true;
}

inline std::string AssetKey(const char* name) {
    if (!name) return {};
    std::string path(name);
    if (path.size() > 1024) return {};
    for (char& c : path) {
        if (c == '\\') c = '/';
        else if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
    }
    constexpr std::string_view roots[] = {
        "/sdcard/android/data/com.rockstargames.gtasa/files/",
        "/storage/emulated/0/android/data/com.rockstargames.gtasa/files/"};
    for (auto root : roots)
        if (path.starts_with(root)) { path.erase(0, root.size()); break; }
    if (path.starts_with("./")) path.erase(0, 2);
    if (path.starts_with("assets/")) path.erase(0, 7);
    if (!SafeRelative(path)) return {};
    if (!(path.starts_with("data/") || path.starts_with("texdb/") ||
          path.starts_with("models/") || path.starts_with("anim/") ||
          path.starts_with("audio/"))) return {};
    return path;
}

inline bool ReadOnlyMode(const char* mode) {
    return mode && mode[0] == 'r' && std::string_view(mode).find_first_of("+wa") == std::string_view::npos;
}
} // namespace savr::modelsets
