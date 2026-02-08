#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

DEFAULT_EXTENSIONS = [".flac", ".m4a"]
DEFAULT_ROOTS = ["uploaded", "downloads"]
AMPERSAND_SPLIT_RE = re.compile(r"\s+&\s+")


@dataclass(frozen=True)
class FileChange:
    path: Path
    ext: str
    composer_before: str
    composer_after: str
    sort_composer_before: str
    sort_composer_after: str

    @property
    def composer_changed(self) -> bool:
        return self.composer_before != self.composer_after

    @property
    def sort_composer_changed(self) -> bool:
        return self.sort_composer_before != self.sort_composer_after


def normalize_ext(value: str) -> str:
    ext = value.strip().lower()
    if not ext:
        return ""
    if not ext.startswith("."):
        ext = f".{ext}"
    return ext


def run_command(cmd: Sequence[str]) -> Tuple[int, str, str]:
    result = subprocess.run(
        list(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def iter_audio_files(roots: Sequence[Path], extensions: Set[str]) -> Iterable[Path]:
    seen: Set[Path] = set()
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                if Path(name).suffix.lower() not in extensions:
                    continue
                path = (Path(dirpath) / name).resolve()
                if path in seen:
                    continue
                seen.add(path)
                yield path


def read_ffprobe_tags(ffprobe_path: str, file_path: Path) -> Optional[Dict[str, str]]:
    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format_tags",
        "-of",
        "default=nw=1",
        str(file_path),
    ]
    code, stdout, stderr = run_command(cmd)
    if code != 0:
        msg = stderr.strip() or stdout.strip() or "ffprobe failed"
        print(f"WARN: failed to read tags for {file_path}: {msg}")
        return None

    tags: Dict[str, str] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = line.removeprefix("TAG:")
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        k = key.strip().lower()
        v = value.strip()
        if not k:
            continue
        if k not in tags:
            tags[k] = v
    return tags


def pick_first(tags: Dict[str, str], *keys: str) -> str:
    for key in keys:
        value = tags.get(key, "").strip()
        if value:
            return value
    return ""


def normalize_composer_ampersand(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    text = AMPERSAND_SPLIT_RE.sub(", ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    parts = [part.strip() for part in text.split(",") if part.strip()]
    return ", ".join(parts)


def build_change(path: Path, tags: Dict[str, str]) -> Optional[FileChange]:
    composer_before = pick_first(tags, "composer")
    sort_before = pick_first(tags, "sort_composer", "composersort")

    composer_after = normalize_composer_ampersand(composer_before)
    sort_after = normalize_composer_ampersand(sort_before)

    if composer_before == composer_after and sort_before == sort_after:
        return None

    return FileChange(
        path=path,
        ext=path.suffix.lower(),
        composer_before=composer_before,
        composer_after=composer_after,
        sort_composer_before=sort_before,
        sort_composer_after=sort_after,
    )


def preview_value(value: str) -> str:
    if not value:
        return "<empty>"
    return value.replace("\n", "\\n")


def print_change(idx: int, change: FileChange) -> None:
    print(f"[{idx}] {change.path}")
    if change.composer_changed:
        print("  composer:")
        print(f"    - {preview_value(change.composer_before)}")
        print(f"    + {preview_value(change.composer_after)}")
    if change.sort_composer_changed:
        print("  sort_composer:")
        print(f"    - {preview_value(change.sort_composer_before)}")
        print(f"    + {preview_value(change.sort_composer_after)}")
    print()


def parse_selection(expr: str, total: int) -> Set[int]:
    raw = expr.strip().lower()
    if raw in {"all", "a", "*"}:
        return set(range(total))
    if raw in {"none", "n", ""}:
        return set()

    selected: Set[int] = set()
    for token in raw.split(","):
        part = token.strip()
        if not part:
            continue
        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start = int(start_raw)
            end = int(end_raw)
            if start > end:
                start, end = end, start
            if start < 1 or end > total:
                raise ValueError(f"range out of bounds: {part}")
            for idx in range(start, end + 1):
                selected.add(idx - 1)
            continue

        idx = int(part)
        if idx < 1 or idx > total:
            raise ValueError(f"index out of bounds: {part}")
        selected.add(idx - 1)

    return selected


def prompt_selection(total: int) -> Set[int]:
    print("Selection mode enabled.")
    print("Enter file indexes (example: 1,3,5-8), or 'all', or 'none'.")
    while True:
        try:
            raw = input("> ").strip()
        except EOFError:
            return set()
        try:
            return parse_selection(raw, total)
        except Exception as exc:
            print(f"Invalid selection: {exc}")


def apply_flac_change(metaflac_path: str, change: FileChange) -> Tuple[bool, str]:
    args: List[str] = [metaflac_path, "--dont-use-padding"]

    if change.composer_changed:
        args.append("--remove-tag=COMPOSER")
        args.append(f"--set-tag=COMPOSER={change.composer_after}")

    if change.sort_composer_changed:
        args.append("--remove-tag=COMPOSERSORT")
        args.append("--remove-tag=sort_composer")
        args.append(f"--set-tag=COMPOSERSORT={change.sort_composer_after}")
        args.append(f"--set-tag=sort_composer={change.sort_composer_after}")

    args.append(str(change.path))
    code, _, stderr = run_command(args)
    if code != 0:
        return False, stderr.strip() or "metaflac failed"
    return True, ""


def apply_m4a_change(exiftool_path: str, change: FileChange) -> Tuple[bool, str]:
    args: List[str] = [exiftool_path, "-overwrite_original"]

    if change.composer_changed:
        args.append(f"-Composer={change.composer_after}")
    if change.sort_composer_changed:
        args.append(f"-SortComposer={change.sort_composer_after}")

    args.append(str(change.path))
    code, stdout, stderr = run_command(args)
    if code != 0:
        return False, stderr.strip() or stdout.strip() or "exiftool failed"
    return True, ""


def resolve_roots(raw_roots: Sequence[str]) -> List[Path]:
    if raw_roots:
        return [Path(p).expanduser().resolve() for p in raw_roots]
    inferred = []
    for path in DEFAULT_ROOTS:
        p = Path(path).resolve()
        if p.exists() and p.is_dir():
            inferred.append(p)
    if inferred:
        return inferred
    return [Path(".").resolve()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize composer separators by replacing ' & ' with ', ' in "
            "composer and sort_composer tags."
        ),
    )
    parser.add_argument(
        "roots",
        nargs="*",
        help=(
            "Root folders to scan. Defaults to existing 'uploaded'/'downloads' "
            "folders (or current directory if neither exists)."
        ),
    )
    parser.add_argument(
        "--ext",
        action="append",
        default=list(DEFAULT_EXTENSIONS),
        help="Extensions to scan (repeatable). Default: .flac and .m4a",
    )
    parser.add_argument(
        "--ffprobe",
        default="ffprobe",
        help="Path to ffprobe binary (default: ffprobe).",
    )
    parser.add_argument(
        "--metaflac",
        default="metaflac",
        help="Path to metaflac binary for FLAC writes (default: metaflac).",
    )
    parser.add_argument(
        "--exiftool",
        default="exiftool",
        help="Path to exiftool binary for M4A writes (default: exiftool).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to files. Without this flag the script runs as dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only (default behavior).",
    )
    parser.add_argument(
        "--select",
        action="store_true",
        help="Interactively select which candidate files to apply.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of files to inspect (0 = no limit).",
    )
    args = parser.parse_args()

    dry_run = args.dry_run or not args.apply

    if not shutil.which(args.ffprobe):
        print(f"ffprobe not found: {args.ffprobe}", file=sys.stderr)
        return 2

    roots = resolve_roots(args.roots)
    exts = {normalize_ext(ext) for ext in args.ext if normalize_ext(ext)}
    if not exts:
        print("No valid extensions provided.", file=sys.stderr)
        return 2

    print("Scan roots:")
    for root in roots:
        print(f"  - {root}")
    print(f"Extensions: {', '.join(sorted(exts))}")
    print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    print()

    scanned = 0
    read_errors = 0
    changes: List[FileChange] = []

    for path in iter_audio_files(roots, exts):
        scanned += 1
        tags = read_ffprobe_tags(args.ffprobe, path)
        if tags is None:
            read_errors += 1
            continue
        change = build_change(path, tags)
        if change is not None:
            changes.append(change)
        if args.limit > 0 and scanned >= args.limit:
            break

    changes.sort(key=lambda item: str(item.path))

    print(f"Audio files scanned: {scanned}")
    print(f"Tag read failures:   {read_errors}")
    print(f"Candidate changes:   {len(changes)}")
    print()

    if not changes:
        print("No composer/sort_composer values need changes.")
        return 0

    for idx, change in enumerate(changes, start=1):
        print_change(idx, change)

    if args.select:
        if not sys.stdin.isatty():
            print("--select requires an interactive terminal.", file=sys.stderr)
            return 2
        selected_idxs = prompt_selection(len(changes))
    else:
        selected_idxs = set(range(len(changes)))

    selected = [changes[idx] for idx in sorted(selected_idxs)]
    print(f"Selected files: {len(selected)}")
    if dry_run:
        print("Dry-run only. No files were modified.")
        return 0

    if not selected:
        print("Nothing selected. No files modified.")
        return 0

    need_flac = any(change.ext == ".flac" for change in selected)
    need_m4a = any(change.ext == ".m4a" for change in selected)

    if need_flac and not shutil.which(args.metaflac):
        print(f"metaflac not found: {args.metaflac}", file=sys.stderr)
        return 2
    if need_m4a and not shutil.which(args.exiftool):
        print(f"exiftool not found: {args.exiftool}", file=sys.stderr)
        return 2

    ok_count = 0
    fail_count = 0

    for change in selected:
        if change.ext == ".flac":
            ok, err = apply_flac_change(args.metaflac, change)
        elif change.ext == ".m4a":
            ok, err = apply_m4a_change(args.exiftool, change)
        else:
            ok, err = False, f"unsupported extension: {change.ext}"

        if ok:
            ok_count += 1
            print(f"OK   {change.path}")
        else:
            fail_count += 1
            print(f"FAIL {change.path}")
            print(f"     {err}")

    print()
    print(f"Applied: {ok_count}")
    print(f"Failed:  {fail_count}")
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
