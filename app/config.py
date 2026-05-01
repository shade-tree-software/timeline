import os
from pathlib import Path


class Config:
    DB_PATH = os.environ.get("TIMELINE_DB_PATH")
    OWNTRACKS_USERNAME = os.environ.get("OWNTRACKS_USERNAME", "phone")
    OWNTRACKS_PASSWORD = os.environ.get("OWNTRACKS_PASSWORD")
    VIEWER_USERNAME = os.environ.get("VIEWER_USERNAME", "viewer")
    VIEWER_PASSWORD = os.environ.get("VIEWER_PASSWORD")
    API_TOKEN = os.environ.get("API_TOKEN")
    API_MAX_LIMIT = int(os.environ.get("API_MAX_LIMIT", "50000"))
    API_DEFAULT_LIMIT = int(os.environ.get("API_DEFAULT_LIMIT", "10000"))
