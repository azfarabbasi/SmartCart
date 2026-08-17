-- Migration 016: Convert image and media path columns to CLOB for Base64 data URL storage
-- Allows direct storage of Base64 encoded images (JPG, JPEG, PNG, HEIC/HEIF, WEBP)

-- Products.image_path
ALTER TABLE Products ADD (image_path_clob CLOB);
UPDATE Products SET image_path_clob = image_path;
ALTER TABLE Products DROP COLUMN image_path;
ALTER TABLE Products RENAME COLUMN image_path_clob TO image_path;

-- ProductMedia.media_path
ALTER TABLE ProductMedia ADD (media_path_clob CLOB);
UPDATE ProductMedia SET media_path_clob = media_path;
ALTER TABLE ProductMedia DROP COLUMN media_path;
ALTER TABLE ProductMedia RENAME COLUMN media_path_clob TO media_path;

-- ProductFeedback.media_path
ALTER TABLE ProductFeedback ADD (media_path_clob CLOB);
UPDATE ProductFeedback SET media_path_clob = media_path;
ALTER TABLE ProductFeedback DROP COLUMN media_path;
ALTER TABLE ProductFeedback RENAME COLUMN media_path_clob TO media_path;

-- FeedbackReplies.media_path
ALTER TABLE FeedbackReplies ADD (media_path_clob CLOB);
UPDATE FeedbackReplies SET media_path_clob = media_path;
ALTER TABLE FeedbackReplies DROP COLUMN media_path;
ALTER TABLE FeedbackReplies RENAME COLUMN media_path_clob TO media_path;

-- ProductSuggestions.media_path
ALTER TABLE ProductSuggestions ADD (media_path_clob CLOB);
UPDATE ProductSuggestions SET media_path_clob = media_path;
ALTER TABLE ProductSuggestions DROP COLUMN media_path;
ALTER TABLE ProductSuggestions RENAME COLUMN media_path_clob TO media_path;

-- Orders.payment_proof_path
ALTER TABLE Orders ADD (payment_proof_path_clob CLOB);
UPDATE Orders SET payment_proof_path_clob = payment_proof_path;
ALTER TABLE Orders DROP COLUMN payment_proof_path;
ALTER TABLE Orders RENAME COLUMN payment_proof_path_clob TO payment_proof_path;
