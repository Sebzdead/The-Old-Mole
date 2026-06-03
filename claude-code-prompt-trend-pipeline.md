# Implementation Spec: Left YouTube Trend-Sensing Pipeline

## What You Are Building

A weekly automated pipeline that:
1. Fetches recent videos from a curated list of left/Marxist YouTube channels
2. Retrieves transcripts for each video
3. Stores everything in a local SQLite cache to avoid reprocessing
4. Sends the corpus to the DeepSeek API for structural theme analysis
5. Outputs a weekly Markdown digest of podcast topic proposals
6. Runs automatically every Monday via GitHub Actions

The entire stack is Python. No web framework. No Docker. Keep it simple and flat.

---

## Project Structure

Create the following file tree exactly:

```
trend-sensor/
├── .github/
│   └── workflows/
│       └── weekly_digest.yml
├── config/
│   └── channels.yml
├── src/
│   ├── __init__.py
│   ├── fetcher.py
│   ├── transcripts.py
│   ├── cache.py
│   ├── analyzer.py
│   └── digest.py
├── digests/
│   └── .gitkeep
├── data/
│   └── .gitkeep
├── main.py
├── requirements.txt
└── .gitignore
```

The `data/` directory holds the SQLite database and must be gitignored.
The `digests/` directory holds output Markdown files and should be committed.

---

## Dependencies — requirements.txt

```
google-api-python-client==2.131.0
youtube-transcript-api==0.6.2
openai>=1.0.0
feedparser==6.0.11
PyYAML==6.0.1
python-dateutil==2.9.0
```

---

## Configuration — config/channels.yml

Populate with real channel IDs. The format is a list of objects with `id`, `name`, and
an optional `tier` field (`core` or `broad`). Core channels get full transcript analysis;
broad channels get title + description only, to manage API quota and cost.

```yaml
channels:
  - id: UCJNAmHGNKMWlRHvxR0gCHyg  # Novara Media
    name: "Novara Media"
    tier: core

  - id: UCaHNFIob5Ql5CKf5oh8bMEQ  # Citations Needed
    name: "Citations Needed"
    tier: core

  - id: UCvBS4iRcKHGGnWaHrBVoMvg  # The Real News Network
    name: "The Real News Network"
    tier: core

  - id: UC3NbMTy4LXrUO5XFaKLCHgg  # Jacobin
    name: "Jacobin"
    tier: core

  - id: UCof6JNvMGSNqhBNRnRSLEEQ  # Richard Wolff / Democracy at Work
    name: "Democracy at Work"
    tier: core

  - id: UCPHBfMvFKGEFg5UISC3D_Bg  # Current Affairs
    name: "Current Affairs"
    tier: broad

  - id: UCBmVHABDTFXNiPTwOKbfIiw  # Means TV
    name: "Means TV"
    tier: broad
```

Add more channels as needed. Channel IDs can be found in the channel's YouTube URL
or via the YouTube Data API channels.list endpoint with a forUsername query.

---

## Module Specs

### src/cache.py

Manages a SQLite database at `data/cache.db`.

Schema: two tables.

**Table `videos`**:
- `video_id` TEXT PRIMARY KEY
- `channel_id` TEXT NOT NULL
- `channel_name` TEXT NOT NULL
- `title` TEXT NOT NULL
- `description` TEXT
- `published_at` TEXT  (ISO 8601)
- `tier` TEXT  ('core' or 'broad')
- `fetched_at` TEXT  (ISO 8601, when we retrieved it)

**Table `transcripts`**:
- `video_id` TEXT PRIMARY KEY REFERENCES videos(video_id)
- `transcript_text` TEXT
- `word_count` INTEGER
- `fetched_at` TEXT

Provide these functions:
- `init_db()` — creates tables if they don't exist
- `is_video_cached(video_id: str) -> bool`
- `save_video(video: dict)` — inserts a video row; ignores conflicts
- `is_transcript_cached(video_id: str) -> bool`
- `save_transcript(video_id: str, text: str)`
- `get_corpus_since(days: int) -> list[dict]` — returns joined rows for all videos
  published within the last N days, including transcript text if available.
  Returns a list of dicts with keys: video_id, channel_name, title, description,
  published_at, tier, transcript_text (may be None).

### src/fetcher.py

Uses the YouTube Data API v3 via `googleapiclient.discovery`.

The API key is read from the environment variable `YOUTUBE_API_KEY`.

Provide these functions:

