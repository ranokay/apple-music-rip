#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import quote_plus, urlparse

import dedupe_music as dm

SURVEY_REPLACE_FLAG = (
    "-mod=mod -replace=github.com/AlecAivazis/survey/v2=../wrapper/survey_stub"
)
AUDIO_EXTS = {".flac", ".m4a"}
FEAT_RE = re.compile(r"\b(feat\.?|featuring|ft\.?)\b.*$", re.IGNORECASE)
ARTIST_SPLIT_RE = re.compile(r"\s*(?:,|&|/| x | and )\s*", re.IGNORECASE)


@dataclass(frozen=True)
class PlaylistTrack:
    num: int
    title: str
    artist: str
    album: str
    track_id: str
    isrc: str
    duration_s: Optional[float]
    title_key: str
    artist_key: str


@dataclass(frozen=True)
class LocalTrack:
    path: Path
    title: str
    artist: str
    album: str
    ext: str
    format_group: str
    isrc: str
    duration_s: Optional[float]
    title_key: str
    artist_key: str
    sample_rate: Optional[int]
    bit_depth: Optional[int]


@dataclass(frozen=True)
class Match:
    playlist: PlaylistTrack
    local: LocalTrack
    score: int
    reason: str


def parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def canonical_artist(value: str) -> str:
    text = dm.norm_text(value)
    text = FEAT_RE.sub("", text)
    text = text.strip(" -")
    if not text:
        return ""
    parts = [part.strip() for part in ARTIST_SPLIT_RE.split(text) if part.strip()]
    return parts[0] if parts else text


