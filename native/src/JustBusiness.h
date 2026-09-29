#pragma once
#include <cstddef>
#include <cstdint>
namespace savr::justbusiness {
bool Install(void* gameHandle);
void Update();
bool Active();
void RecordShot(int weaponType,int hand);
namespace detail {
constexpr std::size_t kScriptSize=52885;
// Script offsets match assets/data/script/mainv1.scm.
constexpr std::uint32_t kScriptHash=0x05ef3388;
template<class Basis> void FaceRear(Basis& base) {
    base.right=base.right*-1.0f;
    base.forward=base.forward*-1.0f;
}
}
}