`get_channel_uploads(channel_id: str, channel_name: str, tier: str,
                     days_back: int = 7) -> list[dict]`

- Gets the uploads playlist ID from the channel's `contentDetails`
- Fetches `playlistItems.list` for that playlist, requesting `snippet` parts
- Filters to only videos published within `days_back` days
- Returns a list of dicts matching the `videos` table schema (without fetched_at,
  which the caller sets)
- Handles pagination; stop after 3 pages maximum to stay within quota
- Log a warning but do not crash if a channel fetch fails

`fetch_all_channels(channels: list[dict], days_back: int = 7) -> list[dict]`

- Iterates over the channels config list, calls `get_channel_uploads` for each
- Skips videos already in cache (call `is_video_cached` before appending)
- Returns the combined list of new videos
- Print progress: "Fetching [channel_name]... N new videos found"

### src/transcripts.py

Uses `youtube_transcript_api`.

Provide:

`fetch_transcript(video_id: str) -> str | None`

- Tries to get English transcript (manual preferred, auto-generated acceptable)
- If no English transcript is available, returns None — do not raise
- Joins all transcript segments into a single string
- Truncates to the first 2000 words (split on whitespace). This keeps token usage
  manageable while preserving the argument structure of most videos.
- Returns the truncated text, or None on any failure

`fetch_transcripts_for_corpus(videos: list[dict]) -> None`

- Only fetches transcripts for videos where tier == 'core' and transcript not cached
- For each such video, calls `fetch_transcript`, then `save_transcript`
- Print progress: "Transcript: [title] (N words)"
- Add a 1-second sleep between requests to be polite

### src/analyzer.py

This is the core module. It formats the corpus and sends it to the DeepSeek API.

The DeepSeek API key is read from `DEEPSEEK_API_KEY`. Use `openai.OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")`.
Model: `deepseek-v4-flash` (or `deepseek-v4-pro[1m]` if reasoning model is preferred — `deepseek-v4-flash` is recommended for standard tasks).
`max_tokens`: 4096.

#### Corpus Formatting

`format_corpus(corpus: list[dict]) -> str`

Formats the corpus as a structured plaintext block for the LLM. Group by tier.

For each **core** video: include channel name, title, published date, and full
transcript text (truncated as above). Format each entry as:

```
--- [Channel Name] | [Title] | [Date]
[transcript text]
```

For each **broad** video: include channel name, title, and description only. Format as:

```
--- [Channel Name] | [Title] | [Date]
[description, max 150 words]
```

If the total formatted corpus exceeds approximately 80,000 words, truncate by
dropping broad-tier entries first, then the oldest core entries, until it fits.
Log a warning when truncation occurs.

#### Analysis Prompt

This is the system prompt. Use it verbatim:

---

```
You are an analyst working for a Marxist podcast that covers current events and
political economy. Your task is to read a corpus of recent left and socialist
YouTube content and identify recurring structural themes — not individual news
stories, but the underlying contradictions, long-running crises, and social
anxieties that multiple sources are independently circling around this week.

You are looking for material that:
- Reveals a structural feature or contradiction of the capitalist system
- Can be analysed using Marxist or materialist frameworks (class, capital,
  imperialism, reproduction, alienation, etc.)
- Is substantive enough for a 30-60 minute podcast discussion
- Is NOT purely breaking news — it should have analytical depth or longevity

The themes you identify should span any domain: economic, political, cultural,
ecological, geopolitical, gender and reproduction, housing, media, technology,
or any other area where the crisis of capitalism manifests.

For each theme:
1. Give it a concise name (5 words or fewer)
2. Describe the underlying structural dynamic in 2-3 sentences — what
   contradiction or tendency of capitalism is producing this phenomenon?
3. Note which channels or content types are raising it (gives a sense of how
   widespread the concern is)
4. Suggest 2-3 specific podcast angles: framings, questions, or entry points
   that would make for a strong Marxist analysis rather than liberal commentary
5. Rate signal strength: HIGH (multiple independent sources, sustained concern),
   MEDIUM (a few sources, emerging), or LOW (single source, speculative)

Aim for 6-10 themes. Do not repeat obvious news summaries. Focus on the
structural, the systemic, and the analytically interesting.

Format your response as a clean Markdown document with one H2 heading per theme.
Do not include preamble or meta-commentary. Start directly with the first theme.
```

---

#### User Message

Format the user message as:

```
Here is this week's corpus of left YouTube content. Identify structural themes
as instructed.

CORPUS:

{formatted_corpus}
```

