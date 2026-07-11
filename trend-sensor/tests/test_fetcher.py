import pytest

from src import fetcher


def test_get_youtube_client_raises_without_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="YOUTUBE_API_KEY"):
        fetcher.get_youtube_client()
