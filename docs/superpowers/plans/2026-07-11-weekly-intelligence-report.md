# Weekly Intelligence Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the trend-sensor into a weekly scheduled Claude routine that collects own-channel YouTube analytics (OAuth), Instagram Graph API insights, own-post comments, and competitor transcripts, then writes a single unified Markdown intelligence report.

**Architecture:** Deterministic Python (`trend-sensor/collect.py`) gathers all raw data into a dated JSON/Markdown bundle under `trend-sensor/output/`, recording per-source success/failure. A scheduled Claude agent (created via the app's scheduled-tasks system, replacing the GitHub Actions cron) runs the collector, then follows `trend-sensor/ROUTINE.md` to analyze the bundle, write `trend-sensor/digests/YYYY-MM-DD.md` (5 sections: TL;DR, Our Week, Our Audience, The Landscape with theme × framing matrix, Podcast Angles), commit, and surface the TL;DR in its completion message. DeepSeek is retired; Claude is the analyst.

**Tech Stack:** Python 3.11+, google-api-python-client (YouTube Data API v3 + YouTube Analytics API v2), google-auth/google-auth-oauthlib (OAuth refresh-token flow), requests (Instagram Graph API), youtube-transcript-api, PyYAML, python-dotenv, pytest.

**Key decisions locked during design review:**
- Own YouTube: full Analytics API from day one. Note: **impressions and thumbnail CTR are not exposed by the YouTube Analytics API** (Studio-only); we get views, watch time, average view duration/percentage, likes, comments, shares, subscriber gain/loss, and traffic sources.
- Instagram: Graph API via Business/Creator account. Feed posts (incl. carousels) + Reels; no Stories. Recommend a never-expiring **System User token** (setup doc covers it).
- Competitor "sentiment" = framing/tone of their *content* (transcripts already scraped), presented as a raw theme × channel framing matrix, no editorializing.
- Performance window: full detail for posts published in the last 7 days + "back-catalog movers" (older posts with unusual activity). YouTube movers come from two Analytics API top-video queries (this week vs. prev week); Instagram movers require a committed snapshot file (`trend-sensor/state/ig_snapshot.json`) because the Graph API only returns lifetime totals.
- Failure mode: partial report with a prominent ⚠ warning banner per failed source.
- Secrets: gitignored `.env` at repo root (the scheduled task runs locally on this machine). `.env.example` documents the variables.
- Analytics data lags ~48h, so the reporting window is `today-8 .. today-2`.

**Environment variables (in `.env`):** `YOUTUBE_API_KEY`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`, `IG_ACCESS_TOKEN`.
**Non-secret config (`trend-sensor/config/accounts.yml`):** `own_youtube_channel_id`, `instagram_user_id`.

**File map:**

| Action | Path | Responsibility |
|---|---|---|
| Create | `trend-sensor/tests/conftest.py` | sys.path setup for tests |
| Create | `trend-sensor/tests/test_fetcher.py` | API-key guard test |
| Create | `trend-sensor/src/accounts.py` + test | Load/validate accounts.yml |
| Create | `trend-sensor/config/accounts.yml` | Own account IDs (placeholders) |
| Create | `trend-sensor/src/corpus.py` + test | `format_corpus` (moved from analyzer.py) |
| Delete | `trend-sensor/src/analyzer.py` | DeepSeek retired |
| Create | `trend-sensor/src/yt_analytics.py` + test | OAuth Analytics client, channel/video metrics, traffic sources, movers |
| Create | `trend-sensor/src/yt_comments.py` + test | Own-video comment threads |
| Create | `trend-sensor/src/instagram.py` + test | Graph API media/insights/comments, movers, snapshot |
| Create | `trend-sensor/collect.py` | Orchestrator → `output/YYYY-MM-DD/` bundle |
| Delete | `trend-sensor/main.py`, `trend-sensor/src/digest.py` | Replaced by collect.py + agent |
| Modify | `trend-sensor/src/fetcher.py` | Remove hardcoded API key |
| Create | `trend-sensor/ROUTINE.md` | Agent analysis/report instructions |
| Create | `scripts/get_yt_refresh_token.py` | One-time OAuth helper |
| Create | `docs/setup-youtube-oauth.md`, `docs/setup-instagram.md`, `.env.example` | Credential setup guides |
| Modify | `trend-sensor/requirements.txt`, new `requirements-dev.txt` | Deps |
| Modify | `.gitignore`, `README.md` | output/ ignore, docs |
| Delete | `.github/workflows/weekly_digest.yml` | Actions retired |
| Runtime | `trend-sensor/state/ig_snapshot.json` | Committed IG lifetime-totals snapshot |

---

### Task 1: Test scaffolding and dev dependencies

**Files:**
- Create: `requirements-dev.txt`
- Create: `trend-sensor/tests/__init__.py`
- Create: `trend-sensor/tests/conftest.py`

- [ ] **Step 1: Create dev requirements**

Create `requirements-dev.txt` at repo root:

```text
pytest>=8.0
```

- [ ] **Step 2: Create test package and conftest**

Create empty `trend-sensor/tests/__init__.py`.

Create `trend-sensor/tests/conftest.py`:

```python
import os
import sys

# Make `from src import ...` imports work when running pytest from repo root.
TREND_SENSOR_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TREND_SENSOR_ROOT not in sys.path:
    sys.path.insert(0, TREND_SENSOR_ROOT)
```

- [ ] **Step 3: Verify pytest runs (collects zero tests, exits cleanly)**

Run: `pip install -r requirements-dev.txt && python -m pytest trend-sensor/tests -v`
Expected: `no tests ran` (exit code 5 is fine at this stage)

- [ ] **Step 4: Commit**

```bash
git add requirements-dev.txt trend-sensor/tests/
git commit -m "chore: add pytest scaffolding for trend-sensor"
```

---

### Task 2: Remove hardcoded YouTube API key from fetcher

**Files:**
- Modify: `trend-sensor/src/fetcher.py:8-17`
- Test: `trend-sensor/tests/test_fetcher.py`

> Note: the removed key is burned into git history — the user must rotate it in Google Cloud Console. Surface this reminder when the task completes.

- [ ] **Step 1: Write the failing test**

Create `trend-sensor/tests/test_fetcher.py`:

```python
import pytest

from src import fetcher


def test_get_youtube_client_raises_without_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="YOUTUBE_API_KEY"):
        fetcher.get_youtube_client()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest trend-sensor/tests/test_fetcher.py -v`
Expected: FAIL (no exception raised — current code falls back to the hardcoded key)

- [ ] **Step 3: Replace `get_youtube_client` in `trend-sensor/src/fetcher.py`**

Replace lines 8-17 with:

```python
def get_youtube_client():
    """Builds and returns a YouTube Data API client."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "YOUTUBE_API_KEY environment variable is not set."
        )
    return build("youtube", "v3", developerKey=api_key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest trend-sensor/tests/test_fetcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add trend-sensor/src/fetcher.py trend-sensor/tests/test_fetcher.py
git commit -m "fix: remove hardcoded YouTube API key fallback"
```

---

### Task 3: Accounts config loader

**Files:**
- Create: `trend-sensor/src/accounts.py`
- Create: `trend-sensor/config/accounts.yml`
- Test: `trend-sensor/tests/test_accounts.py`

- [ ] **Step 1: Write the failing tests**

Create `trend-sensor/tests/test_accounts.py`:

```python
import pytest

from src import accounts


def test_load_accounts_returns_ids(tmp_path):
    p = tmp_path / "accounts.yml"
    p.write_text(
        "own_youtube_channel_id: UCabc123\n"
        "instagram_user_id: '17841400000000000'\n"
    )
    data = accounts.load_accounts(str(p))
    assert data["own_youtube_channel_id"] == "UCabc123"
    assert data["instagram_user_id"] == "17841400000000000"


def test_load_accounts_raises_on_missing_key(tmp_path):
    p = tmp_path / "accounts.yml"
    p.write_text("own_youtube_channel_id: UCabc123\n")
    with pytest.raises(ValueError, match="instagram_user_id"):
        accounts.load_accounts(str(p))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest trend-sensor/tests/test_accounts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.accounts'`

- [ ] **Step 3: Implement `trend-sensor/src/accounts.py`**

```python
import os

import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS_PATH = os.path.join(PROJECT_ROOT, "config", "accounts.yml")

REQUIRED_KEYS = ("own_youtube_channel_id", "instagram_user_id")


def load_accounts(path: str = ACCOUNTS_PATH) -> dict:
    """Loads and validates the own-account configuration."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for key in REQUIRED_KEYS:
        if not data.get(key):
            raise ValueError(f"Missing '{key}' in {path}")
    return {key: str(data[key]) for key in REQUIRED_KEYS}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest trend-sensor/tests/test_accounts.py -v`
Expected: 2 PASS

- [ ] **Step 5: Create `trend-sensor/config/accounts.yml` with placeholders**

```yaml
# Own-account identifiers (not secrets — secrets live in .env at repo root).
# own_youtube_channel_id: find at https://www.youtube.com/account_advanced
# instagram_user_id: the IG *Business* user ID (numeric), see docs/setup-instagram.md
own_youtube_channel_id: "REPLACE_WITH_CHANNEL_ID"
instagram_user_id: "REPLACE_WITH_IG_USER_ID"
```

- [ ] **Step 6: Commit**

```bash
git add trend-sensor/src/accounts.py trend-sensor/config/accounts.yml trend-sensor/tests/test_accounts.py
git commit -m "feat: add own-account config loader"
```

---

### Task 4: Move `format_corpus` to `src/corpus.py`, delete analyzer.py

DeepSeek is retired; the only part of `analyzer.py` that survives is `format_corpus` (the 80k-word competitor corpus formatter). The Claude routine consumes the formatted corpus directly.

**Files:**
- Create: `trend-sensor/src/corpus.py` (copy `format_corpus` verbatim from `trend-sensor/src/analyzer.py:41-130`)
- Delete: `trend-sensor/src/analyzer.py`
- Test: `trend-sensor/tests/test_corpus.py`

- [ ] **Step 1: Write the failing tests**

Create `trend-sensor/tests/test_corpus.py`:

```python
from src import corpus


