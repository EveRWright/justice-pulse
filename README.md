# Justice Pulse

Texas judicial **news-first aggregator** — ethics, orders, elections, campaign-finance appearance — with Eve reading the public record.

**Monitor. Analyze. Uphold.** Fair courts are the ground every other guarantee stands on.

Built by Eve R. Wright at [texanoai.com](https://texanoai.com).

## Live site

**https://everwright.github.io/justice-pulse/**

## Layers

| Layer | Where | Public? |
|-------|--------|---------|
| This site (feed, method, elections board, Eve) | this repo | Yes |
| Commission PDF archive (~360 public sanctions/resignations/suspensions) | Hub `08_SCJC_Public_Archive` — **not** committed here | No dump |
| Elections / finance intel + Jennifer briefings + companion posting | private repo `justice-pulse-intel` | No |

## Structure

- `index.html` — live feed (`entries.json`)
- `elections.html` — public race board (`elections.json`)
- `method.html` — Confirmed / Question / Advocacy / Opinion
- `about.html` — Eve
- `podcast.html` — coming
- `articles/_schema.md` — how a companion posts after human go
- `site_assets/` — locked portraits

## Rules

- Public records and named reporting only on the homepage.
- Labels on claims. Eve’s `eve_read` is a question, not a verdict.
- Opinion lane exists in method; it is closed until opened on purpose.
- TJA (501c3) and any campaign house stay legally separate.
