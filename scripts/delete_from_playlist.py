#!/usr/bin/env python3
"""
Delete songs from music library based on an M3U8 playlist file.

Features:
- Takes music directory path as a parameter
- Deletes associated lyrics files (.lrc, .txt)
- Cleans up empty directories
- Removes folders with only cover art remaining
- Deletes both stereo (FLAC) and Dolby Atmos (M4A) versions
"""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple


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

    songs_deleted: int
    lyrics_deleted: int
    dirs_deleted: int
    atmos_pairs_found: int
    errors: int


def log_info(msg: str) -> None:
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")


def log_success(msg: str) -> None:
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def log_warning(msg: str) -> None:
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")


def log_error(msg: str) -> None:
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def log_delete(msg: str) -> None:
    print(f"  {Colors.RED}🗑{Colors.RESET} {Colors.DIM}{msg}{Colors.RESET}")


def log_skip(msg: str) -> None:
    print(f"  {Colors.DIM}⊘ {msg}{Colors.RESET}")


def parse_m3u8(playlist_path: Path) -> list[str]:
    """Parse M3U8 playlist and extract file paths."""
    paths = []
    with open(playlist_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and metadata lines
            if not line or line.startswith("#"):
                continue
            paths.append(line)
    return paths


def get_alternate_version_path(song_path: Path) -> Path | None:
    """
    Get the alternate version path (stereo <-> Dolby Atmos).

    Dolby Atmos folders have "(Dolby Atmos)" suffix.
    Stereo versions are .flac, Atmos versions are .m4a
    """
    parent = song_path.parent
    parent_name = parent.name

    # Check if this is a Dolby Atmos version
    if "(Dolby Atmos)" in parent_name:
        # Find stereo version
        stereo_parent_name = parent_name.replace(" (Dolby Atmos)", "")
        stereo_parent = parent.parent / stereo_parent_name
        # Change extension from .m4a to .flac
        stereo_name = song_path.stem + ".flac"
        return stereo_parent / stereo_name
    else:
        # This might be stereo, look for Atmos version
        atmos_parent_name = parent_name.rstrip(")")
        # Insert "(Dolby Atmos)" before the closing part if any
        # Typical format: [2025] - Album Name
        # Atmos format: [2025] - Album Name (Dolby Atmos)
        atmos_parent_name = parent_name + " (Dolby Atmos)"
        atmos_parent = parent.parent / atmos_parent_name
        # Change extension from .flac to .m4a
        atmos_name = song_path.stem + ".m4a"
        return atmos_parent / atmos_name


def get_lyrics_files(song_path: Path) -> list[Path]:
    """Get associated lyrics files for a song."""
    lyrics_extensions = [".lrc", ".txt"]
    lyrics_files = []
    stem = song_path.stem
    parent = song_path.parent

    for ext in lyrics_extensions:
        lyrics_path = parent / (stem + ext)
        if lyrics_path.exists():
            lyrics_files.append(lyrics_path)

    return lyrics_files


def is_cover_file(path: Path) -> bool:
    """Check if a file is a cover art file."""
    cover_names = {"cover", "folder", "album", "front", "artwork"}
    cover_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

    return path.suffix.lower() in cover_extensions and path.stem.lower() in cover_names


def is_metadata_file(path: Path) -> bool:
    """Check if a file is a metadata/non-music file that can be deleted with empty folders."""
    metadata_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".bmp",
        ".lrc",
        ".txt",
        ".nfo",
        ".cue",
        ".log",
    }
    return path.suffix.lower() in metadata_extensions


def should_delete_directory(dir_path: Path) -> bool:
    """
    Check if a directory should be deleted.
    Returns True if directory is empty or contains only cover art/metadata files.
    """
    if not dir_path.exists() or not dir_path.is_dir():
        return False

    contents = list(dir_path.iterdir())

    # Empty directory
    if not contents:
        return True

    # Check if all remaining files are just covers/metadata
    for item in contents:
        if item.is_dir():
            return False  # Has subdirectories, don't delete
        if not is_metadata_file(item):
            return False  # Has non-metadata files

    return True


def cleanup_empty_parents(path: Path, base_dir: Path) -> list[Path]:
    """
    Clean up empty parent directories up to base_dir.
    Returns list of deleted directories.
    """
    deleted = []
    current = path.parent

    while current != base_dir and current.is_relative_to(base_dir):
        if should_delete_directory(current):
            deleted.append(current)
            current = current.parent
        else:
            break

    return deleted


def delete_file(path: Path, dry_run: bool) -> bool:
    """Delete a file. Returns True if successful."""
    if not path.exists():
        return False

    if dry_run:
        return True

    try:
        path.unlink()
        return True
    except OSError as e:
        log_error(f"Failed to delete {path}: {e}")
        return False


def delete_directory(path: Path, dry_run: bool) -> bool:
    """Delete a directory and all its contents. Returns True if successful."""
    if not path.exists():
        return False

    if dry_run:
        return True

    try:
        # Delete all files in directory first
        for item in path.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                delete_directory(item, dry_run)
        path.rmdir()
        return True
    except OSError as e:
        log_error(f"Failed to delete directory {path}: {e}")
        return False


