# TODOs for Apple Music Downloader

- Lyrics-only downloads (--lyrics-only)
  - Adds a dedicated mode that only fetches lyrics (no audio).
  - Uses existing config flags save-lrc-file and embed-lrc (embed is skipped in lyrics-only because there’s no audio file).
  - Saves the .lrc/.ttml with the same filename format as audio so it matches track naming. (e.g. “01 - Song Title.ttml”)
- Covers-only downloads (--covers-only)
  - Album-level covers-only path that saves album cover (and optionally artist cover) then exits without downloading tracks.
  - Playlist-level covers-only path that only writes the album cover (per album when derived from playlist tracks) and skips audio.
  - Ensures covers are not downloaded in lyrics-only mode.
- Preview mode (--preview)
  - Outputs JSON metadata for album/playlist/song with track list, used by the web UI for selection.
  - Supports ?i= preselection for album links; song previews auto-preselect track 1.
- CLI track selection (--select-tracks)
  - Accepts comma/range selections (1,2,5-7) and forces selection mode even without interactive prompts.
  - Works for albums and playlists; integrates with existing --select logic.
- Stop signal handling (stop.signal)
  - Clears stale stop file at startup.
  - Checks for stop requests during queues, album/playlist loops, and per-track processing.
  - Gracefully aborts with user message and cleanup.
- Download history output (HISTORY: lines)
  - Emits structured history JSON per track (artist, album, release type, IDs, track number).
  - Also emits history when a track is already on disk (original or converted) so history stays consistent.
- Release-type detection + foldering
  - Adds EP/single detection using Apple metadata and heuristics.
  - Routes albums into Albums/, EPs/, Singles/ subfolders.
- Atmos availability gating
  - Checks master manifest for Atmos codec before download; skips unsupported tracks early.
  - Prevents cover/lyrics work on Atmos-only requests when not available.
- Atmos folder suffix
  - Appends “(Dolby Atmos)” to album/ep/single folder names when Atmos is selected.
- Playlist album/artist grouping
  - For playlists, tracks are reorganized into per-artist/per-album folders, instead of dumping into a flat playlist folder, similar to how albums are structured, and without playlist name in the path.
  - Uses album metadata when available for accurate artist/album names.
- Improved tag writing for multi-artist (collaborative) tracks
  - Forces AlbumArtist tag to the primary artist for consistent library grouping. (e.g AlbumArtist=Alan Walker, Artist=Alan Walker, SORANA; AlbumArtist=Hearts & Colors, Artist=Hearts & Colors & DREAMDNVR)
  - Removes redundant artist names from Title tag. (e.g. Title="Song Title (feat. XXX)" → Title="Song Title")
  - Replaces “&” with “,” in all tags for consistent multi-artist separation based on arist names, e.g. `Alan Walker & SORANA` → `Alan Walker, SORANA`; but for `Hearts & Colors & DREAMDNVR` → `Hearts & Colors, DREAMDNVR`. This helps some players (Symfonium, Navidrome, Subsonic based players etc.) that use comma as multi-artist separator.
  - Add `ALBUMVERSION: Dolby Atmos` tag to indicate Atmos tracks, useful for players to filter Atmos content.

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