def parse_json_payload(raw: str) -> Dict[str, Any]:
    payload = raw.strip()
    if not payload:
        raise ValueError("empty output")
    try:
        value = json.loads(payload)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    start = payload.find("{")
    end = payload.rfind("}")
    if start == -1 or end == -1 or start >= end:
        raise ValueError("no JSON object found in output")
    value = json.loads(payload[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("decoded payload is not a JSON object")
    return value


def run_playlist_preview(playlist_url: str, downloader_dir: Path) -> Dict[str, Any]:
    # Keep subprocess environment identical except GOFLAGS override.
    env = os.environ.copy()
    goflags = str(env.get("GOFLAGS", "")).strip()
    if SURVEY_REPLACE_FLAG not in goflags:
        env["GOFLAGS"] = f"{goflags} {SURVEY_REPLACE_FLAG}".strip()

    proc = subprocess.run(
        ["go", "run", "main.go", "--preview", playlist_url],
        cwd=str(downloader_dir),
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"preview failed with exit code {proc.returncode}: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return parse_json_payload(proc.stdout)


def storefront_from_playlist_url(raw_url: str) -> str:
    try:
        parsed = urlparse(raw_url)
    except Exception:
        return "us"
    parts = [part for part in parsed.path.split("/") if part]
    if parts and re.fullmatch(r"[a-zA-Z]{2}", parts[0]):
        return parts[0].lower()
    return "us"


def playlist_tracks_from_payload(payload: Dict[str, Any]) -> List[PlaylistTrack]:
    tracks_payload = payload.get("tracks", [])
    if not isinstance(tracks_payload, list):
        raise ValueError("preview payload does not contain track list")

    fallback_artist = dm.norm_space(str(payload.get("artist") or ""))
    fallback_album = dm.norm_space(str(payload.get("title") or ""))

    tracks: List[PlaylistTrack] = []
    for idx, entry in enumerate(tracks_payload, start=1):
        if not isinstance(entry, dict):
            continue
        title = dm.norm_space(str(entry.get("name") or ""))
        if not title:
            continue
        artist = dm.norm_space(str(entry.get("artist") or fallback_artist))
        album = dm.norm_space(str(entry.get("album") or fallback_album))
        num = parse_int(entry.get("num")) or idx
        track_id = dm.norm_space(str(entry.get("id") or ""))
        isrc_raw = dm.norm_space(str(entry.get("isrc") or ""))
        isrc = dm.normalize_isrc(isrc_raw) if isrc_raw else ""
        duration_ms = parse_int(entry.get("duration_ms"))
        duration_s = (duration_ms / 1000.0) if duration_ms and duration_ms > 0 else None
        title_key = dm.canonicalize_title_for_matching(title)
        artist_key = canonical_artist(artist)

        tracks.append(
            PlaylistTrack(
                num=num,
                title=title,
                artist=artist,
                album=album,
                track_id=track_id,
                isrc=isrc,
                duration_s=duration_s,
                title_key=title_key,
                artist_key=artist_key,
            )
        )

    return tracks


def scan_local_tracks(local_root: Path) -> List[LocalTrack]:
    out: List[LocalTrack] = []
    for path in dm.iter_files(local_root):
        if path.suffix.lower() not in AUDIO_EXTS:
            continue
        info = dm.extract_fileinfo(path)
        artist = info.artist or local_root.name
        title = info.title
        if not title:
            continue
        out.append(
            LocalTrack(
                path=info.path.resolve(),
                title=title,
                artist=artist,
                album=info.album,
                ext=info.ext,
                format_group=info.format_group,
                isrc=info.isrc,
                duration_s=info.duration_s,
                title_key=info.title_key,
                artist_key=canonical_artist(artist),
                sample_rate=info.sample_rate,
                bit_depth=info.bit_depth,
            )
        )
    return out


def local_keep_score(track: LocalTrack) -> Tuple[int, int, int, int, int, int, str]:
    ext_rank = 2 if track.ext == ".flac" else 1
    sr = track.sample_rate or 0
    bd = track.bit_depth or 0
    fmt_rank = 2 if track.format_group in {"alac", "flac"} else 1
    pri = dm.folder_priority(track.path)
    return (ext_rank, sr, bd, fmt_rank, pri, -len(str(track.path)), str(track.path))


def duration_delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return abs(a - b)


def match_score(
    playlist_track: PlaylistTrack,
    local_track: LocalTrack,
    duration_tolerance: float,
    strict_artist: bool,
) -> Tuple[int, str]:
    if playlist_track.title_key != local_track.title_key:
        return (-10_000, "title mismatch")

    score = 120
    reason_parts: List[str] = ["title"]

    if playlist_track.isrc and local_track.isrc:
        if playlist_track.isrc == local_track.isrc:
            score += 1000
            reason_parts.append("isrc")
        else:
            score -= 300
            reason_parts.append("isrc-conflict")

    if playlist_track.artist_key and local_track.artist_key:
        if playlist_track.artist_key == local_track.artist_key:
            score += 80
            reason_parts.append("artist")
        elif strict_artist and not (
            playlist_track.isrc
            and local_track.isrc
            and playlist_track.isrc == local_track.isrc
        ):
            return (-10_000, "artist mismatch")
        else:
            score -= 10
            reason_parts.append("artist-loose")

    delta = duration_delta(playlist_track.duration_s, local_track.duration_s)
    if delta is not None:
        if delta <= duration_tolerance:
            score += 40
            reason_parts.append("duration")
        elif delta <= duration_tolerance * 2:
            score += 10
            reason_parts.append("duration-loose")
        else:
            score -= 60
            reason_parts.append("duration-mismatch")

    if local_track.ext == ".flac":
        score += 5

    return (score, ",".join(reason_parts))


def accept_match(
    playlist_track: PlaylistTrack,
    local_track: LocalTrack,
    score: int,
    duration_tolerance: float,
    strict_artist: bool,
) -> bool:
    if (
        playlist_track.isrc
        and local_track.isrc
        and playlist_track.isrc == local_track.isrc
    ):
        return True

    if playlist_track.title_key != local_track.title_key:
        return False

    if playlist_track.artist_key == local_track.artist_key:
        return score >= 150

    if strict_artist:
        return False

    delta = duration_delta(playlist_track.duration_s, local_track.duration_s)
    if delta is not None and delta <= duration_tolerance:
        return score >= 120

    return False


def reconcile(
    playlist_tracks: Sequence[PlaylistTrack],
    local_tracks: Sequence[LocalTrack],
    duration_tolerance: float,
    strict_artist: bool,
) -> Tuple[List[Match], List[PlaylistTrack], List[LocalTrack]]:
    by_isrc: Dict[str, List[int]] = {}
    by_key: Dict[Tuple[str, str], List[int]] = {}
    by_title: Dict[str, List[int]] = {}

    for idx, local_track in enumerate(local_tracks):
        if local_track.isrc:
            by_isrc.setdefault(local_track.isrc, []).append(idx)
        by_key.setdefault((local_track.title_key, local_track.artist_key), []).append(
            idx
        )
        by_title.setdefault(local_track.title_key, []).append(idx)

    used_local: Set[int] = set()
    matches: List[Match] = []
    playlist_only: List[PlaylistTrack] = []

    for playlist_track in playlist_tracks:
        candidates: Set[int] = set()
        if playlist_track.isrc:
            candidates.update(by_isrc.get(playlist_track.isrc, []))
        candidates.update(
            by_key.get((playlist_track.title_key, playlist_track.artist_key), [])
        )
        candidates.update(by_title.get(playlist_track.title_key, []))

        candidates = {idx for idx in candidates if idx not in used_local}
        if not candidates:
            playlist_only.append(playlist_track)
            continue

        scored: List[Tuple[int, str, int]] = []
        for idx in candidates:
            score, reason = match_score(
                playlist_track,
                local_tracks[idx],
                duration_tolerance,
                strict_artist,
            )
            scored.append((score, reason, idx))

        scored.sort(key=lambda row: row[0], reverse=True)
        best_score, best_reason, best_idx = scored[0]
        best_local = local_tracks[best_idx]

        if not accept_match(
            playlist_track,
            best_local,
            best_score,
            duration_tolerance,
            strict_artist,
        ):
            playlist_only.append(playlist_track)
            continue

        used_local.add(best_idx)
        matches.append(
            Match(
                playlist=playlist_track,
                local=best_local,
                score=best_score,
                reason=best_reason,
            )
        )

    local_only = [
        track for idx, track in enumerate(local_tracks) if idx not in used_local
    ]
    return (matches, playlist_only, local_only)


def collapse_local_only(
    local_tracks: Sequence[LocalTrack],
) -> List[Tuple[LocalTrack, int]]:
    grouped: Dict[Tuple[Any, ...], List[LocalTrack]] = {}
    for track in local_tracks:
        if track.isrc:
            key = ("isrc", track.isrc)
        else:
            key = ("key", track.title_key, track.artist_key)
        grouped.setdefault(key, []).append(track)

    rows: List[Tuple[LocalTrack, int]] = []
    for group in grouped.values():
        keep = sorted(group, key=local_keep_score, reverse=True)[0]
        rows.append((keep, len(group)))
    rows.sort(key=lambda row: (row[0].artist_key, row[0].title_key, str(row[0].path)))
    return rows


def preview_search_link(storefront: str, artist: str, title: str) -> str:
    query = f"{artist} {title}".strip()
    return f"https://music.apple.com/{storefront}/search?term={quote_plus(query)}"


def write_csv_playlist_only(
    rows: Sequence[PlaylistTrack],
    storefront: str,
    out_path: Path,
) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "playlist_position",
                "title",
                "artist",
                "album",
                "isrc",
                "duration_s",
                "track_id",
                "song_url",
                "search_url",
            ]
        )
        for row in rows:
            song_url = (
                f"https://music.apple.com/{storefront}/song/{row.track_id}"
                if row.track_id
                else ""
            )
            writer.writerow(
                [
                    row.num,
                    row.title,
                    row.artist,
                    row.album,
                    row.isrc,
                    f"{row.duration_s:.3f}" if row.duration_s is not None else "",
                    row.track_id,
                    song_url,
                    preview_search_link(storefront, row.artist, row.title),
                ]
            )


def write_csv_local_only(
    rows: Sequence[Tuple[LocalTrack, int]],
    storefront: str,
    out_path: Path,
) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "title",
                "artist",
                "album",
                "isrc",
                "duration_s",
                "format",
                "path",
                "variant_count",
                "search_url",
            ]
        )
        for track, variant_count in rows:
            writer.writerow(
                [
                    track.title,
                    track.artist,
                    track.album,
                    track.isrc,
                    f"{track.duration_s:.3f}" if track.duration_s is not None else "",
                    track.ext.lstrip("."),
                    str(track.path),
                    variant_count,
                    preview_search_link(storefront, track.artist, track.title),
                ]
            )


