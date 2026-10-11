"""Exercise the production Steam Frame View press state machine and routing."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "frame-view-button-tests"
OUT.mkdir(parents=True, exist_ok=True)
main_source = (ROOT / "native" / "src" / "main.cpp").read_text(encoding="utf-8")
assert re.search(
    r"Button::Route\(viewEvent, viewContext\).*?"
    r"case savr::frameview::Action::ToggleGameplayView:\s*"
    r"savr::locomotion::CycleViewMode\(\+1\);",
    main_source,
    re.S,
), "main.cpp must route a gameplay View short press to CycleViewMode"
assert re.search(
    r"case savr::frameview::Action::Back:\s*viewBack = true;",
    main_source,
), "main.cpp must preserve View short-press menu back"
SOURCE = OUT / "test.cpp"
SOURCE.write_text(r'''#include <cstdio>
#include <cstdlib>
#include "FrameViewButton.h"
using namespace savr::frameview;
#define CHECK(e) do { if (!(e)) { std::fprintf(stderr, "FAIL %d: %s\n", __LINE__, #e); std::exit(1); } } while (0)
int main() {
    Button button;

    // Ordinary on-foot play routes a release to the persistent global view.
    CHECK(button.Update(true, true, Context::Gameplay, 100) == Event::None);
    CHECK(button.Update(false, true, Context::Gameplay, 220) == Event::ShortPress);
    CHECK(Button::Route(Event::ShortPress, Context::Gameplay) == Action::ToggleGameplayView);

    // The global locomotion choice also controls ordinary vehicle gameplay;
    // vehicle-specific CAMERA VIEW rows remain separate settings.
    CHECK(button.Update(true, true, Context::Gameplay, 300) == Event::None);
    CHECK(button.Update(false, true, Context::Gameplay, 450) == Event::ShortPress);
    CHECK(Button::Route(Event::ShortPress, Context::Gameplay) == Action::ToggleGameplayView);

    // Menus preserve the system-layer Back action.
    CHECK(button.Update(true, true, Context::Menu, 500) == Event::None);
    CHECK(button.Update(false, true, Context::Menu, 600) == Event::ShortPress);
    CHECK(Button::Route(Event::ShortPress, Context::Menu) == Action::Back);

    // Ineligible play, a menu transition, and a focus loss cancel short presses.
    CHECK(button.Update(true, true, Context::Ignore, 700) == Event::None);
    CHECK(button.Update(false, true, Context::Gameplay, 800) == Event::None);
    CHECK(button.Update(true, true, Context::Gameplay, 900) == Event::None);
    CHECK(button.Update(false, true, Context::Menu, 1000) == Event::None);
    CHECK(button.Update(true, true, Context::Gameplay, 1050) == Event::None);
    CHECK(button.Update(true, true, Context::Menu, 1075) == Event::None);
    CHECK(button.Update(true, true, Context::Gameplay, 1100) == Event::None);
    CHECK(button.Update(false, true, Context::Gameplay, 1150) == Event::None);
    CHECK(button.Update(true, true, Context::Menu, 1200) == Event::None);
    CHECK(button.Update(false, true, Context::Gameplay, 1300) == Event::None);
    CHECK(button.Update(true, true, Context::Gameplay, 1400) == Event::None);
    CHECK(button.Update(true, false, Context::Ignore, 1450) == Event::None);
    CHECK(button.Update(true, true, Context::Gameplay, 1500) == Event::None);
    CHECK(button.Update(false, true, Context::Gameplay, 1550) == Event::None);
    CHECK(button.Update(true, true, Context::Gameplay, 1600) == Event::None);
    CHECK(button.Update(false, true, Context::Gameplay, 1700) == Event::ShortPress);

    // A one-second hold recentres exactly once and never turns into a toggle.
    CHECK(button.Update(true, true, Context::Gameplay, 2000) == Event::None);
    CHECK(button.Update(true, true, Context::Gameplay, 2999) == Event::None);
    CHECK(button.Update(true, true, Context::Gameplay, 3000) == Event::Recenter);
    CHECK(button.Update(true, true, Context::Gameplay, 3100) == Event::None);
    CHECK(button.Update(false, true, Context::Gameplay, 3200) == Event::None);

    // A three-second hold adds standing calibration after the initial recenter.
    CHECK(button.Update(true, true, Context::Menu, 4000) == Event::None);
    CHECK(button.Update(true, true, Context::Menu, 5000) == Event::Recenter);
    CHECK(button.Update(true, true, Context::Menu, 7000) == Event::Recalibrate);
    CHECK(button.Update(true, true, Context::Menu, 7200) == Event::None);
    CHECK(button.Update(false, true, Context::Menu, 7300) == Event::None);
    CHECK(Button::Route(Event::Recenter, Context::Gameplay) == Action::None);

    // If a stalled frame skips the held samples, a release at/after the hold
    // threshold must not be misclassified as a short press.
    CHECK(button.Update(true, true, Context::Gameplay, 8000) == Event::None);
    CHECK(button.Update(false, true, Context::Gameplay, 9000) == Event::None);
    CHECK(button.Update(true, true, Context::Gameplay, 9100) == Event::None);
    CHECK(button.Update(false, true, Context::Gameplay, 10101) == Event::None);

    std::puts("PASS: main.cpp dispatch, gameplay and ordinary-vehicle toggle routing, menu back, ignored contexts, context/focus cancellation, short/held timing, recenter and standing calibration holds");
}
''', encoding="utf-8")
compiler = "c++"
subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "native" / "src"), str(SOURCE), "-o", str(OUT / "test")], check=True)
result = subprocess.run([str(OUT / "test")], check=False, text=True, capture_output=True)
print(result.stdout, end="")
print(result.stderr, end="", file=sys.stderr)
sys.exit(result.returncode)
