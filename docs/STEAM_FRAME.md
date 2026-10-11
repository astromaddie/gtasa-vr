# GTA San Andreas VR on the Steam Frame

This is my Steam Frame fork of the Quest port. It runs the Google Play GTA San
Andreas 2.11.311 ARM64 game through Lepton and SteamVR OpenXR, with persistent
game files in the Frame's Documents folder.

I've played it on my Frame. Stereo gameplay, menus, 3D cutscenes with subtitles
and fades, and the third-person locked camera are working well.

The Frame build uses a third-person over-the-shoulder view by default. It also
supports first-person play, a live camera preview in the paused VR settings,
and camera adjustment with left grip plus the right stick. A third-person
3D-screen view has not been implemented.

## What's different from the Quest build

All of it sits behind `--steam-frame` (CMake `SAVR_STEAM_FRAME`), so Quest
builds come out the same as before.

- **One APK.** Lepton's Steam titles take a single APK, so the Frame build
  wants a merged ("monolithic") game APK as input and produces one
  `base.apk`. A backup tool's merged APK works with
  `--allow-unofficial-source`. Its signer differs from Google's, but the
  kit still checks `libGame.so` against the expected hash, so you know it's
  the right game.
- **Manifest.** Head tracking is no longer a hard install requirement,
  because Lepton doesn't advertise it. The Quest-only focus-aware flag is
  gone.
- **Files.** Settings, logs, audio, the VR hands and the game data go in
  `/sdcard/Documents/GTASAVR` (`~/Documents/GTASAVR` on the headset). That
  folder survives a Lepton reset; the app's own storage doesn't. If the
  folder can't be written, it falls back to the old Quest paths and logs
  why.
- **Controllers.** The Frame controller profile comes first, then Index,
  then the original Touch map. A, B, X, Y and Menu are on the right
  controller, View is on the left. Hold View for a second to recentre (both
  hands buzz). Hold for three seconds to recalibrate standing height as well.
  A short View press goes back in menus; choose the view in LOCOMOTION.
  The left trigger targets, the right trigger fires, and the right stick aims
  while targeting. Bumpers cycle owned weapons. All four left D-pad directions
  are bound to the game's native pad. Clicking both sticks no longer recentres.
- **Pause and cutscenes.** Menu opens the game's pause menu in play. During a
  story cutscene, hold Menu for half a second to skip it (a tap does nothing).
  Story cutscenes default to CINEMA 3D: a 2.56 x 1.44 m screen 2 m ahead,
  fixed in the room where the cutscene starts (a View-hold recentre moves it),
  showing the director camera in stereo from two parallel off-axis cameras
  converged 1.5 m in front of the camera. It goes out as a projection layer
  whose per-eye fov is the screen rectangle seen from that eye. CINEMA (flat
  screen), CINEMATIC (head-tracked director camera) and FIRST PERSON stay
  selectable in the VR menu under CUTSCENES. A settings file from before this
  default is moved to CINEMA 3D once. `Cinema3DDepth=` in vr_locomotion.ini
  (0.10 to 0.90, default 0.55) sets how far behind the screen the far
  background sits. The screen fade and the subtitles are put back on the 3D
  screen at zero parallax: the fade from the game's own fade colour/alpha
  bytes, the subtitles from the published message text. The subtitles sit in
  a black band under the picture (the screen is 2.56 x 1.92 m: the 16:9
  picture on top, a 0.48 m band below, all in one plane), like the letterbox
  band in the GTA III and Vice City cinema, so they no longer float over a 3D
  image at a different depth. The first subtitle line sits right under the
  picture's bottom edge (about 1.4 cm margin; it used to float about 20 cm
  lower, because the text was centred in a tall box). The tutorial help box
  (the "press X to..." tooltips the opening cutscenes show) is drawn in the
  same band, under the subtitle text, or at the top of it when there are no
  subtitles. It follows the HELP TEXT switch in the HUD menu.
