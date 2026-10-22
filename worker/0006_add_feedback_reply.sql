-- The owner's public reply to a piece of feedback (shown under the comment on the Feedback page).
-- Write one by hand in the D1 console / wrangler (see README, "Feedback"); the worker cleans it the same way as visitor text.
-- Replies are withheld with the comment if the comment is flagged.
ALTER TABLE feedback ADD COLUMN reply TEXT CHECK (reply IS NULL OR length(reply) <= 600);
ALTER TABLE feedback ADD COLUMN reply_ts INTEGER;
