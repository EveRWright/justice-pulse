# Durable news catalog

`captures.jsonl` is append-merged metadata for every clip Justice Pulse has seen.

If a newsroom page 404s, the **title, date, source, snippet, and Wayback pointer** still live here and in git history.

- We do **not** republish full article HTML (copyright).
- `archive_url` is a Wayback Machine pointer (`web.archive.org/web/…`).
- Scheduled GitHub Actions re-run the wire several times a day and commit new rows.

Rebuild live feed from this file:

```bash
python3 ingest/fetch_wire.py --when 1d
```
