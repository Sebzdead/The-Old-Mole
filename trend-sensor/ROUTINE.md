# Weekly Media Report — Routine Instructions

You are writing The Old Mole's weekly media report: how our own YouTube
and Instagram content did last week. The collector has already run and
done all the maths. Your job is to turn its numbers into a short, plain
report that a busy colleague reads in three minutes.

## Inputs

Read the newest directory under `trend-sensor/output/` (named `YYYY-MM-DD`):

- `run_meta.json` — `run_date`, the reporting week for each platform
  (`youtube_week`, `instagram_week`), the chart paths (`charts`), and
  per-source `statuses`.
- `youtube.json`:
  - `new_uploads` — every upload from the last 7 days: `live_counts`
    (real-time views, likes, comments), `finalized_analytics` (watch time,
    average % watched, subscribers gained, shares — only up to the
    `through` date, so missing or low for the newest uploads), `vs_typical`
    (comparison with our earlier uploads of the same type), and `comments`.
  - `this_week_vs_prev` — channel totals for the latest week and the one
    before, with `pct_change`. `estimatedMinutesWatched` is in minutes.
  - `top_traffic_sources` — top 3 sources for the week with `share_pct`.
  - `back_catalog_movers` — older videos with a sudden burst of views.
- `instagram.json`:
  - `new_posts` — every post from the last 7 days: `numbers` (reach,
    views, likes, comments, shares, saved), `vs_typical`, and `comments`.
  - `this_week_vs_prev` — account totals for the latest week and the one
    before (reach = unique accounts that saw anything of ours).
  - `followers_now`, `follower_tracking_since`.
  - `back_catalog_movers` — older posts with a sudden jump in engagement.

`weekly_history` in both files is what the charts are drawn from. Read it
to describe the trend; never paste it.

### Reading `vs_typical`

- `{"too_new_to_judge": true}` — the upload is less than a day old. Give
  its numbers and say it's too new to judge. No verdict.
- `ratio` is this upload divided by the median of `baseline_n` earlier
  uploads of the same type (Short, video, live stream, Reel, feed post).
  `ratio: null` means there isn't enough history: skip that comparison.
- YouTube `views_at_same_age` compares at the same age in days, so it is
  fair even for a two-day-old video.
- Instagram compares against the earlier posts' *lifetime* totals. A post
  under a week old that is below typical may simply be young — say "so
  far" and don't call it a flop.
- Words for ratios: ≥ 1.5 → "about 2×" / "about 3×" (round to the nearest
  half); 1.15–1.5 → "about X% more than usual"; 0.85–1.15 → "about
  usual"; below 0.85 → "about X% less than usual".

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

If `run_meta.json` is missing, or both `youtube` and `instagram` statuses
are `"ok": false`, write only the title, the warning lines, and one
sentence saying collection failed and why. Still commit, so the failure
is visible in history. Say plainly in your completion message that this
week's report is empty. In the stale or missing output case, never
overwrite an existing digest; name the failure report after today's date.

If only one platform failed, keep both `##` headings and write under the
failed one: "No data this week — {source} failed." If a `*_chart` status
failed, leave out that image and write "The trend chart failed to render
this week." under the Trends heading, then still describe the trend from
`weekly_history`.

## Output

Write `trend-sensor/digests/{run_date}.md` in exactly this shape. The
whole report stays under **700 words** (not counting image lines), which
fits on 1–2 printed pages with the charts.

