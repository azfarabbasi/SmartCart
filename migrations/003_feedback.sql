CREATE TABLE ProductFeedback (
    feedback_id  NUMBER PRIMARY KEY,
    product_id   NUMBER NOT NULL REFERENCES Products(product_id),
    user_id      NUMBER NOT NULL REFERENCES Users(user_id),
    rating       NUMBER(1),
    comment_text VARCHAR2(2000),
    media_path   VARCHAR2(255),
    media_type   VARCHAR2(10),
    created_at   DATE DEFAULT SYSDATE,
    CONSTRAINT chk_feedback_rating CHECK (rating BETWEEN 1 AND 5)
);
CREATE SEQUENCE productfeedback_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_feedback_product ON ProductFeedback(product_id, created_at);

CREATE TABLE FeedbackReplies (
    reply_id      NUMBER PRIMARY KEY,
    feedback_id   NUMBER NOT NULL REFERENCES ProductFeedback(feedback_id),
    admin_user_id NUMBER NOT NULL REFERENCES Users(user_id),
    reply_text    VARCHAR2(2000),
    media_path    VARCHAR2(255),
    media_type    VARCHAR2(10),
    created_at    DATE DEFAULT SYSDATE
);
CREATE SEQUENCE feedbackreplies_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_feedbackreplies_feedback ON FeedbackReplies(feedback_id);
