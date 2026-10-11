# Steam Frame cinematic skip

Hold the physical A button for 500 ms during a formal cinematic. A tap does
nothing. A must first be released in that cinematic; a button held through
loading, a scene transition, focus loss, pause, View or grip chords, or a menu
cannot skip on return. One hold supplies one engine-tick skip pulse and gives the existing
two-hand haptic confirmation. Menu also cancels the hold. Short View, View recenter/calibration and gameplay
Menu pause retain their existing routes. The Quest Cross-button path is unchanged.

The Frame route no longer synthesizes Cross for eight frames. That input could
be rejected by the mobile mission blacklist and could remain pressed as gameplay
returned. The native cinematic manager and authored script skip handlers receive the
same accepted pulse through their shared input predicate.
While a formal cinematic runs, a native skip-input wrapper rejects immediate
Cross/keyboard/touch edges, including the first frame when the cinematic begins
after pad sampling. Outside formal cinematics and in the specially handled `finale`, it calls the original predicate,
preserving script-authored skip-label handling and menu confirmation. The wrapper
requires the exact retail address and four-instruction prologue; its fourth
instruction is a PC-relative `ADRP X8` and is relocated to a literal GOT-page
load in the trampoline. The hold route stays disabled if that hook fails.

`Button::Eligible()` publishes availability separately from hold progress, so
“Hold to skip” is visible before pressing A. The bottom-right prompt uses the
existing Android HUD text rasterizer and a procedural white ring around A.
The arc starts at 12 o’clock and fills clockwise over the actual 500 ms hold;
release resets it immediately. The prompt stays above the dedicated subtitle
band and hides on focus/menu/chord cancellation or unavailable native finish.
Repeated stereo frames are copied while the cue is published and once after it
hides, so cached swapchain images cannot freeze or retain the ring. The overlay
saves and restores its own graphics state, including when FXAA is disabled.

## Retail evidence and safety boundary

Inspected the user-supplied Android 2.11.311 ARM64 `libGame.so`, SHA-256
`4c6a7445e30b27afdda781302e4db9bac89c28fc1181b68b1eef16f84d6a282e`.
Addresses below are ELF virtual addresses, not runtime addresses. No retail
binary, assets or disassembly are included in the repository.

- `CCutsceneMgr::IsCutsceneSkipButtonBeingPressed` at `0x374934` returns false
  before reading Cross/keyboard/touch input when the first active script's name
  is `cat3`, `cat4`, `zero1`, `la1fin1` or `bcrash1`. The pointer is the exported
  `CTheScripts::pActiveScripts` (GOT relocation `0x837460`); the compared script
  name starts at `+0x10`. This explains why adding another virtual Cross press
  cannot unblock formal cinematics running under those scripts.
- `CCutsceneMgr::Update_overlay` at `0x54eca8` calls that input predicate and then
  `SkipCutscene` at `0x54f078` / `0x54f080`. Its gates require load status 2,
  `ms_running`, a loaded cinematic camera, active camera mode 17, and a name
  other than `finale`. The Frame route retains these boundaries. It additionally
  waits for play/setup status 0, a valid player, no pause, and an unfinished
  cinematic. Missing optional symbols fail closed.
- `SkipCutscene` at `0x54f0dc` sets exported `ms_wasCutsceneSkipped` to 1
  (`0x54f10c`, GOT `0x837b10`), moves `ms_cutsceneTimer` to the camera's finish
  time, calls `CCamera::FinishCutscene`, restores the player flag and calls
  `CPlayerInfo::MakePlayerSafe(false, 10000)`. It does not delete cinematic data
  or jump a script instruction pointer. The Frame route does not call this function independently. It lets the native
  manager call it in the next engine tick when it reads the accepted pulse.
- `HasCutsceneFinished` at `0x54f240` tests the camera spline position against
  1.0, returning true when no cinematic camera is loaded. The script interpreter
  calls this function at `0x41a294` in `ProcessCommands700To799`, forwarding its
  result to the script comparison flag (`0x41aca8`). Its separate delete-data
  command calls `DeleteCutsceneData` at `0x41a29c`. Thus scripts keep ownership
  of their usual completion branch and cleanup. The skipped flag is set by the
  native function, not fabricated by the VR layer.
- `CRunningScript::Process` at `0x412884` also calls the shared input predicate
  when its authored skip-label field at `+0x128` is nonzero; the opcode handler
  at `0x441f9c` uses it too. `CGame::Process` invokes the cinematic manager at
  `0x4960e4` before scripts at `0x496190`. The same pulse remains true for both
  consumers even after the manager marks the spline finished. It expires at the
  next input sample, or immediately on scene change, rewind, focus loss or block.
  The script predicate does not recheck the finished flag between those native
  consumers. The VR route does not fabricate labels or change script PCs.

`finale` is a separate exclusion in the cinematic manager, not one of the five
script names rejected by the input predicate. It is intentionally retained.
Scripted gameplay cameras, tutorials, dialogue, and mission sequences that do
not run a formal loaded spline cinematic are outside this skip path. Their
native continuation conditions have not been replaced or bypassed. Retail
static evidence establishes the native completion mechanism; it does not prove
every mission's continuation in a running game.

## Verification

`python3 tools/test-cutscene-skip.py` compiles and executes the production
`CutsceneSkip.cpp` against injected native endpoints. It covers queued dispatch,
500 ms timing at 72/90/120 Hz, tap/one-shot behavior, neutral rearming, changed
scene names and rewound scene time, focus/chord/pause cancellation, camera index,
loading/setup/finished states, finale, missing symbols and missing player. It
also checks uninterrupted negative-gate holds, a >250 ms sampling-gap
cancellation, the manager-finished-before-script ordering, original native
fallback (including finale), and pulse expiry. It checks the Frame input
call-site and symbol-resolution wiring. The same test compiles the actual trampoline builder with fake page-allocation
endpoints, checking the new literal relocation, return address and unchanged
default/boat relocation behavior without executing ARM instructions. Existing
`test-frame-view-button.py` and `test-standard-controls.py` pass. The test also
executes the production cache-copy decision through appearance, progress,
release, hiding and failed-copy retry, and checks overlay gating and independent
GL-state restoration wiring. These host checks do not replace runtime GPU or
mission continuation verification.

No headset installation, launch or wearer test was performed for this change.
Wear checklist: skip a normal cinematic and one under a formerly blocked
mission script, verify the mission resumes with its expected objective and
controls; check a tap does nothing; hold A across a transition without a
second skip; cancel a pending hold with View, either grip and focus loss; then
verify gameplay pause, VR menu and short/held View behavior.
