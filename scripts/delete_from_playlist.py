#!/usr/bin/env python3
"""
Delete songs from a music library based on an M3U8 playlist file.

Features:
- Takes playlist path and music directory path as parameters
- Auto-maps playlist paths to the provided music directory
- Deletes only audio files (.flac, .m4a) from playlist entries
- Deletes stereo/Atmos counterpart versions when present
- Deletes associated lyrics files (.lrc, .ttml, .txt)
- Removes empty directories and directories containing only lyrics/covers
"""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple
from urllib.parse import unquote, urlparse

AUDIO_EXTENSIONS = {".flac", ".m4a"}
ATMOS_SUFFIX = " (Dolby Atmos)"
LYRICS_EXTENSIONS = [".lrc", ".ttml", ".txt"]
COVER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
COVER_BASENAMES = {"cover", "folder", "album", "front", "artwork"}


class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


class Stats(NamedTuple):
    """Statistics for the deletion operation."""

    entries_processed: int
    audio_deleted: int
    counterpart_deleted: int
    lyrics_deleted: int
    covers_deleted: int
    dirs_deleted: int
    unmapped_entries: int
    not_found_entries: int
    skipped_non_audio_entries: int
    errors: int


def log_info(msg: str) -> None:
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")


def log_warning(msg: str) -> None:
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")


def log_error(msg: str) -> None:
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def log_delete(msg: str) -> None:
    print(f"  {Colors.RED}🗑{Colors.RESET} {Colors.DIM}{msg}{Colors.RESET}")


def log_skip(msg: str) -> None:
    print(f"  {Colors.DIM}⊘ {msg}{Colors.RESET}")


