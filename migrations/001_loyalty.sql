-- Loyalty points: running balance on Users + full auditable ledger.
ALTER TABLE Users ADD (loyalty_points_balance NUMBER DEFAULT 0 NOT NULL);

CREATE TABLE LoyaltyLedger (
    ledger_id     NUMBER PRIMARY KEY,
    user_id       NUMBER NOT NULL REFERENCES Users(user_id),
    order_id      NUMBER REFERENCES Orders(order_id),
    entry_type    VARCHAR2(10) NOT NULL,
    points        NUMBER NOT NULL,
    rupee_value   NUMBER(10,2),
    balance_after NUMBER NOT NULL,
    created_at    DATE DEFAULT SYSDATE,
    CONSTRAINT chk_ledger_entry_type CHECK (entry_type IN ('earn','redeem','cashback'))
);
CREATE SEQUENCE loyaltyledger_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_loyaltyledger_user ON LoyaltyLedger(user_id, created_at);

ALTER TABLE Orders ADD (
    loyalty_points_redeemed NUMBER DEFAULT 0 NOT NULL,
    loyalty_discount_amount NUMBER(10,2) DEFAULT 0 NOT NULL,
    loyalty_points_earned   NUMBER DEFAULT 0 NOT NULL
);
