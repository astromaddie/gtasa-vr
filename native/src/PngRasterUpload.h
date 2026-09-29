#pragma once
#include <cstring>
#include <cstddef>
namespace savr::hdweapons::pngupload {
inline int Dimension(const void* p, std::size_t offset) {
    int value{}; std::memcpy(&value, static_cast<const char*>(p)+offset, sizeof(value));
    return value;
}
// Retail RwImage: width/height +4/+8; RwRaster: width/height +0x18/+0x1c.
// Never submit a larger source to the native unbounded row-copy loop.
template<class CopyFn, class ResampleFn, class DestroyFn>
void* Copy(void* raster, void* image, CopyFn copy, ResampleFn resample, DestroyFn destroy) {
    if (!raster || !image) return nullptr;
    const int width = Dimension(raster, 0x18), height = Dimension(raster, 0x1c);
    const int sourceWidth = Dimension(image, 4), sourceHeight = Dimension(image, 8);
    if (width <= 0 || height <= 0 || sourceWidth <= 0 || sourceHeight <= 0) return nullptr;
    if (width == sourceWidth && height == sourceHeight) return copy(raster, image);
    void* fitted = resample(image, width, height);
    if (!fitted) return nullptr; // Allocation failure must never fall back to the unsafe copy.
    void* result = nullptr;
    if (Dimension(fitted, 4) == width && Dimension(fitted, 8) == height)
        result = copy(raster, fitted);
    destroy(fitted); // The original PNG remains owned by TextureDatabaseEntry::LoadPNG.
    return result;
}
}
