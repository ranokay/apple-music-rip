#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from typing import Optional


def normalize_ext(ext: str) -> str:
    ext = ext.strip().lower()
    if not ext:
        return ""
    if not ext.startswith("."):
        ext = "." + ext
    return ext


def iter_media_files(root: str, extensions: tuple[str, ...]):
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(extensions):
                yield os.path.join(dirpath, name)


def probe_duration_seconds(
    ffprobe_path: str,
    path: str,
) -> tuple[bool, Optional[float], str]:
    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nw=1:nk=1",
        path,
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    if result.returncode != 0:
        message = stderr if stderr else stdout
        return False, None, message or "ffprobe failed"
    if not stdout:
        return False, None, "ffprobe returned empty duration"
    first = stdout.splitlines()[0].strip()
    try:
        return True, float(first), ""
    except ValueError:
        return False, None, f"ffprobe returned non-numeric duration: {first}"


def validate_file(
    ffmpeg_path: str,
    ffprobe_path: str,
    path: str,
    min_duration: float,
) -> tuple[bool, str]:
    cmd = [
        ffmpeg_path,
        "-v",
        "error",
        "-xerror",
        "-err_detect",
        "explode",
        "-i",
        path,
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    message = stderr if stderr else stdout
    if result.returncode == 0 and not message:
        if min_duration > 0:
            ok, duration, probe_msg = probe_duration_seconds(ffprobe_path, path)
            if not ok:
                return False, f"duration check failed: {probe_msg}"
            if duration is not None and duration < min_duration:
                return (
                    False,
                    f"duration too short: {duration:.2f}s < {min_duration:.2f}s",
                )
        return True, ""
    return False, message


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate downloaded audio files using ffmpeg.",
    )
    parser.add_argument(
        "--root",
        default="downloads/alac",
        help="Root folder to scan (default: downloads/alac).",
    )
    parser.add_argument(
        "--ext",
        action="append",
        default=[".m4a"],
        help="File extension to validate (repeatable; default: .m4a).",
    )
    parser.add_argument(
        "--ffmpeg",
        default="ffmpeg",
        help="Path to ffmpeg binary (default: ffmpeg).",
    )
    parser.add_argument(
        "--ffprobe",
        default="",
        help="Path to ffprobe binary (default: auto from ffmpeg or 'ffprobe').",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=20.0,
        help="Fail if duration (seconds) is below this value (0 to disable).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of files to validate (0 = no limit).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print failures and summary.",
    )
    args = parser.parse_args()

    ffmpeg_path = args.ffmpeg
    if not shutil.which(ffmpeg_path):
        print(f"ffmpeg not found: {ffmpeg_path}", file=sys.stderr)
        return 2

    ffprobe_path = args.ffprobe
    if not ffprobe_path:
        if ffmpeg_path != "ffmpeg":
            candidate = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe")
            if shutil.which(candidate):
                ffprobe_path = candidate
        if not ffprobe_path:
            ffprobe_path = "ffprobe"
    if args.min_duration > 0 and not shutil.which(ffprobe_path):
        print(f"ffprobe not found: {ffprobe_path}", file=sys.stderr)
        return 2

    root = args.root
    if not os.path.isdir(root):
        print(f"Root folder not found: {root}", file=sys.stderr)
        return 2

    extensions = tuple(ext for ext in (normalize_ext(e) for e in args.ext) if ext)
    if not extensions:
        print("No valid extensions provided.", file=sys.stderr)
        return 2

    total = 0
    failures = 0

    for path in iter_media_files(root, extensions):
        total += 1
        ok, message = validate_file(
            ffmpeg_path,
            ffprobe_path,
            path,
            args.min_duration,
        )
        if not ok:
            failures += 1
            print(f"FAIL: {path}")
            if message:
                first_line = message.splitlines()[0]
                print(f"  {first_line}")
        elif not args.quiet:
            print(f"OK: {path}")

        if args.limit > 0 and total >= args.limit:
            break

    print(f"Checked {total} file(s). Failures: {failures}.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
