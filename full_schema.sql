-- SEQUENCES
CREATE SEQUENCE users_seq START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE categories_seq START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE products_seq START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE orders_seq START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE orderitems_seq START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE cart_seq START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE wishlist_seq START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE payments_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE Categories (
    category_id   NUMBER PRIMARY KEY,
    category_name VARCHAR2(100) NOT NULL
);

CREATE TABLE Users (
    user_id    NUMBER PRIMARY KEY,
    name       VARCHAR2(100) NOT NULL,
    email      VARCHAR2(100) UNIQUE NOT NULL,
    password   VARCHAR2(255) NOT NULL,
    role       VARCHAR2(10) DEFAULT 'customer',
    created_at DATE DEFAULT SYSDATE
);

CREATE TABLE Products (
    product_id  NUMBER PRIMARY KEY,
    category_id NUMBER REFERENCES Categories(category_id),
    name        VARCHAR2(150) NOT NULL,
    price       NUMBER(10,2) NOT NULL,
    cost_price  NUMBER(10,2) DEFAULT 0 NOT NULL,
    stock       NUMBER DEFAULT 0,
    description VARCHAR2(500),
    image_path CLOB
);

CREATE TABLE Orders (
    order_id     NUMBER PRIMARY KEY,
    user_id      NUMBER REFERENCES Users(user_id),
    order_date   DATE DEFAULT SYSDATE,
    total_amount NUMBER(10,2),
    status       VARCHAR2(20) DEFAULT 'pending',
    DELIVERY_ADDRESS   VARCHAR2(255),
    PHONE_NUMBER VARCHAR2(20)
);

CREATE TABLE OrderItems (
    item_id    NUMBER PRIMARY KEY,
    order_id   NUMBER REFERENCES Orders(order_id),
    product_id NUMBER REFERENCES Products(product_id),
    quantity   NUMBER NOT NULL,
    unit_price NUMBER(10,2)
);

CREATE TABLE Cart (
    cart_id    NUMBER PRIMARY KEY,
    user_id    NUMBER REFERENCES Users(user_id),
    product_id NUMBER REFERENCES Products(product_id),
    quantity   NUMBER DEFAULT 1
);

CREATE TABLE Wishlist (
    wishlist_id NUMBER PRIMARY KEY,
    user_id     NUMBER REFERENCES Users(user_id),
    product_id  NUMBER REFERENCES Products(product_id)
);

CREATE TABLE Payments (
    payment_id   NUMBER PRIMARY KEY,
    order_id     NUMBER REFERENCES Orders(order_id),
    amount       NUMBER(10,2),
    payment_date DATE DEFAULT SYSDATE,
    method       VARCHAR2(20) DEFAULT 'cash'
);

-- VIEWS
CREATE OR REPLACE VIEW CustomerOrderView AS
SELECT u.user_id, u.name, o.order_id, o.order_date,
       o.total_amount, o.status
FROM Users u JOIN Orders o ON u.user_id = o.user_id;

CREATE OR REPLACE VIEW AdminInventoryView AS
SELECT p.product_id, p.name, c.category_name,
       p.price, p.cost_price, p.stock, p.description
FROM Products p JOIN Categories c ON p.category_id = c.category_id;

-- TRIGGER (auto deducts stock when order item is inserted)
CREATE OR REPLACE TRIGGER update_stock_trigger
AFTER INSERT ON OrderItems
FOR EACH ROW
BEGIN
    UPDATE Products
    SET stock = stock - :NEW.quantity
    WHERE product_id = :NEW.product_id;
END;
/
CREATE OR REPLACE PROCEDURE place_order(
    p_user_id    IN NUMBER,
    p_pay_method IN VARCHAR2,
    p_address    IN VARCHAR2,
    p_phone      IN VARCHAR2
) AS
    v_order_id   NUMBER;
    v_total      NUMBER(10,2) := 0;
    v_unit_price NUMBER(10,2);
    v_item_total NUMBER(10,2);
    v_count      NUMBER;

    CURSOR cart_cursor IS
        SELECT c.cart_id, c.product_id, c.quantity, p.price, p.stock, p.name
        FROM Cart c
        JOIN Products p ON c.product_id = p.product_id
        WHERE c.user_id = p_user_id;

