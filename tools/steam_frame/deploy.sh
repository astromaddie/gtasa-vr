#!/usr/bin/env bash
# Install, launch and feed GTA San Andreas VR on a Valve Steam Frame (Android in
# the Lepton container) from a Mac or Linux host. See docs/STEAM_FRAME.md.
#
#   tools/steam_frame/deploy.sh [options]
#
#   --apk FILE         the Frame build's single APK (built with
#                      tools/build.sh --steam-frame)
#   --payload DIR      the build's payload directory (data_main/, audio/,
#                      vrhands/ ...): copied to the headset's
#                      ~/Documents/GTASAVR (data_main -> data_main/, the rest
#                      -> files/) with rsync over SSH. Several GB the first
#                      time; later runs copy only what changed.
#   --register-title   register ~/devkit-game/GTASAVR as a persistent Steam
#                      library title (once). When the title exists, every
#                      install also refreshes its copy of the APK.
#   --link-saves       point the game's own save folder (Android app storage,
#                      which lives in the title's compatdata and goes with a
#                      Lepton reset) at ~/Documents/GTASAVR/saves. Needs one
#                      launch of the title first so the folder exists; run it
#                      with the game closed. Existing files are copied over and
#                      the old folder is kept as files.orig-<time>.
#   --no-install       skip adb install
#   --no-launch        skip starting the game over adb
#   --logcat SECONDS   after launching, capture SECONDS of log into
#                      scratchpad/frame-logcat.txt and print the key lines
#   --no-adb           only SSH steps (payload, title); no Lepton Development
#
# Environment:
#   FRAME_HOST       required SSH target, for example steamos@frame.local
#   FRAME_ADB_HOST   adb host (default: the host part of FRAME_HOST). Lepton
#                    Development publishes its adbd on <host>:5555
#   ADB              adb binary
#
# adb needs "Lepton Development" running (start it from the Frame's Steam
# library); it deletes its apps when it exits. ~/Documents/GTASAVR and the
# persistent Steam title survive. A game started by adb gets no controllers
# and no focus from SteamVR: use it for logs, and launch the GTASAVR title from
# the Steam library to play.
#
# Before any unattended run (--logcat), make sure nobody is wearing the
# headset: a launch replaces whatever they are playing.
set -euo pipefail

kit="$(cd "$(dirname "$0")/../.." && pwd)"
package="com.rockstargames.gtasa"
activity="com.rockstargames.gtasa.GameActivity"
title="GTASAVR"                  # Steam devkit titles must be alphanumeric
title_apk="GTASA-VR.apk"         # fixed name: the title's argv stays valid across builds
data="Documents/GTASAVR"         # relative to the Frame user's home; /sdcard/Documents/GTASAVR in Lepton

frame_host="${FRAME_HOST:-}"
adb_host="${FRAME_ADB_HOST:-${frame_host#*@}}"
adb_bin="${ADB:-${ANDROID_HOME:-$HOME/Library/Android/sdk}/platform-tools/adb}"
[[ -x "$adb_bin" ]] || adb_bin="$(command -v adb || true)"
apk=""
payload=""
register=0
link_saves=0
install=1
launch=1
use_adb=1
logcat_seconds=0

die() { echo "deploy.sh: $*" >&2; exit 1; }

while (($#)); do
	case "$1" in
	--apk) apk="$2"; shift 2 ;;
	--payload) payload="$2"; shift 2 ;;
	--register-title) register=1; shift ;;
	--link-saves) link_saves=1; shift ;;
	--no-install) install=0; shift ;;
	--no-launch) launch=0; shift ;;
	--logcat) logcat_seconds="$2"; shift 2 ;;
	--no-adb) use_adb=0; shift ;;
	-h|--help) sed -n '2,/^set -euo/p' "$0" | sed '$d'; exit 0 ;;
	*) die "unknown option $1" ;;
	esac
done
[[ -n "$frame_host" ]] || die 'set FRAME_HOST to steamos@<your-frame-host>'

ssh_frame() { ssh -o ConnectTimeout=10 -o BatchMode=yes "$frame_host" "$@"; }
# The app inside Lepton runs as its own Android user: everything it must read
# or write in the shared folder is made world-readable and -writable.
rsync_frame() { rsync -rt --chmod=Du=rwx,Dgo=rwx,Fu=rw,Fgo=rw "$@"; }