def print_section(title: str) -> None:
    print(f"\n== {title} ==")


def print_playlist_only(rows: Sequence[PlaylistTrack], max_print: int) -> None:
    print_section("Playlist Only (in playlist, missing locally)")
    if not rows:
        print("None")
        return
    for item in rows[:max_print]:
        print(
            f"- #{item.num:02d} {item.artist} - {item.title}"
            + (f" [{item.album}]" if item.album else "")
            + (f" (ISRC: {item.isrc})" if item.isrc else "")
        )
    if len(rows) > max_print:
        print(f"... and {len(rows) - max_print} more")


def print_local_only(rows: Sequence[Tuple[LocalTrack, int]], max_print: int) -> None:
    print_section("Local Only (candidate songs to add back to playlist)")
    if not rows:
        print("None")
        return
    for item, variants in rows[:max_print]:
        suffix = f" [variants={variants}]" if variants > 1 else ""
        print(
            f"- {item.artist} - {item.title} ({item.ext.lstrip('.')}){suffix}\n"
            f"  {item.path}"
        )
    if len(rows) > max_print:
        print(f"... and {len(rows) - max_print} more")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare a local artist library folder against an Apple Music playlist "
            "and report missing tracks in both directions."
        )
    )
    parser.add_argument("playlist_url", help="Apple Music playlist URL")
    parser.add_argument("local_root", type=Path, help="Local folder to scan")
    parser.add_argument(
        "--downloader-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "apps" / "apple-music-downloader",
        help="Path to apps/apple-music-downloader (default: repo apps/apple-music-downloader)",
    )
    parser.add_argument(
        "--preview-json",
        type=Path,
        help="Use a saved preview JSON instead of calling `go run main.go --preview`",
    )
    parser.add_argument(
        "--save-preview-json",
        type=Path,
        help="Save fetched preview JSON to this file",
    )
    parser.add_argument(
        "--duration-tolerance",
        type=float,
        default=2.0,
        help="Duration tolerance in seconds for loose matching (default: 2.0)",
    )
    parser.add_argument(
        "--strict-artist",
        action="store_true",
        help="Require artist match unless ISRC matches",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Directory to write reconcile_report.json, local_only.csv, playlist_only.csv",
    )
    parser.add_argument(
        "--max-print",
        type=int,
        default=40,
        help="Max rows to print per section (default: 40)",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    local_root = args.local_root.expanduser().resolve()
    downloader_dir = args.downloader_dir.expanduser().resolve()
    if not local_root.exists():
        raise SystemExit(f"Local root does not exist: {local_root}")
    if not downloader_dir.exists():
        raise SystemExit(f"Downloader directory does not exist: {downloader_dir}")

    if args.preview_json:
        preview_payload = json.loads(args.preview_json.read_text(encoding="utf-8"))
    else:
        print("Fetching playlist preview...")
        preview_payload = run_playlist_preview(args.playlist_url, downloader_dir)
        if args.save_preview_json:
            args.save_preview_json.parent.mkdir(parents=True, exist_ok=True)
            args.save_preview_json.write_text(
                json.dumps(preview_payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    playlist_tracks = playlist_tracks_from_payload(preview_payload)
    if not playlist_tracks:
        raise SystemExit("No playlist tracks found in preview payload")

    print("Scanning local audio files (.flac/.m4a)...")
    local_tracks = scan_local_tracks(local_root)
    if not local_tracks:
        raise SystemExit("No local audio tracks found")

    matches, playlist_only, local_only = reconcile(
        playlist_tracks=playlist_tracks,
        local_tracks=local_tracks,
        duration_tolerance=max(0.0, float(args.duration_tolerance)),
        strict_artist=bool(args.strict_artist),
    )
    local_only_unique = collapse_local_only(local_only)

    print_section("Summary")
    print(f"Playlist tracks: {len(playlist_tracks)}")
    print(f"Local audio files: {len(local_tracks)}")
    print(f"Matched tracks: {len(matches)}")
    print(f"Playlist-only tracks: {len(playlist_only)}")
    print(f"Local-only files: {len(local_only)}")
    print(f"Local-only unique songs: {len(local_only_unique)}")

    print_playlist_only(playlist_only, max_print=max(1, args.max_print))
    print_local_only(local_only_unique, max_print=max(1, args.max_print))

    if args.out_dir:
        out_dir = args.out_dir.expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        storefront = storefront_from_playlist_url(args.playlist_url)

        report_path = out_dir / "reconcile_report.json"
        playlist_only_csv = out_dir / "playlist_only.csv"
        local_only_csv = out_dir / "local_only.csv"

        report_payload = {
            "playlist_url": args.playlist_url,
            "local_root": str(local_root),
            "counts": {
                "playlist_tracks": len(playlist_tracks),
                "local_audio_files": len(local_tracks),
                "matched_tracks": len(matches),
                "playlist_only_tracks": len(playlist_only),
                "local_only_files": len(local_only),
                "local_only_unique_songs": len(local_only_unique),
            },
            "playlist_only": [
                {
                    "num": row.num,
                    "title": row.title,
                    "artist": row.artist,
                    "album": row.album,
                    "track_id": row.track_id,
                    "isrc": row.isrc,
                    "duration_s": row.duration_s,
                }
                for row in playlist_only
            ],
            "local_only": [
                {
                    "title": track.title,
                    "artist": track.artist,
                    "album": track.album,
                    "path": str(track.path),
                    "ext": track.ext,
                    "isrc": track.isrc,
                    "duration_s": track.duration_s,
                    "variant_count": variant_count,
                }
                for track, variant_count in local_only_unique
            ],
        }
        report_path.write_text(
            json.dumps(report_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        write_csv_playlist_only(playlist_only, storefront, playlist_only_csv)
        write_csv_local_only(local_only_unique, storefront, local_only_csv)

        print_section("Wrote Files")
        print(report_path)
        print(playlist_only_csv)
        print(local_only_csv)


if __name__ == "__main__":
    main()
