# TODOs for Apple Music Downloader

## utility scripts

- **scripts/dedupe_music.py — duplicate detection & cleanup**:

- Multi-stage duplicate detection
  - Strong match 1: ISRC
        Groups tracks with the same ISRC (per-extension + language marker + edition marker).
  - Strong match 2: FLAC audio MD5
        Uses “MD5 of the unencoded content” from MediaInfo for FLAC to detect identical audio.
  - Loose match: tags + duration
        Groups by normalized artist/title + language/edition markers, then clusters by duration tolerance.
- Language/edition awareness
  - Normalizes titles like JP Ver. → (japanese).
  - Detects language tokens (JP/KR/EN/CN/etc.) and edition markers (live, acoustic, remix, instrumental, etc.) to avoid collapsing distinct versions.
- Quality-based winner selection
  - For FLAC: prefers higher sample rate, higher bit depth, then folder priority and shorter path.
  - For M4A: uses folder priority and shorter path.
  - Folder priority: Albums > EPs > Singles > other.
- Lyrics & cover cleanup
  - If a duplicate audio file is removed, the script also deletes adjacent .ttml lyrics.
  - Optional cleanup of now-empty directories, including directories that only contain cover/lyrics files.
- Dry-run vs apply
  - Default is safe dry-run; --apply is required to actually delete.
  - Shows a planned operations list before any deletion.
- Optional AAC/M4A detection
  - By default scans .flac; --include-m4a includes .m4a in duplicate detection.
- Colorized output & terminal detection
  - Uses ANSI colors if supported; can force or disable colors.
- CLI options
  - root (library path), --apply, --dry-run, --include-m4a, --tag-match-seconds, --no-color, --force-color.

- **scripts/validate_library.py — library validation vs download history**:

- Validates against download history
  - Reads apps/web/output/download_history.json and compares it to on-disk library structure.
- Understands release types
  - Supports Albums, EPs, Singles subfolders under artist folders.
  - Handles “EPs” capitalization and fallback to flat folders if subfolder not found.
- Artist folder discovery
  - Direct artist folder match (normalized name).
  - Partial match fallback.
  - Supports playlist-structured folders: Apple Music/<Playlist>/<Artist>.
- Release folder matching
  - Normalizes and compares release names.
  - Handles folder names with year prefixes like [2024] - ....
- Track completeness checks
  - Uses track numbers from filenames (e.g. 01 - Track Name.m4a) when available.
  - Falls back to raw audio file count if numbers are missing.
- Detailed reporting
  - Separates missing, incomplete, and complete releases.
  - Verbose mode prints per-artist and per-release details.
- Export missing links
  - --export FILE writes all missing/incomplete items with:
    - Links to re-download
    - Suggested --select-tracks list for missing tracks
- Repo-aware defaults
  - History file default: apps/web/output/download_history.json.
  - Music dirs default:
    - downloads/alac
    - downloads/atmos
    - downloads/aac
