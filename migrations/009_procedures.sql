CREATE OR REPLACE PROCEDURE place_order(
    p_user_id           IN  NUMBER,
    p_pay_method        IN  VARCHAR2,
    p_address           IN  VARCHAR2,
    p_phone             IN  VARCHAR2,
    p_payment_proof_path IN VARCHAR2,
    p_points_to_redeem  IN  NUMBER,
    p_coupon_code       IN  VARCHAR2,
    p_order_id          OUT NUMBER,
    p_final_total       OUT NUMBER,
    p_coupon_discount   OUT NUMBER,
    p_loyalty_discount  OUT NUMBER,
    p_points_redeemed   OUT NUMBER,
    p_advance_required  OUT NUMBER
) AS
    v_order_id      NUMBER;
    v_subtotal      NUMBER(10,2) := 0;
    v_unit_price    NUMBER(10,2);
    v_count         NUMBER;
    v_balance       NUMBER;
    v_max_redeem    NUMBER;
    v_redeem_points NUMBER := NVL(p_points_to_redeem, 0);
    v_loyalty_disc  NUMBER(10,2) := 0;
    v_coupon_id     NUMBER;
    v_coupon_pct    NUMBER;
    v_coupon_disc   NUMBER(10,2) := 0;
    v_discounted    NUMBER(10,2);
    v_final_total   NUMBER(10,2);
    v_advance       NUMBER(10,2);

    CURSOR cart_cursor IS
        SELECT c.cart_id, c.product_id, c.quantity, p.price, p.stock, p.name
        FROM Cart c JOIN Products p ON c.product_id = p.product_id
        WHERE c.user_id = p_user_id;
BEGIN
    SELECT COUNT(*) INTO v_count FROM Cart WHERE user_id = p_user_id;
    IF v_count = 0 THEN
        RAISE_APPLICATION_ERROR(-20002, 'Cart is empty. Cannot place order.');
    END IF;

    SELECT NVL(SUM(c.quantity * p.price), 0) INTO v_subtotal
    FROM Cart c JOIN Products p ON c.product_id = p.product_id
    WHERE c.user_id = p_user_id;

    -- Coupon: validated and applied before anything else; fails loudly if invalid
    -- rather than silently placing the order without the expected discount.
    IF p_coupon_code IS NOT NULL THEN
        BEGIN
            SELECT coupon_id, discount_percent INTO v_coupon_id, v_coupon_pct
            FROM Coupons
            WHERE code = UPPER(p_coupon_code)
              AND active = 1
              AND SYSDATE BETWEEN valid_from AND NVL(valid_to, SYSDATE + 9999)
              AND (max_uses IS NULL OR used_count < max_uses);
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(-20003, 'Invalid or expired coupon code.');
        END;
        v_coupon_disc := ROUND(v_subtotal * v_coupon_pct / 100, 2);
    END IF;

    v_discounted := v_subtotal - v_coupon_disc;

    -- Loyalty points: row-lock the balance to prevent a double-spend race from
    -- two concurrent checkout requests on the same account.
    SELECT loyalty_points_balance INTO v_balance FROM Users WHERE user_id = p_user_id FOR UPDATE;

    IF v_redeem_points < 0 THEN
        v_redeem_points := 0;
    END IF;
    IF v_redeem_points > v_balance THEN
        v_redeem_points := v_balance;
    END IF;
    v_max_redeem := FLOOR(v_discounted * 0.5 * 2);  -- 2 points = Rs.1, capped at 50% of discounted subtotal
    IF v_redeem_points > v_max_redeem THEN
        v_redeem_points := v_max_redeem;
    END IF;
    v_loyalty_disc := v_redeem_points / 2;

    v_final_total := v_discounted - v_loyalty_disc;
    v_advance := CASE WHEN p_pay_method = 'cod' THEN 300 ELSE v_final_total END;

    SELECT orders_seq.NEXTVAL INTO v_order_id FROM DUAL;

    INSERT INTO Orders (order_id, user_id, order_date, total_amount, status, delivery_address, phone_number,
                         loyalty_points_redeemed, loyalty_discount_amount, loyalty_points_earned,
                         payment_method, payment_proof_path, payment_status, advance_amount,
                         coupon_code, coupon_discount_amount)
    VALUES (v_order_id, p_user_id, SYSDATE, v_final_total, 'pending', p_address, p_phone,
            v_redeem_points, v_loyalty_disc, 0,
            p_pay_method, p_payment_proof_path, 'pending_verification', v_advance,
            CASE WHEN v_coupon_id IS NOT NULL THEN UPPER(p_coupon_code) ELSE NULL END, v_coupon_disc);

    FOR rec IN cart_cursor LOOP
        v_unit_price := rec.price;
        INSERT INTO OrderItems (item_id, order_id, product_id, quantity, unit_price)
        VALUES (orderitems_seq.NEXTVAL, v_order_id, rec.product_id, rec.quantity, v_unit_price);
    END LOOP;
    -- check_stock_trigger fires per-row above and raises ORA-20001 on insufficient
    -- stock, which propagates to WHEN OTHERS below and rolls back everything,
    -- including this Orders insert and the loyalty balance decrement further down.

    INSERT INTO Payments (payment_id, order_id, amount, payment_date, method)
    VALUES (payments_seq.NEXTVAL, v_order_id, v_final_total, SYSDATE, p_pay_method);

    IF v_redeem_points > 0 THEN
        UPDATE Users SET loyalty_points_balance = loyalty_points_balance - v_redeem_points
        WHERE user_id = p_user_id;

        INSERT INTO LoyaltyLedger (ledger_id, user_id, order_id, entry_type, points, rupee_value, balance_after, created_at)
        VALUES (loyaltyledger_seq.NEXTVAL, p_user_id, v_order_id, 'redeem', v_redeem_points, v_loyalty_disc,
                v_balance - v_redeem_points, SYSDATE);
    END IF;

    IF v_coupon_id IS NOT NULL THEN
        UPDATE Coupons SET used_count = used_count + 1 WHERE coupon_id = v_coupon_id;
    END IF;

    DELETE FROM Cart WHERE user_id = p_user_id;

    COMMIT;

    p_order_id := v_order_id;
    p_final_total := v_final_total;
    p_coupon_discount := v_coupon_disc;
    p_loyalty_discount := v_loyalty_disc;
    p_points_redeemed := v_redeem_points;
    p_advance_required := v_advance;

EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
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
        p_points_awarded := 400;  -- Rs. 200 cashback at 2 points = Rs.1
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
