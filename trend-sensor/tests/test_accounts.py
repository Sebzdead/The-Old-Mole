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