def _video(tier, channel, title, published, transcript=None, description=""):
    return {
        "video_id": "vid_" + title,
        "channel_name": channel,
        "title": title,
        "published_at": published,
        "tier": tier,
        "transcript_text": transcript,
        "description": description,
    }


def test_format_corpus_groups_core_and_broad():
    videos = [
        _video("core", "Novara", "A", "2026-07-01", transcript="hello world"),
        _video("broad", "Current Affairs", "B", "2026-07-02", description="desc here"),
    ]
    out = corpus.format_corpus(videos)
    assert "=== CORE VIDEOS (FULL TRANSCRIPTS) ===" in out
    assert "=== BROAD VIDEOS (METADATA ONLY) ===" in out
    assert "hello world" in out
    assert "desc here" in out


def test_format_corpus_truncates_over_word_budget():
    # One giant core video plus one broad video; broad gets dropped first.
    videos = [
        _video("core", "Novara", "big", "2026-07-02", transcript="word " * 80001),
        _video("broad", "CA", "small", "2026-07-01", description="droppable"),
    ]
    out = corpus.format_corpus(videos)
    assert "droppable" not in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest trend-sensor/tests/test_corpus.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.corpus'`

- [ ] **Step 3: Create `trend-sensor/src/corpus.py`**

Copy the `format_corpus` function **unchanged** from `trend-sensor/src/analyzer.py` (lines 41-130) into a new file. The file must contain exactly: the `format_corpus(corpus: list[dict]) -> str` function and no imports (it uses only builtins). Do **not** copy `SYSTEM_PROMPT`, `run_analysis`, or the `openai` import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest trend-sensor/tests/test_corpus.py -v`
Expected: 2 PASS

- [ ] **Step 5: Delete analyzer.py and confirm nothing else imports it**

```bash
git rm trend-sensor/src/analyzer.py
grep -rn "analyzer" trend-sensor/src/ trend-sensor/tests/ || echo "clean"
```

Expected: `clean` (main.py still references it — main.py is deleted in Task 8; that's acceptable interim breakage since collect.py replaces it in the same plan, but if you want main.py runnable between tasks, defer this `git rm` to Task 8. Recommended: do the `git rm` now and accept that `main.py` is broken until Task 8.)

- [ ] **Step 6: Commit**

```bash
git add -A trend-sensor/src/ trend-sensor/tests/test_corpus.py
git commit -m "refactor: move format_corpus to corpus.py, retire DeepSeek analyzer"
```

---

### Task 5: YouTube Analytics module (OAuth)

**Files:**
- Create: `trend-sensor/src/yt_analytics.py`
- Test: `trend-sensor/tests/test_yt_analytics.py`

- [ ] **Step 1: Write the failing tests**

Create `trend-sensor/tests/test_yt_analytics.py`:

```python
import pytest

from src import yt_analytics


class _FakeRequest:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _FakeReports:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeRequest(self._responses.pop(0))


class FakeAnalyticsClient:
    def __init__(self, responses):
        self._reports = _FakeReports(responses)

    def reports(self):
        return self._reports


