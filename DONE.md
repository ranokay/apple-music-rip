# Progress Tracker

## Feature Checklist

- [ ] CLI flags: `--preview`, `--select-tracks`, `--lyrics-only`, `--covers-only` (validated)
- [ ] Preview JSON output for album/playlist/song (validated)
- [ ] Release-type detection + folder routing (validated)
- [ ] Playlist album/artist grouping (validated)
- [ ] Track selection parsing + non-interactive behavior (validated)
- [ ] Audio → lyrics → covers ordering (validated)
- [ ] Lyrics-only flow with fallback language + reuse (validated)
- [ ] Covers-only flow with Atmos-only animated artwork (validated)
- [ ] Asset reuse across formats (covers/lyrics) (validated)
- [ ] Atmos gating + Atmos tagging (validated)
- [ ] Stop signal handling + wrapper refusal retry abort (validated)
- [ ] HISTORY emission for successes + already-existing tracks (validated)
- [ ] Web UI alignment + responsive overflow updates (validated)
- [ ] Remove unused UI component(s) (validated)

## Tests Run

- [ ] `go test ./...` (fails: module import `main` not importable in this environment)
- [x] `bun run build` (apps/web)

## Manual Verification Checklist

- [ ] Preview outputs valid JSON for album/playlist/song URLs
- [ ] `--select-tracks` downloads only requested tracks
- [ ] `--lyrics-only` writes lyric files and skips audio
- [ ] `--covers-only` writes album covers and skips audio
- [ ] Atmos-only requests skip non-Atmos tracks before downloads
- [ ] Stop signal exits between queue items and tracks
- [ ] `HISTORY:` lines emitted for existing and new tracks
- [ ] Playlist downloads grouped into artist/album folders
- [ ] Playlist folders include release year from album metadata
- [ ] Playlist downloads use album track numbers (not playlist order)
- [ ] Playlist downloads save artist covers when enabled
- [ ] Atmos-only/lyrics/covers skip albums without matching formats (no empty folders)
- [ ] Covers/lyrics multi-format honors selected formats
- [ ] UI renders cleanly on mobile/tablet/desktop; logs wrap
