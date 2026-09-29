#pragma once

#include <cmath>

namespace savr::xr { struct InputState; }

namespace savr::missioncontrols {

void Install(void* gameHandle);
bool IsSwimming();
// Call once per CPad update, including blocked/menu frames, to advance edges.
void UpdateInput(const xr::InputState& input, bool enabled);
bool TouchJustPressed(int widgetId);
bool TouchDoubleTapped(int widgetId);

namespace detail {

struct Input {
    bool enabled{};
    bool onFoot{};
    bool swimming{};
    bool thumbrest{};
    float rightX{};
    float rightY{};
    bool jump{};
    bool dive{};
    bool recenter{};
};

// Game-thread frame state. Repeated retail queries in one frame see the same
// edge; another caller cannot consume an answer before the mission reads it.
class EdgeState {
public:
    void Update(const Input& input) {
        const bool horizontal = std::fabs(input.rightX) > std::fabs(input.rightY);
        const bool yes = input.thumbrest && horizontal && input.rightX > 0.55f;
        const bool no = input.thumbrest && horizontal && input.rightX < -0.55f;
        const bool active = input.enabled && input.onFoot;
        yesPressed_ = active && !input.swimming && yes && !yesHeld_;
        noPressed_ = active && !input.swimming && no && !noHeld_;
        jumpPressed_ = active && input.swimming && !input.recenter &&
                       input.jump && !jumpHeld_;
        divePressed_ = active && input.swimming && !input.recenter &&
                       input.dive && !diveHeld_ && !jumpPressed_;
        // Raw latches advance even when input is blocked or the ped changes
        // state, so a menu press or a held land jump never becomes a delayed edge.
        yesHeld_ = yes;
        noHeld_ = no;
        jumpHeld_ = input.jump;
        diveHeld_ = input.dive;
    }

    bool JustPressed(int widgetId) const {
        // CPad::Conversation{Yes,No}JustDown and CPad::DiveJustDown,
        // Android 2.11.311. No generic positive/negative widget guessing.
        return (widgetId == 110 && yesPressed_) ||
               (widgetId == 111 && noPressed_) ||
               (widgetId == 33 && divePressed_);
    }

    bool DoubleTapped(int widgetId) const {
        // Dive's alternate touch layout uses 167; SwimJump uses 168.
        return (widgetId == 167 && divePressed_) ||
               (widgetId == 168 && jumpPressed_);
    }

private:
    bool yesHeld_{}, noHeld_{}, jumpHeld_{}, diveHeld_{};
    bool yesPressed_{}, noPressed_{}, jumpPressed_{}, divePressed_{};
};

} // namespace detail
} // namespace savr::missioncontrols