- **In-engine cutscenes.** The camera cuts you get in the middle of play
  (following CJ walking, mission cameras with the black letterbox bars) use
  the same 3D cinema screen. GAME CUTSCENES in the graphics menu has CINEMA,
  CINEMATIC, FIRST PERSON + R3 and CINEMA 3D (the Frame default; an older
  settings file is moved to it once). The letterbox flag is what marks such a
  scene, and it goes through one latch: the scene starts when the bars go up
  and ends when they have been down for 0.8 s and the scene has run for at
  least 1.5 s, so a script that drops the bars for a frame between two shots
  does not bounce you between the cinema, the head-tracked view and the HUD.
  A scene where the game takes your controls but has no letterbox (the
  barber chair, clothes shops) still goes to the flat screen with the laser
  pointer, because those menus need it. In the cinema the hands, weapons and
  HUD are hidden and only the fade and the subtitles are drawn.
- **Focus guard.** The game's pause menu asks Rockstar's SDK for an app-store
  review prompt, and under Lepton that window takes the Android focus away
  and the game stops drawing for good. The review request and external links
  are no-ops on this build, and a watchdog thread logs `[focus.watch]` /
  `[watchdog]` lines and gives the focus back if the headset is in use but the
  window has been unfocused for 1.5 s.
- **OpenXR.** Only extensions SteamVR actually offers are switched on, and
  the swapchain format comes from SteamVR's own list. Everything is logged
  with a `[savr-frame]` prefix.
- **Audio.** The PS2 audio pack is still what you want, but on the Frame
  it's optional. Without it the game should fall back to its own audio.

## Views, HUD and colour

**Views.** LOCOMOTION, VIEW (the first row):

- **FIRST PERSON** is available from the view setting: you are in CJ's head, the controllers
  are his hands and you hold the guns.
- **THIRD: OVER SHOULDER** is a stereo view from behind CJ, with head
  tracking and a level horizon. The camera only turns when you turn, with the
  snap or smooth turn from the right stick. It sits at the distance and height
  of the game's own chase camera, a little to the right of him, and a line
  test from his head pulls it in at walls. CJ's body is drawn, your hands and
  the tracked guns are not. Controls are pad-style: the left stick walks
  relative to the view heading (whatever MOVE DIRECTION says), the right
  trigger fires the weapon CJ has equipped. On Frame, left trigger targets,
  the right stick aims while targeting, and bumpers cycle owned weapons
  (left previous, right next). Physical D-pad directions reach the native pad.
  First-person grips keep their grab/holster actions, and custom face-button
  bindings remain unchanged. Index/Touch keep their existing grip fallback.
  LOCOMOTION, THIRD PERSON MOVE `< FACE MOVE | FACE CAMERA >` (saved as
  `ThirdPersonMove=` in vr_locomotion.ini) says how CJ turns. FACE MOVE, the
  default, is the classic third person: he turns to walk where the stick
  points, at the game's own turn rate, and walks forward along it. While he
  aims or fires a ranged weapon he faces the view heading instead and the
  stick strafes him, so shots go where you look; fists and melee weapons turn
  with the stick. FACE CAMERA keeps him facing the view heading all the time
  and the stick strafes him, with no sideways walk animations: outside the
  aim stance he slides sideways (or backwards) in his forward walk. First
  person is not affected by it. In
  vehicles every vehicle is viewed from the stock chase camera, whatever its
  CAMERA VIEW row says. Getting in or out of a vehicle keeps the camera on the
  player (it blends between its own camera and the stock one over half a
  second). Cutscenes, the jetpack, parachute, RC models and cranes switch
  back to first person for as long as they last.
- **THIRD: 3D SCREEN** is not in. It would need the cinema screen to carry
  the HUD and the stock camera to be turned from the right stick, and on the
  mobile build that stick only reaches the camera through touch-gated
  thresholds that nobody has tested here. Over the shoulder covers the same
  need for now.

