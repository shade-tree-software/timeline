import os
from pathlib import Path


class Config:
    DB_PATH = os.environ.get(
        "LOC_DB_PATH",
        str(Path(__file__).resolve().parent.parent / "loc.sqlite3"),
    )
    OWNTRACKS_USERNAME = os.environ.get("OWNTRACKS_USERNAME", "phone")
    OWNTRACKS_PASSWORD = os.environ.get("OWNTRACKS_PASSWORD")
    VIEWER_USERNAME = os.environ.get("VIEWER_USERNAME", "viewer")
    VIEWER_PASSWORD = os.environ.get("VIEWER_PASSWORD")
