CREATE TABLE IF NOT EXISTS locations (
    id      INTEGER PRIMARY KEY,
    tst     INTEGER NOT NULL,
    tid     TEXT,
    lat     REAL    NOT NULL,
    lon     REAL    NOT NULL,
    acc     REAL,
    alt     REAL,
    vel     REAL,
    cog     REAL,
    batt    INTEGER,
    bs      INTEGER,
    conn    TEXT,
    trigger TEXT,
    raw     TEXT    NOT NULL,
    received_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_locations_tst ON locations(tst);
CREATE INDEX IF NOT EXISTS idx_locations_tid_tst ON locations(tid, tst);
