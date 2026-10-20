-- Why a comment is being held back from the public Feedback page (set by worker/feedback.js, NULL = published).
-- The star rating and topics are still shown; only the comment text is withheld while flag is set.
-- Review:   SELECT id, flag, comment FROM feedback WHERE flag IS NOT NULL AND hidden = 0;
-- Approve:  UPDATE feedback SET flag = NULL WHERE id = 42;
-- Remove:   UPDATE feedback SET hidden = 1 WHERE id = 42;
-- Rows flagged 'spam' are inserted with hidden = 1, so they are not listed or counted at all.
ALTER TABLE feedback ADD COLUMN flag TEXT CHECK (flag IS NULL OR flag IN ('link', 'language', 'spam', 'caps', 'duplicate'));