def parse_m3u8(playlist_path: Path) -> list[str]:
    """Parse M3U8 playlist and extract non-comment path lines."""
    paths: list[str] = []
    with open(playlist_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            paths.append(line)
    return paths


def normalize_playlist_entry(raw_path: str) -> str:
    """Normalize a playlist entry into a filesystem-style path string."""
    entry = raw_path.strip()

    if entry.lower().startswith("file://"):
        parsed = urlparse(entry)
        entry = unquote(parsed.path or "")
        if parsed.netloc and parsed.netloc.lower() != "localhost":
            entry = f"/{parsed.netloc}{entry}"
    else:
        entry = unquote(entry)

    return entry.replace("\\", "/")


def is_absolute_like(path_text: str) -> bool:
    """Treat POSIX absolute and Windows drive paths as absolute-like."""
    if path_text.startswith("/"):
        return True
    return (
        len(path_text) >= 3
        and path_text[0].isalpha()
        and path_text[1] == ":"
        and path_text[2] == "/"
    )


def absolute_suffix_parts(path_text: str) -> list[str]:
    """
    Build suffix parts for absolute-like paths for remapping onto base_dir.

    Examples:
    - /music/A/B.flac     -> ["music", "A", "B.flac"]
    - C:/music/A/B.flac   -> ["music", "A", "B.flac"]
    """
    normalized = path_text

    if normalized.startswith("/"):
        normalized = normalized.lstrip("/")
    elif (
        len(normalized) >= 3
        and normalized[0].isalpha()
        and normalized[1] == ":"
        and normalized[2] == "/"
    ):
        normalized = normalized[3:]

    return [part for part in normalized.split("/") if part]


def resolve_playlist_song_path(raw_path: str, base_dir: Path) -> Path | None:
    """
    Convert a playlist entry into an absolute path under base_dir.

    Resolution strategy:
    1) Relative paths: base_dir / entry
    2) Absolute paths already inside base_dir: use directly
    3) Other absolute paths: suffix-based mapping under base_dir, choosing the
       most specific unique existing file candidate
    """
    base_dir = base_dir.resolve()
    entry = normalize_playlist_entry(raw_path)
    if not entry:
        return None

    if not is_absolute_like(entry):
        candidate = (base_dir / Path(entry)).resolve()
        return candidate if candidate.is_relative_to(base_dir) else None

    if entry.startswith("/"):
        absolute_candidate = Path(entry).resolve()
        if absolute_candidate.is_relative_to(base_dir):
            return absolute_candidate

    parts = absolute_suffix_parts(entry)
    if not parts:
        return None

    matches: list[tuple[int, Path]] = []
    for idx in range(len(parts)):
        suffix = parts[idx:]
        candidate = (base_dir / Path(*suffix)).resolve()
        if not candidate.is_relative_to(base_dir):
            continue
        if candidate.is_file():
            matches.append((len(suffix), candidate))

    if not matches:
        return None

    longest = max(length for length, _ in matches)
    best = [candidate for length, candidate in matches if length == longest]
    if len(best) != 1:
        return None

    return best[0]


def get_alternate_version_path(song_path: Path) -> Path | None:
    """
    Get the stereo/Atmos counterpart path.

    - Stereo: *.flac in "Album" <-> Atmos: *.m4a in "Album (Dolby Atmos)"
    """
    ext = song_path.suffix.lower()
    parent = song_path.parent
    parent_name = parent.name

    if ext == ".flac":
        atmos_parent = parent.parent / f"{parent_name}{ATMOS_SUFFIX}"
        return atmos_parent / f"{song_path.stem}.m4a"

    if ext == ".m4a" and parent_name.endswith(ATMOS_SUFFIX):
        stereo_parent = parent.parent / parent_name[: -len(ATMOS_SUFFIX)]
        return stereo_parent / f"{song_path.stem}.flac"

    return None


def get_associated_lyrics_files(song_path: Path) -> list[Path]:
    """Get associated lyrics files (same stem, .lrc/.ttml/.txt)."""
    lyrics_files: list[Path] = []
    for ext in LYRICS_EXTENSIONS:
        lyrics_path = song_path.with_suffix(ext)
        if lyrics_path.exists():
            lyrics_files.append(lyrics_path)
    return lyrics_files


def is_lyrics_file(path: Path) -> bool:
    return path.suffix.lower() in LYRICS_EXTENSIONS


def is_cover_file(path: Path) -> bool:
    return (
        path.suffix.lower() in COVER_EXTENSIONS and path.stem.lower() in COVER_BASENAMES
    )


def should_delete_directory(dir_path: Path, ignored_paths: set[Path]) -> bool:
    """
    True when directory is effectively empty or has only lyrics/cover files.

    ignored_paths represent files already scheduled/deleted in this run, so
    dry-run cleanup mirrors execute-mode behavior.
    """
    if not dir_path.exists() or not dir_path.is_dir():
        return False

    effective_contents: list[Path] = []
    for item in dir_path.iterdir():
        resolved = item.resolve()
        if resolved in ignored_paths:
            continue
        effective_contents.append(item)

    if not effective_contents:
        return True

    for item in effective_contents:
        if item.is_dir():
            return False
        if not (is_lyrics_file(item) or is_cover_file(item)):
            return False

    return True


def delete_cleanup_directory(
    dir_path: Path, dry_run: bool, handled_paths: set[Path]
) -> tuple[bool, int, int, bool]:
    """
    Delete lyrics/cover files from a cleanup-eligible directory and remove it.

    Returns:
    - deleted_dir: directory deletion planned/performed
    - lyrics_removed: number of lyrics files removed by this step
    - covers_removed: number of cover files removed by this step
    - io_error: True only when an I/O error occurred
    """
    if not should_delete_directory(dir_path, handled_paths):
        return False, 0, 0, False

    lyrics_removed = 0
    covers_removed = 0

    removable_files: list[Path] = []
    for item in dir_path.iterdir():
        resolved = item.resolve()
        if resolved in handled_paths:
            continue
        if item.is_file():
            removable_files.append(item)

    for item in removable_files:
        resolved = item.resolve()
        if is_lyrics_file(item):
            lyrics_removed += 1
        elif is_cover_file(item):
            covers_removed += 1

        if dry_run:
            handled_paths.add(resolved)
            continue

        try:
            item.unlink()
            handled_paths.add(resolved)
        except OSError as e:
            log_error(f"Failed to delete {item}: {e}")
            return False, 0, 0, True

    if dry_run:
        return True, lyrics_removed, covers_removed, False

    try:
        dir_path.rmdir()
        return True, lyrics_removed, covers_removed, False
    except OSError as e:
        log_error(f"Failed to delete directory {dir_path}: {e}")
        return False, 0, 0, True


def delete_file(path: Path, dry_run: bool) -> tuple[bool, bool]:
    """
    Delete a file.

    Returns:
    - deleted: True if file existed and delete would happen/happened
    - io_error: True only when delete attempt failed with OSError
    """
    if not path.exists():
        return False, False

    if dry_run:
        return True, False

    try:
        path.unlink()
        return True, False
    except OSError as e:
        log_error(f"Failed to delete {path}: {e}")
        return False, True


def process_playlist(
    playlist_path: Path, base_dir: Path, dry_run: bool = True, verbose: bool = False
) -> Stats:
    """Process playlist and delete matched audio files with cleanup."""
    audio_deleted = 0
    counterpart_deleted = 0
    lyrics_deleted = 0
    covers_deleted = 0
    dirs_deleted = 0
    unmapped_entries = 0
    not_found_entries = 0
    skipped_non_audio_entries = 0
    errors = 0
    handled_paths: set[Path] = set()
    dirs_to_check: set[Path] = set()

    log_info(f"Parsing playlist: {Colors.CYAN}{playlist_path}{Colors.RESET}")
    song_paths = parse_m3u8(playlist_path)
    entries_processed = len(song_paths)
    log_info(f"Found {Colors.BOLD}{entries_processed}{Colors.RESET} playlist entries")
    print()

    base_dir = base_dir.resolve()

    for raw_path in song_paths:
        song_path = resolve_playlist_song_path(raw_path, base_dir)
        if song_path is None:
            unmapped_entries += 1
            if verbose:
                log_skip(f"Unmapped entry: {raw_path}")
            continue

        song_path = song_path.resolve()
        relative_path = song_path.relative_to(base_dir)

        if verbose:
            print(f"\n{Colors.BOLD}Processing:{Colors.RESET} {relative_path}")

        if song_path.suffix.lower() not in AUDIO_EXTENSIONS:
            skipped_non_audio_entries += 1
            if verbose:
                log_skip(f"Skipped non-audio entry: {relative_path}")
            continue

        if song_path in handled_paths:
            if verbose:
                log_skip(f"Already handled: {relative_path}")
            continue

        if not song_path.exists():
            not_found_entries += 1
            if verbose:
                log_skip(f"Not found: {song_path}")
            continue

        files_to_delete: list[Path] = [song_path]

        alt_path = get_alternate_version_path(song_path)
        if alt_path is not None:
            alt_path = alt_path.resolve()
            if alt_path.is_relative_to(base_dir) and alt_path.exists():
                files_to_delete.append(alt_path)
                if verbose:
                    log_info(
                        f"Found alternate version: {alt_path.relative_to(base_dir)}"
                    )

        unique_targets: list[Path] = []
        seen_this_entry: set[Path] = set()
        for target in files_to_delete:
            target = target.resolve()
            if target in handled_paths or target in seen_this_entry:
                continue
            seen_this_entry.add(target)
            unique_targets.append(target)

        for target in unique_targets:
            deleted, io_error = delete_file(target, dry_run)
            if io_error:
                errors += 1
                continue
            if not deleted:
                continue

            handled_paths.add(target)
            rel_target = target.relative_to(base_dir)
            log_delete(f"Song: {rel_target}")
            audio_deleted += 1
            dirs_to_check.add(target.parent)

            if target != song_path:
                counterpart_deleted += 1

            for lyrics_path in get_associated_lyrics_files(target):
                lyrics_path = lyrics_path.resolve()
                if not lyrics_path.is_relative_to(base_dir):
                    continue
                if lyrics_path in handled_paths:
                    continue
                deleted_lyrics, io_error = delete_file(lyrics_path, dry_run)
                if io_error:
                    errors += 1
                    continue
                if not deleted_lyrics:
                    continue

                handled_paths.add(lyrics_path)
                log_delete(f"Lyrics: {lyrics_path.relative_to(base_dir)}")
                lyrics_deleted += 1
                dirs_to_check.add(lyrics_path.parent)

    if dirs_to_check:
        print()
        log_info("Cleaning up empty/lyrics-cover-only directories...")

    sorted_dirs = sorted(
        {d.resolve() for d in dirs_to_check}, key=lambda p: len(p.parts), reverse=True
    )
    deleted_dirs_seen: set[Path] = set()

    for dir_path in sorted_dirs:
        current = dir_path
        while current != base_dir and current.is_relative_to(base_dir):
            if current in deleted_dirs_seen:
                current = current.parent
                continue

            if not should_delete_directory(current, handled_paths):
                break

            deleted_dir, lyrics_removed, covers_removed, io_error = (
                delete_cleanup_directory(current, dry_run, handled_paths)
            )
            if io_error:
                errors += 1
                break
            if not deleted_dir:
                break

            deleted_dirs_seen.add(current)
            handled_paths.add(current.resolve())
            dirs_deleted += 1
            lyrics_deleted += lyrics_removed
            covers_deleted += covers_removed
            log_delete(f"Directory: {current.relative_to(base_dir)}/")
            current = current.parent

    return Stats(
        entries_processed=entries_processed,
        audio_deleted=audio_deleted,
        counterpart_deleted=counterpart_deleted,
        lyrics_deleted=lyrics_deleted,
        covers_deleted=covers_deleted,
        dirs_deleted=dirs_deleted,
        unmapped_entries=unmapped_entries,
        not_found_entries=not_found_entries,
        skipped_non_audio_entries=skipped_non_audio_entries,
        errors=errors,
    )


def print_summary(stats: Stats, dry_run: bool) -> None:
    """Print summary of operations."""
    print()
    mode = (
        f"{Colors.YELLOW}DRY RUN{Colors.RESET}"
        if dry_run
        else f"{Colors.GREEN}COMPLETED{Colors.RESET}"
    )
    print(f"{Colors.BOLD}{'═' * 50}{Colors.RESET}")
    print(f"{Colors.BOLD}Summary{Colors.RESET} ({mode})")
    print(f"{Colors.BOLD}{'═' * 50}{Colors.RESET}")
    print(
        f"  Playlist entries:     {Colors.CYAN}{stats.entries_processed}{Colors.RESET}"
    )
    print(f"  Audio deleted:        {Colors.CYAN}{stats.audio_deleted}{Colors.RESET}")
    print(
        f"  Counterparts deleted: {Colors.CYAN}{stats.counterpart_deleted}{Colors.RESET}"
    )
    print(f"  Lyrics deleted:       {Colors.CYAN}{stats.lyrics_deleted}{Colors.RESET}")
    print(f"  Covers deleted:       {Colors.CYAN}{stats.covers_deleted}{Colors.RESET}")
    print(f"  Directories deleted:  {Colors.CYAN}{stats.dirs_deleted}{Colors.RESET}")
    print(
        f"  Unmapped entries:     {Colors.CYAN}{stats.unmapped_entries}{Colors.RESET}"
    )
    print(
        f"  Not found entries:    {Colors.CYAN}{stats.not_found_entries}{Colors.RESET}"
    )
    print(
        f"  Skipped non-audio:    {Colors.CYAN}{stats.skipped_non_audio_entries}{Colors.RESET}"
    )
    if stats.errors > 0:
        print(f"  I/O errors:           {Colors.RED}{stats.errors}{Colors.RESET}")
    print(f"{Colors.BOLD}{'═' * 50}{Colors.RESET}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete songs from music library based on M3U8 playlist",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s playlist.m3u8 /music              # Dry run (preview changes)
  %(prog)s playlist.m3u8 /music --execute    # Actually delete files
  %(prog)s playlist.m3u8 /music -v           # Verbose dry run
        """,
    )

    parser.add_argument("playlist", type=Path, help="Path to M3U8 playlist file")
    parser.add_argument("directory", type=Path, help="Base music directory path")

    parser.add_argument(
        "-x",
        "--execute",
        action="store_true",
        help="Actually delete files (default is dry run)",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose output"
    )

    parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    if not args.playlist.exists():
        log_error(f"Playlist file not found: {args.playlist}")
        return 1

    if not args.directory.exists():
        log_error(f"Directory not found: {args.directory}")
        return 1

    if not args.directory.is_dir():
        log_error(f"Not a directory: {args.directory}")
        return 1

    print()
    print(f"{Colors.BOLD}{Colors.MAGENTA}╔{'═' * 48}╗{Colors.RESET}")
    print(
        f"{Colors.BOLD}{Colors.MAGENTA}║{Colors.RESET}  🎵 Music Library Playlist Cleaner              {Colors.BOLD}{Colors.MAGENTA}║{Colors.RESET}"
    )
    print(f"{Colors.BOLD}{Colors.MAGENTA}╚{'═' * 48}╝{Colors.RESET}")
    print()

    dry_run = not args.execute

    if dry_run:
        log_warning("DRY RUN MODE - No files will be deleted")
        log_info(f"Use {Colors.BOLD}--execute{Colors.RESET} to actually delete files")
    else:
        log_warning(
            f"{Colors.RED}EXECUTE MODE - Files will be permanently deleted!{Colors.RESET}"
        )

    print()
    log_info(f"Music directory: {Colors.CYAN}{args.directory.absolute()}{Colors.RESET}")

    stats = process_playlist(
        playlist_path=args.playlist,
        base_dir=args.directory,
        dry_run=dry_run,
        verbose=args.verbose,
    )

    print_summary(stats, dry_run)

    if dry_run and stats.audio_deleted > 0 and not args.yes:
        print()
        try:
            response = input(
                f"{Colors.YELLOW}Run with --execute to delete these files. Continue? [y/N]: {Colors.RESET}"
            )
            if response.lower() in ("y", "yes"):
                print()
                log_info("Re-running with --execute...")
                stats = process_playlist(
                    playlist_path=args.playlist,
                    base_dir=args.directory,
                    dry_run=False,
                    verbose=args.verbose,
                )
                print_summary(stats, dry_run=False)
        except (KeyboardInterrupt, EOFError):
            print()
            log_info("Aborted.")
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
