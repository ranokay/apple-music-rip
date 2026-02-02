# New Features Built on apps/apple-music-downloader

This project layers a set of custom features on top of the upstream Apple Music downloader. The list below captures what has been implemented in this repo (from TODO.md and related changes).

## Download Modes

- **Lyrics-only (`--lyrics-only`)**
  - Fetches lyrics without downloading audio.
  - Honors `save-lrc-file` and `embed-lrc` (embedding is skipped because no audio file exists).
  - Writes `.lrc` / `.ttml` using the same filename format as audio (e.g., `01 - Song Title.ttml`).
  - Skips stations/music videos and avoids re-writing lyrics if the file already exists.

- **Covers-only (`--covers-only`)**
  - Album mode: downloads album cover (and optionally artist cover) then exits without track downloads.
  - Playlist mode: writes per-album covers derived from playlist tracks.
  - Respects `--select-tracks` to determine which albums to include.
  - Disabled when `--lyrics-only` is active.

## Selection, Preview, and Web UI Support

- **Preview mode (`--preview`)**
  - Outputs JSON metadata for album/playlist/song, used by the web UI.
  - Supports `?i=` preselection for album links.
  - Song previews auto-select track 1.

- **CLI track selection (`--select-tracks`)**
  - Accepts lists and ranges (e.g., `1,2,5-7`).
  - Forces selection mode even without interactive prompts.
  - Works for albums and playlists.

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

## Tagging & Metadata Improvements

- **Multi-artist tagging**
  - Forces `AlbumArtist` to the primary artist for consistent grouping.
  - Removes redundant artist names and `feat.` fragments from `Title`.
  - Replaces `&` with `,` in tag values for consistent multi-artist separation.
  - FLAC: writes multiple `ARTISTS` tags (`ARTISTS=Artist A`, `ARTISTS=Artist B`).
  - M4A/MP4: writes multiple `©ART` atoms via a local `go-mp4tag` fork while keeping a joined `Artist` string for compatibility.

- **Unicode normalization + filename sanitization**
  - Normalizes text to NFC and strips forbidden filesystem characters.
  - Ensures consistent matching across platforms.

## Cover & Lyrics Reuse Across Formats

- **Sibling reuse**
  - Copies cover art, artist cover, and lyric files from other format folders when available.
  - Avoids redundant downloads when formats are fetched sequentially.

## Download History Output

- **Structured history emission**
  - Emits `HISTORY:` JSON per track (artist, album, release type, IDs, track numbers).
  - Emits history even when a track already exists or a converted file is reused, keeping history consistent.
