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


def test_fetch_comments_stops_on_empty_page_with_token():
    # Pathological API response: empty items but a nextPageToken present.
    # Without a guard this would loop forever.
    client = FakeDataClient([_page(["a"] * 5, "tok"), _page([], "tok2")])
    comments = yt_comments.fetch_comments(client, "vid1", max_comments=100)
    assert len(comments) == 5
    # The empty page must terminate pagination: exactly two API calls,
    # no third attempt to follow "tok2".
    assert len(client.commentThreads().calls) == 2


def test_fetch_comments_returns_empty_on_error():
    class Exploding:
        def commentThreads(self):
            raise RuntimeError("comments disabled")

    comments = yt_comments.fetch_comments(Exploding(), "vid1")
    assert comments == []
