import sqlite3
from pathlib import Path

from flask import Flask, current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DB_PATH"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(app: Flask) -> None:
    schema = (Path(app.root_path) / "schema.sql").read_text()
    with sqlite3.connect(app.config["DB_PATH"]) as conn:
        conn.executescript(schema)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(locations)")}
        if "spurious" not in cols:
            conn.execute(
                "ALTER TABLE locations ADD COLUMN spurious INTEGER NOT NULL DEFAULT 0"
            )


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)
    init_db(app)
