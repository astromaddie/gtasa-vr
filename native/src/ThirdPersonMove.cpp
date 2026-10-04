#include "ThirdPersonMove.h"

#include "Locomotion.h"
#include "Log.h"
#include "Symbols.h"
#include "VrCamera.h"
#include "Xr.h"

#include <cmath>
#include <cstdint>
#include <cstring>
#include <dlfcn.h>
#include <sys/mman.h>
#include <unistd.h>

namespace savr::thirdmove {
namespace {
// Offsets, all read from the 2.11.311 arm64 libGame.so:
//   ped+0x538  CPedIntelligence*          ped+0x540  CPlayerData*
//   ped+0x6c4  m_fRotationCur             ped+0x6c8  m_fRotationDest
//   ped+0x6bc  desired move (vec2), built by CPed::CalculateNewVelocity from
//              the animation's movement and applied by CPed::UpdatePosition
//   ped+0x730  weapon slots, 0x20 apart, type first; ped+0x8dc active slot
//   data+0x20  move blend ratio PlayerControlZelda sets from the stick
//   PlayerControlZelda sets m_fRotationDest to the stick's heading.
constexpr int kOffIntelligence = 0x538;
constexpr int kOffPlayerData = 0x540;
constexpr int kOffRotationCur = 0x6c4;
constexpr int kOffRotationDest = 0x6c8;
constexpr int kOffDesiredMove = 0x6bc;
constexpr int kOffWeapons = 0x730;
constexpr int kWeaponStride = 0x20;
constexpr int kOffActiveSlot = 0x8dc;
constexpr int kOffMoveBlend = 0x20;
constexpr float kPi = 3.14159265358979323846f;

using VelocityFn = void (*)(void* ped);
using ZeldaFn = void (*)(void* task, void* ped, bool avoidJumpingAndDucking);
using ZeldaWeaponFn = void (*)(void* task, void* ped);
using CanStrafeFn = bool (*)(void* ped);
using GetTaskFn = void* (*)(void* intelligence);

VelocityFn g_velocity{};
ZeldaFn g_zelda{};
ZeldaWeaponFn g_zeldaWeapon{};
CanStrafeFn g_canStrafe{};
GetTaskFn g_getTaskUseGun{};
bool g_installed{};

// Set by the two player control functions for the ped they ran on, consumed
// (and cleared) by CalculateNewVelocity, which runs right after the tasks in
// CPed::ProcessControl.
void* g_zeldaPed{};
void* g_weaponPed{};
bool g_walking{};
float g_walkHeading{};

template<class T> T Read(const void* p, int offset) {
    T out{}; std::memcpy(&out, static_cast<const char*>(p) + offset, sizeof(out));
    return out;
}
template<class T> void Write(void* p, int offset, T value) {
    std::memcpy(static_cast<char*>(p) + offset, &value, sizeof(value));
}

float LimitRadians(float angle) {
    if (!std::isfinite(angle)) return 0.0f;
    while (angle >= kPi) angle -= 2.0f * kPi;
    while (angle < -kPi) angle += 2.0f * kPi;
    return angle;
}

// Weapons that are aimed or fired. Fists, melee weapons, the detonator,
// goggles and the parachute turn with the stick like on a pad.
bool RangedWeapon(int type) {
    return (type >= 16 && type <= 18) || (type >= 22 && type <= 39) ||
           (type >= 41 && type <= 43);
}

bool AimingOrFiring(void* ped) {
    const int slot = Read<std::int8_t>(ped, kOffActiveSlot);
    if (slot < 0 || slot > 12) return false;
    const int type = Read<std::int32_t>(ped, kOffWeapons + slot * kWeaponStride);
    if (!RangedWeapon(type)) return false;
    // The game's aim task is up while it aims or shoots; the right trigger is
    // the fire button (VrFire's GetWeapon hook), so count it too for the frame
    // before the task exists.
    void* intelligence = Read<void*>(ped, kOffIntelligence);
    if (intelligence && g_getTaskUseGun && g_getTaskUseGun(intelligence))
        return true;
    xr::InputState in{};
    xr::GetInput(in);
    return in.triggers[1] >= 0.60f && in.grip[0] < 0.75f && in.grip[1] < 0.75f;
}

// Should this ped be held to the view heading this frame? On foot, over the
// shoulder, in a state where the game itself would let the player strafe.
bool FaceView(void* ped, float* heading) {
    if (!ped || !g.FindPlayerPed || ped != g.FindPlayerPed(-1)) return false;
    if (!vrcam::OverShoulderFootHeading(heading)) return false;
    if (g_canStrafe && !g_canStrafe(ped)) return false;
    return locomotion::ThirdPersonFaceCamera() || AimingOrFiring(ped);
}

void OnZelda(void* task, void* ped, bool avoid) {
    g_zelda(task, ped, avoid);
    void* data = Read<void*>(ped, kOffPlayerData);
    g_zeldaPed = ped;
    g_walking = data && Read<float>(data, kOffMoveBlend) > 0.0f;
    g_walkHeading = Read<float>(ped, kOffRotationDest);
}

void OnZeldaWeapon(void* task, void* ped) {
    g_zeldaWeapon(task, ped);
    g_weaponPed = ped;
}

void OnVelocity(void* ped) {
    const bool zelda = ped == g_zeldaPed;
    const bool weapon = ped == g_weaponPed;
    const bool walking = g_walking;
    const float walkHeading = g_walkHeading;
    if (zelda) g_zeldaPed = nullptr;
    if (weapon) g_weaponPed = nullptr;

    float heading = 0.0f;
    float slide = 0.0f;
    const bool face = FaceView(ped, &heading);
    if (face) {
        // On the walking path (not the aim task, which strafes by itself) the
        // stick's heading was the turn target: keep it as the walk direction.
        if (zelda && !weapon && walking)
            slide = LimitRadians(walkHeading - heading);
        Write(ped, kOffRotationCur, heading);
        Write(ped, kOffRotationDest, heading);
    }
    static bool wasFacing = false;
    if (face != wasFacing && ped == (g.FindPlayerPed ? g.FindPlayerPed(-1) : nullptr)) {
        wasFacing = face;
        LOGI("[view.os] character %s the view (%s)",
             face ? "faces" : "turns with the stick again",
             locomotion::ThirdPersonMoveName());
    }

    g_velocity(ped);

    if (face && slide != 0.0f) {
        float x = Read<float>(ped, kOffDesiredMove);
        float y = Read<float>(ped, kOffDesiredMove + 4);
        const float c = std::cos(slide), s = std::sin(slide);
        const float nx = x * c - y * s, ny = x * s + y * c;
        if (std::isfinite(nx) && std::isfinite(ny)) {
            Write(ped, kOffDesiredMove, nx);
            Write(ped, kOffDesiredMove + 4, ny);
        }
    }
}

// The prologue is checked first, then the first 16 bytes are moved to a
// trampoline and replaced with a jump. They only save registers, so they are
// safe to copy (same method as the swimming hooks).
bool Hook(void* target, const std::uint32_t (&expected)[4], void* hook,
          void** original) {
    if (!target || std::memcmp(target, expected, 16)) return false;
    const long size = sysconf(_SC_PAGESIZE);
    if (size <= 0) return false;
    void* trampoline = mmap(nullptr, size, PROT_READ | PROT_WRITE | PROT_EXEC,
                            MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (trampoline == MAP_FAILED) return false;
    auto* t = static_cast<std::uint32_t*>(trampoline);
    std::memcpy(t, target, 16);
    t[4] = 0x58000051;   // LDR X17, #8
    t[5] = 0xd61f0220;   // BR  X17
    const auto resume = reinterpret_cast<std::uintptr_t>(target) + 16;
    std::memcpy(t + 6, &resume, sizeof(resume));
    __builtin___clear_cache(static_cast<char*>(trampoline),
                            static_cast<char*>(trampoline) + 32);
    const auto address = reinterpret_cast<std::uintptr_t>(target);
    const auto start = address & ~(static_cast<std::uintptr_t>(size) - 1);
    const auto end = (address + 16 + size - 1) & ~(static_cast<std::uintptr_t>(size) - 1);
    if (mprotect(reinterpret_cast<void*>(start), end - start,
                 PROT_READ | PROT_WRITE | PROT_EXEC)) {
        munmap(trampoline, size);
        return false;
    }
    *original = trampoline;
    auto* code = static_cast<std::uint32_t*>(target);
    std::memcpy(code + 2, &hook, sizeof(hook));
    code[1] = 0xd61f0220;
    __atomic_store_n(code, 0x58000051u, __ATOMIC_RELEASE);
    __builtin___clear_cache(static_cast<char*>(target), static_cast<char*>(target) + 16);
    return true;
}
} // namespace

void Install(void* handle) {
    if (!handle || g_installed) return;
    g_canStrafe = reinterpret_cast<CanStrafeFn>(
        dlsym(handle, "_ZN4CPed23CanStrafeOrMouseControlEv"));
    g_getTaskUseGun = reinterpret_cast<GetTaskFn>(
        dlsym(handle, "_ZNK16CPedIntelligence13GetTaskUseGunEv"));
    void* velocity = dlsym(handle, "_ZN4CPed20CalculateNewVelocityEv");
    void* zelda = dlsym(handle, "_ZN23CTaskSimplePlayerOnFoot18PlayerControlZeldaEP10CPlayerPedb");
    void* weapon = dlsym(handle, "_ZN23CTaskSimplePlayerOnFoot24PlayerControlZeldaWeaponEP10CPlayerPed");
    // First four instructions of each, from the 2.11.311 arm64 libGame.so.
    constexpr std::uint32_t vp[] = {0x6dbb2bebu, 0x6d0123e9u, 0xa9027bfdu, 0xf9001bf5u};
    constexpr std::uint32_t zp[] = {0x6dba23e9u, 0xa9017bfdu, 0xf90013f9u, 0xa9035ff8u};
    constexpr std::uint32_t wp[] = {0xd10203ffu, 0xfd0013ecu, 0x6d02abebu, 0x6d03a3e9u};
    if (!g_canStrafe || !g_getTaskUseGun || !velocity || !zelda || !weapon ||
        std::memcmp(velocity, vp, 16) || std::memcmp(zelda, zp, 16) ||
        std::memcmp(weapon, wp, 16)) {
        LOGW("[view.os] third person character control hooks unavailable; the stock turning stays");
        return;
    }
    // The originals are stored straight into the globals, before each hook
    // goes live, so a hook can never run without its way through. The
    // velocity hook is last: until it is in, the flags the other two set are
    // simply never read.
    if (!Hook(zelda, zp, reinterpret_cast<void*>(&OnZelda),
              reinterpret_cast<void**>(&g_zelda)) ||
        !Hook(weapon, wp, reinterpret_cast<void*>(&OnZeldaWeapon),
              reinterpret_cast<void**>(&g_zeldaWeapon)) ||
        !Hook(velocity, vp, reinterpret_cast<void*>(&OnVelocity),
              reinterpret_cast<void**>(&g_velocity))) {
        LOGW("[view.os] third person character control hook failed; the stock turning stays");
        return;
    }
    g_installed = true;
    LOGI("[view.os] third person character control hooked (FACE MOVE / FACE CAMERA)");
}
} // namespace savr::thirdmove