**HUD.** HUD, PRESET now has three choices. FRONT PANEL is the Frame default
(an old `vr_hud.ini` is moved to it once): one 1.1 x 0.62 m panel 1.7 m in
front of you with the radar bottom left, the money/health/armour/wanted
block top right, help text top left, mission timers under the status block,
big messages low centre and the air and locator bars bottom right. It hangs
in the room and eases after your head. Yaw does nothing inside 12 degrees and
past that follows with a 0.3 s time constant, position follows past 10 cm
(0.45 s), and the height stays at your eye level. It only yaws, it never
rolls. CLASSIC (pasted onto the eye image, so head-locked and jittery) and
IMMERSIVE (wrist panels) are still there. The panel is drawn as geometry at
the pose the eye image was rendered from, so the runtime re-projects it like
the world.

**Colour filter.** GRAPHICS, COLOUR FILTER < MOBILE | PS2 >. PS2 gives the
golden, yellow-green look of the PlayStation 2 game, which the mobile build
lacks. It rebuilds the PS2 colour filter from the game's current timecycle
(its two post-fx colours), as a per-channel gain applied while the eye image
is resolved: colour 1 / 127.5 plus alpha 2 / 255 x colour 2 / 127.5. It
replaces the mobile grade while it is on (COLOR GRADING only governs MOBILE).
Night vision, infrared and CCTV fall back to the mobile grade. The
formula follows aap's SkyGfx; no code was taken from it (NOTICE.md). PS2 is
the Frame default: at midday in Los Angeles the gain works out to about
1.8 / 1.5 / 0.85 for red / green / blue, which is the orange cast the PS2
game has, so if it turns out too strong, switch it back in the menu. The flat
screen (menus, flat CINEMA) is not filtered.

## Laser pointer, menu pointing and upright sprites

The right controller's laser points into flat game menus and the VR settings
panel. The beam and dot follow the submitted screen and panel poses, and the
pointer is drawn above those panels so it remains visible when you aim at a
menu row or slider.

**The pointer is always on top.** In the flat screen (frontend, pause, the
barber chair and similar) and in the VR menu, the right controller's aim pose
casts a ray. It is tested against the flat game screen and the VR menu panel,
using the quads exactly as they were last submitted (their real pose and size,
no hard-coded numbers), and the nearest hit wins. The pointer is drawn as two
alpha-blended quad layers, a thin beam from the controller to the hit point and a
cursor dot (cyan, amber while the trigger is down), submitted last. Layer order
each frame is now: world projection or flat screen, VR menu panel (when open),
beam, dot. SteamVR composites later layers over earlier ones, so the beam can no
longer disappear behind the VR menu or the cinema. If the ray hits nothing the
beam still shows (1.5 m long, no dot) so you can find the screen. In gameplay
there is nothing to point at and no pointer layers are submitted. The old arrow
baked into the flat screen is kept only as a fallback if the pointer swapchain
cannot be created. The trigger uses hysteresis (down at 0.6, up at 0.45), with a
10 ms 0.2 hover pulse on the right hand when the hovered menu row changes and a
30 ms 0.5 click pulse (`ui_hover` / `ui_click`; the kit has no haptics-scale
setting yet, so these are unscaled). The dot lies flat on whatever surface the ray hit (see "Round 3" below),
so it does not roll with the head.

**The VR menu is pointer-operable.** Hovering a row selects it (only when the
hovered row changes, so the left stick keeps working while the ray rests
elsewhere). Trigger click on the middle of a row does what A does; a click on
the outer 16% at either side steps that row's value down (left) or up (right),
like L2/R2. While the ray is on the panel the right trigger is the click and
no longer R2 "plus" (L2 still steps down), which is the one behaviour change.
The row layout of each page is registered by its builder (`PanelRowsSet`, one
line per page), including the scrolling pages, and a page change is ignored for
three frames so a hover from the old page cannot land on the new one. About and
Control Tips close on any click. Log line: `[ui.pointer]`.