BEGIN
    -- Step 1: Ensure cart is not empty
    SELECT COUNT(*) INTO v_count FROM Cart WHERE user_id = p_user_id;
    IF v_count = 0 THEN
        RAISE_APPLICATION_ERROR(-20002, 'Cart is empty. Cannot place order.');
    END IF;

    -- Step 2: Create the order
    SELECT orders_seq.NEXTVAL INTO v_order_id FROM DUAL;

    INSERT INTO Orders (order_id, user_id, order_date, total_amount, status, delivery_address, phone_number)
    VALUES (v_order_id, p_user_id, SYSDATE, 0, 'pending', p_address, p_phone);

    -- Step 3: Insert order items (triggers fire automatically)
    FOR rec IN cart_cursor LOOP
        v_unit_price := rec.price;
        v_item_total := v_unit_price * rec.quantity;
        v_total      := v_total + v_item_total;

        INSERT INTO OrderItems (item_id, order_id, product_id, quantity, unit_price)
        VALUES (orderitems_seq.NEXTVAL, v_order_id, rec.product_id, rec.quantity, v_unit_price);
    END LOOP;

    -- Step 4: Update order total
    UPDATE Orders
    SET total_amount = v_total
    WHERE order_id = v_order_id;

    -- Step 5: Record payment
    INSERT INTO Payments (payment_id, order_id, amount, payment_date, method)
    VALUES (payments_seq.NEXTVAL, v_order_id, v_total, SYSDATE, p_pay_method);

    -- Step 6: Clear cart
    DELETE FROM Cart WHERE user_id = p_user_id;

    COMMIT;

    DBMS_OUTPUT.PUT_LINE('Order placed successfully.');
    DBMS_OUTPUT.PUT_LINE('Order ID    : ' || v_order_id);
    DBMS_OUTPUT.PUT_LINE('Total Amount: Rs. ' || v_total);
    DBMS_OUTPUT.PUT_LINE('Payment via : ' || p_pay_method);

EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        DBMS_OUTPUT.PUT_LINE('Order failed. All changes rolled back.');
        DBMS_OUTPUT.PUT_LINE('Reason: ' || SQLERRM);
END place_order;
/
CREATE OR REPLACE TRIGGER check_stock_trigger
BEFORE INSERT ON OrderItems
FOR EACH ROW
DECLARE
    v_stock    NUMBER;
    v_name     VARCHAR2(150);
BEGIN
    SELECT stock, name
    INTO v_stock, v_name
    FROM Products
    WHERE product_id = :NEW.product_id;

    IF :NEW.quantity > v_stock THEN
        RAISE_APPLICATION_ERROR(
            -20001,
            'Insufficient stock for product "' || v_name ||
            '". Requested: ' || :NEW.quantity ||
            ', Available: ' || v_stock
        );
    END IF;
END;
/
-- SAMPLE DATA
SET DEFINE OFF;
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Electronics');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Clothing');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Books');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Electronics');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Clothing');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Books');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Home Appliances');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Sports');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Beauty & Personal Care');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Grocery');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Toys & Games');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Automotive');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Accessories');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Mobiles & Tablets');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Laptops');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Furniture');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Kitchen Appliances');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Fitness Equipment');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Stationery');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Footwear');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Watches');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Jewellery');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Gaming');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Music');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Movies & Media');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Pet Supplies');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Health Care');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Baby Products');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Outdoor & Travel');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Office Supplies');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Perfumes');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Smart Devices');
INSERT INTO Categories VALUES (categories_seq.NEXTVAL, 'Fashion Accessories');

COMMIT;

INSERT INTO Users (user_id, name, email, password, role, created_at)
VALUES (users_seq.NEXTVAL, 'Admin User', 'admin@smartcart.com', 'scrypt:32768:8:1$QNdQMDmArcAB7pCe$7e9f88639f1e1002a959881df8971f321f4eb5917df073cc8798146742dd61cb9cb2d2d0260887a8c68f9db543e0f139a62d49c43f43e3b3588748d350207f5d', 'admin', SYSDATE);
COMMIT;

