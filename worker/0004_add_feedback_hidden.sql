-- Moderation switch for the public Feedback page. Rows with hidden = 1 are never listed or counted there.
-- To remove something: UPDATE feedback SET hidden = 1 WHERE id = 42;   (see README, "Feedback")
ALTER TABLE feedback ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0, 1));
CREATE INDEX IF NOT EXISTS feedback_visible ON feedback (hidden, id);
