# Article / post schema (public site)

Used when a human or a named companion (future: Jennifer’s Grok companion) assembles a piece and asks it to be posted.

1. Draft stays off the live feed until **go**.
2. Every factual sentence needs a source URL or official citation.
3. Labels on the piece: `confirmed` | `question` | `advocacy` | `opinion` (opinion lane is closed until opened on purpose).
4. Eve may add `eve_read` — a public-record question, not a verdict.
5. Posting writes a new object into `entries.json` (newest first) and optionally `articles/YYYY-MM-DD-slug.md`.

```json
{
  "date": "YYYY-MM-DD",
  "title": "",
  "source": "",
  "url": "",
  "summary": "",
  "area": "SCJC | Elections | Campaign finance | Family | Criminal | Civil | Probate | Appellate | Legislation",
  "county": "",
  "status": "confirmed",
  "eve_read": "optional",
  "posted_by": "human | companion:<name>",
  "approved_by": ""
}
```
