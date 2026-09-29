#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace savr::modelsets::lodsort {
using FirstAtomic = void* (*)(void*);
using ArraysId = std::uint64_t (*)(std::uint64_t);

template<class T> inline T Read(const void* base, std::size_t offset) {
    T value;
    // Retail resource-entry mesh data starts at +0x34, so its handles are
    // unaligned. Do not cast them to aligned C++ pointer/integer references.
    std::memcpy(&value, static_cast<const char*>(base) + offset, sizeof(value));
    return value;
}

inline std::uint64_t Key(const void* entity, FirstAtomic firstAtomic, ArraysId arraysId) {
    if (!entity) return 0;
    auto* object = Read<void*>(entity, 0x20);
    if (!object) return 0;
    auto* atomic = Read<std::uint8_t>(object, 0) == 1 ? object : firstAtomic(object);
    if (!atomic) return 0;
    auto* geometry = Read<void*>(atomic, 0x30);
    if (!geometry) return 0;
    auto* entry = Read<void*>(geometry, 0x98);
    if (!entry || !Read<std::uint16_t>(entry, 0x32)) return 0;
    // Retail 2.11 sortLODs only reads the first mesh's +0x28 handle.
    // DrawStored also supports a combined array at mesh+0x18 when it is null.
    // Mirror that fallback without altering native instancing or rendering.
    auto arrays = Read<std::uint64_t>(entry, 0x5c);
    if (!arrays) arrays = Read<std::uint64_t>(entry, 0x4c);
    return arrays ? arraysId(arrays) : 0;
}

inline int Compare(const void* a, const void* b, FirstAtomic firstAtomic, ArraysId arraysId) {
    const auto left = Key(Read<void*>(a, 0), firstAtomic, arraysId);
    const auto right = Key(Read<void*>(b, 0), firstAtomic, arraysId);
    // Preserve retail's descending unsigned array-ID order and equality.
    return (right > left) - (right < left);
}
} // namespace savr::modelsets::lodsort
