#!/usr/bin/env python3
"""Locally assemble a personal Steam Frame install from a public native kit.

The game APK and aircraft HLOD are player-provided inputs. This tool writes
the personalized APK and game-data payload only to the selected local build
directory; those outputs must not be redistributed.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(command: list[str]) -> None:
    print("==>", " ".join(command), flush=True)
    result = subprocess.run(command)
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-package", required=True, help="your GTA SA 2.11.311 APK or complete APK set")
    parser.add_argument("--release-kit", default=str(Path(__file__).resolve().parents[1]), help="extracted public release kit directory")
    parser.add_argument("--build-dir", required=True, help="dedicated local scratch directory for APKs, HLOD and signing material")
    parser.add_argument("--output-dir", help="personal patched APK output (inside --build-dir)")
    parser.add_argument("--payload-dir", help="personal game-data payload output (inside --build-dir)")
    parser.add_argument("--sdk")
    parser.add_argument("--java-home")
    parser.add_argument("--apktool")
    parser.add_argument("--keystore")
    parser.add_argument("--allow-unofficial-source", action="store_true", help="allow an unofficial signer; the retail libGame.so hash is still verified")
    args = parser.parse_args()

    kit = Path(args.release_kit).expanduser().resolve()
    game = Path(args.game_package).expanduser().resolve()
    build = Path(args.build_dir).expanduser().resolve()
    assemble = kit / "tools" / "assemble.py"
    required = (
        assemble,
        kit / "tools" / "build_aircraft_hlod.py",
        kit / "defaults" / "quest" / "vr_driving.ini",
        kit / "assets" / "vrhands" / "SOURCE.md",
        kit / "tools" / "vendor" / "apktool_3.0.3.jar",
        kit / "lib" / "arm64-v8a" / "libsavr.so",
        kit / "lib" / "arm64-v8a" / "libopenxr_loader.so",
        kit / "classes.dex",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("release kit is incomplete:\n  " + "\n  ".join(missing))
    if not game.is_file() and not game.is_dir():
        raise SystemExit(f"game package does not exist: {game}")

    output = Path(args.output_dir).expanduser().resolve() if args.output_dir else build / "personal-apks"
    payload = Path(args.payload_dir).expanduser().resolve() if args.payload_dir else build / "personal-payload"
    common = [
        sys.executable,
        str(assemble),
        "--game-package", str(game),
        "--steam-frame",
        "--build-dir", str(build),
        "--output-dir", str(output),
        "--payload-dir", str(payload),
        "--native-lib", str(kit / "lib" / "arm64-v8a" / "libsavr.so"),
        "--loader-dex", str(kit / "classes.dex"),
        "--openxr-loader", str(kit / "lib" / "arm64-v8a" / "libopenxr_loader.so"),
        "--apktool", args.apktool or str(kit / "tools" / "vendor" / "apktool_3.0.3.jar"),
    ]
    if args.sdk:
        common += ["--sdk", args.sdk]
    if args.java_home:
        common += ["--java-home", args.java_home]
    if args.keystore:
        common += ["--keystore", args.keystore]
    if args.allow_unofficial_source:
        common.append("--allow-unofficial-source")

    # The validation pass extracts only the supported aircraft texture input
    # to local scratch and runs the source-kit HLOD generator. Its output is
    # consumed by the assembly pass and staged outside the redistributable kit.
    run(common + ["--validate-only"])
    hlod = build / "aircraft-hlod-global" / "aircraft.hlod"
    if not hlod.is_file() or hlod.stat().st_size == 0:
        raise SystemExit(f"local aircraft HLOD generation failed: {hlod}")
    run(common + ["--runtime-hlod", str(hlod)])
    print(f"Personal APK(s): {output}")
    print(f"Player-owned payload: {payload}")
    print("Keep both outputs private; they contain data derived from your retail game copy.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FileNotFoundError as error:
        raise SystemExit(f"required command or file not found: {error}")
