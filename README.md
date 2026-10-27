# The Old Mole — Weekly Media Report

A weekly pipeline that produces a short Markdown report (1–2 pages) on how
our own content did: one section for YouTube, one for Instagram. Each
covers last week's new uploads (numbers, how they compare with our usual
upload of the same type, what commenters said) and a 26-week trend chart.
Runs as a scheduled Claude agent every Sunday night. Python collects the
data and does all the maths and charts; the agent writes the words.

## How it works

1. **Collector** (`trend-sensor/collect.py`): pulls both platforms into
   `trend-sensor/output/YYYY-MM-DD/` (`youtube.json`, `instagram.json`,
   `run_meta.json` with per-source statuses) and draws the trend charts
   into `trend-sensor/digests/charts/YYYY-MM-DD/`. A failed source never
   aborts the run (partial-report policy).
2. **Routine** (scheduled Claude agent): runs the collector, then follows
   `trend-sensor/ROUTINE.md` to write
   `trend-sensor/digests/YYYY-MM-DD.md`, commit, push, and post a short
   teaser to Slack `#weekly-report`.

The routine runs locally via the Claude app's scheduled tasks (Sundays
22:00 local; if the app is closed it runs on next launch).

## Setup

1. `/opt/homebrew/bin/python3.12 -m venv venv && source venv/bin/activate`
   (Python 3.10+ is required; macOS system python3 is 3.9)
2. `pip install -r trend-sensor/requirements.txt`
3. `cp .env.example .env` and fill it in:
   - `YOUTUBE_API_KEY` — Google Cloud Console API key
   - YouTube Analytics OAuth — see `docs/setup-youtube-oauth.md`
   - `IG_ACCESS_TOKEN` — see `docs/setup-instagram.md`
4. Fill `trend-sensor/config/accounts.yml` (own channel ID, IG user ID).
5. Test: `python trend-sensor/collect.py` and check
   `trend-sensor/output/<today>/run_meta.json` and the charts.

## Development

- Tests: `pip install -r requirements-dev.txt && python -m pytest trend-sensor/tests -v`
- `trend-sensor/state/` is committed on purpose: `ig_snapshot.json` is the
  baseline for spotting older Instagram posts that pick up again, and
  `ig_followers.json` is the weekly follower count (Instagram's API keeps
  no follower history beyond 30 days, so the chart's history lives here).
- `trend-sensor/output/` and `trend-sensor/data/` are ephemeral and
  gitignored.
