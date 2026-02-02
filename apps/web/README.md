# Apple Music Rip Web (Astro + Elysia)

This app replaces the old Flask UI with an Astro front-end and an Elysia API server.

## Development

```bash
bun install
bun run dev:all
```

- UI: `astro dev` on <http://localhost:4321>
- API: Elysia on <http://localhost:3001> (proxied by Astro during dev)

If you prefer separate terminals:

```bash
bun run dev:ui
bun run dev:api
```

## Production

```bash
bun run build
bun run start
```

The Elysia server will serve the static `dist/` output and the `/api/*` routes.
