#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

AUDIO_EXTS = {".flac", ".m4a"}
LYRICS_EXT = ".ttml"
COVER_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Language markers (expanded; we normalize "JP Ver." => "japanese")
LANG_TOKENS = {
    "japanese": ["jp", "jpn", "japan", "japanese"],
    "korean": ["kr", "kor", "korea", "korean"],
    "english": ["en", "eng", "english"],
    "chinese": ["cn", "chn", "china", "chinese", "mandarin", "cantonese"],
    "spanish": ["es", "spanish", "espanol", "español"],
    "portuguese": ["pt", "portuguese"],
    "french": ["fr", "french"],
    "german": ["de", "german"],
    "italian": ["it", "italian"],
    "russian": ["ru", "russian"],
}

# Edition markers we should keep separate (not part of "language", but important)
EDITION_PATTERNS = [
    r"\bacoustic\b",
    r"\blive\b",
    r"\bremix\b",
    r"\binstrumental\b",
    r"\bk(a|á)raoke\b",
    r"\bdemo\b",
    r"\bedit\b",
    r"\bradio edit\b",
    r"\bextended\b",
]

TITLE_CLEAN_RE = re.compile(r"[\u200b\u200c\u200d\uFEFF]")  # zero-width junk


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Map the "normal" colors to BRIGHT variants for higher contrast
    BLACK = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    # Map the "bright" colors to vivid 256-color values (more noticeable on macOS terminals)
    BRIGHT_BLACK = "\033[38;5;240m"
    BRIGHT_RED = "\033[38;5;196m"
    BRIGHT_GREEN = "\033[38;5;46m"
    BRIGHT_YELLOW = "\033[38;5;226m"
    BRIGHT_BLUE = "\033[38;5;27m"
    BRIGHT_MAGENTA = "\033[38;5;201m"
    BRIGHT_CYAN = "\033[38;5;51m"
    BRIGHT_WHITE = "\033[38;5;15m"


def supports_color(force: bool = False) -> bool:
    if force:
        return True
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    term = os.environ.get("TERM", "")
    if term in ("dumb", ""):
        return False
    return True


def colorize(enabled: bool, s: str, *codes: str) -> str:
    if not enabled or not codes:
        return s
    return "".join(codes) + s + C.RESET