def test_get_analytics_client_requires_env(monkeypatch):
    for var in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="YT_CLIENT_ID"):
        yt_analytics.get_analytics_client()


def test_channel_week_metrics_zips_headers_and_row():
    client = FakeAnalyticsClient([
        {
            "columnHeaders": [{"name": "views"}, {"name": "likes"}],
            "rows": [[1200, 80]],
        }
    ])
    out = yt_analytics.channel_week_metrics(client, "2026-07-03", "2026-07-09")
    assert out == {"views": 1200, "likes": 80}


def test_video_week_metrics_keyed_by_video_id():
    client = FakeAnalyticsClient([
        {
            "columnHeaders": [{"name": "video"}, {"name": "views"}, {"name": "likes"}],
            "rows": [["abc", 500, 40], ["def", 100, 5]],
        }
    ])
    out = yt_analytics.video_week_metrics(
        client, ["abc", "def"], "2026-07-03", "2026-07-09"
    )
    assert out["abc"] == {"views": 500, "likes": 40}
    assert out["def"]["views"] == 100


def test_back_catalog_movers_excludes_recent_and_applies_thresholds():
    this_week = {"rows": [["old1", 900], ["new1", 800], ["old2", 150], ["old3", 400]]}
    prev_week = {"rows": [["old1", 100], ["old3", 350]]}
    client = FakeAnalyticsClient([this_week, prev_week])
    movers = yt_analytics.back_catalog_movers(
        client,
        recent_video_ids={"new1"},
        this_start="2026-07-03",
        this_end="2026-07-09",
        prev_start="2026-06-26",
        prev_end="2026-07-02",
    )
    ids = [m["video_id"] for m in movers]
    assert ids == ["old1"]  # new1 excluded; old2 under min views; old3 under 2x ratio
    assert movers[0]["views_prev_week"] == 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest trend-sensor/tests/test_yt_analytics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.yt_analytics'`

- [ ] **Step 3: Implement `trend-sensor/src/yt_analytics.py`**

```python
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_URI = "https://oauth2.googleapis.com/token"

CHANNEL_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,likes,comments,"
    "shares,subscribersGained,subscribersLost"
)
VIDEO_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,"
    "averageViewPercentage,likes,comments,shares"
)


def get_analytics_client():
    """Builds a YouTube Analytics API v2 client from OAuth refresh-token env vars."""
    client_id = os.environ.get("YT_CLIENT_ID")
    client_secret = os.environ.get("YT_CLIENT_SECRET")
    refresh_token = os.environ.get("YT_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        raise RuntimeError(
            "YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN must all be set."
        )
    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
    )
    return build("youtubeAnalytics", "v2", credentials=creds)


def _rows_as_dicts(response: dict) -> list[dict]:
    headers = [h["name"] for h in response.get("columnHeaders", [])]
    return [dict(zip(headers, row)) for row in response.get("rows", []) or []]


def channel_week_metrics(client, start_date: str, end_date: str) -> dict:
    """Channel-wide totals for the window."""
    response = (
        client.reports()
        .query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics=CHANNEL_METRICS,
        )
        .execute()
    )
    rows = _rows_as_dicts(response)
    return rows[0] if rows else {}


def video_week_metrics(
    client, video_ids: list[str], start_date: str, end_date: str
) -> dict:
    """Per-video metrics for the given videos, keyed by video ID."""
    if not video_ids:
        return {}
    response = (
        client.reports()
        .query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics=VIDEO_METRICS,
            dimensions="video",
            filters="video==" + ",".join(video_ids),
            maxResults=200,
        )
        .execute()
    )
    out = {}
    for row in _rows_as_dicts(response):
        video_id = row.pop("video")
        out[video_id] = row
    return out


def traffic_sources(client, start_date: str, end_date: str) -> dict:
    """Views by traffic source type for the window."""
    response = (
        client.reports()
        .query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="insightTrafficSourceType",
            sort="-views",
        )
        .execute()
    )
    return {row[0]: row[1] for row in response.get("rows", []) or []}


def _top_videos_by_views(client, start_date: str, end_date: str) -> dict:
    response = (
        client.reports()
        .query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="video",
            sort="-views",
            maxResults=200,
        )
        .execute()
    )
    return {row[0]: row[1] for row in response.get("rows", []) or []}


def back_catalog_movers(
    client,
    recent_video_ids: set[str],
    this_start: str,
    this_end: str,
    prev_start: str,
    prev_end: str,
    min_views: int = 200,
    ratio: float = 2.0,
    top_n: int = 5,
) -> list[dict]:
    """
    Older videos (not in recent_video_ids) with unusual activity this week:
    at least min_views this window AND at least ratio x last window's views.
    """
    this_week = _top_videos_by_views(client, this_start, this_end)
    prev_week = _top_videos_by_views(client, prev_start, prev_end)
    movers = []
    for video_id, views in this_week.items():
        if video_id in recent_video_ids:
            continue
        prev = prev_week.get(video_id, 0)
        if views >= min_views and views >= ratio * max(prev, 1):
            movers.append(
                {
                    "video_id": video_id,
                    "views_this_week": views,
                    "views_prev_week": prev,
                }
            )
    movers.sort(key=lambda m: m["views_this_week"], reverse=True)
    return movers[:top_n]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest trend-sensor/tests/test_yt_analytics.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add trend-sensor/src/yt_analytics.py trend-sensor/tests/test_yt_analytics.py
git commit -m "feat: add YouTube Analytics API module (channel/video metrics, traffic, movers)"
```

---

### Task 6: Own-video comments module

**Files:**
- Create: `trend-sensor/src/yt_comments.py`
- Test: `trend-sensor/tests/test_yt_comments.py`

- [ ] **Step 1: Write the failing tests**

Create `trend-sensor/tests/test_yt_comments.py`:

```python
from src import yt_comments


class _FakeRequest:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _FakeCommentThreads:
    def __init__(self, pages):
        self._pages = list(pages)
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeRequest(self._pages.pop(0))


class FakeDataClient:
    def __init__(self, pages):
        self._ct = _FakeCommentThreads(pages)

    def commentThreads(self):
        return self._ct


def _page(texts, next_token=None):
    items = [
        {
            "snippet": {
                "topLevelComment": {
                    "snippet": {
                        "textDisplay": t,
                        "likeCount": 3,
                        "authorDisplayName": "user",
                        "publishedAt": "2026-07-05T00:00:00Z",
                    }
                }
            }
        }
        for t in texts
    ]
    page = {"items": items}
    if next_token:
        page["nextPageToken"] = next_token
    return page


def test_fetch_comments_paginates_and_caps():
    client = FakeDataClient([_page(["a"] * 100, "tok"), _page(["b"] * 100)])
    comments = yt_comments.fetch_comments(client, "vid1", max_comments=120)
    assert len(comments) == 120
    assert comments[0]["text"] == "a"
    assert comments[0]["like_count"] == 3


def test_fetch_comments_returns_empty_on_error():
    class Exploding:
        def commentThreads(self):
            raise RuntimeError("comments disabled")

    comments = yt_comments.fetch_comments(Exploding(), "vid1")
    assert comments == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest trend-sensor/tests/test_yt_comments.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.yt_comments'`

