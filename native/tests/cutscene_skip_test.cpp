#include "CutsceneSkip.h"
#include "Symbols.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <limits>

#define CHECK(e) do { if (!(e)) { std::fprintf(stderr, "FAIL %d: %s\n", __LINE__, #e); std::exit(1); } } while (0)
namespace savr { GameSymbols g{}; }
using savr::g;
using savr::cutsceneskip::Button;
namespace {
bool running = true, finished = false, userPause = false, codePause = false;
bool androidPause = false, playerExists = true;
int loaded = 2, playing = 0, skips = 0;
int nativeInputCalls = 0;
bool nativeInputResult = true;
bool NativeInput() { ++nativeInputCalls; return nativeInputResult; }
float timer = 1.0f;
char name[8] = "zero1";
unsigned char camera[0x1000]{};
void Skip() { ++skips; }
bool Finished() { return finished; }
bool AndroidPaused() { return androidPause; }
void* Player(int) { return playerExists ? camera : nullptr; }
void CameraMode(unsigned active, std::uint16_t mode) {
    camera[0x5f] = active;
    if (active < 3) std::memcpy(camera + active * 0x228 + 0x186, &mode, sizeof(mode));
}
bool Step(Button& button, bool down, bool focused, bool blocked, std::uint64_t now) {
    const bool requested = button.Update(down, focused, blocked, now);
    if (requested) {
        // Model the native manager then script order using the real predicate.
        CHECK(savr::cutsceneskip::FilterNativeInput(NativeInput));
        Skip();
        finished = true;
        CHECK(savr::cutsceneskip::FilterNativeInput(NativeInput));
        finished = false;
    }
    return requested;
}
void CannotSkip() {
    const int before = skips;
    Button b;
    CHECK(!Step(b, false, true, false, 0));
    CHECK(!b.Eligible());
    for (unsigned now = 10; now <= 710; now += 100) {
        CHECK(!Step(b, true, true, false, now));
        CHECK(!b.Eligible());
    }
    CHECK(skips == before);
}
}
int main() {
    g.CCutsceneMgr_Skip = Skip;
    g.CCutsceneMgr_HasFinished = Finished;
    g.CCutsceneMgr_ms_running = &running;
    g.CCutsceneMgr_ms_loadStatus = &loaded;
    g.CCutsceneMgr_ms_playStatus = &playing;
    g.CCutsceneMgr_ms_timer = &timer;
    g.CCutsceneMgr_ms_cutsceneName = name;
    g.CTimer_m_UserPause = &userPause;
    g.CTimer_m_CodePause = &codePause;
    g.AndroidPaused = AndroidPaused;
    g.FindPlayerPed = Player;
    g.TheCamera = camera;
    CameraMode(0, 17);
    CannotSkip(); // the hook must be installed before the hold route is enabled
    savr::cutsceneskip::SetNativeInputFilterInstalled(true);
    CHECK(!savr::cutsceneskip::FilterNativeInput(NativeInput));
    CHECK(nativeInputCalls == 0); // immediate A/keyboard/touch cannot skip a formal scene
    running = false;
    CHECK(savr::cutsceneskip::FilterNativeInput(NativeInput));
    nativeInputResult = false;
    CHECK(!savr::cutsceneskip::FilterNativeInput(NativeInput));
    CHECK(nativeInputCalls == 2); // authored scripted skip predicate preserved exactly
    running = true;

    // Full production gate and native dispatch, at 72/90/120 Hz. No Cross
    // provider or script-name input permission is needed for a formal scene.
    for (unsigned hz : {72u, 90u, 120u}) {
        Button b;
        const int before = skips;
        CHECK(!Step(b, false, true, false, 0));
        CHECK(!Step(b, true, true, false, 100));
        for (unsigned frame = 1; frame <= hz; ++frame) {
            const unsigned elapsed = frame * 1000 / hz;
            const bool fired = Step(b, true, true, false, 100 + elapsed);
            CHECK(fired == (elapsed >= 500 && (frame - 1) * 1000 / hz < 500));
        }
        CHECK(skips == before + 1);
        CHECK(!Step(b, false, true, false, 1200));
    }

    Button b;
    int before = skips;
    // Boot/scene entry with A already down requires release in the scene.
    CHECK(!Step(b, true, true, false, 0));
    CHECK(!Step(b, true, true, false, 1000));
    CHECK(!Step(b, false, true, false, 1010));
    CHECK(!Step(b, true, true, false, 1100));
    CHECK(!Step(b, false, true, false, 1599)); // tap/short hold
    CHECK(skips == before);
    CHECK(!Step(b, true, true, false, 2000));
    CHECK(!Step(b, true, true, false, 2250));
    CHECK(!Step(b, true, true, false, 2499));
    CHECK(b.Progress() > 0.997f && b.Progress() < 1.0f);
    CHECK(Step(b, true, true, false, 2500));
    CHECK(b.Progress() == 1.0f);
    CHECK(!Step(b, true, true, false, 4000));
    CHECK(b.Progress() == 0.0f);
    CHECK(skips == before + 1);

    // A scene swap on the very frame of the press also requires neutral in
    // the new scene, even when no loading frame was observed between them.
    b = Button{};
    before = skips;
    CHECK(!Step(b, false, true, false, 0));
    name[0] = 'a';
    CHECK(!Step(b, true, true, false, 10));
    CHECK(!Step(b, true, true, false, 1000));
    CHECK(skips == before);
    name[0] = 'z';

    // Every interruption invalidates the entire press, even if eligibility
    // returns with A still held. Blocked covers View, either grip and menus.
    for (int reason = 0; reason < 9; ++reason) {
        b = Button{};
        before = skips;
        CHECK(!Step(b, false, true, false, 0));
        CHECK(!Step(b, true, true, false, 10));
        if (reason == 2) running = false;
        if (reason == 3) userPause = true;
        if (reason == 4) codePause = true;
        if (reason == 5) androidPause = true;
        if (reason == 6) name[0] = 'a';
        if (reason == 7) timer = 0.1f; // same name restarted
        CHECK(!Step(b, true, reason != 0, reason == 1,
                        reason == 8 ? 5 : 100)); // clock reset
        CHECK(b.Progress() == 0.0f);
        running = true; userPause = codePause = androidPause = false;
        name[0] = 'z'; timer = 1.0f;
        CHECK(!Step(b, true, true, false, 2000));
        CHECK(skips == before);
        CHECK(!Step(b, false, true, false, 2010));
        CHECK(!Step(b, true, true, false, 2020));
        CHECK(!Step(b, true, true, false, 2270));
        CHECK(Step(b, true, true, false, 2520));
    }

    // Native completion gates: no arbitrary scripted gameplay cameras,
    // Finale is ineligible for the custom hold but retains native authored
    // input. A pending pulse from the previous scene cannot leak into it.
    {
        Button b;
        CHECK(!b.Update(false, true, false, 0));
        for (unsigned now = 10; now < 510; now += 100)
            CHECK(!b.Update(true, true, false, now));
        CHECK(b.Update(true, true, false, 510));
        std::memcpy(name, "finale", 7);
        nativeInputResult = false;
        CHECK(!savr::cutsceneskip::FilterNativeInput(NativeInput));
        nativeInputResult = true;
        CHECK(savr::cutsceneskip::FilterNativeInput(NativeInput));
        std::memcpy(name, "zero1", 6);
        CHECK(!savr::cutsceneskip::FilterNativeInput(NativeInput));
    }
    // finale, loading/setup/finished scene, null player, paused or missing API.
    running = false; CannotSkip(); running = true;
    loaded = 1; CannotSkip(); loaded = 2;
    for (playing = 1; playing <= 4; ++playing) CannotSkip(); playing = 0;
    finished = true; CannotSkip(); finished = false;
    playerExists = false; CannotSkip(); playerExists = true;
    std::strcpy(name, "FiNaLe"); CannotSkip(); std::strcpy(name, "zero1");
    name[0] = 0; CannotSkip(); std::strcpy(name, "zero1");
    CameraMode(0, 15); CannotSkip(); CameraMode(3, 17); CannotSkip(); CameraMode(2, 17);
    timer = std::numeric_limits<float>::quiet_NaN(); CannotSkip(); timer = 1.0f;
    g.CCutsceneMgr_Skip = nullptr; CannotSkip(); g.CCutsceneMgr_Skip = Skip;
    g.CCutsceneMgr_HasFinished = nullptr; CannotSkip(); g.CCutsceneMgr_HasFinished = Finished;
    g.CCutsceneMgr_ms_running = nullptr; CannotSkip(); g.CCutsceneMgr_ms_running = &running;
    g.CCutsceneMgr_ms_loadStatus = nullptr; CannotSkip(); g.CCutsceneMgr_ms_loadStatus = &loaded;
    g.CCutsceneMgr_ms_playStatus = nullptr; CannotSkip(); g.CCutsceneMgr_ms_playStatus = &playing;
    g.CCutsceneMgr_ms_timer = nullptr; CannotSkip(); g.CCutsceneMgr_ms_timer = &timer;
    g.CCutsceneMgr_ms_cutsceneName = nullptr; CannotSkip(); g.CCutsceneMgr_ms_cutsceneName = name;
    g.TheCamera = nullptr; CannotSkip(); g.TheCamera = camera;
    g.FindPlayerPed = nullptr; CannotSkip(); g.FindPlayerPed = Player;
    // Real active camera index 2 is accepted, not just fixture camera zero.
    b = Button{};
    CHECK(!Step(b, false, true, false, 0));
    CHECK(!Step(b, true, true, false, 1));
    CHECK(!Step(b, true, true, false, 251));
    CHECK(Step(b, true, true, false, 501));
    // Queue, do not execute outside the engine tick; both native consumers
    // see the same accepted pulse even after the manager marks it finished.
    for (int cancel = 0; cancel < 5; ++cancel) {
        b = Button{};
        CHECK(!b.Update(false, true, false, 0));
        CHECK(b.Eligible() && b.Progress() == 0);
        CHECK(!b.Update(true, true, false, 10));
        CHECK(!b.Update(true, true, false, 260));
        before = skips;
        CHECK(b.Update(true, true, false, 510));
        CHECK(skips == before);
        CHECK(savr::cutsceneskip::FilterNativeInput(NativeInput));
        finished = true;
        CHECK(savr::cutsceneskip::FilterNativeInput(NativeInput));
        finished = false;
        if (cancel == 0) CHECK(!b.Update(true, true, false, 520));
        if (cancel == 1) name[0] = 'a';
        if (cancel == 2) timer = 0.1f;
        CHECK(!savr::cutsceneskip::FilterNativeInput(NativeInput, cancel != 3, cancel == 4));
        name[0] = 'z'; timer = 1.0f;
        CHECK(!savr::cutsceneskip::FilterNativeInput(NativeInput));
    }
    // A long missing sample cannot silently supply the rest of the hold.
    b = Button{};
    CHECK(!b.Update(false, true, false, 0));
    CHECK(!b.Update(true, true, false, 10));
    CHECK(!b.Update(true, true, false, 261));
    CHECK(!b.Update(true, true, false, 510));
    CHECK(!b.Update(true, true, false, 1000));
    CHECK(b.Progress() == 0);
    CHECK(!b.Update(false, true, false, 1010));
    CHECK(!b.Update(true, true, false, 1020));
    CHECK(!b.Update(true, true, false, 1270));
    CHECK(b.Update(true, true, false, 1520));
    std::puts("PASS: production native completion pulse, 500ms hold at 72/90/120Hz, one-shot/release, scene/focus/chord/pause cancellation, native safety gates and missing symbols");
}