commit;
select * from users;


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
CREATE TABLE SeasonalEvents (
    event_id       NUMBER PRIMARY KEY,
    event_name     VARCHAR2(100) NOT NULL,
    start_date     DATE NOT NULL,
    end_date       DATE NOT NULL,
    boost_weight   NUMBER(4,2) DEFAULT 1.20,
    is_approximate NUMBER(1) DEFAULT 1,
    notes          VARCHAR2(255)
);
CREATE SEQUENCE seasonalevents_seq START WITH 1 INCREMENT BY 1;

-- Ramadan/Eid dates are lunar-calendar estimates (moon-sighting dependent, can shift +/-1 day) --
-- flagged is_approximate=1, admin-editable via /admin/seasonal-events once official dates are announced.
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Ramadan 2026', DATE '2026-02-18', DATE '2026-03-19', 1.10, 1, 'Approx. - confirm via moon sighting');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Eid-ul-Fitr 2026', DATE '2026-03-20', DATE '2026-03-22', 1.40, 1, 'Approx. - 1 Shawwal 1447 AH');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Eid-ul-Adha 2026', DATE '2026-05-27', DATE '2026-05-29', 1.35, 1, 'Approx. - 10 Dhu al-Hijjah 1447 AH');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Pakistan Independence Day 2026', DATE '2026-08-14', DATE '2026-08-14', 1.15, 0, 'Fixed date');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, '11.11 Sale 2026', DATE '2026-11-11', DATE '2026-11-11', 1.50, 0, 'Fixed date');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Ramadan 2027', DATE '2027-02-08', DATE '2027-03-09', 1.10, 1, 'Approx.');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Eid-ul-Fitr 2027', DATE '2027-03-10', DATE '2027-03-12', 1.40, 1, 'Approx.');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Eid-ul-Adha 2027', DATE '2027-05-17', DATE '2027-05-19', 1.35, 1, 'Approx.');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Pakistan Independence Day 2027', DATE '2027-08-14', DATE '2027-08-14', 1.15, 0, 'Fixed date');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, '11.11 Sale 2027', DATE '2027-11-11', DATE '2027-11-11', 1.50, 0, 'Fixed date');
COMMIT;

CREATE TABLE ForecastCache (
    cache_id          NUMBER PRIMARY KEY,
    generated_at       DATE DEFAULT SYSDATE,
    horizon             VARCHAR2(10),
    predicted_total     NUMBER(12,2),
    pct_change          NUMBER(6,2),
    confidence_pct      NUMBER(5,2),
    sufficiency_level   VARCHAR2(20),
    details_json        CLOB
);
CREATE SEQUENCE forecastcache_seq START WITH 1 INCREMENT BY 1;
CREATE TABLE ProductFeedback (
    feedback_id  NUMBER PRIMARY KEY,
    product_id   NUMBER NOT NULL REFERENCES Products(product_id),
    user_id      NUMBER NOT NULL REFERENCES Users(user_id),
    rating       NUMBER(1),
    comment_text VARCHAR2(2000),
    media_path   CLOB,
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
    media_path    CLOB,
    media_type    VARCHAR2(10),
    created_at    DATE DEFAULT SYSDATE
);
CREATE SEQUENCE feedbackreplies_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_feedbackreplies_feedback ON FeedbackReplies(feedback_id);
CREATE TABLE AdminAuditLog (
    audit_id      NUMBER PRIMARY KEY,
    admin_user_id NUMBER REFERENCES Users(user_id),
    action        VARCHAR2(100) NOT NULL,
    target_type   VARCHAR2(50),
    target_id     NUMBER,
    details       VARCHAR2(1000),
    ip_address    VARCHAR2(45),
    created_at    DATE DEFAULT SYSDATE
);
CREATE SEQUENCE adminauditlog_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_auditlog_created ON AdminAuditLog(created_at);

