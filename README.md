# Apple Music Rip

A monorepo that stitches together:

- `apps/apple-music-downloader` (Go downloader)
- `apps/wrapper` (FairPlay wrapper runtime)
- `apps/web` (Astro + React + shadcn UI + Elysia API)

The web app replaces the old Flask UI and talks directly to the downloader and wrapper.

## Requirements

- Bun (for the web UI + API)
- Go (for running the downloader via `go run`)
- Docker (for the wrapper runtime container)
- ffmpeg (optional, for post-download conversions)

## Quick start

1. Build/run the wrapper runtime and sign in.
   - Follow the instructions in `apps/wrapper`.
   - The web app expects the container to be named `wrapper-runtime`.
2. Configure the downloader.
   - Edit `apps/apple-music-downloader/config.yaml` for tokens, folders, etc.
3. Run the web app.

```bash
cd apps/web
bun install
bun run dev:all
```

- UI: <http://localhost:4321>
- API: <http://localhost:3001> (proxied from the UI during dev)

If you prefer separate terminals:

```bash
bun run dev:ui
bun run dev:api
```

## Production

```bash
cd apps/web
bun run build
bun run start
```

The Elysia server will serve the static `dist/` output and `/api/*` routes on port 3001.

## Files & data

- Downloader config: `apps/apple-music-downloader/config.yaml`
- Download history (generated): `apps/download_history.json`

## Repo maintenance (subtrees)

```bash
# add upstream remotes (names are arbitrary)
git remote add amd https://github.com/zhaarey/apple-music-downloader.git
git remote add wrapper https://github.com/WorldObservationLog/wrapper.git

git fetch amd
git fetch wrapper

# import as subtrees into apps/...
git subtree add --prefix=apps/apple-music-downloader amd main
git subtree add --prefix=apps/wrapper wrapper main
```

To pull latest upstream later:

```bash
git fetch amd
git subtree pull --prefix=apps/apple-music-downloader amd main

git fetch wrapper
git subtree pull --prefix=apps/wrapper wrapper main
```
