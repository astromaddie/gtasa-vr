#pragma once
#include <array>
#include <cstddef>

namespace savr::graphicsfx {
// A model's 2DFX corona can own a texture other than gpCoronaTexture's three
// common sprites. Batch by the actual record texture so those lights survive
// the per-eye replacement of CCoronas::Render too.
template<std::size_t N> class CoronaTextures {
public:
    void Add(void* texture) {
        if (!texture) return;
        for (std::size_t i = 0; i < count_; ++i)
            if (textures_[i] == texture) return;
        if (count_ < N) textures_[count_++] = texture;
    }
    auto begin() const { return textures_.begin(); }
    auto end() const { return textures_.begin() + count_; }
private:
    std::array<void*, N> textures_{};
    std::size_t count_{};
};
} // namespace savr::graphicsfx
