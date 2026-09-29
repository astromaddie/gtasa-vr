#include "MissionControls.h"

#include <cstdint>
#include <cstring>
#include <dlfcn.h>

#include "Locomotion.h"
#include "Log.h"
#include "Symbols.h"
#include "Xr.h"

namespace savr::missioncontrols {
namespace {

using GetTaskSwimFn = void* (*)(void* intelligence);
GetTaskSwimFn g_getTaskSwim = nullptr;
detail::EdgeState g_edges;

bool HasSwimTask(void* ped) {
    if (!ped || !g_getTaskSwim) return false;
    void* intelligence = nullptr;
    // CPed::m_pIntelligence, ARM64 2.11.311, also used by the crouch bridge.
    std::memcpy(&intelligence, static_cast<const std::uint8_t*>(ped) + 0x538,
                sizeof(intelligence));
    return intelligence && g_getTaskSwim(intelligence);
}

} // namespace

void Install(void* gameHandle) {
    if (gameHandle) {
        g_getTaskSwim = reinterpret_cast<GetTaskSwimFn>(
            dlsym(gameHandle, "_ZNK16CPedIntelligence11GetTaskSwimEv"));
    }
    LOGI("[mission.input] conversation widgets=110/111 swimTask=%p",
         reinterpret_cast<void*>(g_getTaskSwim));
}

bool IsSwimming() {
    if (g.FindPlayerVehicle && g.FindPlayerVehicle(-1, false)) return false;
    return HasSwimTask(g.FindPlayerPed ? g.FindPlayerPed(-1) : nullptr);
}

void UpdateInput(const xr::InputState& input, bool enabled) {
    void* ped = enabled && g.FindPlayerPed ? g.FindPlayerPed(-1) : nullptr;
    const bool onFoot = ped &&
        (!g.FindPlayerVehicle || !g.FindPlayerVehicle(-1, false));
    const bool bothGrips = input.grip[0] >= 0.75f && input.grip[1] >= 0.75f;
    detail::Input state{};
    state.enabled = enabled && !bothGrips && !input.menu;
    state.onFoot = onFoot;
    state.swimming = onFoot && HasSwimTask(ped);
    state.thumbrest = input.thumbrest[0] || input.thumbrest[1];
    state.rightX = input.rightStick[0];
    state.rightY = input.rightStick[1];
    state.jump = locomotion::ActionHeld(locomotion::BIND_ACT_JUMP,
        input.a, input.b, input.x, input.y, input.l3, input.r3, true);
    state.dive = locomotion::ActionHeld(locomotion::BIND_ACT_CROUCH,
        input.a, input.b, input.x, input.y, input.l3, input.r3, true);
    state.recenter = input.l3 && input.r3;
    g_edges.Update(state);
    if (g_edges.JustPressed(110)) LOGI("[mission.input] conversation YES");
    if (g_edges.JustPressed(111)) LOGI("[mission.input] conversation NO");
    if (g_edges.JustPressed(33)) LOGI("[mission.input] swim DIVE");
    if (g_edges.DoubleTapped(168)) LOGI("[mission.input] swim JUMP");
}

bool TouchJustPressed(int widgetId) { return g_edges.JustPressed(widgetId); }
bool TouchDoubleTapped(int widgetId) { return g_edges.DoubleTapped(widgetId); }

} // namespace savr::missioncontrols