# ---- Payload: persistent storage on the Frame host ---------------------------
if [[ -n "$payload" ]]; then
	[[ -d "$payload" ]] || die "no such payload directory: $payload"
	ssh_frame "mkdir -p ~/$data/files ~/$data/data_main && chmod 777 ~/$data ~/$data/files ~/$data/data_main"
	for tree in "$payload"/*; do
		[[ -d "$tree" ]] || continue
		name="$(basename "$tree")"
		if [[ "$name" == data_main ]]; then
			dest="$data/data_main/"
		else
			dest="$data/files/$name/"
		fi
		echo "copying $name -> ~/$dest"
		rsync_frame "$tree/" "$frame_host:$dest"
	done
	echo "payload in ~/$data (/sdcard/Documents/GTASAVR inside Lepton)"
fi

if ((install || register)); then
	[[ -n "$apk" && -f "$apk" ]] || die "no APK (pass --apk; build it with tools/build.sh --steam-frame)"
fi

# ---- Persistent Steam title --------------------------------------------------
title_exists=0
ssh_frame "test -d ~/devkit-game/$title" 2>/dev/null && title_exists=1
if ((register || (title_exists && install))); then
	ssh_frame "mkdir -p ~/devkit-game/$title"
	rsync -t --progress "$apk" "$frame_host:devkit-game/$title/$title_apk"
	echo "copied the APK into ~/devkit-game/$title/$title_apk"
fi
if ((register)); then
	parms="{\"gameid\": \"$title\", \"directory\": \"/home/steamos/devkit-game/$title\", \"force_appid\": \"\", \"argv\": [\"$title_apk\"], \"env\": {}, \"settings\": {\"steam_play\": \"1\", \"compat_tool\": \"lepton\"}, \"lepton_args\": \"\"}"
	# needs the Steam client running on the Frame; it answers with success or an error
	ssh_frame "cd ~/devkit-utils && python3 steam-client-create-shortcut --parms '$parms'"
fi

# ---- Saves into Documents ----------------------------------------------------
# Inside Lepton the app's external files dir is a FUSE view of the title's
# compatdata on the host, and the container mounts ~/Documents at the same
# absolute path, so a host-side symlink is followed from inside the game.
if ((link_saves)); then
	appid="$(ssh_frame "python3 - <<'PY'
import glob, re, struct
for f in glob.glob('/home/steamos/.local/share/Steam/userdata/*/config/shortcuts.vdf'):
    d = open(f, 'rb').read()
    for m in re.finditer(rb'\\x02appid\\x00(....)', d, re.I | re.S):
        n = re.search(rb'\\x01appname\\x00([^\\x00]*)\\x00', d[m.end():m.end() + 300], re.I)
        if n and n.group(1).endswith(b'$title'):
            print(struct.unpack('<I', m.group(1))[0])
PY")"
	[[ -n "$appid" ]] || die "no Steam shortcut for $title (register it with --register-title)"
	ssh_frame "set -e
		F=~/.local/share/Steam/steamapps/compatdata/$appid/external/Android/data/$package/files
		S=~/$data/saves
		[ -e \"\$F\" ] || { echo 'launch $title once first, so its save folder exists' >&2; exit 1; }
		mkdir -p \"\$S\"
		if [ ! -L \"\$F\" ]; then
			cp -a \"\$F/.\" \"\$S/\"
			mv \"\$F\" \"\$F.orig-\$(date +%s)\"
			ln -s \"\$S\" \"\$F\"
		fi
		chmod 777 \"\$S\"; chmod 666 \"\$S\"/* 2>/dev/null || true
		ls -la \"\$F\""
	echo "saves now in ~/$data/saves"
fi

((use_adb)) || exit 0
[[ -n "$adb_bin" && -x "$adb_bin" ]] || die "adb not found; set ADB"

# ---- Lepton Development over network adb --------------------------------------
"$adb_bin" start-server >/dev/null
for attempt in 1 2 3 4 5; do
	"$adb_bin" connect "$adb_host:5555" >/dev/null 2>&1 || true
	if "$adb_bin" -s "$adb_host:5555" shell true 2>/dev/null; then break; fi
	sleep $((attempt * 2))
	if ((attempt == 5)); then
		die 'cannot reach Lepton Development at '"$adb_host"':5555. Start "Lepton Development" from the Frame'"'"'s Steam library.'
	fi
done
device="$adb_host:5555"
adb() { "$adb_bin" -s "$device" "$@"; }

if ((install)); then
	adb install -r -g "$apk" | grep -i -E 'success|fail|error' || true
	adb shell appops set "$package" MANAGE_EXTERNAL_STORAGE allow >/dev/null 2>&1 || true
fi

if ((launch)); then
	adb shell am force-stop "$package"
	adb logcat -c
	adb shell am start -n "$package/$activity" >/dev/null
	echo "started $package; follow it with: $adb_bin -s $device logcat"
fi

if ((logcat_seconds > 0)); then
	out="$kit/scratchpad/frame-logcat.txt"
	mkdir -p "$(dirname "$out")"
	("$adb_bin" -s "$device" logcat -v time >"$out" & pid=$!; sleep "$logcat_seconds"; kill "$pid") 2>/dev/null || true
	echo "log: $out"
	grep -E "savr-frame|\[stereo\]|\[perf\.|OpenXR|xrCreate|session|Session|swapchain|interaction profile|FATAL|SIGSEGV|SIGILL|SIGBUS|abort|mprotect|denied" "$out" | head -80 || true
fi
