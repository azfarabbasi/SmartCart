-- Insert default setting for minimum profit margin floor if not already present
MERGE INTO SiteSettings s
USING (SELECT 'min_profit_margin_floor' AS setting_key FROM dual) d
ON (s.setting_key = d.setting_key)
WHEN NOT MATCHED THEN INSERT (setting_key, setting_value) VALUES ('min_profit_margin_floor', '300');

-- Recompile place_order with price floor protection: sale price after discounts cannot fall below (cost price + floor)
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
    v_unit_price    NUMBER(10,2);
    v_cost_price    NUMBER(10,2);
    v_count         NUMBER;
    v_balance       NUMBER;
    v_max_redeem    NUMBER;
    v_redeem_points NUMBER := NVL(p_points_to_redeem, 0);
    v_loyalty_disc  NUMBER(10,2) := 0;
    v_coupon_pct    NUMBER := 0;
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

    -- Stock check with row locking
    FOR item IN (
        SELECT c.product_id, c.quantity, p.stock, p.name, p.price, NVL(p.cost_price, 0) AS cost_price
        FROM Cart c
        JOIN Products p ON c.product_id = p.product_id
        WHERE c.user_id = p_user_id
        FOR UPDATE OF p.stock
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

    -- Maximum total allowable discount across both coupon & loyalty points
    v_max_total_discount := GREATEST(0, v_subtotal - v_min_floor_price);

    -- Process coupon if provided
    IF p_coupon_code IS NOT NULL AND TRIM(p_coupon_code) IS NOT NULL THEN
        BEGIN
            SELECT coupon_id, discount_percent INTO v_coupon_id, v_coupon_pct
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
        WHERE user_id = p_user_id AND UPPER(coupon_code) = UPPER(TRIM(p_coupon_code)) AND status != 'cancelled';
        IF v_already_used > 0 THEN
            RAISE_APPLICATION_ERROR(-20004, 'You have already used this coupon code.');
        END IF;

        -- Coupon discount is capped so total price doesn't drop below cost + floor
        v_coupon_disc := LEAST(ROUND(v_subtotal * v_coupon_pct / 100, 2), v_max_total_discount);
    END IF;

    v_discounted := v_subtotal - v_coupon_disc;
    v_remaining_discount_cap := GREATEST(0, v_max_total_discount - v_coupon_disc);

    -- Loyalty points: row-lock balance, capped at 50% of discounted subtotal AND remaining discount cap
    SELECT loyalty_points_balance INTO v_balance FROM Users WHERE user_id = p_user_id FOR UPDATE;

    IF v_redeem_points < 0 THEN
        v_redeem_points := 0;
    END IF;
    IF v_redeem_points > v_balance THEN
        v_redeem_points := v_balance;
    END IF;
    v_max_redeem := FLOOR(LEAST(v_discounted * 0.5, v_remaining_discount_cap) * 2);
    IF v_redeem_points > v_max_redeem THEN
        v_redeem_points := v_max_redeem;
    END IF;
    v_loyalty_disc := v_redeem_points / 2;

    v_final_total := v_discounted - v_loyalty_disc;
    v_advance := CASE WHEN p_pay_method = 'cod' THEN NVL(p_cod_advance_amount, 300) ELSE v_final_total END;

    SELECT orders_seq.NEXTVAL INTO v_order_id FROM DUAL;

    INSERT INTO Orders (order_id, user_id, order_date, total_amount, status, delivery_address, phone_number,
                         loyalty_points_redeemed, loyalty_discount_amount, loyalty_points_earned,
                         payment_method, payment_proof_path, payment_status, advance_amount,
                         coupon_code, coupon_discount_amount)
    VALUES (v_order_id, p_user_id, SYSDATE, v_final_total, 'pending', p_address, p_phone,
            v_redeem_points, v_loyalty_disc, 0,
            p_pay_method, p_payment_proof_path, 'pending_verification', v_advance,
            CASE WHEN v_coupon_id IS NOT NULL THEN UPPER(p_coupon_code) ELSE NULL END, v_coupon_disc);

    -- Move cart items to OrderItems and deduct stock
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

    INSERT INTO Payments (payment_id, order_id, amount, payment_date, method)
    VALUES (payments_seq.NEXTVAL, v_order_id, v_final_total, SYSDATE, p_pay_method);

    -- Clear cart
    DELETE FROM Cart WHERE user_id = p_user_id;

    -- Deduct loyalty points from balance
    IF v_redeem_points > 0 THEN
        UPDATE Users
        SET loyalty_points_balance = loyalty_points_balance - v_redeem_points
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
