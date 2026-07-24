# Landing page (L20)

Static, single-file landing page for the agent-sessions + agent-session-router
launch: motivation, design rationale, architecture, quick start, honest limits.

- `public/index.html` — the whole site. Self-contained (no external assets,
  no build step), light/dark via `prefers-color-scheme`.
- `wrangler.toml` — Cloudflare Worker (assets-only) config, mirroring the
  khelsutra.guru site pattern.

## Preview locally

```bash
python -m http.server --directory site/public 8788
```

## Deploy (owner)

Either connect the repo in the Cloudflare dashboard via **Workers Builds**
(project root `site/`), or once:

```bash
cd site && npx wrangler login && npx wrangler deploy
```

GitHub Pages is deliberately not used: GitHub Actions stay disabled on the
covered GitHub repos (Forgejo-primary backup policy), and branch-based Pages
deploys ride on Actions infrastructure.