- [ ] **Step 3: Implement `trend-sensor/src/yt_comments.py`**

```python
def fetch_comments(youtube, video_id: str, max_comments: int = 100) -> list[dict]:
    """
    Fetches top-level comments for a video, ordered by relevance,
    capped at max_comments. Returns [] on any API error (e.g. comments
    disabled) — a missing comment section must not fail the run.
    """
    comments = []
    page_token = None
    try:
        while len(comments) < max_comments:
            response = (
                youtube.commentThreads()
                .list(
                    part="snippet",
                    videoId=video_id,
                    order="relevance",
                    textFormat="plainText",
                    maxResults=min(100, max_comments - len(comments)),
                    pageToken=page_token,
                )
                .execute()
            )
            for item in response.get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                comments.append(
                    {
                        "text": top.get("textDisplay", ""),
                        "like_count": top.get("likeCount", 0),
                        "author": top.get("authorDisplayName", ""),
                        "published_at": top.get("publishedAt", ""),
                    }
                )
            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        print(f"Warning: comment fetch failed for {video_id}: {e}")
    return comments[:max_comments]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest trend-sensor/tests/test_yt_comments.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add trend-sensor/src/yt_comments.py trend-sensor/tests/test_yt_comments.py
git commit -m "feat: add own-video comment fetcher"
```

---

### Task 7: Instagram Graph API module

**Files:**
- Create: `trend-sensor/src/instagram.py`
- Test: `trend-sensor/tests/test_instagram.py`

- [ ] **Step 1: Write the failing tests**

Create `trend-sensor/tests/test_instagram.py`:

```python
import pytest

from src import instagram


def test_fetch_media_paginates(monkeypatch):
    pages = [
        {
            "data": [{"id": "1", "like_count": 5}],
            "paging": {"next": "https://graph.facebook.com/next"},
        },
        {"data": [{"id": "2", "like_count": 7}]},
    ]
    calls = []

    def fake_get(url, params):
        calls.append(url)
        return pages.pop(0)

    monkeypatch.setattr(instagram, "_get", fake_get)
    media = instagram.fetch_media("178414", "tok")
    assert [m["id"] for m in media] == ["1", "2"]
    assert calls[1] == "https://graph.facebook.com/next"


def test_fetch_media_insights_flattens_values(monkeypatch):
    def fake_get(url, params):
        return {
            "data": [
                {"name": "reach", "values": [{"value": 1500}]},
                {"name": "saved", "values": [{"value": 12}]},
            ]
        }

    monkeypatch.setattr(instagram, "_get", fake_get)
    out = instagram.fetch_media_insights("m1", "tok", "FEED")
    assert out == {"reach": 1500, "saved": 12}


def test_fetch_media_insights_tolerates_errors(monkeypatch):
    def fake_get(url, params):
        raise RuntimeError("unsupported metric")

    monkeypatch.setattr(instagram, "_get", fake_get)
    assert instagram.fetch_media_insights("m1", "tok", "REELS") == {}


def test_compute_movers_requires_baseline_and_thresholds():
    snapshot = {
        "media": {
            "old_hot": {"engagement": 100, "delta": 10},
            "old_cold": {"engagement": 100, "delta": 10},
            "old_flat": {"engagement": 100, "delta": 40},
        }
    }
    media = [
        {"id": "old_hot", "like_count": 140, "comments_count": 10, "permalink": "p1"},
        {"id": "old_cold", "like_count": 105, "comments_count": 5, "permalink": "p2"},
        {"id": "old_flat", "like_count": 150, "comments_count": 0, "permalink": "p3"},
        {"id": "brand_new", "like_count": 999, "comments_count": 0, "permalink": "p4"},
        {"id": "recent1", "like_count": 500, "comments_count": 0, "permalink": "p5"},
    ]
    movers = instagram.compute_movers(media, snapshot, recent_ids={"recent1"})
    ids = [m["media_id"] for m in movers]
    # old_hot: delta 50 >= 20 and >= 2x prev delta 10 -> mover
    # old_cold: delta 10 < 20 -> no. old_flat: delta 50 < 2x40 -> no.
    # brand_new: no baseline -> no. recent1: excluded.
    assert ids == ["old_hot"]
    assert movers[0]["delta_engagement"] == 50


def test_build_snapshot_records_engagement_and_delta():
    old = {"media": {"a": {"engagement": 10, "delta": 0}}}
    media = [
        {"id": "a", "like_count": 25, "comments_count": 5},
        {"id": "b", "like_count": 7, "comments_count": 0},
    ]
    snap = instagram.build_snapshot(media, old, "2026-07-11")
    assert snap["snapshot_date"] == "2026-07-11"
    assert snap["media"]["a"] == {"engagement": 30, "delta": 20}
    assert snap["media"]["b"] == {"engagement": 7, "delta": 0}


def test_snapshot_roundtrip(tmp_path):
    path = str(tmp_path / "snap.json")
    assert instagram.load_snapshot(path) == {"media": {}}
    instagram.save_snapshot(path, {"snapshot_date": "d", "media": {"x": {}}})
    assert instagram.load_snapshot(path)["media"] == {"x": {}}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest trend-sensor/tests/test_instagram.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.instagram'`

- [ ] **Step 3: Implement `trend-sensor/src/instagram.py`**