def process_playlist(
    playlist_path: Path, base_dir: Path, dry_run: bool = True, verbose: bool = False
) -> Stats:
    """Process the playlist and delete songs."""

    songs_deleted = 0
    lyrics_deleted = 0
    dirs_deleted = 0
    atmos_pairs_found = 0
    errors = 0

    # Track directories to clean up at the end
    dirs_to_check: set[Path] = set()

    # Parse playlist
    log_info(f"Parsing playlist: {Colors.CYAN}{playlist_path}{Colors.RESET}")
    song_paths = parse_m3u8(playlist_path)
    log_info(f"Found {Colors.BOLD}{len(song_paths)}{Colors.RESET} songs in playlist")
    print()

    # Process each song
    for raw_path in song_paths:
        # Convert path to be relative to base_dir
        # Paths in m3u8 start with /music/, we need to make them relative
        if raw_path.startswith("/music/"):
            relative_path = raw_path[7:]  # Remove "/music/"
        elif raw_path.startswith("/"):
            relative_path = raw_path[1:]
        else:
            relative_path = raw_path

        song_path = base_dir / relative_path

        if verbose:
            print(f"\n{Colors.BOLD}Processing:{Colors.RESET} {relative_path}")

        # Check if main file exists
        if not song_path.exists():
            if verbose:
                log_skip(f"Not found: {song_path}")
            errors += 1
            continue

        files_to_delete: list[Path] = [song_path]

        # Find alternate version (stereo <-> Atmos)
        alt_path = get_alternate_version_path(song_path)
        if alt_path and alt_path.exists():
            files_to_delete.append(alt_path)
            atmos_pairs_found += 1
            if verbose:
                log_info(f"Found alternate version: {alt_path.relative_to(base_dir)}")

        # Find lyrics files for all versions
        for f in list(files_to_delete):
            lyrics = get_lyrics_files(f)
            files_to_delete.extend(lyrics)

        # Delete files
        for f in files_to_delete:
            rel_path = f.relative_to(base_dir) if f.is_relative_to(base_dir) else f

            if f.suffix.lower() in {".lrc", ".txt"}:
                if delete_file(f, dry_run):
                    log_delete(f"Lyrics: {rel_path}")
                    lyrics_deleted += 1
            else:
                if delete_file(f, dry_run):
                    log_delete(f"Song: {rel_path}")
                    songs_deleted += 1
                    dirs_to_check.add(f.parent)

    print()
    log_info("Cleaning up empty directories...")

    # Clean up directories
    # Sort by depth (deepest first) to clean up properly
    sorted_dirs = sorted(dirs_to_check, key=lambda p: len(p.parts), reverse=True)

    for dir_path in sorted_dirs:
        # Walk up the directory tree
        current = dir_path
        while current != base_dir and current.is_relative_to(base_dir):
            if should_delete_directory(current):
                rel_path = current.relative_to(base_dir)
                if delete_directory(current, dry_run):
                    log_delete(f"Directory: {rel_path}/")
                    dirs_deleted += 1
                current = current.parent
            else:
                break

    return Stats(
        songs_deleted=songs_deleted,
        lyrics_deleted=lyrics_deleted,
        dirs_deleted=dirs_deleted,
        atmos_pairs_found=atmos_pairs_found,
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
    print(f"  Songs deleted:        {Colors.CYAN}{stats.songs_deleted}{Colors.RESET}")
    print(f"  Lyrics deleted:       {Colors.CYAN}{stats.lyrics_deleted}{Colors.RESET}")
    print(f"  Directories deleted:  {Colors.CYAN}{stats.dirs_deleted}{Colors.RESET}")
    print(
        f"  Stereo/Atmos pairs:   {Colors.CYAN}{stats.atmos_pairs_found}{Colors.RESET}"
    )
    if stats.errors > 0:
        print(f"  Errors/Not found:     {Colors.RED}{stats.errors}{Colors.RESET}")
    print(f"{Colors.BOLD}{'═' * 50}{Colors.RESET}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete songs from music library based on M3U8 playlist",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /music playlist.m3u8              # Dry run (preview changes)
  %(prog)s /music playlist.m3u8 --execute    # Actually delete files
  %(prog)s /music playlist.m3u8 -v           # Verbose dry run
        """,
    )

    parser.add_argument("directory", type=Path, help="Base music directory path")

    parser.add_argument("playlist", type=Path, help="Path to M3U8 playlist file")

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

    # Validate inputs
    if not args.playlist.exists():
        log_error(f"Playlist file not found: {args.playlist}")
        return 1

    if not args.directory.exists():
        log_error(f"Directory not found: {args.directory}")
        return 1

    if not args.directory.is_dir():
        log_error(f"Not a directory: {args.directory}")
        return 1

    # Print header
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

    # Run the process
    stats = process_playlist(
        playlist_path=args.playlist,
        base_dir=args.directory,
        dry_run=dry_run,
        verbose=args.verbose,
    )

    print_summary(stats, dry_run)

    # If dry run and there are files to delete, prompt for execution
    if dry_run and stats.songs_deleted > 0 and not args.yes:
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
