#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

DEFAULT_ROOT = "downloads/aac"
DEFAULT_CONFIG = "apps/apple-music-downloader/config.yaml"
DEFAULT_SONG_FILE_FORMAT = "{SongNumer} - {SongName}"

FORBIDDEN_FILENAME_CHARS = re.compile(r'[/\\<>:"|?*]')

KNOWN_FLAC_TAG_IDS = {
    "title",
    "title_sort",
    "artist",
    "artist_sort",
    "album",
    "album_sort",
    "album_artist",
    "album_artist_sort",
    "composer",
    "composer_sort",
    "genre",
    "track_number",
    "track_total",
    "disc_number",
    "disc_total",
    "release_date",
    "original_date",
    "release_type",
    "isrc",
    "upc",
    "label",
    "publisher",
    "copyright",
    "advisory",
    "album_version",
    "lyrics",
    "cover",
    "performer",
    "loudness",
}

DEFAULT_FLAC_TAG_IDS_ORDER = [
    "title",
    "title_sort",
    "artist",
    "artist_sort",
    "album",
    "album_sort",
    "album_artist",
    "album_artist_sort",
    "composer",
    "composer_sort",
    "genre",
    "track_number",
    "track_total",
    "disc_number",
    "disc_total",
    "release_date",
    "original_date",
    "release_type",
    "isrc",
    "upc",
    "label",
    "publisher",
    "copyright",
    "advisory",
    "album_version",
    "lyrics",
    "cover",
    "performer",
    "loudness",
]


def normalize_ext(value: str) -> str:
    ext = value.strip().lower()
    if not ext:
        return ""
    if not ext.startswith("."):
        ext = f".{ext}"
    return ext


def iter_files(root: Path, extension: str) -> Iterable[Path]:
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(extension):
                yield Path(dirpath) / name


def run_command(cmd: List[str]) -> Tuple[int, str, str]:
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


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
        err = stderr.strip() or stdout.strip() or "ffprobe failed"
        print(f"FAIL ffprobe: {file_path} ({err})")
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
        key = key.strip().lower()
        value = value.strip()
        if not key or not value:
            continue
        tags[key] = value
    return tags


def pick_first(tags: Dict[str, str], *keys: str) -> str:
    for key in keys:
        value = tags.get(key, "").strip()
        if value:
            return value
    return ""


def split_fraction(value: str) -> Tuple[str, str]:
    raw = value.strip()
    if not raw:
        return "", ""
    parts = raw.split("/", 1)
    left = parts[0].strip()
    if len(parts) == 1:
        return left, ""
    right = parts[1].strip()
    return left, right


