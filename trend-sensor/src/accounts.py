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