```python
import json
import os

import requests

GRAPH_BASE = "https://graph.facebook.com/v21.0"

MEDIA_FIELDS = (
    "id,caption,media_type,media_product_type,timestamp,permalink,"
    "like_count,comments_count"
)

# Insight metric sets per media_product_type. Meta deprecated `impressions`
# in favor of `views` (2025); metric availability varies by type, and
# fetch_media_insights degrades to {} if a set is rejected.
INSIGHT_METRICS = {
    "REELS": "reach,saved,shares,likes,comments,views,total_interactions",
    "FEED": "reach,saved,shares,views,total_interactions",
}


def _get(url: str, params: dict) -> dict:
    """Single Graph API GET with error unwrapping. Tests monkeypatch this."""
    response = requests.get(url, params=params, timeout=30)
    data = response.json()
    if "error" in data:
        raise RuntimeError(
            f"Instagram API error: {data['error'].get('message', 'unknown')}"
        )
    return data


def fetch_media(ig_user_id: str, token: str, limit: int = 100) -> list[dict]:
    """Fetches the most recent media objects (feed posts, carousels, reels)."""
    media = []
    url = f"{GRAPH_BASE}/{ig_user_id}/media"
    params = {"fields": MEDIA_FIELDS, "access_token": token, "limit": 50}
    while url and len(media) < limit:
        data = _get(url, params)
        media.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = {}  # the `next` URL already carries all query params
    return media[:limit]


def fetch_media_insights(media_id: str, token: str, media_product_type: str) -> dict:
    """Per-media insight metrics; returns {} if the API rejects the request."""
    metrics = INSIGHT_METRICS.get(media_product_type, INSIGHT_METRICS["FEED"])
    try:
        data = _get(
            f"{GRAPH_BASE}/{media_id}/insights",
            {"metric": metrics, "access_token": token},
        )
    except RuntimeError as e:
        print(f"Warning: insights fetch failed for media {media_id}: {e}")
        return {}
    out = {}
    for entry in data.get("data", []):
        values = entry.get("values") or [{}]
        out[entry.get("name")] = values[0].get("value", 0)
    return out


def fetch_media_comments(media_id: str, token: str, max_comments: int = 100) -> list[dict]:
    """Comments on a media object, capped. Returns [] on error."""
    comments = []
    url = f"{GRAPH_BASE}/{media_id}/comments"
    params = {
        "fields": "text,like_count,timestamp,username",
        "access_token": token,
        "limit": 50,
    }
    try:
        while url and len(comments) < max_comments:
            data = _get(url, params)
            comments.extend(data.get("data", []))
            url = data.get("paging", {}).get("next")
            params = {}
    except RuntimeError as e:
        print(f"Warning: comment fetch failed for media {media_id}: {e}")
    return comments[:max_comments]


def _engagement(media_item: dict) -> int:
    return (media_item.get("like_count") or 0) + (media_item.get("comments_count") or 0)


def compute_movers(
    media: list[dict],
    snapshot: dict,
    recent_ids: set[str],
    min_delta: int = 20,
    ratio: float = 2.0,
    top_n: int = 5,
) -> list[dict]:
    """
    Back-catalog media with unusual engagement growth since the last snapshot:
    delta >= min_delta AND delta >= ratio x last week's delta. Media without a
    snapshot baseline (first sighting) are skipped — no way to know the delta.
    """
    old = snapshot.get("media", {})
    movers = []
    for m in media:
        media_id = m["id"]
        if media_id in recent_ids:
            continue
        baseline = old.get(media_id)
        if baseline is None or "engagement" not in baseline:
            continue
        delta = _engagement(m) - baseline["engagement"]
        prev_delta = baseline.get("delta", 0)
        if delta >= min_delta and delta >= ratio * max(prev_delta, 1):
            movers.append(
                {
                    "media_id": media_id,
                    "permalink": m.get("permalink"),
                    "delta_engagement": delta,
                    "prev_week_delta": prev_delta,
                }
            )
    movers.sort(key=lambda x: x["delta_engagement"], reverse=True)
    return movers[:top_n]


def build_snapshot(media: list[dict], old_snapshot: dict, run_date: str) -> dict:
    """New snapshot of lifetime engagement totals plus this week's delta."""
    old = old_snapshot.get("media", {})
    new_media = {}
    for m in media:
        engagement = _engagement(m)
        baseline = old.get(m["id"], {}).get("engagement")
        delta = engagement - baseline if baseline is not None else 0
        new_media[m["id"]] = {"engagement": engagement, "delta": delta}
    return {"snapshot_date": run_date, "media": new_media}


def load_snapshot(path: str) -> dict:
    if not os.path.exists(path):
        return {"media": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(path: str, snapshot: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest trend-sensor/tests/test_instagram.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add trend-sensor/src/instagram.py trend-sensor/tests/test_instagram.py
git commit -m "feat: add Instagram Graph API module (media, insights, comments, movers)"
```

---

### Task 8: Collector orchestrator (`collect.py`), delete `main.py` and `digest.py`

**Files:**
- Create: `trend-sensor/collect.py`
- Delete: `trend-sensor/main.py`, `trend-sensor/src/digest.py`
- Test: `trend-sensor/tests/test_collect.py`

- [ ] **Step 1: Write the failing tests (window math + status recording)**

Create `trend-sensor/tests/test_collect.py`:

```python
from datetime import date

import collect


def test_reporting_windows_account_for_analytics_lag():
    win = collect.reporting_windows(date(2026, 7, 13))  # a Monday
    assert win["this_start"] == "2026-07-05"
    assert win["this_end"] == "2026-07-11"
    assert win["prev_start"] == "2026-06-28"
    assert win["prev_end"] == "2026-07-04"


def test_run_source_records_success_and_failure():
    statuses = {}
    ok = collect.run_source(statuses, "good", lambda: 42)
    bad = collect.run_source(statuses, "bad", lambda: 1 / 0)
    assert ok == 42
    assert bad is None
    assert statuses["good"] == {"ok": True, "error": None}
    assert statuses["bad"]["ok"] is False
    assert "division" in statuses["bad"]["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest trend-sensor/tests/test_collect.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collect'`
(conftest.py already puts `trend-sensor/` on sys.path, so `import collect` resolves once the file exists.)

- [ ] **Step 3: Implement `trend-sensor/collect.py`**

