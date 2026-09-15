# Landing page (L20)

**Live: https://agent-sessions.khelsutra.guru** (also
`https://agent-sessions-site.avi-dullu.workers.dev`).

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

Merge the reviewed website PR first, then deploy its exact merged commit after
the owner approves deployment. A source merge or PyPI release does not update
this Cloudflare Worker automatically in the manual workflow.

Either connect the repo in the Cloudflare dashboard via **Workers Builds**
(project root `site/`), or once:

```bash
cd site && npx wrangler login && npx wrangler deploy
```

Cloudflare serves this site; GitHub Pages is not configured here. GitHub Actions
is enabled for this repository's CI and PyPI release, but neither workflow
deploys the website. Keep publication surfaces separate.

Before deployment, run the hub's `scripts/local_ci.sh`, preview the page at
desktop and mobile widths, and verify release/documentation links. After
deployment, check both live URLs for the 0.3.0 release link, `agent-archive init`,
the baseline guide and the product direction. Check any advertised extension
capabilities against the actual Marketplace version. This page uses the existing
router Output panel for watcher troubleshooting, so it can deploy independently
of the 0.2.2 extension release.

Rollback: redeploy the previous known-good website commit; no archive data,
package versions, DNS records or extension installations need to change.
