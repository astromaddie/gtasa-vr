#pragma once

// OpenXR action and interaction-profile binding tables.
//
// Kept as plain data so tools/steam_frame_check_bindings.py can verify every
// suggested component path against the profile's component list and that
// action names / localized names are unique, without building the library.
// One bad path rejects a whole xrSuggestInteractionProfileBindings call, so
// each profile only lists components that profile really has.
namespace savr::xr::bindings {

enum class Act {
    Stick, Trigger, Grip, A, B, X, Y, Menu, View, StickClick, Thumbrest,
    Aim, GripPose, Haptic,
#ifdef SAVR_STEAM_FRAME
    Bumper, DpadUp, DpadDown, DpadLeft, DpadRight, CameraGrip,
#endif
};

enum class Kind { Bool, Float, Vec2, Pose, Haptic };

struct ActionDef {
    Act         id;
    Kind        kind;
    bool        perHand;
    const char* name;       // XrActionCreateInfo::actionName
    const char* localized;  // XrActionCreateInfo::localizedActionName
};

// ACTIONS-BEGIN
inline constexpr ActionDef kActions[] = {
    {Act::Stick,      Kind::Vec2,   true,  "stick",      "stick"},
    {Act::Trigger,    Kind::Float,  true,  "trigger",    "trigger"},
    {Act::Grip,       Kind::Float,  true,  "grip",       "grip"},
    {Act::A,          Kind::Bool,   false, "a",          "a"},
    {Act::B,          Kind::Bool,   false, "b",          "b"},
    {Act::X,          Kind::Bool,   false, "x",          "x"},
    {Act::Y,          Kind::Bool,   false, "y",          "y"},
    {Act::Menu,       Kind::Bool,   false, "menu",       "menu"},
    {Act::View,       Kind::Bool,   false, "view",       "View"},
    {Act::StickClick, Kind::Bool,   true,  "stickclick", "stickclick"},
    {Act::Thumbrest,  Kind::Bool,   true,  "thumbrest",  "thumbrest"},
    {Act::Aim,        Kind::Pose,   true,  "aim",        "aim"},
    {Act::GripPose,   Kind::Pose,   true,  "grippose",   "grippose"},
    {Act::Haptic,     Kind::Haptic, true,  "haptic",     "haptic"},
};
// Frame gamepad additions do not alter the inherited Quest action set.
#ifdef SAVR_STEAM_FRAME
    // Extra actions are declared in kFrameActions below.
#endif

#ifdef SAVR_STEAM_FRAME
inline constexpr ActionDef kFrameActions[] = {
    {Act::Bumper,Kind::Bool,true,"bumper","Gamepad bumper"},
    {Act::DpadUp,Kind::Bool,false,"dpad_up","D-pad up"},
    {Act::DpadDown,Kind::Bool,false,"dpad_down","D-pad down"},
    {Act::DpadLeft,Kind::Bool,false,"dpad_left","D-pad left"},
    {Act::DpadRight,Kind::Bool,false,"dpad_right","D-pad right"},
    {Act::CameraGrip,Kind::Bool,false,"camera_grip_left","Left grip camera adjustment"},
};
#endif

// ACTIONS-END

struct Binding {
    Act         action;
    const char* path;
};

inline constexpr char kProfileFrame[] =
    "/interaction_profiles/valve/frame_controller_valve";
inline constexpr char kProfileIndex[] =
    "/interaction_profiles/valve/index_controller";
inline constexpr char kProfileTouch[] =
    "/interaction_profiles/oculus/touch_controller";

// Steam Frame controller. A B X Y and Menu are on the RIGHT controller; View
// and the D-pad are on the LEFT. Components: a/b/x/y/menu/click (right),
// view/click and dpad_*/click (left), bumper/click, trigger/value|click,
// squeeze/value, thumbstick (+/click), aim/pose, grip/pose, output/haptic.
// There is no thumbrest.
// FRAME-BEGIN
inline constexpr Binding kFrameBindings[] = {
#ifdef SAVR_STEAM_FRAME
    {Act::Bumper,"/user/hand/left/input/bumper/click"},
    {Act::Bumper,"/user/hand/right/input/bumper/click"},
    {Act::DpadUp,"/user/hand/left/input/dpad_up/click"},
    {Act::DpadDown,"/user/hand/left/input/dpad_down/click"},
    {Act::DpadLeft,"/user/hand/left/input/dpad_left/click"},
    {Act::DpadRight,"/user/hand/left/input/dpad_right/click"},
    {Act::CameraGrip,"/user/hand/left/input/squeeze/value"},
#endif
    {Act::Stick,      "/user/hand/left/input/thumbstick"},
    {Act::Stick,      "/user/hand/right/input/thumbstick"},
    {Act::Trigger,    "/user/hand/left/input/trigger/value"},
    {Act::Trigger,    "/user/hand/right/input/trigger/value"},
    {Act::Grip,       "/user/hand/left/input/squeeze/value"},
    {Act::Grip,       "/user/hand/right/input/squeeze/value"},
    {Act::A,          "/user/hand/right/input/a/click"},
    {Act::B,          "/user/hand/right/input/b/click"},
    {Act::X,          "/user/hand/right/input/x/click"},
    {Act::Y,          "/user/hand/right/input/y/click"},
    {Act::Menu,       "/user/hand/right/input/menu/click"},
    {Act::View,       "/user/hand/left/input/view/click"},
    {Act::StickClick, "/user/hand/left/input/thumbstick/click"},
    {Act::StickClick, "/user/hand/right/input/thumbstick/click"},
    {Act::Aim,        "/user/hand/right/input/aim/pose"},
    {Act::Aim,        "/user/hand/left/input/aim/pose"},
    {Act::GripPose,   "/user/hand/left/input/grip/pose"},
    {Act::GripPose,   "/user/hand/right/input/grip/pose"},
    {Act::Haptic,     "/user/hand/left/output/haptic"},
    {Act::Haptic,     "/user/hand/right/output/haptic"},
};
// FRAME-END

// Valve Index controller. a/b exist on both hands; there is no menu/x/y and no
// thumbrest. Left B stands in for Menu, left A for View, right A/B stay A/B.
// INDEX-BEGIN
inline constexpr Binding kIndexBindings[] = {
    {Act::Stick,      "/user/hand/left/input/thumbstick"},
    {Act::Stick,      "/user/hand/right/input/thumbstick"},
    {Act::Trigger,    "/user/hand/left/input/trigger/value"},
    {Act::Trigger,    "/user/hand/right/input/trigger/value"},
    {Act::Grip,       "/user/hand/left/input/squeeze/value"},
    {Act::Grip,       "/user/hand/right/input/squeeze/value"},
    {Act::A,          "/user/hand/right/input/a/click"},
    {Act::B,          "/user/hand/right/input/b/click"},
    {Act::Menu,       "/user/hand/left/input/b/click"},
    {Act::View,       "/user/hand/left/input/a/click"},
    {Act::StickClick, "/user/hand/left/input/thumbstick/click"},
    {Act::StickClick, "/user/hand/right/input/thumbstick/click"},
    {Act::Aim,        "/user/hand/right/input/aim/pose"},
    {Act::Aim,        "/user/hand/left/input/aim/pose"},
    {Act::GripPose,   "/user/hand/left/input/grip/pose"},
    {Act::GripPose,   "/user/hand/right/input/grip/pose"},
    {Act::Haptic,     "/user/hand/left/output/haptic"},
    {Act::Haptic,     "/user/hand/right/output/haptic"},
};
// INDEX-END

// Meta Quest Touch (the original, unchanged map).
// TOUCH-BEGIN
inline constexpr Binding kTouchBindings[] = {
    {Act::Stick,      "/user/hand/left/input/thumbstick"},
    {Act::Stick,      "/user/hand/right/input/thumbstick"},
    {Act::Trigger,    "/user/hand/left/input/trigger/value"},
    {Act::Trigger,    "/user/hand/right/input/trigger/value"},
    {Act::Grip,       "/user/hand/left/input/squeeze/value"},
    {Act::Grip,       "/user/hand/right/input/squeeze/value"},
    {Act::A,          "/user/hand/right/input/a/click"},
    {Act::B,          "/user/hand/right/input/b/click"},
    {Act::X,          "/user/hand/left/input/x/click"},
    {Act::Y,          "/user/hand/left/input/y/click"},
    {Act::Menu,       "/user/hand/left/input/menu/click"},
    {Act::StickClick, "/user/hand/left/input/thumbstick/click"},
    {Act::StickClick, "/user/hand/right/input/thumbstick/click"},
    {Act::Thumbrest,  "/user/hand/left/input/thumbrest/touch"},
    {Act::Thumbrest,  "/user/hand/right/input/thumbrest/touch"},
    {Act::Aim,        "/user/hand/right/input/aim/pose"},
    {Act::Aim,        "/user/hand/left/input/aim/pose"},
    {Act::GripPose,   "/user/hand/left/input/grip/pose"},
    {Act::GripPose,   "/user/hand/right/input/grip/pose"},
    {Act::Haptic,     "/user/hand/left/output/haptic"},
    {Act::Haptic,     "/user/hand/right/output/haptic"},
};
// TOUCH-END

} // namespace savr::xr::bindings
