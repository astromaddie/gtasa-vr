# GTA San Andreas VR on the Steam Frame

This branch runs the Quest kit on the Valve Steam Frame. The Frame runs
Android apps inside a container called Lepton, on top of SteamVR's OpenXR
runtime. The game itself is unchanged: it's the same Google Play build
(2.11.311) with the same VR layer. What's different is how it's packaged,
where its files live and how the controllers map.

Status: it has been worn twice (2026-10-03 and 2026-10-04, see "Wear
feedback" at the end). Menus, story cutscenes in 3D cinema, subtitles and
fades work. The changes made after the second wear build on the host and
have not been worn yet.

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
  hands buzz). A short View press is back in the VR menu, and in play (no menu
  open, no cutscene) it switches between first person and over the shoulder.
  Clicking both sticks no longer recentres.
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
  image at a different depth.
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

**Views.** LOCOMOTION, VIEW (the first row), or a short press of the left View
button in play:

- **FIRST PERSON** is the normal view: you are in CJ's head, the controllers
  are his hands and you hold the guns.
- **THIRD: OVER SHOULDER** is a stereo view from behind CJ, with head
  tracking and a level horizon. The camera only turns when you turn, with the
  snap or smooth turn from the right stick. It sits at the distance and height
  of the game's own chase camera, a little to the right of him, and a line
  test from his head pulls it in at walls. CJ's body is drawn, your hands and
  the tracked guns are not. Controls are pad-style: the left stick walks
  relative to the view heading (whatever MOVE DIRECTION says), the right
  trigger fires the weapon CJ has equipped, the grips step through his weapons
  (left previous, right next), and the A/B/X/Y bindings are the usual ones.
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

Host build, not worn. Three rules shared with the other Steam Frame ports.

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
setting yet, so these are unscaled). The dot and beam face the head about world
up, so they do not roll.

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

What to look at on the headset: the beam above the VR menu, above the 3D cinema
and above the flat pause menu; the dot landing on the right row; clicking rows,
the side zones and the sliders; tilting your head while looking at a street
lamp, a wet road or through a scope.

## Build (Mac or Linux)

You need the merged game APK, the PS2 audio pack (extracted is fine), an
Android SDK with NDK 27.2, a JDK, apktool 3.0.3, and the Khronos OpenXR
loader `.so` (`build-and-install.sh` normally fetches the last two). Run the
validation step first, because it also generates the aircraft LOD data the
native build needs:

```sh
python3 tools/assemble.py --validate-only --steam-frame --allow-unofficial-source \
  --game-package <merged.apk> --audio-source <audio dir or .7z> \
  --build-dir <build> --sdk <sdk> --java-home <jdk> --apktool <apktool.jar>

/bin/bash tools/build.sh --package --steam-frame --allow-unofficial-source \
  --android-sdk <sdk> --java-home <jdk> --openxr-loader <libopenxr_loader.so> \
  --apktool <apktool.jar> --build-dir <build> \
  --game-package <merged.apk> --audio-source <audio dir or .7z>
```

You get `<build>/out/base.apk` (about 1.4 GB) and `<build>/payload` (about
2.5 GB). Keep at least 8 GB free while it builds.

## Put it on the headset

```sh
tools/steam_frame/deploy.sh --apk <build>/out/base.apk \
  --payload <build>/payload --register-title --no-adb
```

That copies the game data into `~/Documents/GTASAVR` over SSH, then puts the
APK in a persistent **GTASAVR** title in the Steam library. Launch that
title to play. A game started over adb gets no controllers. You can also launch the title
from SSH by writing `steam://rungameid/<id>` into `~/.steam/steam.pipe`. The
id is `(appid << 32) | 0x02000000`, and the appid is in Steam's
`shortcuts.vdf`.

`FRAME_HOST` picks the SSH target. The default is the Frame on Wi-Fi,
`steamos@192.168.1.31`.

## Known gaps

- The game's own saves go to its app storage. On the Frame that's a folder
  in the title's compatdata, which a Lepton reset can take with it. Run
  `deploy.sh --link-saves` once, after the first launch and with the game
  closed, to point that folder at `~/Documents/GTASAVR/saves`. The game
  sees the link fine. Whether it writes saves through it is still to be
  confirmed with a real save.
- The game data is in the APK and in `data_main`, so it takes up space
  twice.
- Bumpers and the D-pad aren't bound yet.
- What's been checked on the Frame (no one in the headset, 2026-10-03):
  - The title installs and launches from Steam.
  - The hooks patch the game fine.
  - OpenXR comes up on SteamVR's GLES path with an sRGB swapchain.
  - All three controller profiles are accepted.
  - Data, PS2 audio and settings load from `~/Documents/GTASAVR`.
  - The menus present at 72 fps with no failed frames.
- Stereo gameplay has now been worn twice (see below).

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

Logs to look for: `[cutscene.scripted] scene on/off`, `[cinema3d] projection
screen ON/OFF`, `[cinema3d] anchor ... subtitle band`, `[hud.front] panel`,
`[view] mode`, `[view.os]` lines, `[ps2.colour]` and `[graphics.colourfilter]`.