CREATE TABLE LoginAttempts (
    attempt_id   NUMBER PRIMARY KEY,
    email        VARCHAR2(100) NOT NULL,
    ip_address   VARCHAR2(45),
    success      NUMBER(1) DEFAULT 0,
    attempted_at DATE DEFAULT SYSDATE
);
CREATE SEQUENCE loginattempts_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_loginattempts_email_time ON LoginAttempts(email, attempted_at);
ALTER TABLE Orders ADD (
    payment_method           VARCHAR2(20) DEFAULT 'cod' NOT NULL,
    payment_proof_path       CLOB,
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
    discount_type     VARCHAR2(20) DEFAULT 'percentage' NOT NULL,
    discount_percent  NUMBER(5,2),
    discount_amount   NUMBER(10,2) DEFAULT 0,
    max_uses          NUMBER,
    used_count        NUMBER DEFAULT 0 NOT NULL,
    valid_from        DATE DEFAULT SYSDATE,
    valid_to          DATE,
    active            NUMBER(1) DEFAULT 1,
    created_by        NUMBER REFERENCES Users(user_id),
    created_at        DATE DEFAULT SYSDATE,
    CONSTRAINT chk_coupon_type CHECK (discount_type IN ('percentage', 'fixed')),
    CONSTRAINT chk_coupon_discount CHECK (discount_percent IS NULL OR (discount_percent BETWEEN 1 AND 100))
);
CREATE SEQUENCE coupons_seq START WITH 1 INCREMENT BY 1;
CREATE TABLE ProductMedia (
    media_id    NUMBER PRIMARY KEY,
    product_id  NUMBER NOT NULL REFERENCES Products(product_id),
    media_path  CLOB NOT NULL,
    media_type  VARCHAR2(10) NOT NULL,
    sort_order  NUMBER DEFAULT 0,
    created_at  DATE DEFAULT SYSDATE,
    CONSTRAINT chk_productmedia_type CHECK (media_type IN ('image','video'))
);
CREATE SEQUENCE productmedia_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_productmedia_product ON ProductMedia(product_id, sort_order);
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
CREATE TABLE SiteSettings (
    setting_key   VARCHAR2(50) PRIMARY KEY,
    setting_value VARCHAR2(500)
);
INSERT INTO SiteSettings VALUES ('bank_name', 'PLEASE SET IN ADMIN PORTAL');
INSERT INTO SiteSettings VALUES ('bank_account_title', 'PLEASE SET IN ADMIN PORTAL');
INSERT INTO SiteSettings VALUES ('bank_account_number', 'PLEASE SET IN ADMIN PORTAL');
INSERT INTO SiteSettings VALUES ('bank_iban', 'PLEASE SET IN ADMIN PORTAL');
COMMIT;
CREATE OR REPLACE PROCEDURE place_order(
    p_user_id           IN  NUMBER,
    p_pay_method        IN  VARCHAR2,
    p_address           IN  VARCHAR2,
    p_phone             IN  VARCHAR2,
    p_payment_proof_path IN CLOB,
    p_points_to_redeem  IN  NUMBER,
    p_coupon_code       IN  VARCHAR2,
    p_cod_advance_amount IN NUMBER,
    p_min_margin_floor  IN  NUMBER,
    p_order_id          OUT NUMBER,
    p_final_total       OUT NUMBER,
    p_coupon_discount   OUT NUMBER,
    p_loyalty_discount  OUT NUMBER,
    p_points_redeemed   OUT NUMBER,
    p_advance_required  OUT NUMBER
) AS
    v_order_id      NUMBER;
    v_subtotal      NUMBER(10,2) := 0;
    v_min_floor_price NUMBER(10,2) := 0;
    v_max_total_discount NUMBER(10,2) := 0;
    v_remaining_discount_cap NUMBER(10,2) := 0;
    v_margin_floor  NUMBER(10,2) := NVL(p_min_margin_floor, 300);
    v_count         NUMBER;
    v_balance       NUMBER := 0;
    v_max_redeem    NUMBER;
    v_redeem_points NUMBER := NVL(p_points_to_redeem, 0);
    v_loyalty_disc  NUMBER(10,2) := 0;
    v_coupon_type   VARCHAR2(20) := 'percentage';
    v_coupon_pct    NUMBER := 0;
    v_coupon_amt    NUMBER(10,2) := 0;
    v_coupon_disc   NUMBER(10,2) := 0;
    v_coupon_id     NUMBER;
    v_discounted    NUMBER(10,2);
    v_final_total   NUMBER(10,2);
    v_advance       NUMBER(10,2);
    v_already_used  NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM Cart WHERE user_id = p_user_id;
    IF v_count = 0 THEN
        RAISE_APPLICATION_ERROR(-20002, 'Cart is empty');
    END IF;

    FOR item IN (
        SELECT c.product_id, c.quantity, p.stock, p.name, p.price, NVL(p.cost_price, 0) AS cost_price
        FROM Cart c
        JOIN Products p ON c.product_id = p.product_id
        WHERE c.user_id = p_user_id
    ) LOOP
        IF item.stock < item.quantity THEN
            RAISE_APPLICATION_ERROR(
                -20001,
                'Insufficient stock for product "' || item.name || '". Requested: ' || item.quantity || ', Available: ' || item.stock
            );
        END IF;
        v_subtotal := v_subtotal + (item.price * item.quantity);
        v_min_floor_price := v_min_floor_price + (item.quantity * (item.cost_price + v_margin_floor));
    END LOOP;

    v_max_total_discount := GREATEST(0, v_subtotal - v_min_floor_price);

    IF p_coupon_code IS NOT NULL AND TRIM(p_coupon_code) IS NOT NULL THEN
        BEGIN
            SELECT coupon_id, NVL(discount_type, 'percentage'), NVL(discount_percent, 0), NVL(discount_amount, 0)
            INTO v_coupon_id, v_coupon_type, v_coupon_pct, v_coupon_amt
            FROM Coupons
            WHERE UPPER(code) = UPPER(TRIM(p_coupon_code))
              AND active = 1
              AND (valid_to IS NULL OR valid_to >= SYSDATE)
              AND (max_uses IS NULL OR used_count < max_uses);
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(-20003, 'Invalid or expired coupon code.');
        END;

        SELECT COUNT(*) INTO v_already_used FROM Orders
        WHERE user_id = p_user_id AND UPPER(coupon_code) = UPPER(p_coupon_code) AND status != 'cancelled';
        IF v_already_used > 0 THEN
            RAISE_APPLICATION_ERROR(-20004, 'You have already used this coupon code.');
        END IF;

        IF v_coupon_type = 'fixed' THEN
            v_coupon_disc := LEAST(v_coupon_amt, v_max_total_discount, v_subtotal);
        ELSE
            v_coupon_disc := LEAST(ROUND(v_subtotal * v_coupon_pct / 100, 2), v_max_total_discount);
        END IF;
    END IF;

    v_discounted := v_subtotal - v_coupon_disc;
    v_remaining_discount_cap := GREATEST(0, v_max_total_discount - v_coupon_disc);

    BEGIN
        SELECT NVL(loyalty_points_balance, 0) INTO v_balance FROM Users WHERE user_id = p_user_id;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            v_balance := 0;
    END;

    IF v_redeem_points < 0 THEN
        v_redeem_points := 0;
    END IF;
    IF v_redeem_points > v_balance THEN
        v_redeem_points := v_balance;
    END IF;
    v_max_redeem := FLOOR(LEAST(v_discounted * 0.5, v_remaining_discount_cap) * 10);
    IF v_redeem_points > v_max_redeem THEN
        v_redeem_points := v_max_redeem;
    END IF;
    v_loyalty_disc := v_redeem_points / 10;

    v_final_total := v_discounted - v_loyalty_disc;
    v_advance := CASE WHEN p_pay_method = 'cod' THEN 0 ELSE v_final_total END;

    SELECT orders_seq.NEXTVAL INTO v_order_id FROM DUAL;

    INSERT INTO Orders (order_id, user_id, order_date, total_amount, status, delivery_address, phone_number,
                         loyalty_points_redeemed, loyalty_discount_amount, loyalty_points_earned,
                         payment_method, payment_proof_path, payment_status, advance_amount,
                         coupon_code, coupon_discount_amount)
    VALUES (v_order_id, p_user_id, SYSDATE, v_final_total, 'pending', p_address, p_phone,
            v_redeem_points, v_loyalty_disc, 0,
            p_pay_method,
            CASE WHEN p_pay_method = 'cod' THEN NULL ELSE p_payment_proof_path END,
            CASE WHEN p_pay_method = 'cod' THEN 'verified' ELSE 'pending_verification' END,
            CASE WHEN p_pay_method = 'cod' THEN 0 ELSE v_final_total END,
            CASE WHEN v_coupon_id IS NOT NULL THEN UPPER(p_coupon_code) ELSE NULL END, v_coupon_disc);

    FOR item IN (
        SELECT c.product_id, c.quantity, p.price
        FROM Cart c
        JOIN Products p ON c.product_id = p.product_id
        WHERE c.user_id = p_user_id
    ) LOOP
        INSERT INTO OrderItems (item_id, order_id, product_id, quantity, unit_price)
        VALUES (orderitems_seq.NEXTVAL, v_order_id, item.product_id, item.quantity, item.price);

        UPDATE Products SET stock = stock - item.quantity WHERE product_id = item.product_id;
    END LOOP;

    BEGIN
        INSERT INTO Payments (payment_id, order_id, amount, payment_date, method)
        VALUES (payments_seq.NEXTVAL, v_order_id, v_final_total, SYSDATE, p_pay_method);
    EXCEPTION
        WHEN OTHERS THEN
            NULL;
    END;

    DELETE FROM Cart WHERE user_id = p_user_id;

    IF v_redeem_points > 0 THEN
        UPDATE Users
        SET loyalty_points_balance = loyalty_points_balance - v_redeem_points
        WHERE user_id = p_user_id;

        BEGIN
            INSERT INTO LoyaltyLedger (ledger_id, user_id, order_id, entry_type, points, rupee_value, balance_after, created_at)
            VALUES (loyaltyledger_seq.NEXTVAL, p_user_id, v_order_id, 'redeem', v_redeem_points, v_loyalty_disc,
                    v_balance - v_redeem_points, SYSDATE);
        EXCEPTION
            WHEN OTHERS THEN
                NULL;
        END;
    END IF;

    IF v_coupon_id IS NOT NULL THEN
        UPDATE Coupons SET used_count = used_count + 1 WHERE coupon_id = v_coupon_id;
    END IF;

    p_order_id          := v_order_id;
    p_final_total       := v_final_total;
    p_coupon_discount   := v_coupon_disc;
    p_loyalty_discount  := v_loyalty_disc;
    p_points_redeemed   := v_redeem_points;
    p_advance_required  := v_advance;
