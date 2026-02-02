# DONE

- Preview mode (--preview) with album/playlist/song metadata and preselection
- Lyrics-only mode (--lyrics-only) with skip logic and safe reuse of existing lyrics
- Covers-only mode (--covers-only) for album/playlist cover downloads
- CLI track selection (--select-tracks) parsing for albums/playlists
- Stop signal handling (stop.signal) across queue/album/playlist/track loops
- Non-interactive retry abort + wrapper connection-refused detection
- Release-type routing (Albums/EPs/Singles) + Dolby Atmos folder suffix
- Playlist album/artist grouping (no playlist-name paths)
- Atmos availability gating + ALBUMVERSION tag for Atmos tracks
- Cover & lyrics sibling reuse across formats
- Structured HISTORY JSON output per track (including existing files)
- Web UI/API improvements: clearer preview JSON errors and release info in modal
- CoreAudio (afconvert) ALAC -> FLAC conversion option on macOS

Skipped for now (per request):

- Tagging & Metadata Improvements