```python
#!/usr/bin/env python3
"""
Weekly data collector for The Old Mole intelligence report.

Gathers competitor transcripts, own-channel YouTube analytics + comments,
and Instagram insights + comments into trend-sensor/output/YYYY-MM-DD/.
Every source is isolated: a failure is recorded in run_meta.json statuses
and the remaining sources still run (partial-report policy).

The Claude routine (see ROUTINE.md) consumes the output bundle.
"""

import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta, timezone

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import yaml
from dateutil.parser import isoparse
from dotenv import load_dotenv

from src import accounts, cache, corpus, fetcher, instagram, transcripts
from src import yt_analytics, yt_comments

load_dotenv(os.path.join(REPO_ROOT, ".env"))

OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "output")
SNAPSHOT_PATH = os.path.join(PROJECT_ROOT, "state", "ig_snapshot.json")
COMMENTS_PER_POST = 100


def reporting_windows(today: date) -> dict:
    """
    Analytics data lags ~48h, so the report window is today-8 .. today-2,
    with the preceding 7 days as the comparison window for movers.
    """
    this_end = today - timedelta(days=2)
    this_start = this_end - timedelta(days=6)
    prev_end = this_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    return {
        "this_start": this_start.isoformat(),
        "this_end": this_end.isoformat(),
        "prev_start": prev_start.isoformat(),
        "prev_end": prev_end.isoformat(),
    }


def run_source(statuses: dict, name: str, fn):
    """Runs one source, recording ok/error. Returns fn() or None on failure."""
    try:
        result = fn()
        statuses[name] = {"ok": True, "error": None}
        return result
    except Exception as e:
        traceback.print_exc()
        statuses[name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return None


def collect_competitors(out_dir: str) -> None:
    config_path = os.path.join(PROJECT_ROOT, "config", "channels.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        channels = yaml.safe_load(f).get("channels", [])
    cache.init_db()
    new_videos = fetcher.fetch_all_channels(channels, days_back=7)
    for video in new_videos:
        cache.save_video(video)
    transcripts.fetch_transcripts_for_corpus(new_videos)
    weekly_corpus = cache.get_corpus_since(days=7)
    formatted = corpus.format_corpus(weekly_corpus)
    meta = {
        "video_count": len(weekly_corpus),
        "channel_count": len({v["channel_name"] for v in weekly_corpus}),
    }
    with open(os.path.join(out_dir, "competitor_corpus.md"), "w", encoding="utf-8") as f:
        f.write(formatted)
    with open(os.path.join(out_dir, "competitor_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def collect_own_youtube(out_dir: str, own_channel_id: str, windows: dict) -> None:
    data_client = fetcher.get_youtube_client()
    analytics_client = yt_analytics.get_analytics_client()

    uploads = fetcher.get_channel_uploads(
        own_channel_id, "The Old Mole", tier="own", days_back=7
    )
    recent_ids = {v["video_id"] for v in uploads}

    per_video = yt_analytics.video_week_metrics(
        analytics_client, sorted(recent_ids), windows["this_start"], windows["this_end"]
    )
    for video in uploads:
        video["metrics"] = per_video.get(video["video_id"], {})
        video["comments"] = yt_comments.fetch_comments(
            data_client, video["video_id"], max_comments=COMMENTS_PER_POST
        )

    movers = yt_analytics.back_catalog_movers(
        analytics_client,
        recent_ids,
        windows["this_start"],
        windows["this_end"],
        windows["prev_start"],
        windows["prev_end"],
    )

    payload = {
        "channel_week": yt_analytics.channel_week_metrics(
            analytics_client, windows["this_start"], windows["this_end"]
        ),
        "channel_prev_week": yt_analytics.channel_week_metrics(
            analytics_client, windows["prev_start"], windows["prev_end"]
        ),
        "traffic_sources": yt_analytics.traffic_sources(
            analytics_client, windows["this_start"], windows["this_end"]
        ),
        "recent_uploads": uploads,
        "back_catalog_movers": movers,
    }
    with open(os.path.join(out_dir, "own_youtube.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def collect_instagram(out_dir: str, ig_user_id: str, run_date: str) -> None:
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("IG_ACCESS_TOKEN environment variable is not set.")

    media = instagram.fetch_media(ig_user_id, token, limit=100)
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = [
        m for m in media
        if m.get("timestamp") and isoparse(m["timestamp"]) >= cutoff
    ]
    recent_ids = {m["id"] for m in recent}

    for m in recent:
        m["insights"] = instagram.fetch_media_insights(
            m["id"], token, m.get("media_product_type", "FEED")
        )
        m["comments"] = instagram.fetch_media_comments(
            m["id"], token, max_comments=COMMENTS_PER_POST
        )

    old_snapshot = instagram.load_snapshot(SNAPSHOT_PATH)
    movers = instagram.compute_movers(media, old_snapshot, recent_ids)
    permalinks = {m["id"]: m.get("permalink") for m in media}
    new_snapshot = instagram.build_snapshot(media, old_snapshot, run_date)
    instagram.save_snapshot(SNAPSHOT_PATH, new_snapshot)

    payload = {
        "recent_posts": recent,
        "back_catalog_movers": movers,
        "permalinks": permalinks,
        "previous_snapshot_date": old_snapshot.get("snapshot_date"),
    }
    with open(os.path.join(out_dir, "instagram.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main():
    run_date = date.today().isoformat()
    windows = reporting_windows(date.today())
    out_dir = os.path.join(OUTPUT_ROOT, run_date)
    os.makedirs(out_dir, exist_ok=True)

    statuses = {}

    account_config = run_source(statuses, "accounts_config", accounts.load_accounts)

    run_source(statuses, "competitors", lambda: collect_competitors(out_dir))

    if account_config:
        run_source(
            statuses,
            "own_youtube",
            lambda: collect_own_youtube(
                out_dir, account_config["own_youtube_channel_id"], windows
            ),
        )
        run_source(
            statuses,
            "instagram",
            lambda: collect_instagram(
                out_dir, account_config["instagram_user_id"], run_date
            ),
        )
    else:
        statuses["own_youtube"] = {"ok": False, "error": "accounts_config failed"}
        statuses["instagram"] = {"ok": False, "error": "accounts_config failed"}

    run_meta = {
        "run_date": run_date,
        "windows": windows,
        "statuses": statuses,
        "output_dir": out_dir,
    }
    with open(os.path.join(out_dir, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump(run_meta, f, indent=2)

    print(json.dumps(run_meta, indent=2))
    failed = [name for name, s in statuses.items() if not s["ok"]]
    if failed:
        print(f"Completed with failed sources: {', '.join(failed)}", file=sys.stderr)
    else:
        print("All sources collected successfully.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest trend-sensor/tests/test_collect.py -v`
Expected: 2 PASS

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest trend-sensor/tests -v`
Expected: all tests PASS

- [ ] **Step 6: Delete replaced files**

```bash
git rm trend-sensor/main.py trend-sensor/src/digest.py
grep -rn "digest\|main\.py" trend-sensor/src/ trend-sensor/collect.py || echo "clean"
```

Expected: `clean`

- [ ] **Step 7: Commit**

```bash
git add -A trend-sensor/
git commit -m "feat: add collect.py orchestrator with partial-failure statuses; retire main.py/digest.py"
```

---

### Task 9: Dependencies, .gitignore, state directory

**Files:**
- Modify: `trend-sensor/requirements.txt`
- Modify: `.gitignore`
- Create: `trend-sensor/state/.gitkeep`

- [ ] **Step 1: Rewrite `trend-sensor/requirements.txt`**

`openai` (DeepSeek client) and `feedparser` are removed — first verify feedparser really is unused:

```bash
grep -rn "feedparser\|openai" trend-sensor/src/ trend-sensor/collect.py || echo "unused"
```

Expected: `unused`. Then write:

```text
google-api-python-client==2.131.0
google-auth>=2.30
google-auth-oauthlib>=1.2
youtube-transcript-api==0.6.2
PyYAML==6.0.1
python-dateutil==2.9.0
requests>=2.31
python-dotenv>=1.0
```

- [ ] **Step 2: Update `.gitignore`**

Append to the repo-root `.gitignore` (the `trend-sensor/state/` dir must stay tracked — do NOT add it here):

```text