def run_mediainfo_json(path: Path) -> Dict[str, Any]:
    proc = subprocess.run(
        ["mediainfo", "--Output=JSON", str(path)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"mediainfo failed for {path}:\n{proc.stderr.strip()}")
    return json.loads(proc.stdout)


def get_tracks(mi: Dict[str, Any]) -> List[Dict[str, Any]]:
    media = mi.get("media", {})
    tracks = media.get("track", [])
    if isinstance(tracks, dict):
        return [tracks]
    if isinstance(tracks, list):
        return tracks
    return []


def pick_track(tracks: List[Dict[str, Any]], kind: str) -> Dict[str, Any]:
    for t in tracks:
        if str(t.get("@type", "")).lower() == kind.lower():
            return t
    return {}


def norm_space(s: str) -> str:
    s = TITLE_CLEAN_RE.sub("", s)
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def norm_text(s: str) -> str:
    return norm_space(s).lower()


def folder_priority(path: Path) -> int:
    p = str(path).lower()
    if "/albums/" in p:
        return 300
    if "/eps/" in p or "/ep/" in p:
        return 200
    if "/singles/" in p or "/single/" in p:
        return 100
    return 0


def parse_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return int(x)
    s = str(x).strip()
    if not s:
        return None
    m = re.search(r"(\d+(\.\d+)?)", s)
    if not m:
        return None
    num = float(m.group(1))
    return int(round(num))


def parse_duration_seconds(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        if float(x) > 1000:
            return float(x) / 1000.0
        return float(x)
    s = str(x).strip()
    if not s:
        return None
    if s.isdigit():
        return float(s) / 1000.0
    mins = re.search(r"(\d+)\s*min", s)
    secs = re.search(r"(\d+)\s*s", s)
    total = 0.0
    if mins:
        total += float(mins.group(1)) * 60.0
    if secs:
        total += float(secs.group(1))
    return total if total > 0 else None


def canonicalize_title_for_matching(title: str) -> str:
    """
    Normalize titles so:
      "WHISTLE -JP Ver.-"  -> "whistle (japanese)"
      "Whistle (Japanese Version)" -> "whistle (japanese)"
    while keeping editions like (Acoustic Ver.) separate.
    """
    t = norm_text(title)

    # Normalize common "JP Ver." notations to "(japanese)"
    t = re.sub(r"[\-\(\[]\s*jp\s*ver\.?\s*[\-\)\]]", " (japanese) ", t)
    t = re.sub(r"\bjp\s*ver\.?\b", " (japanese) ", t)

    # Normalize "(Japanese Version)" to "(japanese)" (and similar)
    t = re.sub(r"\(.*?\bjapanese\b.*?\bversion\b.*?\)", " (japanese) ", t)
    t = re.sub(r"\(.*?\bkorean\b.*?\bversion\b.*?\)", " (korean) ", t)
    t = re.sub(r"\(.*?\benglish\b.*?\bversion\b.*?\)", " (english) ", t)

    # Normalize "- korean ver -" etc (just in case)
    t = re.sub(r"\b(korean|japanese|english)\s*ver\.?\b", r"(\1)", t)

    # Keep parentheses content, reduce whitespace
    t = re.sub(r"[‐‑–—]", "-", t)
    t = re.sub(r"\s*-\s*", " - ", t)
    t = norm_space(t).lower()

    return t


def extract_language_marker(title: str, album: str) -> str:
    hay = canonicalize_title_for_matching(f"{title} {album}")

    found: List[str] = []
    for canon, toks in LANG_TOKENS.items():
        for tok in toks:
            if re.search(rf"\b{re.escape(tok)}\b", hay):
                found.append(canon)
                break

    # Also detect canonical "(japanese)" "(korean)" forms after normalization
    for canon in LANG_TOKENS.keys():
        if re.search(rf"\({re.escape(canon)}\)", hay):
            found.append(canon)

    found = sorted(set(found))
    return ",".join(found)


def extract_edition_marker(title: str, album: str) -> str:
    hay = norm_text(f"{title} {album}")
    found: List[str] = []
    for pat in EDITION_PATTERNS:
        m = re.search(pat, hay)
        if m:
            found.append(m.group(0))
    return ",".join(sorted(set(found)))


def normalize_isrc(isrc: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", isrc).upper()


@dataclass(frozen=True)
class FileInfo:
    path: Path
    ext: str
    format_group: str
    artist: str
    title: str
    title_key: str
    album: str
    isrc: str
    lang_marker: str
    edition_marker: str
    duration_s: Optional[float]

    # FLAC quality
    sample_rate: Optional[int]
    bit_depth: Optional[int]
    flac_audio_md5: str  # "MD5 of the unencoded content" if present else ""

    @property
    def pri(self) -> int:
        return folder_priority(self.path)

    def pretty(self, use_color: bool) -> str:
        p = colorize(use_color, str(self.path), C.BRIGHT_WHITE)
        parts = []
        parts.append(p)

        if self.ext == ".flac":
            sr = self.sample_rate if self.sample_rate is not None else "?"
            bd = self.bit_depth if self.bit_depth is not None else "?"
            md5 = self.flac_audio_md5[:8] + "…" if self.flac_audio_md5 else "no-md5"
            parts.append(
                colorize(use_color, f"sr={sr}", C.CYAN)
                + " "
                + colorize(use_color, f"bd={bd}", C.CYAN)
                + " "
                + colorize(use_color, f"md5={md5}", C.BRIGHT_BLACK)
            )

        meta = (
            f"title={self.title!r} "
            f"fmt={self.format_group} "
            f"lang={self.lang_marker or 'none'} "
            f"ed={self.edition_marker or 'none'} "
            f"isrc={self.isrc or 'none'} "
            f"dur={self.duration_s or '?'} "
            f"pri={self.pri}"
        )
        parts.append(colorize(use_color, meta, C.BRIGHT_BLACK))
        return " ".join(parts)


def detect_format_group(path: Path, gen: Dict[str, Any], aud: Dict[str, Any]) -> str:
    p = str(path).lower()
    if "/atmos/" in p or "dolby atmos" in p:
        return "atmos"
    if "/alac/" in p:
        return "alac"
    if "/aac/" in p:
        return "aac"
    if path.suffix.lower() == ".flac":
        return "flac"

    fmt = norm_text(str(aud.get("Format") or ""))
    prof = norm_text(
        str(aud.get("Format profile") or aud.get("Format_Profile") or "")
    )
    extra = norm_text(
        str(
            aud.get("Format_AdditionalFeatures")
            or aud.get("Format additional features")
            or ""
        )
    )
    codec = norm_text(str(aud.get("CodecID") or ""))
    combo = " ".join([fmt, prof, extra, codec])
    if "atmos" in combo or "e-ac-3" in combo or "ec-3" in combo or "joc" in combo:
        return "atmos"
    return "unknown"


def extract_fileinfo(path: Path) -> FileInfo:
    mi = run_mediainfo_json(path)
    tracks = get_tracks(mi)
    gen = pick_track(tracks, "General")
    aud = pick_track(tracks, "Audio")

    artist = norm_space(str(gen.get("Performer") or gen.get("Album_Performer") or ""))
    title = norm_space(str(gen.get("Title") or ""))
    album = norm_space(str(gen.get("Album") or ""))
    isrc_raw = norm_space(str(gen.get("ISRC") or ""))
    isrc = normalize_isrc(isrc_raw) if isrc_raw else ""

    title_key = canonicalize_title_for_matching(title)
    lang_marker = extract_language_marker(title, album)
    edition_marker = extract_edition_marker(title, album)

    ext = path.suffix.lower()
    format_group = detect_format_group(path, gen, aud)
    duration_s = parse_duration_seconds(gen.get("Duration"))

    sample_rate = None
    bit_depth = None
    flac_audio_md5 = ""

    if ext == ".flac":
        sample_rate = parse_int(aud.get("SamplingRate") or aud.get("Sampling rate"))
        bit_depth = parse_int(aud.get("BitDepth") or aud.get("Bit depth"))
        flac_audio_md5 = norm_space(
            str(aud.get("MD5 of the unencoded content") or "")
        ).upper()

    return FileInfo(
        path=path,
        ext=ext,
        format_group=format_group,
        artist=artist,
        title=title,
        title_key=title_key,
        album=album,
        isrc=isrc,
        lang_marker=lang_marker,
        edition_marker=edition_marker,
        duration_s=duration_s,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        flac_audio_md5=flac_audio_md5,
    )


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            yield Path(dirpath) / name


def related_lyrics(audio_path: Path) -> List[Path]:
    cand = audio_path.with_suffix(LYRICS_EXT)
    return [cand] if cand.exists() else []


def is_cover(path: Path) -> bool:
    return path.suffix.lower() in COVER_EXTS


def is_lyrics(path: Path) -> bool:
    return path.suffix.lower() == LYRICS_EXT


def cleanup_dirs(root: Path, touched_dirs: Iterable[Path], dry_run: bool) -> List[Path]:
    removed: List[Path] = []
    root = root.resolve()

    def eligible(dir_path: Path) -> bool:
        if not dir_path.exists() or not dir_path.is_dir():
            return False
        items = list(dir_path.iterdir())
        if not items:
            return True
        for it in items:
            if it.is_dir():
                return False
            if not (is_cover(it) or is_lyrics(it)):
                return False
        return True

    queue = sorted(
        {d.resolve() for d in touched_dirs},
        key=lambda p: len(str(p)),
        reverse=True,
    )

    for d in queue:
        cur = d
        while True:
            if cur == root or not str(cur).startswith(str(root) + os.sep):
                break
            if eligible(cur):
                if dry_run:
                    removed.append(cur)
                else:
                    shutil.rmtree(cur)
                    removed.append(cur)
                cur = cur.parent
                continue
            break

    return removed


def choose_winner(group: List[FileInfo]) -> FileInfo:
    ext = group[0].ext

    def score_flac(fi: FileInfo) -> Tuple[int, int, int, int, str]:
        sr = fi.sample_rate or 0
        bd = fi.bit_depth or 0
        pri = fi.pri
        return (sr, bd, pri, -len(str(fi.path)), str(fi.path))

    def score_m4a(fi: FileInfo) -> Tuple[int, int, str]:
        pri = fi.pri
        return (pri, -len(str(fi.path)), str(fi.path))

    if ext == ".flac":
        return sorted(group, key=score_flac, reverse=True)[0]
    return sorted(group, key=score_m4a, reverse=True)[0]


def print_header(use_color: bool, title: str) -> None:
    line = f"== {title} =="
    print(colorize(use_color, line, C.BOLD, C.BRIGHT_BLUE))


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Find and optionally delete duplicate music tracks."
    )
    ap.add_argument("root", type=Path, help="Library root folder to scan")
    ap.add_argument("--apply", action="store_true", help="Actually delete")
    ap.add_argument("--dry-run", action="store_true", help="Show only (default)")
    ap.add_argument(
        "--include-m4a",
        action="store_true",
        help="Include .m4a duplicate detection (no quality comparison)",
    )
    ap.add_argument(
        "--no-split-formats",
        action="store_true",
        help="Allow deduping across format folders (alac/atmos/aac).",
    )
    ap.add_argument(
        "--tag-match-seconds",
        type=float,
        default=3.0,
        help="Duration tolerance (seconds) for tag-based matching (default: 3.0)",
    )
    ap.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors",
    )
    ap.add_argument(
        "--force-color",
        action="store_true",
        help="Force ANSI colors even if not detected",
    )
    args = ap.parse_args()

    use_color = supports_color(force=args.force_color) and not args.no_color

    root = args.root.expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Root does not exist: {root}")

    dry_run = args.dry_run or not args.apply

    exts = {".flac"}
    if args.include_m4a:
        exts.add(".m4a")
    split_formats = not args.no_split_formats

    print_header(use_color, "Scan")
    print(
        f"Root: {colorize(use_color, str(root), C.BRIGHT_WHITE)}\n"
        f"Extensions: {colorize(use_color, ', '.join(sorted(exts)), C.CYAN)}\n"
        f"Mode: {colorize(use_color, 'DRY-RUN', C.BRIGHT_YELLOW) if dry_run else colorize(use_color, 'APPLY', C.BRIGHT_RED)}\n"
        f"Tag duration tolerance: {colorize(use_color, str(args.tag_match_seconds) + 's', C.CYAN)}\n"
        f"Split formats: {colorize(use_color, 'yes', C.BRIGHT_GREEN) if split_formats else colorize(use_color, 'no', C.BRIGHT_YELLOW)}\n"
    )

    infos: List[FileInfo] = []
    scanned = 0
    for p in iter_files(root):
        if p.suffix.lower() in exts:
            scanned += 1
            try:
                infos.append(extract_fileinfo(p))
            except Exception as e:
                print(
                    colorize(use_color, "[WARN]", C.BRIGHT_YELLOW),
                    f"Skipping {p}: {e}",
                )

    print(
        colorize(use_color, "[INFO]", C.BRIGHT_CYAN),
        f"Audio files scanned: {scanned}",
    )
    print(
        colorize(use_color, "[INFO]", C.BRIGHT_CYAN),
        f"Audio files parsed: {len(infos)}",
    )
    print()

    # Grouping strategy:
    # 1) Strong: same ISRC (same ext + same language marker + same edition marker)
    # 2) Strong: FLAC decoded-audio MD5 (same language marker + same edition marker)
    # 3) Loose: tags (artist + normalized title_key) + language+edition, refined by duration
    strong: Dict[Tuple, List[FileInfo]] = {}
    for fi in infos:
        if fi.isrc:
            k = (
                fi.ext,
                fi.format_group if split_formats else "any",
                "isrc",
                fi.lang_marker,
                fi.edition_marker,
                fi.isrc,
            )
            strong.setdefault(k, []).append(fi)

    for fi in infos:
        if fi.ext == ".flac" and fi.flac_audio_md5:
            k = (
                fi.ext,
                fi.format_group if split_formats else "any",
                "flac-md5",
                fi.lang_marker,
                fi.edition_marker,
                fi.flac_audio_md5,
            )
            strong.setdefault(k, []).append(fi)

    loose: Dict[Tuple, List[FileInfo]] = {}
    for fi in infos:
        if fi.artist and fi.title_key:
            k = (
                fi.ext,
                fi.format_group if split_formats else "any",
                "tags",
                fi.lang_marker,
                fi.edition_marker,
                norm_text(fi.artist),
                fi.title_key,
            )
            loose.setdefault(k, []).append(fi)

    tol = float(args.tag_match_seconds)

    candidate_groups: List[List[FileInfo]] = []
    for _, g in strong.items():
        if len(g) > 1:
            candidate_groups.append(g)

    for _, bucket in loose.items():
        if len(bucket) < 2:
            continue
        bucket_sorted = sorted(bucket, key=lambda x: x.duration_s or 0.0)
        cluster: List[FileInfo] = []
        for fi in bucket_sorted:
            if not cluster:
                cluster = [fi]
                continue
            prev = cluster[-1]
            if fi.duration_s is None or prev.duration_s is None:
                if len(cluster) > 1:
                    candidate_groups.append(cluster)
                cluster = [fi]
                continue
            if abs(fi.duration_s - prev.duration_s) <= tol:
                cluster.append(fi)
            else:
                if len(cluster) > 1:
                    candidate_groups.append(cluster)
                cluster = [fi]
        if len(cluster) > 1:
            candidate_groups.append(cluster)

    seen_sets = set()
    groups: List[List[FileInfo]] = []
    for g in candidate_groups:
        key = tuple(sorted(str(x.path.resolve()) for x in g))
        if key not in seen_sets:
            seen_sets.add(key)
            groups.append(g)

    if not groups:
        print_header(use_color, "Result")
        print(colorize(use_color, "No duplicates found.", C.BRIGHT_GREEN))
        return

    print_header(use_color, "Duplicate Groups")

    to_delete: List[Path] = []
    touched_dirs: List[Path] = []

    for idx, g in enumerate(groups, start=1):
        winner = choose_winner(g)
        losers = [x for x in g if x.path != winner.path]

        print(
            colorize(use_color, f"[GROUP {idx}/{len(groups)}]", C.BOLD, C.BRIGHT_BLUE)
        )
        print(colorize(use_color, "KEEP", C.BOLD, C.BRIGHT_GREEN), winner.pretty(use_color))
        for lo in losers:
            print(colorize(use_color, "DEL ", C.BOLD, C.BRIGHT_RED), lo.pretty(use_color))
        print()

        for lo in losers:
            to_delete.append(lo.path)
            touched_dirs.append(lo.path.parent)
            for lyr in related_lyrics(lo.path):
                to_delete.append(lyr)
                touched_dirs.append(lyr.parent)

    seen = set()
    uniq_delete: List[Path] = []
    for p in to_delete:
        rp = p.resolve()
        if rp.exists() and rp not in seen:
            seen.add(rp)
            uniq_delete.append(rp)

    print_header(use_color, "Planned Operations")
    print(
        colorize(use_color, "[INFO]", C.BRIGHT_CYAN),
        f"Total files to delete (including .ttml): {len(uniq_delete)}",
    )
    if dry_run:
        print(
            colorize(use_color, "[MODE]", C.BRIGHT_YELLOW),
            "DRY-RUN (nothing will be deleted)",
        )
    else:
        print(
            colorize(use_color, "[MODE]", C.BRIGHT_RED),
            "APPLY (files will be deleted)",
        )
    print()

    for p in uniq_delete:
        tag = colorize(use_color, "[DRY]", C.BRIGHT_YELLOW) if dry_run else colorize(use_color, "[DEL]", C.BRIGHT_RED)
        print(tag, colorize(use_color, str(p), C.BRIGHT_WHITE))

    if not dry_run:
        print()
        print_header(use_color, "Deleting Files")
        for p in uniq_delete:
            try:
                p.unlink()
                print(colorize(use_color, "[OK ]", C.BRIGHT_GREEN), str(p))
            except Exception as e:
                print(colorize(use_color, "[ERR]", C.BRIGHT_RED), f"{p}: {e}")

    removed_dirs = cleanup_dirs(root, touched_dirs, dry_run=dry_run)

    print()
    print_header(use_color, "Cleanup")
    if removed_dirs:
        for d in removed_dirs:
            tag = (
                colorize(use_color, "[DRY-RMDIR]", C.BRIGHT_YELLOW)
                if dry_run
                else colorize(use_color, "[RMDIR]", C.BRIGHT_MAGENTA)
            )
            print(tag, colorize(use_color, str(d), C.BRIGHT_WHITE))
    else:
        print(colorize(use_color, "[INFO]", C.BRIGHT_CYAN), "No directories removed.")


if __name__ == "__main__":
    main()
