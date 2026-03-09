---
name: "patsearch"
description: "Use when the user needs to query patent records through a custom search API that accepts JSON payload keys `q`, `f`, `s`, and `o`, then save structured JSON results; run `scripts/patsearch_search.py` for repeatable requests with endpoint and base URL overrides."
---

# PatSearch

## Quick start
- Set `PATSEARCH_API_KEY`.
- Optionally set `PATSEARCH_BASE_URL`.
- Run `scripts/patsearch_search.py` with `--q` or `--body-file`.

## Core workflow
1. Build a JSON query:
   - Required: `q`
   - Optional: `f`, `s`, `o`
2. Run the script with the desired endpoint path (default `patent`).
3. Save output JSON with `--out`, or let the script auto-name output files.
4. Summarize key fields from the returned JSON (`count`, `total_hits`, and records).

## CLI usage
```bash
python scripts/patsearch_search.py --q '{"_contains":{"patent_title":"battery"}}'
python scripts/patsearch_search.py --endpoint patent/us_patent_citation --body-file query.json
python scripts/patsearch_search.py --q '{}' --o '{"size":10}' --out results.json
python scripts/patsearch_search.py --base-url "https://your-endpoint.example/api/v1" --q '{}'
```

## Environment
- `PATSEARCH_API_KEY`: required for live requests unless `--api-key` is passed.
- `PATSEARCH_BASE_URL`: optional default base URL unless `--base-url` is passed.

## Dependencies
Prefer `uv`:
```bash
uv pip install requests
```

Fallback:
```bash
python -m pip install requests
```

## Notes
- Keep request payload keys limited to `q`, `f`, `s`, and `o`.
- `o.size` must be an integer and must not exceed `1000`.
- The script writes JSON responses and auto-versions output filenames if needed.
