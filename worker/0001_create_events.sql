-- Anonymous usage counts for filamentclip.com. No IPs, user agents, filenames or label text are stored.
CREATE TABLE IF NOT EXISTS events (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      INTEGER NOT NULL,            -- unix seconds
  clips   INTEGER NOT NULL,            -- label clips in the batch (1-100)
  holders INTEGER NOT NULL DEFAULT 0,  -- holders / templates in the batch
  plates  INTEGER NOT NULL DEFAULT 0,
  printer TEXT,                        -- printer id from the studio list, e.g. H2D
  nfc     INTEGER NOT NULL DEFAULT 0,  -- NFC pockets selected
  sleeve  INTEGER NOT NULL DEFAULT 0,  -- holder sleeve selected
  vendors TEXT                         -- JSON, e.g. {"Bambu Lab":4,"Amolen":2}
);
CREATE INDEX IF NOT EXISTS events_ts ON events (ts);