# Weekly raw data bundles (ephemeral; the digest is the durable artifact)
trend-sensor/output/

# Google OAuth client file used by scripts/get_yt_refresh_token.py
client_secret.json
```

- [ ] **Step 3: Create the tracked state directory**

```bash
mkdir -p trend-sensor/state && touch trend-sensor/state/.gitkeep
```

- [ ] **Step 4: Verify install works from scratch**

Run: `pip install -r trend-sensor/requirements.txt && python -m pytest trend-sensor/tests -v`
Expected: install succeeds; all tests PASS

- [ ] **Step 5: Commit**

```bash
git add trend-sensor/requirements.txt .gitignore trend-sensor/state/.gitkeep
git commit -m "chore: update deps (drop openai/feedparser), ignore output/, track state/"
```

---

### Task 10: ROUTINE.md — the agent's analysis and report instructions

**Files:**
- Create: `trend-sensor/ROUTINE.md`

- [ ] **Step 1: Create `trend-sensor/ROUTINE.md`**

````markdown
# Weekly Intelligence Report — Routine Instructions

You are producing The Old Mole's weekly intelligence report. The data
collector has already run; your job is analysis and writing.

## Inputs

Read the newest directory under `trend-sensor/output/` (named `YYYY-MM-DD`):

- `run_meta.json` — run date, reporting windows, and per-source `statuses`.
- `competitor_corpus.md` — formatted competitor transcripts/metadata.
- `competitor_meta.json` — video/channel counts.
- `own_youtube.json` — channel week metrics (this + prev week), traffic
  sources, recent uploads (each with `metrics` and `comments`), and
  `back_catalog_movers`.
- `instagram.json` — recent posts (each with `insights` and `comments`),
  `back_catalog_movers`, and `permalinks`.

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

### 2. `## Our Week`

- Channel table: this week vs. prev week (views, watch time, avg view
  duration, subs gained/lost) with % change.
- Traffic sources: top 3 with view counts.
- Per recent upload (YouTube, then Instagram): title/caption (first ~60
  chars), key metrics inline. Order by views/reach descending.
- `### Back-catalog movers`: each mover with its numbers and permalink/URL.
  If none: "No unusual back-catalog activity this week."
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
2. Commit with message `digest: {run_date}` and push.
3. Your completion message must be the TL;DR section verbatim, prefixed
   by any warning banners.
````

- [ ] **Step 2: Commit**

```bash
git add trend-sensor/ROUTINE.md
git commit -m "feat: add ROUTINE.md agent instructions for weekly report"
```

---

### Task 11: Credential setup — OAuth helper script, setup docs, .env.example

**Files:**
- Create: `scripts/get_yt_refresh_token.py`
- Create: `docs/setup-youtube-oauth.md`
- Create: `docs/setup-instagram.md`
- Create: `.env.example`

- [ ] **Step 1: Create `scripts/get_yt_refresh_token.py`**

```python
#!/usr/bin/env python3
"""
One-time helper: obtain a YouTube Analytics OAuth refresh token.

Prereq: download the OAuth client JSON from Google Cloud Console to
./client_secret.json (Desktop app type). See docs/setup-youtube-oauth.md.

Usage: python scripts/get_yt_refresh_token.py
Opens a browser for consent as the channel owner, then prints the values
to copy into .env.
"""

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]

CLIENT_SECRET_FILE = "client_secret.json"


def main():
    if not os.path.exists(CLIENT_SECRET_FILE):
        print(
            f"Error: {CLIENT_SECRET_FILE} not found. Download it from "
            "Google Cloud Console (APIs & Services > Credentials).",
            file=sys.stderr,
        )
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(
        port=0, access_type="offline", prompt="consent"
    )

    print("\nAdd these lines to .env at the repo root:\n")
    print(f"YT_CLIENT_ID={creds.client_id}")
    print(f"YT_CLIENT_SECRET={creds.client_secret}")
    print(f"YT_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `.env.example`**

```text
# Copy to .env (gitignored) and fill in. See docs/setup-youtube-oauth.md
# and docs/setup-instagram.md.

# YouTube Data API v3 key (Google Cloud Console > Credentials > API key)
YOUTUBE_API_KEY=

# YouTube Analytics OAuth (run: python scripts/get_yt_refresh_token.py)
YT_CLIENT_ID=
YT_CLIENT_SECRET=
YT_REFRESH_TOKEN=

# Instagram Graph API token (System User token recommended — never expires)
IG_ACCESS_TOKEN=
```

- [ ] **Step 3: Create `docs/setup-youtube-oauth.md`**

```markdown
# YouTube Analytics OAuth Setup (one-time, ~30 min)

The Analytics API needs OAuth as the channel owner (an API key is not
enough). Result: three values in `.env`.

1. Go to https://console.cloud.google.com/ — use the same project as your
   existing YouTube API key (or create one).
2. **APIs & Services > Library**: enable "YouTube Analytics API" and
   "YouTube Data API v3".
3. **APIs & Services > OAuth consent screen**: configure (External is
   fine), add your Google account as a Test user. The app can stay in
   Testing mode — but note Google expires refresh tokens for Testing-mode
   apps after 7 days. To avoid weekly re-consent, publish the app
   ("In production" — no verification needed for these read-only scopes
   used by only you).
4. **APIs & Services > Credentials > Create credentials > OAuth client
   ID**, type **Desktop app**. Download the JSON as `client_secret.json`
   into the repo root (it is gitignored).
5. Run `python scripts/get_yt_refresh_token.py`, complete consent in the
   browser **as the account that owns the channel**, and copy the three
   printed lines into `.env`.
