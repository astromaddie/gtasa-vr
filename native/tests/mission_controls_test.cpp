#include "../src/MissionControls.h"

#include <cstdio>
#include <initializer_list>

int main() {
    using savr::missioncontrols::detail::EdgeState;
    using savr::missioncontrols::detail::Input;
    int checked = 0;
    int failed = 0;
    auto check = [&](bool passed, const char* label) {
        ++checked;
        if (!passed) { ++failed; std::fprintf(stderr, "FAIL: %s\n", label); }
    };
    EdgeState edges;
    Input input{};
    input.enabled = input.onFoot = true;
    input.thumbrest = true;
    input.rightX = 1.0f;
    edges.Update(input);
    check(edges.JustPressed(110) && !edges.JustPressed(111), "right answers yes");
    check(edges.JustPressed(110), "repeated same-frame query preserves answer");
    edges.Update(input);
    check(!edges.JustPressed(110), "held answer does not repeat");
    input.rightX = -1.0f;
    edges.Update(input);
    check(edges.JustPressed(111) && !edges.JustPressed(110), "left answers no");
    for (int id : {0, 1, 8, 31, 69, 71, 73, 74, 156, 160, 161, 175, 187}) {
        check(!edges.JustPressed(id) && !edges.DoubleTapped(id), "unrelated widget unchanged");
    }
    input.thumbrest = false;
    input.rightX = 1.0f;
    edges.Update(input);
    check(!edges.JustPressed(110), "turn stick alone cannot answer");
    input.thumbrest = true;
    input.rightY = 1.0f;
    edges.Update(input);
    check(!edges.JustPressed(110), "diagonal does not answer");
    input.rightY = 0.0f;
    input.enabled = false;
    edges.Update(input);
    check(!edges.JustPressed(110), "menu blocks answer");
    input.enabled = true;
    edges.Update(input);
    check(!edges.JustPressed(110), "menu close cannot replay held answer");
    input.rightX = 0.0f;
    input.jump = true;
    edges.Update(input);
    check(!edges.DoubleTapped(168), "land jump does not fake swim widget");
    input.swimming = true;
    edges.Update(input);
    check(!edges.DoubleTapped(168), "entering water does not replay held jump");
    input.jump = false;
    edges.Update(input);
    input.jump = true;
    edges.Update(input);
    check(edges.DoubleTapped(168) && !edges.DoubleTapped(167), "fresh swim jump edge");
    edges.Update(input);
    check(!edges.DoubleTapped(168), "held swim jump does not repeat");
    input.jump = false;
    input.dive = true;
    edges.Update(input);
    check(edges.JustPressed(33) && edges.DoubleTapped(167), "dive works in both touch layouts");
    check(!edges.DoubleTapped(168), "dive cannot also climb");
    input.dive = false;
    edges.Update(input);
    input.dive = true;
    input.recenter = true;
    edges.Update(input);
    check(!edges.JustPressed(33), "recenter cannot dive");
    input.recenter = false;
    edges.Update(input);
    check(!edges.JustPressed(33), "releasing recenter cannot replay dive");
    input.dive = false;
    input.jump = false;
    edges.Update(input);
    input.dive = input.jump = true;
    edges.Update(input);
    check(edges.DoubleTapped(168) && !edges.JustPressed(33), "native jump priority on simultaneous press");
    input.enabled = false;
    edges.Update(input);
    check(!edges.DoubleTapped(168) && !edges.JustPressed(33), "blocked frame clears swim edges");
    std::printf("mission controls: %d checks, %d failures\n", checked, failed);
    return failed ? 1 : 0;
}
