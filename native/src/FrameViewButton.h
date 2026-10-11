#pragma once

#include <cstdint>

namespace savr::frameview {

enum class Context {
    Ignore,
    Menu,
    Gameplay,
};

enum class Event {
    None,
    ShortPress,
    Recenter,
    Recalibrate,
};

enum class Action {
    None,
    Back,
    ToggleGameplayView,
};

// View is a release action when the press started and ended in the same
// controllable context. A focus or menu transition cancels a pending short
// press, while holds keep the system recenter/calibration behavior.
class Button {
public:
    Event Update(bool pressed, bool focused, Context context,
                 std::uint64_t nowMs) {
        if (!focused) {
            Reset();
            suppressUntilNeutral_ = true;
            return Event::None;
        }

        if (suppressUntilNeutral_) {
            if (!pressed) suppressUntilNeutral_ = false;
            return Event::None;
        }

        if (pressed) {
            if (!held_) {
                held_ = true;
                downAtMs_ = nowMs;
                downContext_ = context;
                recentered_ = false;
                recalibrated_ = false;
                contextChanged_ = false;
            } else if (context != downContext_) {
                contextChanged_ = true;
            }
            const std::uint64_t heldFor = nowMs >= downAtMs_
                ? nowMs - downAtMs_ : 0;
            if (!recentered_ && heldFor >= 1000) {
                recentered_ = true;
                return Event::Recenter;
            }
            if (recentered_ && !recalibrated_ && heldFor >= 3000) {
                recalibrated_ = true;
                return Event::Recalibrate;
            }
            return Event::None;
        }

        if (!held_) return Event::None;
        const std::uint64_t heldFor = nowMs >= downAtMs_
            ? nowMs - downAtMs_ : 0;
        const bool shortPress = heldFor < 1000 && !recentered_ &&
                                !contextChanged_ &&
                                downContext_ != Context::Ignore &&
                                downContext_ == context;
        Reset();
        return shortPress ? Event::ShortPress : Event::None;
    }

    static Action Route(Event event, Context context) {
        if (event != Event::ShortPress) return Action::None;
        if (context == Context::Menu) return Action::Back;
        if (context == Context::Gameplay) return Action::ToggleGameplayView;
        return Action::None;
    }

private:
    void Reset() {
        held_ = false;
        downAtMs_ = 0;
        downContext_ = Context::Ignore;
        recentered_ = false;
        recalibrated_ = false;
        contextChanged_ = false;
    }

    bool held_{};
    std::uint64_t downAtMs_{};
    Context downContext_{Context::Ignore};
    bool recentered_{};
    bool recalibrated_{};
    bool contextChanged_{};
    bool suppressUntilNeutral_{};
};

} // namespace savr::frameview