6. Fill `own_youtube_channel_id` in `trend-sensor/config/accounts.yml`
   (find it at https://www.youtube.com/account_advanced).
7. Verify: `python trend-sensor/collect.py` → `run_meta.json` should show
   `"own_youtube": {"ok": true}`.

Known limitation: impressions and thumbnail CTR are not exposed by the
Analytics API (Studio-only). The report covers views, watch time, average
view duration/percentage, subs gained/lost, likes/comments/shares, and
traffic sources.
```

- [ ] **Step 4: Create `docs/setup-instagram.md`**

```markdown
# Instagram Graph API Setup (one-time, ~45 min)

Prereqs: the Instagram account is a **Professional** account (Business or
Creator) linked to a Facebook Page you admin.

1. Link the accounts: Instagram app > Settings > Business tools > connect
   your Facebook Page (or via the Page's settings on Facebook).
2. Create a Meta app at https://developers.facebook.com/apps > Create App
   > type "Business".
3. In the app dashboard, add the **Instagram Graph API** product.
4. Get your IG Business user ID: in https://developers.facebook.com/tools/explorer
   select your app, request permissions `instagram_basic`,
   `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`,
   then query `me/accounts` → take the Page ID → query
   `{page-id}?fields=instagram_business_account` → the returned numeric ID
   goes into `trend-sensor/config/accounts.yml` as `instagram_user_id`.
5. **Token (recommended: System User — never expires):**
   - https://business.facebook.com/settings > Users > System users >
     Add (Admin system user).
   - Assign assets: the Facebook Page (full control not required — Insights
     access suffices) and the app.
   - Generate token: select the app; scopes `instagram_basic`,
     `instagram_manage_insights`, `pages_show_list`,
     `pages_read_engagement`; expiry "Never".
   - Put it in `.env` as `IG_ACCESS_TOKEN`.
   - Fallback if System Users are unavailable on your Business account
     tier: generate a 60-day long-lived user token in Graph API Explorer
     and expect to refresh it manually every ~2 months (the report's
     warning banner will tell you when it has expired).
6. Verify: `python trend-sensor/collect.py` → `run_meta.json` should show
   `"instagram": {"ok": true}`.
```

- [ ] **Step 5: Commit**

```bash
git add scripts/get_yt_refresh_token.py docs/setup-youtube-oauth.md docs/setup-instagram.md .env.example
git commit -m "docs: add credential setup guides, OAuth helper, .env.example"
```

---

### Task 12: Retire GitHub Actions, update README

**Files:**
- Delete: `.github/workflows/weekly_digest.yml`
- Modify: `README.md`

- [ ] **Step 1: Delete the workflow**

```bash
git rm .github/workflows/weekly_digest.yml
```

- [ ] **Step 2: Rewrite README.md**

Replace the full README with:

```markdown
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
   (`core` = transcripts analyzed; `broad` = titles/descriptions only).
6. Test: `python trend-sensor/collect.py` and check
   `trend-sensor/output/<today>/run_meta.json`.

## Development

- Tests: `pip install -r requirements-dev.txt && python -m pytest trend-sensor/tests -v`
- `trend-sensor/state/ig_snapshot.json` is committed on purpose — it is
  the baseline for detecting Instagram back-catalog movers week to week.
- `trend-sensor/output/` and `trend-sensor/data/` are ephemeral and
  gitignored.
```

- [ ] **Step 3: Commit**

```bash
git add -A .github/ README.md
git commit -m "chore: retire GitHub Actions workflow, rewrite README for routine architecture"
```

---

### Task 13: End-to-end smoke test and scheduled task creation

This task needs the user's credentials in place (Tasks 11's manual steps done by the user). If credentials are not yet configured, complete Step 1 with only the competitors source and note the others failed — that exercises the partial-report path, which is itself worth verifying.

- [ ] **Step 1: Run the collector for real**

```bash
source venv/bin/activate 2>/dev/null; pip install -r trend-sensor/requirements.txt -q
python trend-sensor/collect.py
cat trend-sensor/output/$(date +%F)/run_meta.json
```

Expected: `run_meta.json` exists; `competitors.ok == true`; `own_youtube` / `instagram` true if credentials configured, otherwise recorded errors.

- [ ] **Step 2: Dry-run the routine instructions manually**

Follow `trend-sensor/ROUTINE.md` in-session against the bundle from Step 1 and write a first report to `trend-sensor/digests/`. Verify: five sections present, warning banners match failed statuses, TL;DR ≤ 10 bullets, matrix has no editorial commentary.

- [ ] **Step 3: Commit the first report**

```bash
git add trend-sensor/digests/ trend-sensor/state/
git commit -m "digest: first unified intelligence report (smoke test)"
```

- [ ] **Step 4: Create the scheduled task**

Call the `mcp__scheduled-tasks__create_scheduled_task` tool (schemas load via ToolSearch) with:

- `taskId`: `weekly-intelligence-report`
- `cronExpression`: `0 8 * * 1` (Mondays 08:00 **local time**)
- `description`: `Collect YouTube/Instagram/competitor data and write The Old Mole weekly intelligence report`
- `prompt`:

```text
Produce The Old Mole weekly intelligence report.

1. cd "/Users/sebastian/Documents/GitHub/The Old Mole" and run `git pull`.
2. Ensure deps: `source venv/bin/activate` (create the venv and
   `pip install -r trend-sensor/requirements.txt` if missing).
3. Run `python trend-sensor/collect.py`. It writes a dated bundle to
   trend-sensor/output/ and prints run_meta.json with per-source statuses.
   A failed source is NOT fatal — continue with what succeeded.
4. Read trend-sensor/ROUTINE.md and follow it exactly: analyze the newest
   output bundle and write trend-sensor/digests/{run_date}.md with the
   five required sections and warning banners for any failed sources.
5. git add trend-sensor/digests/ trend-sensor/state/, commit as
   "digest: {run_date}", and push.
6. Your completion message must be the report's warning banners (if any)
   followed by the TL;DR section verbatim.
```

The tool shows the user an approval prompt — that approval is the confirmation step. Remind the user: scheduled tasks run while the Claude app is open; a missed Monday runs on next launch.

- [ ] **Step 5: Final full-suite verification and push**

```bash
python -m pytest trend-sensor/tests -v
git push
```

Expected: all tests PASS; branch pushed.

---

## Post-plan reminders (surface to the user at completion)

1. **Rotate the leaked YouTube API key** (`AIzaSy...RRDYTM`) in Google Cloud Console — removing it from code (Task 2) does not remove it from git history.
2. Fill in `trend-sensor/config/accounts.yml` and `.env` (guides in `docs/`).
3. Scheduling is **local**: the Monday run happens when the Claude desktop app is open (or on next launch). If a detached cloud schedule is ever needed, the fallback is re-adding a GitHub Action that runs only `collect.py` and commits the bundle for a cloud agent to analyze.
4. Impressions/CTR are not API-accessible — if those matter, they must be read manually in YouTube Studio.