def parse_int_from_tag(value: str) -> Optional[int]:
    if not value:
        return None
    left, _ = split_fraction(value)
    source = left if left else value
    match = re.search(r"\d+", source)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def normalize_tag_ids(raw_ids: List[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw in raw_ids:
        key = raw.strip().lower()
        if not key or key not in KNOWN_FLAC_TAG_IDS:
            continue
        if key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized


def split_tokens(raw: str, delimiters: List[str]) -> List[str]:
    parts: List[str] = [raw]
    for delimiter in delimiters:
        next_parts: List[str] = []
        for part in parts:
            if delimiter in part:
                next_parts.extend(part.split(delimiter))
            else:
                next_parts.append(part)
        parts = next_parts
    return parts


def should_split_composer_conjunction(raw: str) -> bool:
    text = raw.strip()
    if not text:
        return False
    if ";" in text or " / " in text or " x " in text or " X " in text or " × " in text:
        return True
    if should_split_standalone_composer_ampersand(text):
        return True
    return text.count(",") >= 2


def should_split_standalone_composer_ampersand(raw: str) -> bool:
    if raw.count(" & ") != 1:
        return False
    if (
        "," in raw
        or ";" in raw
        or " / " in raw
        or " x " in raw
        or " X " in raw
        or " × " in raw
    ):
        return False
    left, right = [part.strip() for part in raw.split(" & ", 1)]
    if not left or not right:
        return False
    left_words = left.split()
    right_words = right.split()
    if not left_words or not right_words:
        return False
    if len(left_words) == 1 and len(right_words) == 1:
        if not looks_like_composer_abbreviation(left_words[0]) and not looks_like_composer_abbreviation(right_words[0]):
            return False
    return True


def looks_like_composer_abbreviation(token: str) -> bool:
    text = token.strip()
    if not text:
        return False
    if len(text) <= 3 and text.upper() == text:
        return any(ch.isalpha() for ch in text)
    return False


def normalize_composer_value(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    parts = split_tokens(
        raw,
        [
            "; ",
            ";",
            " / ",
            " x ",
            " X ",
            " × ",
            ", ",
            ",",
        ],
    )
    split_conjunction = should_split_composer_conjunction(raw)
    normalized: List[str] = []
    seen = set()
    for part in parts:
        token = part.strip()
        if not token:
            continue
        sub_parts = [token]
        if split_conjunction:
            sub_parts = split_tokens(token, [" & ", " and ", " And "])
        for sub in sub_parts:
            name = sub.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            normalized.append(name)
    return ", ".join(normalized)


def parse_config(path: Path) -> Tuple[str, List[str]]:
    if not path.exists():
        return DEFAULT_SONG_FILE_FORMAT, list(DEFAULT_FLAC_TAG_IDS_ORDER)

    song_file_format = DEFAULT_SONG_FILE_FORMAT
    flac_tags: List[str] = []
    in_flac_list = False

    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if stripped.startswith("song-file-format:"):
                value = stripped.split(":", 1)[1].strip()
                if value and value not in {"''", '""'}:
                    song_file_format = value.strip("'\"")
                continue

            if stripped == "metadata-tags-flac:":
                in_flac_list = True
                continue

            if in_flac_list:
                if stripped.startswith("- "):
                    flac_tags.append(stripped[2:].strip().strip("'\""))
                    continue
                if line.startswith("  - "):
                    flac_tags.append(line.split("-", 1)[1].strip().strip("'\""))
                    continue
                in_flac_list = False

    normalized = normalize_tag_ids(flac_tags)
    if not normalized:
        normalized = list(DEFAULT_FLAC_TAG_IDS_ORDER)
    return song_file_format, normalized


def normalize_advisory(value: str) -> str:
    lower = value.strip().lower()
    if not lower:
        return ""
    if lower in {"1", "explicit", "e"}:
        return "1"
    if lower in {"2", "clean", "c"}:
        return "2"
    if lower in {"0", "none", "n"}:
        return "0"
    return ""


def assign_tag(tags: Dict[str, str], key: str, value: str) -> None:
    clean = value.strip()
    if key and clean:
        tags[key] = clean


def build_flac_target_tags(
    reference_tags: Dict[str, str], enabled_ids: List[str]
) -> Dict[str, str]:
    enabled = set(enabled_ids)
    target: Dict[str, str] = {}

    if "title" in enabled:
        assign_tag(target, "TITLE", pick_first(reference_tags, "title"))
    if "title_sort" in enabled:
        sort_title = pick_first(reference_tags, "titlesort", "sort_name")
        assign_tag(target, "TITLESORT", sort_title)
        assign_tag(target, "sort_name", sort_title)
    if "artist" in enabled:
        assign_tag(target, "ARTIST", pick_first(reference_tags, "artist"))
    if "artist_sort" in enabled:
        sort_artist = pick_first(reference_tags, "artistsort", "sort_artist")
        assign_tag(target, "ARTISTSORT", sort_artist)
        assign_tag(target, "sort_artist", sort_artist)
    if "album" in enabled:
        assign_tag(target, "ALBUM", pick_first(reference_tags, "album"))
    if "album_sort" in enabled:
        sort_album = pick_first(reference_tags, "albumsort", "sort_album")
        assign_tag(target, "ALBUMSORT", sort_album)
        assign_tag(target, "sort_album", sort_album)
    if "album_artist" in enabled:
        assign_tag(
            target,
            "ALBUMARTIST",
            pick_first(reference_tags, "albumartist", "album_artist"),
        )
    if "album_artist_sort" in enabled:
        sort_album_artist = pick_first(
            reference_tags,
            "albumartistsort",
            "sort_album_artist",
            "sort_albumartist",
        )
        assign_tag(target, "ALBUMARTISTSORT", sort_album_artist)
        assign_tag(target, "sort_album_artist", sort_album_artist)
    if "composer" in enabled:
        assign_tag(
            target,
            "COMPOSER",
            normalize_composer_value(pick_first(reference_tags, "composer")),
        )
    if "composer_sort" in enabled:
        sort_composer = normalize_composer_value(
            pick_first(reference_tags, "composersort", "sort_composer")
        )
        assign_tag(target, "COMPOSERSORT", sort_composer)
        assign_tag(target, "sort_composer", sort_composer)
    if "genre" in enabled:
        assign_tag(target, "GENRE", pick_first(reference_tags, "genre"))

    track_raw = pick_first(reference_tags, "tracknumber", "track", "tracknum")
    track_num, track_total = split_fraction(track_raw)
    if "track_number" in enabled:
        assign_tag(target, "TRACKNUMBER", track_num)
    if "track_total" in enabled:
        if not track_total:
            track_total = pick_first(
                reference_tags, "tracktotal", "totaltracks", "track_total"
            )
        assign_tag(target, "TRACKTOTAL", track_total)
        assign_tag(target, "TOTALTRACKS", track_total)

    disc_raw = pick_first(reference_tags, "discnumber", "disc", "disk")
    disc_num, disc_total = split_fraction(disc_raw)
    if "disc_number" in enabled:
        assign_tag(target, "DISCNUMBER", disc_num)
    if "disc_total" in enabled:
        if not disc_total:
            disc_total = pick_first(
                reference_tags, "disctotal", "totaldiscs", "disc_total"
            )
        assign_tag(target, "DISCTOTAL", disc_total)
        assign_tag(target, "TOTALDISCS", disc_total)

    if "release_date" in enabled:
        assign_tag(
            target,
            "DATE",
            pick_first(reference_tags, "date", "release_date", "releasedate"),
        )
    if "original_date" in enabled:
        assign_tag(
            target,
            "ORIGINALDATE",
            pick_first(
                reference_tags, "originaldate", "original_date", "origdate", "tdor"
            ),
        )
    if "release_type" in enabled:
        assign_tag(
            target,
            "RELEASETYPE",
            pick_first(reference_tags, "releasetype", "release_type"),
        )
    if "isrc" in enabled:
        assign_tag(target, "ISRC", pick_first(reference_tags, "isrc"))
    if "upc" in enabled:
        assign_tag(target, "UPC", pick_first(reference_tags, "upc"))
    if "label" in enabled:
        assign_tag(target, "LABEL", pick_first(reference_tags, "label"))
    if "publisher" in enabled:
        assign_tag(
            target, "PUBLISHER", pick_first(reference_tags, "publisher", "label")
        )
    if "copyright" in enabled:
        assign_tag(target, "COPYRIGHT", pick_first(reference_tags, "copyright"))
    if "performer" in enabled:
        assign_tag(target, "PERFORMER", pick_first(reference_tags, "performer"))
    if "lyrics" in enabled:
        assign_tag(target, "LYRICS", pick_first(reference_tags, "lyrics"))
    if "album_version" in enabled:
        assign_tag(
            target,
            "ALBUMVERSION",
            pick_first(reference_tags, "albumversion", "edition", "version"),
        )
    if "advisory" in enabled:
        advisory = normalize_advisory(
            pick_first(reference_tags, "rating", "advisory", "itunesadvisory")
        )
        assign_tag(target, "RATING", advisory)
    if "loudness" in enabled:
        assign_tag(
            target,
            "REPLAYGAIN_TRACK_GAIN",
            pick_first(reference_tags, "replaygain_track_gain"),
        )
        assign_tag(
            target,
            "REPLAYGAIN_TRACK_PEAK",
            pick_first(reference_tags, "replaygain_track_peak"),
        )
        assign_tag(
            target,
            "REPLAYGAIN_ALBUM_GAIN",
            pick_first(reference_tags, "replaygain_album_gain"),
        )
        assign_tag(
            target,
            "REPLAYGAIN_ALBUM_PEAK",
            pick_first(reference_tags, "replaygain_album_peak"),
        )
        assign_tag(
            target, "R128_TRACK_GAIN", pick_first(reference_tags, "r128_track_gain")
        )
        assign_tag(
            target, "R128_ALBUM_GAIN", pick_first(reference_tags, "r128_album_gain")
        )

    return target


def build_target_name(song_file_format: str, reference_tags: Dict[str, str]) -> str:
    track_raw = pick_first(reference_tags, "tracknumber", "track", "tracknum")
    track_num = parse_int_from_tag(track_raw) or 0
    disc_raw = pick_first(reference_tags, "discnumber", "disc", "disk")
    disc_num = parse_int_from_tag(disc_raw) or 0
    title = pick_first(reference_tags, "title")

    replacements = {
        "{SongId}": "",
        "{SongNumer}": f"{track_num:02d}" if track_num > 0 else "00",
        "{SongName}": title,
        "{DiscNumber}": str(disc_num),
        "{TrackNumber}": str(track_num if track_num > 0 else 0),
        "{Quality}": "",
        "{Tag}": "",
        "{Codec}": "FLAC",
    }

    name = song_file_format
    for key, value in replacements.items():
        name = name.replace(key, value)
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        name = title or "Unknown Track"
    return FORBIDDEN_FILENAME_CHARS.sub("_", name)


def select_reference(
    flac_tags: Dict[str, str],
    candidates: List[Tuple[Path, Dict[str, str]]],
) -> Optional[Tuple[Path, Dict[str, str], str]]:
    if not candidates:
        return None

    flac_isrc = pick_first(flac_tags, "isrc").upper()
    flac_track = parse_int_from_tag(
        pick_first(flac_tags, "tracknumber", "track", "tracknum")
    )
    flac_title = normalize_title(pick_first(flac_tags, "title"))

    if flac_isrc:
        matches = [
            item
            for item in candidates
            if pick_first(item[1], "isrc").upper() == flac_isrc
        ]
        if len(matches) == 1:
            return matches[0][0], matches[0][1], "isrc"

    if flac_track is not None:
        matches = [
            item
            for item in candidates
            if parse_int_from_tag(
                pick_first(item[1], "tracknumber", "track", "tracknum")
            )
            == flac_track
        ]
        if len(matches) == 1:
            return matches[0][0], matches[0][1], "track"

    if flac_title:
        matches = [
            item
            for item in candidates
            if normalize_title(pick_first(item[1], "title")) == flac_title
        ]
        if len(matches) == 1:
            return matches[0][0], matches[0][1], "title"

    if len(candidates) == 1:
        return candidates[0][0], candidates[0][1], "single"
    return None


def apply_flac_tags(
    metaflac_path: str,
    file_path: Path,
    tags: Dict[str, str],
    dry_run: bool,
) -> bool:
    if not tags:
        return True
    args = [metaflac_path, "--dont-use-padding", "--remove-all-tags"]
    for key in sorted(tags.keys()):
        value = tags[key]
        args.append(f"--set-tag={key}={value}")
    args.append(str(file_path))
    if dry_run:
        return True
    code, _, stderr = run_command(args)
    if code != 0:
        print(f"FAIL tag write: {file_path} ({stderr.strip() or 'metaflac failed'})")
        return False
    return True


def remove_picture_blocks(
    metaflac_path: str,
    file_path: Path,
    dry_run: bool,
) -> bool:
    if dry_run:
        return True
    code, _, stderr = run_command(
        [
            metaflac_path,
            "--dont-use-padding",
            "--remove",
            "--block-type=PICTURE",
            str(file_path),
        ]
    )
    if code != 0:
        err = stderr.strip() or "metaflac remove picture failed"
        print(f"FAIL remove picture: {file_path} ({err})")
        return False
    return True


def remove_padding_blocks(
    metaflac_path: str,
    file_path: Path,
    dry_run: bool,
) -> bool:
    if dry_run:
        return True
    code, _, stderr = run_command(
        [
            metaflac_path,
            "--dont-use-padding",
            "--remove",
            "--block-type=PADDING",
            str(file_path),
        ]
    )
    if code != 0:
        err = stderr.strip() or "metaflac remove padding failed"
        print(f"FAIL remove padding: {file_path} ({err})")
        return False
    return True


def read_streaminfo_md5(metaflac_path: str, file_path: Path) -> Optional[str]:
    code, stdout, stderr = run_command([metaflac_path, "--show-md5sum", str(file_path)])
    if code != 0:
        err = stderr.strip() or stdout.strip() or "metaflac --show-md5sum failed"
        print(f"FAIL md5 read: {file_path} ({err})")
        return None
    md5 = stdout.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", md5):
        print(f"FAIL md5 read: {file_path} (invalid md5 value: {md5!r})")
        return None
    return md5


def fix_zero_md5(flac_bin: str, file_path: Path, dry_run: bool) -> bool:
    if dry_run:
        return True
    parent = file_path.parent
    fd, tmp_name = tempfile.mkstemp(
        prefix=".retag-md5-",
        suffix=".flac",
        dir=str(parent),
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        code, _, stderr = run_command(
            [flac_bin, "-f", "-o", str(tmp_path), str(file_path)]
        )
        if code != 0:
            err = stderr.strip() or "flac re-encode failed"
            print(f"FAIL md5 fix: {file_path} ({err})")
            return False
        tmp_path.replace(file_path)
        return True
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def maybe_rename(
    file_path: Path, new_base_name: str, dry_run: bool
) -> Tuple[Path, bool]:
    target = file_path.with_name(f"{new_base_name}.flac")
    if target == file_path:
        return file_path, False
    if target.exists():
        print(f"SKIP rename exists: {target}")
        return file_path, False
    if dry_run:
        return target, True
    file_path.rename(target)
    return target, True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retag and rename external FLAC files using sibling M4A metadata from this project.",
    )
    parser.add_argument(
        "--root",
        default=DEFAULT_ROOT,
        help=f"Root folder containing FLAC files (default: {DEFAULT_ROOT}).",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"Path to config.yaml (default: {DEFAULT_CONFIG}).",
    )
    parser.add_argument(
        "--ffprobe",
        default="ffprobe",
        help="Path to ffprobe binary (default: ffprobe).",
    )
    parser.add_argument(
        "--metaflac",
        default="metaflac",
        help="Path to metaflac binary (default: metaflac).",
    )
    parser.add_argument(
        "--flac-bin",
        default="flac",
        help="Path to flac binary used to rebuild invalid STREAMINFO MD5 (default: flac).",
    )
    parser.add_argument(
        "--fix-zero-md5",
        action="store_true",
        help="Rebuild FLAC files whose STREAMINFO MD5 is 000...000 before retagging.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without writing tags or renaming files.",
    )
    parser.add_argument(
        "--keep-padding",
        action="store_true",
        help="Keep FLAC padding blocks after retagging (default strips padding).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of FLAC files to process (0 = no limit).",
    )
    args = parser.parse_args()

    root = Path(args.root)
    config_path = Path(args.config)

    if not root.is_dir():
        print(f"Root folder not found: {root}", file=sys.stderr)
        return 2
    if not shutil.which(args.ffprobe):
        print(f"ffprobe not found: {args.ffprobe}", file=sys.stderr)
        return 2
    if not shutil.which(args.metaflac):
        print(f"metaflac not found: {args.metaflac}", file=sys.stderr)
        return 2
    if args.fix_zero_md5 and not shutil.which(args.flac_bin):
        print(f"flac not found: {args.flac_bin}", file=sys.stderr)
        return 2

    song_file_format, enabled_tag_ids = parse_config(config_path)
    print(f"Using config: {config_path}")
    print(f"Song file format: {song_file_format}")
    print(f"Enabled FLAC tag IDs: {', '.join(enabled_tag_ids)}")
    if args.dry_run:
        print("Dry run mode enabled: no files will be modified.")

    total = 0
    updated = 0
    renamed = 0
    md5_fixed = 0
    picture_removed = 0
    padding_removed = 0
    skipped = 0
    failed = 0

    m4a_cache: Dict[Path, Optional[Dict[str, str]]] = {}

    for flac_path in iter_files(root, ".flac"):
        total += 1
        if args.limit > 0 and total > args.limit:
            break

        md5_was_fixed = False
        flac_tags = read_ffprobe_tags(args.ffprobe, flac_path)
        if flac_tags is None:
            failed += 1
            continue

        if args.fix_zero_md5:
            md5_before = read_streaminfo_md5(args.metaflac, flac_path)
            if md5_before is None:
                failed += 1
                continue
            if md5_before == "0" * 32:
                ok_md5 = fix_zero_md5(args.flac_bin, flac_path, args.dry_run)
                if not ok_md5:
                    failed += 1
                    continue
                md5_fixed += 1
                md5_was_fixed = True
                if not args.dry_run:
                    flac_tags = read_ffprobe_tags(args.ffprobe, flac_path)
                    if flac_tags is None:
                        failed += 1
                        continue

        parent = flac_path.parent
        candidate_refs: List[Tuple[Path, Dict[str, str]]] = []
        for m4a_path in sorted(parent.glob("*.m4a")):
            if m4a_path not in m4a_cache:
                m4a_cache[m4a_path] = read_ffprobe_tags(args.ffprobe, m4a_path)
            tags = m4a_cache[m4a_path]
            if tags is not None:
                candidate_refs.append((m4a_path, tags))

        selected = select_reference(flac_tags, candidate_refs)
        if selected is None:
            print(f"SKIP no unique reference: {flac_path}")
            skipped += 1
            continue

        ref_path, ref_tags, matched_by = selected
        target_tags = build_flac_target_tags(ref_tags, enabled_tag_ids)
        if not target_tags:
            print(f"SKIP no mapped tags: {flac_path}")
            skipped += 1
            continue

        ok = apply_flac_tags(args.metaflac, flac_path, target_tags, args.dry_run)
        if not ok:
            failed += 1
            continue
        updated += 1

        picture_was_removed = False
        if "cover" not in enabled_tag_ids:
            ok = remove_picture_blocks(args.metaflac, flac_path, args.dry_run)
            if not ok:
                failed += 1
                continue
            picture_removed += 1
            picture_was_removed = True

        padding_was_removed = False
        if not args.keep_padding:
            ok = remove_padding_blocks(args.metaflac, flac_path, args.dry_run)
            if not ok:
                failed += 1
                continue
            padding_removed += 1
            padding_was_removed = True

        new_name = build_target_name(song_file_format, ref_tags)
        _, did_rename = maybe_rename(flac_path, new_name, args.dry_run)
        if did_rename:
            renamed += 1

        print(
            f"OK: {flac_path} <- {ref_path.name} (matched by {matched_by})"
            + (", md5 fixed" if md5_was_fixed else "")
            + (", picture removed" if picture_was_removed else "")
            + (", padding removed" if padding_was_removed else "")
            + (f", rename -> {new_name}.flac" if did_rename else "")
        )

    print(
        f"Processed {total} FLAC file(s). "
        f"Retagged: {updated}. Renamed: {renamed}. "
        f"MD5 fixed: {md5_fixed}. Picture removed: {picture_removed}. "
        f"Padding removed: {padding_removed}. "
        f"Skipped: {skipped}. Failed: {failed}."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
