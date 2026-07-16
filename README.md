# The Old Mole — Weekly Intelligence Report

A weekly pipeline that produces a single Markdown intelligence report
combining: our own YouTube channel analytics and comments, our Instagram
insights and comments, and structural-theme analysis of left/Marxist
YouTube channels (with a theme × framing matrix). Runs as a scheduled
Claude agent every Monday; Python collects the data deterministically and
the agent writes the report.

## How it works

1. **Collector** (`trend-sensor/collect.py`): pulls all sources into
   `trend-sensor/output/YYYY-MM-DD/` with per-source success/failure
   statuses. A failed source never aborts the run (partial-report policy).
2. **Routine** (scheduled Claude agent): runs the collector, then follows
   `trend-sensor/ROUTINE.md` to write
   `trend-sensor/digests/YYYY-MM-DD.md`, commit, and push. Report
   sections: TL;DR · Our Week · Our Audience · The Landscape ·
   Podcast Angles.

The routine runs locally via the Claude app's scheduled tasks (Mondays
08:00 local; if the app is closed it runs on next launch).

## Setup

1. `python3 -m venv venv && source venv/bin/activate`
2. `pip install -r trend-sensor/requirements.txt`
3. `cp .env.example .env` and fill it in:
   - `YOUTUBE_API_KEY` — Google Cloud Console API key
   - YouTube Analytics OAuth — see `docs/setup-youtube-oauth.md`
   - `IG_ACCESS_TOKEN` — see `docs/setup-instagram.md`
4. Fill `trend-sensor/config/accounts.yml` (own channel ID, IG user ID).
5. Competitor channels: edit `trend-sensor/config/channels.yml`
   (`core` = titles/descriptions + top audience comments;
   `broad` = titles/descriptions only).
   The same file's `instagram_competitors` list adds competitor Instagram
   accounts (public metadata via Business Discovery; professional
   accounts only).
6. Test: `python trend-sensor/collect.py` and check
   `trend-sensor/output/<today>/run_meta.json`.

## Development

- Tests: `pip install -r requirements-dev.txt && python -m pytest trend-sensor/tests -v`
- `trend-sensor/state/ig_snapshot.json` is committed on purpose — it is
  the baseline for detecting Instagram back-catalog movers week to week.
- `trend-sensor/output/` and `trend-sensor/data/` are ephemeral and
  gitignored.