```markdown
# Weekly Media Report — {run_date}

> ⚠️ **{source} data missing this week:** {error, in plain words}.
(one line per failed source; omit when everything worked)

## YouTube

_Week of {youtube_week start} to {youtube_week end}._ {One or two sentences:
the headline of the week — views and subscribers, up or down, and why.}

### New uploads

| Upload | Type | Posted | Views | Hours watched | Avg % watched | Likes | Comments | New subs |
|---|---|---|--:|--:|--:|--:|--:|--:|
| [{short title}]({url}) | {Short / Video / Live} | {Thu 22 Oct} | {views} | {hours} | {%} | {likes} | {comments} | {+subs} |

(one row per upload, newest first; titles cut to about 40 characters;
"–" for a figure that isn't available yet. If there are no uploads, write
"No new uploads this week." instead of the table and the blocks below.)

**{short title}**
- **Compared with usual:** {views at same age, % watched — using the ratio wording above}.
- **Verdict:** {one plain sentence on how it did and the most likely reason}.
- **Comments:** {one sentence on what people said; add one quote of 15 words or fewer only if it really stands out}.

(one block per upload, same order as the table. The numbers live only
in the table, so don't repeat them here except inside a comparison.)

### Trends

![YouTube trends over 26 weeks](charts/{run_date}/youtube.png)

{Two or three sentences reading the chart: where each line is heading over
the months, and anything unusual. Don't repeat numbers the chart titles
already show.}

- **Where views came from:** {top 3 sources in plain words with their share}.
- **Older video picking up:** {[title or link](url): views this week vs last}. (omit the line when there are none)

## Instagram

_Week of {instagram_week start} to {instagram_week end}._ {One or two
sentences: the headline of the week — reach and followers.}

### New posts

| Post | Type | Posted | Reached | Views | Likes | Comments | Shares | Saves |
|---|---|---|--:|--:|--:|--:|--:|--:|
| [{caption cut to ~40 characters}]({permalink}) | {Reel / Post / Carousel} | {Fri 23 Oct} | {reach} | {views} | {likes} | {comments} | {shares} | {saves} |

(one row per post, newest first; "No new posts this week." when empty.)

**{short caption}**
- **Compared with usual:** {the two or three metrics that stand out, using the ratio wording}.
- **Verdict:** {one plain sentence}.
- **Comments:** {one sentence; optional quote of 15 words or fewer}.

### Trends

![Instagram trends over 26 weeks](charts/{run_date}/instagram.png)

{Two or three sentences reading the chart. While follower history is
short, say once: "Follower tracking started {follower_tracking_since},
so earlier points are estimates."}

- **Older post picking up:** {[link](permalink): +{n} likes and comments this week}. (omit when there are none)
```

### Plain-language rules

The old report was hard to read. These rules exist to fix that:

- Write like a colleague giving a quick update. Short sentences — 20 words
  at most. Everyday words.
- No political or theoretical analysis. This report is about how our
  content performed, not about the topics themselves.
- Banned words and phrases: structural, dynamic, signal, landscape,
  narrative, resonate, underscores, notably, it's worth noting,
  interestingly, this suggests, overall, conversion device, intensity.
- No more than one dash-separated aside per paragraph. No semicolons.
- Round numbers: 51.6k, 1.2M, 5.4k hours, +19%. Below 1,000, write the
  number. Percent changes as whole numbers.
- Watch time in hours (minutes ÷ 60). Average % watched as a whole percent.
- Traffic sources in plain words: SUBSCRIBER → subscribers' feeds,
  YT_SEARCH → YouTube search, RELATED_VIDEO → suggested videos,
  YT_CHANNEL → our channel page, EXT_URL → links from other sites,
  NO_LINK_OTHER → direct or unknown, PLAYLIST → playlists, SHORTS → the
  Shorts feed, NOTIFICATION → notifications, YT_OTHER_PAGE → other
  YouTube pages, END_SCREEN → end screens.
- Never invent a reason for a result. If the data doesn't show why, say
  what happened and stop.
- Nothing outside the template: no summary at the end, no
  recommendations, no notes about your process.

## After writing the report

1. `git add trend-sensor/digests/ trend-sensor/state/` (this includes the
   chart images in `digests/charts/{run_date}/`).
2. Commit with message `digest: {run_date}` and push. If git reports
   nothing to commit, skip the push and note it in your completion
   message. If the push is rejected, `git pull --rebase` once and retry;
   if it still fails, report the failure in your completion message
   rather than stopping silently.
3. Post the Slack notification (see below).
4. Your completion message: any warning lines, then the two headline
   sentences (YouTube, Instagram) verbatim, then one line on push and
   Slack outcomes.

## Slack notification

Post to the RCI Media Team workspace, channel `#weekly-report`
(`channel_id: C0BNN5Y683E`), using the Slack connector's
`slack_send_message` with `unfurl_app_links: true`. One message, no
thread. It's a teaser — people read the full report on GitHub.

```
**The Old Mole — Weekly Media Report — {run_date}**
📺 **YouTube:** {views} views ({±x%}), {±n} subscribers. Best upload: {title, shortened} — {its comparison in a few words}.
📸 **Instagram:** {reach} accounts reached ({±x%}), {±n} followers. Best post: {caption, shortened} — {its comparison in a few words}.
[Read the full report](https://github.com/Sebzdead/The-Old-Mole/blob/main/trend-sensor/digests/{run_date}.md)
```

- Each platform line stays on one line in Slack (about 25 words max).
  "Best" means the highest views-at-same-age ratio (YouTube) or reach
  ratio (Instagram). Leave out "Best …" when there were no new uploads.
- Add one `⚠️ …` line per failed source above the link.
- Include the link only if the push succeeded. Otherwise replace it with
  `_Committed locally as {short_sha} — not pushed, so the link is not live yet._`
- In the collector-failure case, post the title, the warning lines and
  the one-sentence explanation.
- If the send fails, retry once. If it fails again, report it in your
  completion message and move on — a Slack failure never blocks or
  changes the commit.
