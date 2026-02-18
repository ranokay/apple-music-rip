# New Features Built on apps/apple-music-downloader

This project layers a set of custom features on top of the upstream Apple Music downloader. The list below captures what has been implemented in this repo (from TODO.md and related changes).

## General Improvements

- **Improved logging**
  - More informative and user-friendly log messages.
  - Clearer error reporting and status updates.
- **Enhanced configuration options**
  - Additional flags and settings for greater control over downloads.
- **Better performance**
  - Optimizations to speed up download and processing times.
- **Increased stability**
  - Bug fixes and improvements to reduce crashes and errors.

## Download Modes

- **Lyrics-only (`--lyrics-only`)**
  - Fetches lyrics without downloading audio.
  - Honors `save-lrc-file` and `embed-lrc` (embedding is skipped because no audio file exists).
  - Writes `.lrc` / `.ttml` using the same filename format as audio (e.g., `01 - Song Title.ttml`).
  - Skips stations/music videos and avoids re-writing lyrics if the file already exists.
  - Handles missing lyrics for the language option from config `language: "en-gb&l%5Bscript%5D=en-Latn"`. If not found, falls back to any available lyrics (`language: ""`).
  - Disabled when `--covers-only` is active.

- **Covers-only (`--covers-only`)**
  - Album mode: downloads album cover (and optionally artist cover) then exits without track downloads.
  - Playlist mode: writes per-album covers derived from playlist tracks.
  - Respects `--select-tracks` to determine which albums to include.
  - Downloads animated covers only for Dolby Atmos albums/eps/singles. Downloads only `square_animated_artwork.mp4` without `tall_animated_artwork.mp4`.
  - Disabled when `--lyrics-only` is active.

- **Download order**
  - First downloads audio tracks, then lyrics, then covers (if applicable). So it won't create folders with just covers/lyrics if audio tracks fail.
  - If multiple formats are requested, downloads lossless/lossy formats first, then Dolby Atmos last.

## Selection, Preview, and Web UI Support

- **Preview mode (`--preview`)**
  - Outputs JSON metadata for album/playlist/song, used by the web UI.
  - Supports `?i=` preselection for album links.
  - Song previews auto-select track 1.
  - Playlist previews dedupe duplicates by default and expose `original_track_count` / `duplicates_removed` in JSON when matches are removed.

- **CLI track selection (`--select-tracks`)**
  - Accepts lists and ranges (e.g., `1,2,5-7`).
  - Forces selection mode even without interactive prompts.
  - Works for albums and playlists.

- **Playlist pre-download dedupe (`--no-playlist-dedupe`)**
  - Playlist downloads dedupe before selection and ripping using:
    - ISRC (primary)
    - normalized title+artist+type+content-rating with duration tolerance fallback (2s)
  - Keeps album/EP versions over single versions where duplicates collide.
  - Can be disabled with `--no-playlist-dedupe`.

## Flow Control & Safety

- **Stop signal handling (`stop.signal`)**
  - Clears stale stop file at startup.
  - Checks for stop requests between queues, album/playlist loops, and per-track processing.
  - Gracefully exits with user feedback.

- **Non-interactive retry behavior**
  - When stdin is not a TTY, the downloader aborts retries instead of prompting.

- **Wrapper connection refusal detection**
  - If decryption port refuses connections, retries are aborted to avoid infinite loops.

## Library Organization

- **Release-type detection + folder routing**
  - Detects Albums / EPs / Singles using Apple metadata and name heuristics.
  - Routes releases into `Albums/`, `EPs/`, or `Singles/`.
  - Applies to covers-only paths as well.

- **Playlist album/artist grouping**
  - Playlist downloads are reorganized into per-artist/per-album folders.
  - Avoids dumping everything into a flat playlist folder and omits playlist name in the path.

- **Atmos folder suffix**
  - Appends `(Dolby Atmos)` to album/EP/single folder names when Atmos is selected.

## Atmos Handling

- **Atmos availability gating**
  - Checks the master manifest for Atmos variants before download.
  - Skips unsupported tracks early and avoids cover/lyrics work for Atmos-only requests.

- **Atmos tagging**
  - Adds `ALBUMVERSION: Dolby Atmos` to Atmos tracks for easy filtering in players.

## Cover & Lyrics Reuse Across Formats

- **Sibling reuse**
  - Copies cover art, artist cover, and lyric files from other format folders when available.
  - Avoids redundant downloads when formats are fetched sequentially.

## Download History Output

- **Structured history emission**
  - Emits `HISTORY:` JSON per track (artist, album, release type, IDs, track numbers).
  - Emits history even when a track already exists or a converted file is reused, keeping history consistent.