END place_order;
/

CREATE OR REPLACE PROCEDURE complete_order_loyalty(
    p_order_id      IN  NUMBER,
    p_points_earned OUT NUMBER
) AS
    v_user_id NUMBER;
    v_total   NUMBER(10,2);
    v_already NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_already FROM LoyaltyLedger
    WHERE order_id = p_order_id AND entry_type = 'earn';
    IF v_already > 0 THEN
        p_points_earned := 0;
        RETURN;
    END IF;

    SELECT user_id, total_amount INTO v_user_id, v_total FROM Orders WHERE order_id = p_order_id;

    IF v_total >= 5000 THEN
        p_points_earned := 100 + FLOOR((v_total - 5000) / 1000) * 20;
    ELSE
        p_points_earned := 0;
    END IF;

    IF p_points_earned > 0 THEN
        UPDATE Users SET loyalty_points_balance = loyalty_points_balance + p_points_earned
        WHERE user_id = v_user_id;

        UPDATE Orders SET loyalty_points_earned = p_points_earned WHERE order_id = p_order_id;

        INSERT INTO LoyaltyLedger (ledger_id, user_id, order_id, entry_type, points, rupee_value, balance_after, created_at)
        SELECT loyaltyledger_seq.NEXTVAL, v_user_id, p_order_id, 'earn', p_points_earned, NULL,
               loyalty_points_balance, SYSDATE
        FROM Users WHERE user_id = v_user_id;
    END IF;

    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END complete_order_loyalty;