#### Function to expose:

`run_analysis(corpus: list[dict]) -> str`

- Calls `format_corpus`, builds the messages, calls the API
- Returns the full response text (the Markdown theme analysis)
- Raises clearly if the API call fails

### src/digest.py

`save_digest(analysis_text: str, run_date: str) -> str`

- Prepends a header to the analysis:
  ```markdown
  # Trend Digest — {run_date}
  _Generated by trend-sensor. {N} videos analysed from {M} channels._

  ---
  ```
- Saves to `digests/{run_date}.md`
- Returns the filepath

`print_summary(analysis_text: str) -> None`

- Prints the first 1000 characters of the analysis to stdout so GitHub Actions
  logs show something meaningful

---

## Orchestrator — main.py

```python
#!/usr/bin/env python3
"""
Weekly left YouTube trend-sensing pipeline.
Run directly or via GitHub Actions cron.
"""
```

Steps in order:
1. Load `config/channels.yml`
2. Call `cache.init_db()`
3. Call `fetcher.fetch_all_channels(channels, days_back=7)` to get new videos
4. Save all new videos to cache via `cache.save_video`
5. Call `transcripts.fetch_transcripts_for_corpus` for core-tier new videos
6. Call `cache.get_corpus_since(days=7)` to get the full week's corpus
7. If corpus is empty, print "No new videos this week. Exiting." and exit 0
8. Call `analyzer.run_analysis(corpus)`
9. Call `digest.save_digest(analysis, run_date)` where run_date is today in YYYY-MM-DD
10. Call `digest.print_summary(analysis)`
11. Print "Digest saved to {filepath}"

Use `datetime.date.today().isoformat()` for the run date.
Wrap the whole thing in a try/except that prints the error and exits with code 1.

---

## GitHub Actions — .github/workflows/weekly_digest.yml

```yaml
name: Weekly Trend Digest

on:
  schedule:
    - cron: '0 8 * * 1'   # Every Monday at 08:00 UTC
  workflow_dispatch:         # Allow manual trigger from Actions UI

jobs:
  run-digest:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run trend pipeline
        env:
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
        run: python main.py

      - name: Upload digest as artifact
        uses: actions/upload-artifact@v4
        with:
          name: weekly-digest-${{ github.run_id }}
          path: digests/

      - name: Commit digest to repository
        run: |
          git config user.name "trend-sensor-bot"
          git config user.email "bot@users.noreply.github.com"
          git add digests/
          git diff --cached --quiet || git commit -m "digest: $(date -u +%Y-%m-%d)"
          git push
```

Note: for the `git push` step to work, the default Actions token needs write
permission. Add this at the top level of the YAML (before `jobs:`):

```yaml
permissions:
  contents: write
```

---

## .gitignore

```
data/
*.db
__pycache__/
*.pyc
.env
.DS_Store
```

---

## Error Handling and Logging Expectations

- All functions should use `print()` for progress output (no logging framework needed)
- Any single channel or transcript failure should be caught, printed, and skipped —
  never crash the whole run
- API errors (YouTube quota exceeded, DeepSeek rate limit) should bubble up and
  cause a clean exit with a descriptive message
- Do not retry automatically — keep the logic simple

---

## Environment Variables Required

| Variable | Description |
|---|---|
| `YOUTUBE_API_KEY` | YouTube Data API v3 key from Google Cloud Console |
| `DEEPSEEK_API_KEY` | DeepSeek API key |

Both are secrets in GitHub Actions. For local development, export them in your shell
or use a `.env` file (add `.env` to .gitignore — do not use python-dotenv, just
document that the user should `export` them manually).

---

## Quota and Cost Notes (implement as comments in the code)

- YouTube Data API: fetching videos costs ~1-2 units per channel per page.
  At 50 channels with 3 pages max = ~300 units per run. Daily quota is 10,000.
  Well within limits.
- youtube-transcript-api: does not use API quota; scrapes directly.
- DeepSeek API: one call per run with up to ~80k-word context. At DeepSeek pricing
  (which is significantly lower), this costs roughly $0.01-0.03 per run depending on corpus size.

---

## What Not To Do

- Do not use async/await — keep everything synchronous for simplicity
- Do not add a web server, dashboard, or GUI
- Do not use pandas or numpy — plain Python dicts and lists are sufficient
- Do not add tests — this is a personal automation tool, not a library
- Do not add type annotations everywhere — only where they aid clarity
