#!/usr/bin/env python3
"""Host check for the Steam Frame OpenXR binding tables.

Parses native/src/InputBindings.h (plain data, no OpenXR needed) and verifies:
  * every suggested component path exists on that interaction profile
    (one bad path makes xrSuggestInteractionProfileBindings reject the whole
    profile), including no thumbrest on the Frame or Index profiles;
  * every binding references a declared action;
  * action names and localized action names are each unique, and the new
    "view" action is distinct from all others;
  * the Frame/Index layouts keep the game's A/B/X/Y/Menu/View semantics.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = ROOT / "native" / "src" / "InputBindings.h"

HANDS = ("left", "right")


def both(prefix: str, *components: str) -> set[str]:
    return {
        f"/user/hand/{hand}/{prefix}{component}"
        for hand in HANDS
        for component in components
    }


def side(hand: str, *components: str) -> set[str]:
    return {f"/user/hand/{hand}/{component}" for component in components}


def pose_and_haptic() -> set[str]:
    return both("input/", "aim/pose", "grip/pose") | both("output/", "haptic")


# Component lists per interaction profile.
PROFILES: dict[str, set[str]] = {
    # XR_VALVE_frame_controller_interaction: A B X Y Menu on the RIGHT,
    # View and the D-pad on the LEFT. No thumbrest.
    "kProfileFrame": (
        side(
            "right",
            "input/a/click", "input/b/click", "input/x/click",
            "input/y/click", "input/menu/click",
        )
        | side(
            "left",
            "input/view/click", "input/dpad_up/click", "input/dpad_down/click",
            "input/dpad_left/click", "input/dpad_right/click",
        )
        | both(
            "input/",
            "bumper/click", "trigger/value", "trigger/click", "squeeze/value",
            "thumbstick", "thumbstick/click", "thumbstick/x", "thumbstick/y",
        )
        | pose_and_haptic()
    ),
    # Valve Index: a/b on both hands, no menu/x/y, no thumbrest.
    "kProfileIndex": (
        both(
            "input/",
            "a/click", "a/touch", "b/click", "b/touch",
            "trigger/click", "trigger/value", "trigger/touch",
            "thumbstick", "thumbstick/x", "thumbstick/y",
            "thumbstick/click", "thumbstick/touch",
            "trackpad", "trackpad/x", "trackpad/y", "trackpad/force",
            "trackpad/touch", "squeeze/value", "squeeze/force",
        )
        | pose_and_haptic()
    ),
    # Oculus Touch.
    "kProfileTouch": (
        side(
            "left",
            "input/x/click", "input/x/touch", "input/y/click", "input/y/touch",
            "input/menu/click",
        )
        | side(
            "right",
            "input/a/click", "input/a/touch", "input/b/click", "input/b/touch",
            "input/system/click",
        )
        | both(
            "input/",
            "squeeze/value", "trigger/value", "trigger/touch",
            "thumbstick", "thumbstick/x", "thumbstick/y",
            "thumbstick/click", "thumbstick/touch", "thumbrest/touch",
        )
        | pose_and_haptic()
    ),
}

TABLES = {
    "kProfileFrame": ("kFrameBindings", "FRAME"),
    "kProfileIndex": ("kIndexBindings", "INDEX"),
    "kProfileTouch": ("kTouchBindings", "TOUCH"),
}

EXPECTED_PROFILE_STRINGS = {
    "kProfileFrame": "/interaction_profiles/valve/frame_controller_valve",
    "kProfileIndex": "/interaction_profiles/valve/index_controller",
    "kProfileTouch": "/interaction_profiles/oculus/touch_controller",
}


def section(text: str, tag: str) -> str:
    match = re.search(rf"// {tag}-BEGIN(.*?)// {tag}-END", text, re.S)
    if not match:
        raise SystemExit(f"FAIL: marker {tag}-BEGIN/END missing in {HEADER}")
    return match.group(1)


def parse_actions(text: str) -> list[dict]:
    pattern = re.compile(
        r'\{Act::(\w+),\s*Kind::(\w+),\s*(true|false),\s*"([^"]*)",\s*"([^"]*)"\}'
    )
    return [
        {
            "id": m.group(1),
            "kind": m.group(2),
            "perHand": m.group(3) == "true",
            "name": m.group(4),
            "localized": m.group(5),
        }
        for m in pattern.finditer(section(text, "ACTIONS"))
    ]


def parse_bindings(text: str, tag: str) -> list[tuple[str, str]]:
    pattern = re.compile(r'\{Act::(\w+),\s*"([^"]+)"\}')
    return [(m.group(1), m.group(2)) for m in pattern.finditer(section(text, tag))]


def main() -> int:
    text = HEADER.read_text(encoding="utf-8")
    failures: list[str] = []

    actions = parse_actions(text)
    if not actions:
        failures.append("no actions parsed")
    ids = [a["id"] for a in actions]
    names = [a["name"] for a in actions]
    localized = [a["localized"] for a in actions]
    if len(set(ids)) != len(ids):
        failures.append(f"duplicate action ids: {ids}")
    if len(set(names)) != len(names):
        failures.append(f"action names are not unique: {names}")
    if len({n.lower() for n in localized}) != len(localized):
        failures.append(f"localized action names are not unique: {localized}")
    for action in actions:
        if not re.fullmatch(r"[a-z0-9_\-.]+", action["name"]):
            failures.append(f"action name {action['name']!r} is not a valid OpenXR name")
        if not action["localized"]:
            failures.append(f"action {action['name']!r} has an empty localized name")
    view = [a for a in actions if a["name"] == "view"]
    if len(view) != 1:
        failures.append("expected exactly one 'view' action")
    elif view[0]["kind"] != "Bool" or view[0]["perHand"]:
        failures.append("'view' must be a single (non per-hand) boolean action")

    for const, expected in EXPECTED_PROFILE_STRINGS.items():
        match = re.search(rf'{const}\[\]\s*=\s*"([^"]+)"', text)
        if not match or match.group(1) != expected:
            failures.append(f"{const} should be {expected!r}")

    declared = set(ids)
    summary = []
    for const, (table, tag) in TABLES.items():
        bindings = parse_bindings(text, tag)
        if not bindings:
            failures.append(f"{table}: no bindings parsed")
            continue
        valid = PROFILES[const]
        seen: set[tuple[str, str]] = set()
        by_action: dict[str, set[str]] = {}
        for action, path in bindings:
            if action not in declared:
                failures.append(f"{table}: unknown action {action}")
            if path not in valid:
                failures.append(f"{table}: {path} is not a component of {const}")
            if "thumbrest" in path and const != "kProfileTouch":
                failures.append(f"{table}: thumbrest must not be suggested ({path})")
            if (action, path) in seen:
                failures.append(f"{table}: duplicate binding {action} {path}")
            seen.add((action, path))
            by_action.setdefault(action, set()).add(path)

        def expect(action: str, *paths: str) -> None:
            if by_action.get(action, set()) != set(paths):
                failures.append(
                    f"{table}: {action} should bind exactly {sorted(paths)}, "
                    f"got {sorted(by_action.get(action, set()))}"
                )

        r = "/user/hand/right/input/"
        l = "/user/hand/left/input/"
        if const == "kProfileFrame":
            expect("A", r + "a/click")
            expect("B", r + "b/click")
            expect("X", r + "x/click")
            expect("Y", r + "y/click")
            expect("Menu", r + "menu/click")
            expect("View", l + "view/click")
            expect("Bumper", l + "bumper/click", r + "bumper/click")
            expect("CameraGrip", l + "squeeze/value")
            for direction in ("Up", "Down", "Left", "Right"):
                expect("Dpad" + direction, l + "dpad_" + direction.lower() + "/click")
            if "Thumbrest" in by_action:
                failures.append("kFrameBindings: thumbrest bound")
        elif const == "kProfileIndex":
            expect("A", r + "a/click")
            expect("B", r + "b/click")
            expect("Menu", l + "b/click")
            expect("View", l + "a/click")
            for missing in ("X", "Y", "Thumbrest"):
                if missing in by_action:
                    failures.append(f"kIndexBindings: {missing} must not be bound")
        else:
            expect("A", r + "a/click")
            expect("B", r + "b/click")
            expect("X", l + "x/click")
            expect("Y", l + "y/click")
            expect("Menu", l + "menu/click")
            if "View" in by_action:
                failures.append("kTouchBindings: the original Touch map must not bind View")
        for core in ("Stick", "Trigger", "Grip", "StickClick", "Aim", "GripPose", "Haptic"):
            if core not in by_action:
                failures.append(f"{table}: core action {core} is unbound")
        summary.append(f"{const}: {len(bindings)} bindings OK")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"actions: {len(actions)} unique names, {len({n.lower() for n in localized})} unique localized names")
    for line in summary:
        print(line)
    print("steam_frame_check_bindings: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