/

CREATE OR REPLACE PROCEDURE verify_bank_transfer_cashback(
    p_order_id       IN  NUMBER,
    p_cashback_points IN NUMBER,
    p_points_awarded OUT NUMBER
) AS
    v_user_id NUMBER;
    v_method  VARCHAR2(20);
    v_already NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_already FROM LoyaltyLedger
    WHERE order_id = p_order_id AND entry_type = 'cashback';
    IF v_already > 0 THEN
        p_points_awarded := 0;
        RETURN;
    END IF;

    SELECT user_id, payment_method INTO v_user_id, v_method FROM Orders WHERE order_id = p_order_id;

    IF v_method = 'bank_transfer' THEN
        p_points_awarded := NVL(p_cashback_points, 400);
        UPDATE Users SET loyalty_points_balance = loyalty_points_balance + p_points_awarded
        WHERE user_id = v_user_id;

        UPDATE Orders SET cashback_points_awarded = p_points_awarded WHERE order_id = p_order_id;

        INSERT INTO LoyaltyLedger (ledger_id, user_id, order_id, entry_type, points, rupee_value, balance_after, created_at)
        SELECT loyaltyledger_seq.NEXTVAL, v_user_id, p_order_id, 'cashback', p_points_awarded, NULL,
               loyalty_points_balance, SYSDATE
        FROM Users WHERE user_id = v_user_id;
    ELSE
        p_points_awarded := 0;
    END IF;

    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END verify_bank_transfer_cashback;
