ALTER TABLE Orders ADD (
    payment_method           VARCHAR2(20) DEFAULT 'cod' NOT NULL,
    payment_proof_path       VARCHAR2(255),
    payment_status           VARCHAR2(20) DEFAULT 'pending_verification' NOT NULL,
    advance_amount           NUMBER(10,2) DEFAULT 0 NOT NULL,
    cashback_points_awarded  NUMBER DEFAULT 0 NOT NULL,
    coupon_code              VARCHAR2(30),
    coupon_discount_amount   NUMBER(10,2) DEFAULT 0 NOT NULL,
    payment_verified_at      DATE,
    payment_verified_by      NUMBER REFERENCES Users(user_id),
    payment_rejection_reason VARCHAR2(255)
);
ALTER TABLE Orders ADD CONSTRAINT chk_orders_payment_method CHECK (payment_method IN ('cod','bank_transfer'));
ALTER TABLE Orders ADD CONSTRAINT chk_orders_payment_status CHECK (payment_status IN ('pending_verification','verified','rejected'));

CREATE TABLE Coupons (
    coupon_id        NUMBER PRIMARY KEY,
    code              VARCHAR2(30) UNIQUE NOT NULL,
    discount_percent  NUMBER(5,2) NOT NULL,
    max_uses          NUMBER,
    used_count        NUMBER DEFAULT 0 NOT NULL,
    valid_from        DATE DEFAULT SYSDATE,
    valid_to          DATE,
    active            NUMBER(1) DEFAULT 1,
    created_by        NUMBER REFERENCES Users(user_id),
    created_at        DATE DEFAULT SYSDATE,
    CONSTRAINT chk_coupon_discount CHECK (discount_percent BETWEEN 1 AND 100)
);
CREATE SEQUENCE coupons_seq START WITH 1 INCREMENT BY 1;