**Sprites never roll with the head.** Coronas and wet-road reflections used the
per-eye camera basis, roll included. They now build their axes from world up
(right = normalize(cross(up, toCentre)), up = cross(toCentre, right), like the
sky quads), with the signs taken from the camera's own left/up so the textures
keep their orientation; straight above or below the eye the camera basis is
used. Centres are unchanged, so they still sit on their light sources in both
eyes. The scope reticle stays centred on the aim, but the cross is drawn in a
frame whose vertical follows world up (the head roll at the eye image's render
pose is counter-rotated); the circular mask is rotation-invariant. The front HUD
and the sky sun/moon were already upright.

The same layered pointer is used over the pause menu, the VR settings and the
cinema screen.

## Display: 120 Hz and 2160 per eye

The Frame build requests a 120 Hz display rate and targets 2160 x 2160 per
eye. That is a display configuration, not a benchmark or a promise that the
game holds 120 frames per second in every scene.

**Target.** 120 Hz at about 2160 x 2160 per eye (the panel's own resolution;
the runtime recommends 1728 x 1728 by default, or 2160 with SteamVR's per-app
resolution override set).

**An app can't change the refresh rate on the Frame.** SteamVR offers only one
rate: the title's per-app preferred rate (or the display setting when the title
has no entry), and only for launches through the Steam title. So the rate is set
by the user once, in SteamVR's per-app settings in the headset. The GTASAVR
title is set to 120 Hz and resolution 2160 (done 2026-10-05). Editing the
settings file from SSH while SteamVR runs does nothing.

**What the port does about it.** `refresh_rate=120` in `vr_display.ini` (next to
the other `vr_*.ini` files; written with the default on first launch) is the
rate it asks for. At session start it enumerates `XR_FB_display_refresh_rate`
and logs

    [vr] refresh: setting 120, offered {120}, requested 120

