CREATE TABLE CustomerActivityLog (
    activity_id  NUMBER PRIMARY KEY,
    user_id      NUMBER NOT NULL REFERENCES Users(user_id),
    event_type   VARCHAR2(30) NOT NULL,
    product_id   NUMBER REFERENCES Products(product_id),
    order_id     NUMBER REFERENCES Orders(order_id),
    created_at   DATE DEFAULT SYSDATE,
    CONSTRAINT chk_activitylog_event CHECK (event_type IN
        ('view_product','add_to_cart','checkout_start','payment_uploaded','order_placed'))
);
CREATE SEQUENCE customeractivitylog_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_activitylog_user_time ON CustomerActivityLog(user_id, created_at);

CREATE TABLE ChurnScoreCache (
    cache_id       NUMBER PRIMARY KEY,
    generated_at   DATE DEFAULT SYSDATE,
    user_id        NUMBER NOT NULL REFERENCES Users(user_id),
    risk_score     NUMBER(5,2),
    risk_level     VARCHAR2(10),
    reason_summary VARCHAR2(500)
);
CREATE SEQUENCE churnscorecache_seq START WITH 1 INCREMENT BY 1;
