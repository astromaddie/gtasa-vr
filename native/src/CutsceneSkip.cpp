#include "CutsceneSkip.h"
#include "Symbols.h"

#include <cmath>
#include <cstring>
#include <strings.h>

namespace savr::cutsceneskip {
namespace {
bool nativeInputFilterInstalled{};
bool pendingSkip{};
char pendingSceneName[8]{};
float pendingSceneTime{};
bool Ready(bool checkFinished = true) {
    // Retail 2.11.311 Update_overlay @0x54eca8 only offers skip for a loaded,
    // running spline camera (mode 17), excluding "finale". Keep these gates;
    // only bypass IsCutsceneSkipButtonBeingPressed's mission-name blacklist.
    if (!nativeInputFilterInstalled || !g.CCutsceneMgr_Skip || !g.CCutsceneMgr_HasFinished ||
        !g.CCutsceneMgr_ms_running || !*g.CCutsceneMgr_ms_running ||
        !g.CCutsceneMgr_ms_loadStatus || *g.CCutsceneMgr_ms_loadStatus != 2 ||
        !g.CCutsceneMgr_ms_playStatus || *g.CCutsceneMgr_ms_playStatus != 0 ||
        !g.CCutsceneMgr_ms_timer || !std::isfinite(*g.CCutsceneMgr_ms_timer) ||
        !g.CCutsceneMgr_ms_cutsceneName ||
        !g.CCutsceneMgr_ms_cutsceneName[0] ||
        !strncasecmp(g.CCutsceneMgr_ms_cutsceneName, "finale", 8) ||
        !g.TheCamera || !g.FindPlayerPed || !g.FindPlayerPed(-1)) return false;
    if ((g.CTimer_m_UserPause && *g.CTimer_m_UserPause) ||
        (g.CTimer_m_CodePause && *g.CTimer_m_CodePause) ||
        (g.AndroidPaused && g.AndroidPaused())) return false;

    const auto* camera = static_cast<const unsigned char*>(g.TheCamera);
    const unsigned active = camera[0x5f];
    if (active >= 3) return false;
    std::uint16_t mode{};
    std::memcpy(&mode, camera + active * 0x228 + 0x186, sizeof(mode));
    // HasCutsceneFinished also returns true when no cutscene camera is loaded.
    return mode == 17 && (!checkFinished || !g.CCutsceneMgr_HasFinished());
}
} // namespace

void SetNativeInputFilterInstalled(bool installed) {
    nativeInputFilterInstalled = installed;
}

bool FilterNativeInput(bool (*original)(), bool focused, bool blocked) {
    // The manager deliberately excludes finale. Keep its authored native input
    // behavior too; never deliver a pulse accepted in the preceding scene.
    const bool finale = g.CCutsceneMgr_ms_cutsceneName &&
        !strncasecmp(g.CCutsceneMgr_ms_cutsceneName, "finale", 8);
    if (!finale && g.CCutsceneMgr_ms_running && *g.CCutsceneMgr_ms_running) {
        if (pendingSkip && (!focused || blocked || !Ready(false) ||
            std::memcmp(pendingSceneName, g.CCutsceneMgr_ms_cutsceneName, 8) ||
            *g.CCutsceneMgr_ms_timer < pendingSceneTime))
            pendingSkip = false;
        return pendingSkip;
    }
    pendingSkip = false;
    return original && original();
}

bool Button::Update(bool aDown, bool focused, bool blocked, std::uint64_t nowMs) {
    progress_ = 0.0f;
    eligible_ = false;
    // End the prior tick's pulse even if the engine never polled it (paused,
    // focus lost, changed scene). Never queue work for a later cinematic.
    pendingSkip = false;
    if (!focused || blocked || !Ready()) {
        armed_ = holding_ = false;
        haveScene_ = false;
        return false;
    }
    eligible_ = true;
    if (holding_ && (nowMs < lastSampleMs_ || nowMs - lastSampleMs_ > 250))
        armed_ = holding_ = false;
    lastSampleMs_ = nowMs;
    const float sceneTime = *g.CCutsceneMgr_ms_timer;
    if (haveScene_ &&
        (std::memcmp(sceneName_, g.CCutsceneMgr_ms_cutsceneName, sizeof(sceneName_)) ||
         sceneTime < lastSceneTime_)) {
        armed_ = holding_ = false;
    }
    haveScene_ = true;
    std::memcpy(sceneName_, g.CCutsceneMgr_ms_cutsceneName, sizeof(sceneName_));
    lastSceneTime_ = sceneTime;
    // Observe neutral in this eligible scene before accepting a new hold. A
    // held confirm/chord/focus-return button cannot skip a newly entered scene.
    if (!aDown) {
        armed_ = true;
        holding_ = false;
        return false;
    }
    if (!armed_) return false;
    if (!holding_) {
        holding_ = true;
        downAtMs_ = nowMs;
        return false;
    }
    if (nowMs < downAtMs_) {
        armed_ = holding_ = false;
        return false;
    }
    progress_ = static_cast<float>(nowMs - downAtMs_) / 500.0f;
    if (progress_ < 1.0f) return false;
    progress_ = 1.0f;
    armed_ = holding_ = false;
    // CGame::Process calls the cinematic manager before scripts. Preserve
    // both native consumers for this one tick: the manager runs SkipCutscene,
    // then scripts may consume their authored skip label or finished test.
    pendingSkip = true;
    std::memcpy(pendingSceneName, sceneName_, sizeof(pendingSceneName));
    pendingSceneTime = sceneTime;
    return true;
}
} // namespace savr::cutsceneskip