/
-- Extends SiteSettings (already created in 008) with contact info, site
-- copy/messages, an optional sitewide announcement banner, and the
-- payment amounts shown on the checkout page -- so all of it is
-- admin-editable from /admin/settings instead of hardcoded in templates
-- or environment config.
INSERT INTO SiteSettings VALUES ('contact_phone', '+923312344418');
INSERT INTO SiteSettings VALUES ('contact_email', 'azfar.aa.abbasi@gmail.com');
INSERT INTO SiteSettings VALUES ('whatsapp_number', '923312344418');
INSERT INTO SiteSettings VALUES ('hero_title', 'Welcome to SmartCart');
INSERT INTO SiteSettings VALUES ('hero_subtitle', 'Browse our full catalog - no account needed to look around.');
INSERT INTO SiteSettings VALUES ('checkout_notice', 'Orders are dispatched once payment is verified. You''ll receive an email once your payment is confirmed.');
INSERT INTO SiteSettings VALUES ('site_announcement', '');
INSERT INTO SiteSettings VALUES ('footer_note', '');
INSERT INTO SiteSettings VALUES ('cod_advance_amount', '300');
INSERT INTO SiteSettings VALUES ('cashback_points', '400');
COMMIT;
ALTER TABLE Users ADD (
    email_verified NUMBER(1) DEFAULT 0 NOT NULL,
    verification_code VARCHAR2(6),
    verification_code_expires DATE
);

-- Existing accounts registered before this feature existed shouldn't be
-- locked out retroactively -- only new registrations go through the flow.
UPDATE Users SET email_verified = 1 WHERE email_verified = 0;
COMMIT;
ALTER TABLE Products ADD (
    delivery_time_text VARCHAR2(100),
    free_delivery NUMBER(1) DEFAULT 0 NOT NULL
);
-- Widen the legacy single-line address (kept for backward compatibility --
-- anything already reading Orders.delivery_address, e.g. WhatsApp/email
-- text, keeps working) and add structured parts for cleaner display on
-- the printable packing slip and admin order views.
ALTER TABLE Orders MODIFY (delivery_address VARCHAR2(500));

ALTER TABLE Orders ADD (
    address_city         VARCHAR2(50),
    address_area         VARCHAR2(150),
    address_house_no     VARCHAR2(100),
    address_block_sector VARCHAR2(100),
    address_landmark     VARCHAR2(150),
    address_notes        VARCHAR2(255)
);
CREATE TABLE ProductSuggestions (
    suggestion_id NUMBER PRIMARY KEY,
    user_id       NUMBER NOT NULL REFERENCES Users(user_id),
    description   VARCHAR2(1000),
    media_path    CLOB,
    media_type    VARCHAR2(10),
    status        VARCHAR2(20) DEFAULT 'new' NOT NULL,
    created_at    DATE DEFAULT SYSDATE
);
CREATE SEQUENCE productsuggestions_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_productsuggestions_created ON ProductSuggestions(created_at);
