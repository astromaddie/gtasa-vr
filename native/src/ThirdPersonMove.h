#pragma once

namespace savr::thirdmove {
// THIRD: OVER SHOULDER, on foot: how the character turns and walks.
//
// The stock mobile control already turns the ped to walk where the stick
// points relative to the camera (CTaskSimplePlayerOnFoot::PlayerControlZelda),
// at the game's own turn rate, and strafes only while it runs the aim task
// (PlayerControlZeldaWeapon). What it never does is face the view. This module
// adds that on top, only in the over-the-shoulder view:
//  - aiming or firing a ranged weapon: the ped is turned to the view heading
//    every frame and the stick strafes him (the game's own aim-walk), so
//    shots go where you look;
//  - FACE CAMERA (LOCOMOTION > THIRD PERSON MOVE): the same all the time, and
//    outside the aim task the walk direction is slid sideways to follow the
//    stick, since there are no sideways walk animations.
// FACE MOVE (the default) otherwise leaves the stock turning alone. First
// person and vehicles never reach it.
void Install(void* gameHandle);
} // namespace savr::thirdmove