where requested is the highest offered rate not above the setting. It then makes
at most one request per session, only for an offered rate, and only if the
compositor runs below it (it never asks for less than the compositor already
runs: the FB list can offer one rate while the compositor does something else).
With the title set to 120 the log says no request was needed. The game loop is
paced to the rate the compositor really runs (the pacer reads
`xr::TargetFrameRateHz`, which follows `predictedDisplayPeriod`). GTA's own
frame cap word is now 120 on the Frame build (the ceiling); the Quest build
keeps 72. There is no automatic fallback ladder (a request for a lower rate
can't take effect).

**Telling you when it can't hold the rate.** While the session is FOCUSED and
you are in the world, the port counts game frames in 10 s windows. After two
windows in a row below 90% of the display rate it logs once per session:

    [vr] refresh: not holding 120 Hz (fps 71.0, 70.5); set GTASAVR to 72 Hz in SteamVR per-app settings

The suggested rate is the highest of 120, 90 and 72 the measured fps would hold
(72 at the lowest). Menus, loading and lost focus don't count windows.

The build requests the highest offered rate up to the selected setting. The
Steam title's per-app refresh preference controls which rate SteamVR offers.
The game loop follows the runtime's actual display period. No stable 120 fps
gameplay benchmark is claimed here.

**Resolution.** The default is an absolute ~2160 x 2160 per eye, whatever the
runtime recommends. At session start the port takes the runtime's recommended
eye width and picks the RESOLUTION step whose eye image comes closest to 2160:
a recommendation of 1728 gives 125% (1728 x 1.25 = 2160), and one of 2160 (what
SteamVR's per-app `resolutionOverride=2160` makes it) gives 100%, not 125% of
2160. It logs the lot:

    [vr] eye resolution: runtime recommends 2160, target 2160, default scale 100% (default would be 100%) -> 2160 per eye

A scale you pick in the RESOLUTION menu row overrides the default from then on
(saved as `RenderScaleUser=1` in `vr_graphics.ini`); RESET DEFAULTS goes back to
the computed one. The eye swapchains are created at that size at launch and the
game renders straight into rasters of the same size, so there is no render-
larger-then-blit-down step any more (the old code rendered at the scale and
blitted into a swapchain at the runtime's recommended size). The consequence:
the scale is fixed for the session. Changing RESOLUTION in the menu is saved and
shows `[NEXT LAUNCH]`; it applies on restart. An older `vr_graphics.ini` (which
holds the old 100% but no marker) is not treated as a choice and gets the
computed default. Logs: `[vr] eye resolution`, `[vr] eye image WxH` and
`[stereo] N eye-texture sets created WxH`.

## Round 3 (2026-10-05): laser dot, tooltips, subtitle gap, grip

Host build, not worn.

**Laser dot and beam.** The dot was a quad facing the head and centred exactly
on the hit point, so on a tilted panel half of it sat behind the surface.
SteamVR depth-composites quads that intersect, so that half was hidden and the
crossing dithered (the same cause as the GTA III and Vice City ports; the beam's
last centimetres crossed the plane the same way). Now:

- The dot takes the orientation of the surface that was hit (the flat game
  screen or the VR menu panel, as last submitted), so it lies flat on it and
  can't roll with the head. Its position is the hit point plus 12 mm along the
  surface normal, flipped to the side the head is on. The size rule is
  unchanged (5% of the head distance, 4 to 14 cm).
- The beam ends in front of the surface: it is pulled back along the ray by
  `0.02 / max(|dot(dir, n)|, 0.25)` m, never shorter than 3 cm.
- Beam and dot are still the last two layers submitted, drawn as alpha-blended
  quad layers, so they sit above the menu, the cinema and the HUD.

**Cutscene tooltips.** The tutorial help text lives in `CWidgetHelpText`'s
queue, and the cinema's text path published only the subtitles
(`PublishCinemaOverlayState` passed a null help string), so the box never
reached the cinema. It is published now, from the same queue the in-world HUD
reads. Where it draws: in the black band under the picture, under the subtitle
text (or at the top of the band with no subtitles), in a slightly smaller font.
Why there and not top-left on the picture like a TV: the user didn't like text
on the 3D picture at the screen plane for subtitles (round 2), and a tooltip
would have the same problem, so the band is the consistent place, and it needs
no new layer. The front HUD panel isn't an option inside the cinema, because it
is geometry drawn into the eye image and the cinema frame is its own render.
A long box under two subtitle lines can run out of band; the box is capped at
4 lines and the subtitles at 3.

**Subtitle gap.** Before: the text was centred in a 0.44 m tall raster that sat
in the 0.48 m band, so one subtitle line started about 0.2 m under the picture
(two and a bit lines; two lines about 0.15 m). After: the raster is top-aligned
and placed at the top edge of the band, so the first line starts about 1.4 cm
under the picture. (Computed from the layout, not measured on the headset.)

**Grip and the handbrake.** Grip is not the handbrake here. In a vehicle the
handbrake is A alone (the `CPad::GetHandBrake` hook returns full while A is
held, unless a mission has claimed A), and no grip reaches it. Grip is a
modifier: both grips with Menu or Y open the VR menu, both grips with R2 answer
the phone, both grips with B quit a minigame; in a vehicle X changes the radio
station (with the left grip, back a station) and B with one grip held looks and
drive-by fires to that side; in the Hydra the left grip with R2 climbs; in OVER
SHOULDER on foot the grips step through weapons; with tracked hands it grabs
the wheel and the holstered weapons. Nothing needed changing, so the bindings
check and the controls docs stay as they are.

## Build (Mac or Linux)

Use Python 3.10+, JDK 21, Android platform 35, build-tools 35.0.0, NDK
27.2.12479018 and CMake 3.22.1. The Frame package also needs the pinned
Apktool 3.0.3 JAR and Khronos OpenXR Android loader 1.1.43 for arm64. The
Frame helper `tools/build.sh` requires explicit paths to both files and
checks their SHA-256 hashes. For download and SDK setup commands, see the
[README build section](../README.md#build-the-frame-version).

Supply your own Google Play GTA San Andreas 2.11.311 ARM64 merged APK or a
supported split set. The PS2 audio pack is optional for Steam Frame; without
it, the game uses its own audio. Build the personal APK and payload:

```sh
/bin/bash tools/build.sh --steam-frame --package \
  --android-sdk "$ANDROID_HOME" --java-home "$JAVA_HOME" \
  --openxr-loader "/path/to/libopenxr_loader.so" \
  --apktool "/path/to/apktool_3.0.3.jar" \
  --build-dir "$PWD/.frame-build" \
  --game-package "/path/to/your/GTA-SA-2.11.311-ARM64.apk"
```

The result is `<build>/out/base.apk` plus `<build>/payload`. The native code
can be rebuilt alone by running `ninja` in `<build>/native`; changes to the
Java loader need a full build.

## Put it on the headset

```sh
export FRAME_HOST="steamos@YOUR_FRAME_ADDRESS"
tools/steam_frame/deploy.sh --apk "$PWD/.frame-build/out/base.apk" \
  --payload "$PWD/.frame-build/payload" --register-title --no-adb
```

That copies the game data into `~/Documents/GTASAVR` over SSH, then puts the
APK in a persistent **GTASAVR** title in the Steam library. Launch that
title to play. A game started over adb gets no controllers. You can also launch the title
from SSH by writing `steam://rungameid/<id>` into `~/.steam/steam.pipe`. The
id is `(appid << 32) | 0x02000000`, and the appid is in Steam's
`shortcuts.vdf`.

`FRAME_HOST` must name your own Frame SSH target, for example
`steamos@frame.local`. Do not copy a host value from another setup.

After the first launch, close the game and link its save folder into persistent
Documents storage:

```sh
tools/steam_frame/deploy.sh --no-adb --no-install --no-launch --link-saves
```

## Current limits

- A third-person 3D-screen view is not implemented; third-person play uses the over-the-shoulder camera.
- The retail game data is present in the APK and payload, so the installed game uses additional storage for the duplicate data.

## Wear feedback

**First wear (2026-10-03).** Menus fine, stereo gameplay ran. (Story cutscenes
in 3D cinema, subtitles and fades were added after it; they are what the
second wear looked at.)

**Second wear (2026-10-04).** Subtitles and the smooth cutscene fades work, and
an interior cutscene on the 3D cinema screen looks good. Problems:

1. In-engine cutscenes (the camera cutting to cinematic positions while you
   play) were first person with the hands flying around, the view jumped, and
   turning your head showed black frames flickering at the edges.
2. The HUD sat far below the hands and out of view; CLASSIC helped but was
   very jittery and rotated with head yaw.
3. No third-person view.
4. The 3D cinema subtitles sat on the image at the screen plane, which read as
   a different depth from the 3D picture.
5. Wish: the PS2 yellow/golden colour grade.

What was done about them (all "host build, not worn"):

1. In-engine cutscenes go to the 3D cinema screen, behind one hysteresis latch
   (above). The flicker most likely came from the head-locked frame: the
   runtime re-projects it to your head at display time, and a frame older than
   about 90 ms (a camera cut into a place that has to stream in, a busy
   scene) leaves a strip at the edge with nothing in it, and past three
   repeats or 90 ms the kit throws the pair away and shows a black view until
   two fresh ones arrive. The flat/stereo gate was also taking the raw
   letterbox flag, so a bar dropped for a frame sent the view to the flat
   screen and back. The cinema image is rebuilt from your live eye positions
   on every present and is exactly the screen rectangle, so there is no edge
   to expose, and a cinema frame is allowed to be 2.5 s old before it is
   dropped: a hitch freezes the picture instead of blacking it. This is
   inferred from the code, not seen on a headset.
2. FRONT PANEL HUD, default.
3. THIRD: OVER SHOULDER (3D SCREEN is not in, see above).
4. The black subtitle band under the cinema picture.
5. COLOUR FILTER PS2.

**Third person turning (after the second wear, host build, not worn).** The
view heading is the user's own snap/smooth turn yaw, so "relative to the
camera" means relative to that. What the stock mobile game does with it: the
engine's `CTaskSimplePlayerOnFoot::PlayerControlZelda` already sets the ped's
target heading to the stick direction minus `TheCamera.m_fOrientation` and
walks him forward at the stock turn rate. The kit writes the camera matrix and
calls `CalculateDerivedValues`, which sets that orientation from the view, and
the stick is rotated into the body frame (`forceBody`, also on the Java
provider path, which had skipped it), so CJ already turned to the stick
direction in OVER SHOULDER. The mobile build has no camera-pinned mode (the
`Process_FollowPedWithMouse` camera is never called), and while he aims the
stock aim stance (`PlayerControlZeldaWeapon`, `ControlGunMove`) strafes but
only turns toward a locked target, never to the view, so shots went along
whichever way he last faced. `ThirdPersonMove.cpp` hooks `PlayerControlZelda`,
`PlayerControlZeldaWeapon` and `CPed::CalculateNewVelocity` (prologue-checked;
without a match the stock turning stays): when the view should be faced
(aiming or firing a ranged weapon with the aim task up or the right trigger
held, or FACE CAMERA, and `CanStrafeOrMouseControl` says the ped state allows
it) it sets the ped's current and target heading to the view heading before
`CalculateNewVelocity`, and on the walking path rotates the animation's
desired move by the stick's heading minus the view heading. Log line:
`[view.os] character faces the view`.

**Third wear (2026-10-05).** Worn and good: the third-person camera now stays
locked to the player whichever way the character faces (the FACE MOVE work
above). Problems:

1. The laser dot was clipped to a half circle, with a dither where it met the
   menu.
2. The tutorial tooltips in the opening cutscenes weren't visible.
3. The subtitles sat about two dialogue lines too far under the cinema picture.
4. Question: is grip the handbrake? (It isn't, see above.)
5. Display: wanted 120 Hz at native resolution.

What was done (all "host build, not worn"): 1 to 4 are under "Round 3" above,
and 5 is "Display: 120 Hz and 2160 per eye". The first three need looking at
on the headset; the display one needs the per-app refresh set first (done).

Logs to look for: `[cutscene.scripted] scene on/off`, `[cinema3d] projection
screen ON/OFF`, `[cinema3d] anchor ... subtitle band`, `[hud.front] panel`,
`[view] mode`, `[view.os]` lines, `[ps2.colour]` and `[graphics.colourfilter]`,
`[hud.text]` (the `cinema subtitle` / `cinema help` rasters),
`[cinema3d] help box shown`, `[vr] refresh:`, `[vr] eye resolution` and `[vr] eye image`.


## Camera standard migration (2026-10-07; headset-unverified)

Fresh Frame settings use third person and snap 30 degrees. Smooth turning
(default speed 120 degrees/s, adjustable 30..360) and off remain available.
Explicit saved choices win; the persistent `defaults_profile=frame_personal`
selects smooth 120 and third person when Defaults is pressed.

LOCOMOTION → CAMERA SETTINGS uses the existing panel assets for a live camera
preview. Gameplay simulation pauses while VR settings are open; stereo keeps
showing the gameplay view with the current head pose and camera settings as
you adjust them. The yaw-only
panel anchors to the room, sits to the right by default, and shares its pose
with pointer hit testing. View recentres its anchor.

The new atomic `vr_camera.ini` stores world size (25..400%, represented as
0.25..4 native units/metre), signed `camera_closer` (-1..0.8), signed
`camera_lower` (-1..1), height (-1..1 metres), head movement (0..2), seated
mode, standing calibration, `settings_page_side=right|left|centre`, and
`defaults_profile=standard|frame_personal`. Native line tests constrain the
shown view while retaining requested camera values. Runtime eye positions
remain physical metres; game, hand, weapon, and inverse point conversions
use the same world scale. Existing settings and saves remain separate.

Hold physical left grip and use right stick: left/right shrinks/grows the
apparent world; up/down moves farther/higher or closer/lower. The stick is
consumed before game/turn input, with Menu/View priority and a neutral latch
after release or focus loss. Targeting, firing, two-hand grip contexts and
vehicles retain their actions. In first person the modifier is available in
the VR preview for scale only.

Verified locally: ARM64 native build and DEX build; supported Frame, Index
and Touch binding tables; existing production controls regression; actual
comfort adapter saved/default values, calibration, signed adjustment and
release/focus/menu behavior; actual native targeting queries, aim values,
context fallbacks, and the settings pause guard. The target hooks retain
the pinned 2.11.311 prologue checks and native fallback on mismatch.

No migrated APK has been signed or installed. The previous personal signing
key is absent from the build folder, and the Frame went offline. Wear
acceptance (live adjustment, panel readability, pause/resume, recentring,
aiming, and vehicle/first-person transitions) remains pending.

### Signing-key recovery and APK writer (2026-10-07)

The Steam library title uses Lepton's APK-hash rebake path. The installed launcher
compares the APK hash (`lepton:166-180`), clears only `compatdata/<appid>/baked`
(`liblepton.sh:64-76`, `baking.sh:27-36`), and reinstates the persistent
`internal/<package>` data link (`mounting.sh:502-513,629-635`). A newly generated
personal key can therefore update this title through Steam. This exception does
not apply to `adb install -r` in an existing Quest/development container. Keep keys
under `~/.local/share/gtasavr-builder/signing`, outside disposable build output;
back up saves/settings and verify launch/data retention after replacement.

The streaming APK writer now retains known entry sizes, strips source ZIP64
size/offset fields and writes classic unsigned 32-bit ZIP headers. This avoids
forced ZIP64 local headers and Python's unnecessary 2 GiB offset conversion,
which caused Android zipalign to reject a valid 2.6 GiB retail APK rewrite.
`tools/test-apk-assembly.py` exercises the production copier, preserved contents,
local/central headers, Android zipalign and the platform-specific signer guard.

## Camera migration Steam delivery (2026-10-07)

The camera source is `e7e8cb2ae8413412ba561689f8b014fd16dce484`; packaging-only
repair `313999d742bc3f21c891a3e4bfd74e0d6011729d` handles classic ZIP headers and
the verified Steam-title rebake route. The locally signed/aligned ARM64 APK
preserves all 1,187 unchanged non-signature payload entries, including the
original manifest and retail libGame.so; all 11 intended replacements match
the built inputs.

Installed `~/devkit-game/GTASAVR/GTASA-VR.apk` SHA-256:
`ec095a4a404348fcd3b2b31c52b3e5e58abd74e64ad4584a0d1e67946c8bf43d`.
After booking and an idle launch gate, the existing Steam title (raw app ID
3627321462) ran for 60 seconds through normal Lepton, without adb installation.
The new certificate worked; the log confirms 2160x2160 eye targets, 120 Hz,
Frame/Index/Touch profile suggestions accepted (27/18/21 bindings), session
READY/SYNCHRONIZED, and game frames. Only the task's container was stopped.
Documents configuration and all saves retain their pre-run hashes and modes.

The old key's loss is not evidence of a deleted cache's cause. A regenerated
build cannot recreate that key, but same-certificate Android in-place update
rules are not the normal Frame rebake route. The installed Lepton launcher was
inspected first: APK hash changes clear baked package state while retaining and
relinking persistent internal data. The builder now stores its key outside
disposable build output. No credential is in the package evidence.

| Current increment | Evidence level |
| --- | --- |
| ARM64 package, new-signer Steam rebake, game frames and data retention | verified unattended |
| Live paused camera preview, physical modifier/remaps, tracked recentring and comfort | not worn; preview not captured |

Wear checks: live settings and grip/right-stick adjustments; neutral release;
right-side panel; pause/resume/recentre; LT target, RT fire and owned-weapon
cycling on bumpers; first-person actions and vehicle transitions. Evidence:
task output `device-camera-migration/GTASAVR/lepton-steamlaunch.log` and the
cross-port report. This smoke run does not certify physical controls or visuals.
