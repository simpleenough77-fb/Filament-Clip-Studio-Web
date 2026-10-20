-- Anonymous feedback from filamentclip.com (rating, optional topics, optional short comment).
-- No IPs, user agents, cookies or identifiers are stored, and nothing in this table is ever rendered on the site.
-- comment is plain text, already normalized by worker/feedback.js; read it only in the D1 console or wrangler.
CREATE TABLE IF NOT EXISTS feedback (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      INTEGER NOT NULL,                                          -- unix seconds
  source  TEXT    NOT NULL CHECK (source IN ('download', 'page')),   -- prompt after the ZIP download, or the Feedback page
  rating  INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  tags    TEXT    NOT NULL DEFAULT '[]',                             -- JSON array of allowlisted topic ids
  comment TEXT    CHECK (comment IS NULL OR length(comment) <= 500)
);
CREATE INDEX IF NOT EXISTS feedback_ts ON feedback (ts);
