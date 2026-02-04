# Progress Tracker

## Feature Checklist

- [x] CLI flags: `--preview`, `--select-tracks`, `--lyrics-only`, `--covers-only` (validated)
- [x] Preview JSON output for album/playlist/song (validated)
- [x] Release-type detection + folder routing (validated)
- [x] Playlist album/artist grouping (validated)
- [x] Track selection parsing + non-interactive behavior (validated)
- [x] Audio → lyrics → covers ordering (validated)
- [x] Lyrics-only flow with fallback language + reuse (validated)
- [x] Covers-only flow with Atmos-only animated artwork (validated)
- [x] Asset reuse across formats (covers/lyrics) (validated)
- [x] Atmos gating + Atmos tagging (validated)
- [x] Stop signal handling + wrapper refusal retry abort (validated)
- [x] HISTORY emission for successes + already-existing tracks (validated)
- [x] Web UI alignment + responsive overflow updates (validated)
- [x] Remove unused UI component(s) (validated)

## Tests Run

- [ ] `go test ./...` (fails: module import `main` not importable in this environment)
- [x] `bun run build` (apps/web)

## Manual Verification Checklist

- [x] Preview outputs valid JSON for album/playlist/song URLs
- [x] `--select-tracks` downloads only requested tracks
- [x] `--lyrics-only` writes lyric files and skips audio
- [x] `--covers-only` writes album covers and skips audio
- [x] Atmos-only requests skip non-Atmos tracks before downloads
- [x] Stop signal exits between queue items and tracks
- [x] `HISTORY:` lines emitted for existing and new tracks
- [x] Playlist downloads grouped into artist/album folders
- [x] Playlist folders include release year from album metadata
- [x] Playlist downloads use album track numbers (not playlist order)
- [x] Playlist downloads save artist covers when enabled
- [x] Atmos-only/lyrics/covers skip albums without matching formats (no empty folders)
- [x] Covers/lyrics multi-format honors selected formats
- [x] UI renders cleanly on mobile/tablet/desktop; logs wrap
