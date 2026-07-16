# Weekly Intelligence Report — Routine Instructions

You are producing The Old Mole's weekly intelligence report. The data
collector has already run; your job is analysis and writing.

## Inputs

Read the newest directory under `trend-sensor/output/` (named `YYYY-MM-DD`):

- `run_meta.json` — run date, reporting windows, and per-source `statuses`.
- `competitor_corpus.md` — formatted competitor video metadata: titles,
  descriptions, and (for core-tier channels) top audience comments. No
  transcripts — analyze themes and framing from titles, descriptions,
  and the audience reaction in the comments.
- `competitor_meta.json` — video/channel counts.
- `own_youtube.json` — channel week metrics (this + prev week), traffic
  sources, recent uploads (each with `metrics` and `comments`), and
  `back_catalog_movers`.
- `instagram.json` — recent posts (each with `insights` and `comments`),
  `back_catalog_movers`, and `permalinks`.
- `instagram_competitors.json` — may be absent. Competitor Instagram
  profiles via Business Discovery: `profiles` (username, followers_count,
  media_count, recent_posts with caption/like_count/comments_count/
  permalink) and per-account `errors`. Public metadata only — competitor
  comment text and insights are not available via the API.

## Ground rules

- `{run_date}` always means the `run_date` field in `run_meta.json` (it
  matches the output directory name) — never today's actual date.
- "Newest directory" means the directory whose `YYYY-MM-DD` name sorts
  greatest as a string. If that date is more than 7 days old, or if
  `run_meta.json` is missing from it, treat the run as a collector
  failure (see "When collection fails" below).
- If `trend-sensor/digests/{run_date}.md` already exists, overwrite it —
  a rerun replaces the same day's report.

## When collection fails

If `run_meta.json` is missing, or EVERY source status is `"ok": false`,
do not fabricate analysis: write only the header and warning banners plus
one line explaining that collection failed, skip all five analysis
sections, still commit (so the failure is visible in history), and say
plainly in your completion message that this week's report is empty and
why. If only SOME sources failed, keep every mandated H2 heading: for a
section whose source data is missing, write the heading and one line —
"No data this week — {source} failed." Never drop a mandated heading.
In the collector-failure case (stale or missing output directory), never
overwrite an existing digest; name the failure report after today's date
instead.

## Output

Write `trend-sensor/digests/{run_date}.md` with EXACTLY these five sections:

### 0. Header and warning banners

Title: `# Weekly Intelligence Report — {run_date}`.
For every source in `run_meta.json` statuses with `"ok": false`, add
immediately under the title:

> ⚠️ **{source} data missing this week:** {error}. The affected sections
> are omitted or partial.

### 1. `## TL;DR`

At most 10 bullets. The single most important takeaways across all
sections: biggest performance story, loudest audience signal, most
significant landscape shift, top content opportunity. Every bullet must be
specific (name the video/post/theme and the number that matters).
Cover a category only when there is a genuine signal — never pad toward
10 bullets.

### 2. `## Our Week`

- Channel table: this week vs. prev week (views, watch time, avg view
  duration, subs gained/lost) with % change.
- Traffic sources: top 3 with view counts.
- Per recent upload (YouTube, then Instagram): title/caption (first ~60
  chars), key metrics inline. Order by views/reach descending.
- `### Back-catalog movers`: each mover with its numbers and permalink/URL.
  If none: "No unusual back-catalog activity this week."
  For YouTube movers, build the URL as
  `https://www.youtube.com/watch?v={video_id}`.
- Note: impressions/CTR are not available via API (YouTube Studio only).

### 3. `## Our Audience`

For each recent post that has comments (skip posts with none):
- Sentiment split: rough % positive / negative / mixed-neutral.
- 3-5 recurring comment clusters, each with a one-line label and ONE
  representative quote (verbatim, ≤25 words).
- Standout comments worth acting on: substantive critiques, questions
  worth answering, and explicit content requests.

End with `### Cross-cutting audience signals`: 2-4 bullets on patterns
appearing across multiple posts/platforms.

### 4. `## The Landscape`

Analyze `competitor_corpus.md` for 6-10 structural themes, exactly as the
podcast's analytical tradition demands: not news summaries but underlying
contradictions, long-running crises, and social anxieties multiple sources
are independently circling. For each theme (H3 heading):

1. Concise name (≤5 words)
2. The structural dynamic in 2-3 sentences (what contradiction or tendency
   of capitalism produces this?)
3. Signal strength: HIGH / MEDIUM / LOW

Then `### Theme × Framing Matrix` — a table: rows = themes, columns =
channels that touched the theme, cells = a 2-5 word framing/tone
descriptor (e.g. "doomer explainer", "organizing-focused", "polemic",
"electoral horse-race", "ironic/meme"). Present the matrix RAW: no
commentary, no recommendations, no "gap" analysis in this section.

If `instagram_competitors.json` exists and has profiles, add
`### Instagram competitor pulse`: one line per account — followers,
posts this week, and the standout post (caption first ~60 chars,
like/comment counts, permalink). Present raw, no commentary. Note any
accounts listed under `errors` in one line. Omit the whole subsection
when the file is absent or has no profiles.

### 5. `## Podcast Angles`

3-6 concrete episode angles connecting the landscape themes to what OUR
audience is asking for (from Our Audience). Each: a framing/question that
makes for Marxist analysis rather than liberal commentary, plus one line
on why now.

## Style

The whole report must be readable in ~10 minutes. Tables over prose for
numbers. No preamble, no meta-commentary about your process.

## After writing the report

1. `git add trend-sensor/digests/ trend-sensor/state/`
2. Commit with message `digest: {run_date}` and push. If git reports
   nothing to commit, skip the push and note it in your completion
   message. If the push is rejected, `git pull --rebase` once and retry;
   if it still fails, report the failure in your completion message
   rather than stopping silently.
3. Your completion message must be the TL;DR section verbatim, prefixed
   by any warning banners.
