import oracledb
from flask import g

_pool = None


def _output_type_handler(cursor, metadata):
    # Auto-fetch CLOB/BLOB columns as plain str/bytes instead of LOB objects
    # (Oracle 11.2 thick-mode default), so callers never need cur.read().
    if metadata.type_code is oracledb.DB_TYPE_CLOB:
        return cursor.var(oracledb.DB_TYPE_LONG, arraysize=cursor.arraysize)
    if metadata.type_code is oracledb.DB_TYPE_BLOB:
        return cursor.var(oracledb.DB_TYPE_LONG_RAW, arraysize=cursor.arraysize)


def init_pool(app):
    global _pool
    # Use thick mode only when ORACLE_CLIENT_LIB_DIR is set (local dev).
    # On Vercel / serverless, thin mode is used automatically (no native libs).
    oracle_client_dir = app.config.get('ORACLE_CLIENT_LIB_DIR')
    if oracle_client_dir:
        try:
            oracledb.init_oracle_client(lib_dir=oracle_client_dir)
        except oracledb.ProgrammingError:
            pass  # Already initialised
    _pool = oracledb.create_pool(
        user=app.config['DB_USER'],
        password=app.config['DB_PASSWORD'],
        dsn=app.config['DB_DSN'],
        min=2,
        max=10,
        increment=1,
        getmode=oracledb.POOL_GETMODE_WAIT,
    )


_migrated = False


def _auto_migrate(conn):
    try:
        cur = conn.cursor()
        # 1. Ensure cost_price column exists on Products
        try:
            cur.execute("SELECT cost_price FROM Products WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("ALTER TABLE Products ADD (cost_price NUMBER(10,2) DEFAULT 0 NOT NULL)")
                conn.commit()
            except Exception:
                pass

        # 2. Ensure min_profit_margin_floor in SiteSettings
        try:
            cur.execute("""
            MERGE INTO SiteSettings s
            USING (SELECT 'min_profit_margin_floor' AS setting_key FROM dual) d
            ON (s.setting_key = d.setting_key)
            WHEN NOT MATCHED THEN INSERT (setting_key, setting_value) VALUES ('min_profit_margin_floor', '300')
            """)
            conn.commit()
        except Exception:
            pass

        # 3. Ensure image and media columns are CLOB for Base64 storage
        media_columns = (
            ('PRODUCTS', 'IMAGE_PATH'),
            ('PRODUCTMEDIA', 'MEDIA_PATH'),
            ('PRODUCTFEEDBACK', 'MEDIA_PATH'),
            ('FEEDBACKREPLIES', 'MEDIA_PATH'),
            ('PRODUCTSUGGESTIONS', 'MEDIA_PATH'),
            ('ORDERS', 'PAYMENT_PROOF_PATH'),
        )
        for table, col in media_columns:
            try:
                cur.execute(
                    "SELECT data_type FROM user_tab_cols WHERE table_name = :t AND column_name = :c",
                    {'t': table, 'c': col},
                )
                row = cur.fetchone()
                if row and row[0] != 'CLOB':
                    temp_col = f"{col.lower()}_clob"
                    cur.execute(f"ALTER TABLE {table} ADD ({temp_col} CLOB)")
                    cur.execute(f"UPDATE {table} SET {temp_col} = {col}")
                    cur.execute(f"ALTER TABLE {table} DROP COLUMN {col}")
                    cur.execute(f"ALTER TABLE {table} RENAME COLUMN {temp_col} TO {col}")
                    conn.commit()
            except Exception:
                pass

        # 4. Ensure address columns exist on Orders
        try:
            cur.execute("SELECT address_city FROM Orders WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("ALTER TABLE Orders MODIFY (delivery_address VARCHAR2(500))")
            except Exception:
                pass
            try:
                cur.execute("""
                ALTER TABLE Orders ADD (
                    address_city         VARCHAR2(50),
                    address_area         VARCHAR2(150),
                    address_house_no     VARCHAR2(100),
                    address_block_sector VARCHAR2(100),
                    address_landmark     VARCHAR2(150),
                    address_notes        VARCHAR2(255)
                )
                """)
                conn.commit()
            except Exception:
                pass

        # 5. Ensure cash_received_at and cash_received_by columns exist on Orders
        try:
            cur.execute("SELECT cash_received_at FROM Orders WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("ALTER TABLE Orders ADD (cash_received_at DATE)")
                conn.commit()
            except Exception:
                pass

        try:
            cur.execute("SELECT cash_received_by FROM Orders WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("ALTER TABLE Orders ADD (cash_received_by NUMBER)")
                conn.commit()
            except Exception:
                pass

        # 6. Ensure discount_type and discount_amount columns exist on Coupons
        try:
            cur.execute("SELECT discount_type FROM Coupons WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("ALTER TABLE Coupons ADD (discount_type VARCHAR2(20) DEFAULT 'percentage' NOT NULL, discount_amount NUMBER(10,2) DEFAULT 0)")
                conn.commit()
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE Coupons MODIFY (discount_percent NUMBER(5,2) NULL)")
                conn.commit()
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE Coupons DROP CONSTRAINT chk_coupon_discount")
                conn.commit()
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE Coupons ADD CONSTRAINT chk_coupon_type CHECK (discount_type IN ('percentage', 'fixed'))")
                conn.commit()
            except Exception:
                pass

        # 7. Ensure AdminAuditLog table and sequence exist
        try:
            cur.execute("SELECT 1 FROM AdminAuditLog WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("""
                CREATE TABLE AdminAuditLog (
                    audit_id      NUMBER PRIMARY KEY,
                    admin_user_id NUMBER,
                    action        VARCHAR2(100) NOT NULL,
                    target_type   VARCHAR2(50),
                    target_id     NUMBER,
                    details       VARCHAR2(1000),
                    ip_address    VARCHAR2(45),
                    created_at    DATE DEFAULT SYSDATE
                )
                """)
                conn.commit()
            except Exception:
                pass
            try:
                cur.execute("CREATE SEQUENCE adminauditlog_seq START WITH 1 INCREMENT BY 1")
                conn.commit()
            except Exception:
                pass

        # 8. Ensure LoginAttempts table and sequence exist
        try:
            cur.execute("SELECT 1 FROM LoginAttempts WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("""
                CREATE TABLE LoginAttempts (
                    attempt_id   NUMBER PRIMARY KEY,
                    email        VARCHAR2(100) NOT NULL,
                    ip_address   VARCHAR2(45),
                    success      NUMBER(1) DEFAULT 0,
                    attempted_at DATE DEFAULT SYSDATE
                )
                """)
                conn.commit()
            except Exception:
                pass
            try:
                cur.execute("CREATE SEQUENCE loginattempts_seq START WITH 1 INCREMENT BY 1")
                conn.commit()
            except Exception:
                pass

        # 9. Ensure Categories columns (icon_name, image_path, sort_order) exist
        try:
            cur.execute("SELECT icon_name FROM Categories WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("ALTER TABLE Categories ADD (icon_name VARCHAR2(100) DEFAULT 'bi-tag')")
                conn.commit()
            except Exception:
                pass
        try:
            cur.execute("SELECT image_path FROM Categories WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("ALTER TABLE Categories ADD (image_path CLOB)")
                conn.commit()
            except Exception:
                pass
        try:
            cur.execute("SELECT sort_order FROM Categories WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("ALTER TABLE Categories ADD (sort_order NUMBER DEFAULT 0)")
                conn.commit()
            except Exception:
                pass

        # 10. Ensure Brands table and sequence exist
        try:
            cur.execute("SELECT 1 FROM Brands WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("""
                CREATE TABLE Brands (
                    brand_id     NUMBER PRIMARY KEY,
                    brand_name   VARCHAR2(100) NOT NULL,
                    subtitle     VARCHAR2(150),
                    logo_path    CLOB,
                    badge_text   VARCHAR2(10),
                    badge_color  VARCHAR2(50) DEFAULT 'brand-bg-dark',
                    search_query VARCHAR2(100),
                    sort_order   NUMBER DEFAULT 0,
                    is_active    NUMBER(1) DEFAULT 1,
                    created_at   DATE DEFAULT SYSDATE
                )
                """)
                conn.commit()
            except Exception:
                pass
            try:
                cur.execute("CREATE SEQUENCE brands_seq START WITH 1 INCREMENT BY 1")
                conn.commit()
            except Exception:
                pass

            # Seed default brands if table just created or empty
            try:
                cur.execute("SELECT COUNT(*) FROM Brands")
                if cur.fetchone()[0] == 0:
                    seed_brands = [
                        ('Ronin', 'Audio & Power', 'RO', 'brand-bg-dark', 'Ronin', 1),
                        ('Anker', 'Fast Chargers', 'AK', 'brand-bg-blue', 'Anker', 2),
                        ('Apple', 'Smart Tech', 'AP', 'brand-bg-gray', 'Apple', 3),
                        ('Samsung', 'Galaxy & Audio', 'SM', 'brand-bg-navy', 'Samsung', 4),
                        ('Sony', 'Audio Systems', 'SN', 'brand-bg-black', 'Sony', 5),
                        ('Audionic', 'Speakers & TWS', 'AD', 'brand-bg-red', 'Audionic', 6),
                        ('Razer', 'Pro Gaming', 'RZ', 'brand-bg-green', 'Razer', 7),
                        ('Baseus', 'Smart Gadgets', 'BS', 'brand-bg-yellow', 'Baseus', 8),
                    ]
                    for bname, bsub, bbadge, bcolor, bsearch, bsort in seed_brands:
                        cur.execute("""
                        INSERT INTO Brands (brand_id, brand_name, subtitle, badge_text, badge_color, search_query, sort_order)
                        VALUES (brands_seq.NEXTVAL, :bn, :bs, :bt, :bc, :bq, :so)
                        """, {'bn': bname, 'bs': bsub, 'bt': bbadge, 'bc': bcolor, 'bq': bsearch, 'so': bsort})
                    conn.commit()
            except Exception:
                pass

        # 11. Ensure HeroBanners table and sequence exist
        try:
            cur.execute("SELECT 1 FROM HeroBanners WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("""
                CREATE TABLE HeroBanners (
                    banner_id      NUMBER PRIMARY KEY,
                    badge_tag      VARCHAR2(100),
                    title          VARCHAR2(150) NOT NULL,
                    subtitle       VARCHAR2(255),
                    cta_text       VARCHAR2(100) DEFAULT 'SHOP NOW',
                    cta_link       VARCHAR2(255) DEFAULT '/#productsGrid',
                    gradient_class VARCHAR2(100) DEFAULT 'promo-gradient-autumn',
                    image_path     CLOB,
                    sort_order     NUMBER DEFAULT 0,
                    is_active      NUMBER(1) DEFAULT 1,
                    created_at     DATE DEFAULT SYSDATE
                )
                """)
                conn.commit()
            except Exception:
                pass
            try:
                cur.execute("CREATE SEQUENCE banners_seq START WITH 1 INCREMENT BY 1")
                conn.commit()
            except Exception:
                pass

            # Seed default hero banners if empty
            try:
                cur.execute("SELECT COUNT(*) FROM HeroBanners")
                if cur.fetchone()[0] == 0:
                    seed_banners = [
                        ('🔥 AUTUMN SALE', '80% OFF', 'Top Audio, Earbuds & Smart Tech', 'SHOP NOW', '/#productsGrid', 'promo-gradient-autumn', 1),
                        ('🚚 FAST SHIPPING', 'FREE DELIVERY', 'On All Orders Above Rs 2,000 Nationwide', 'EXPLORE DEALS', '/#productsGrid', 'promo-gradient-ocean', 2),
                        ('🛡️ 100% GENUINE', 'TOP TECH BRANDS', 'Ronin, Apple, Samsung, Anker, Sony & Razer', 'VIEW BRANDS', '#brandsSection', 'promo-gradient-violet', 3),
                    ]
                    for btag, btitle, bsub, bcta, bctl, bgrad, bsort in seed_banners:
                        cur.execute("""
                        INSERT INTO HeroBanners (banner_id, badge_tag, title, subtitle, cta_text, cta_link, gradient_class, sort_order)
                        VALUES (banners_seq.NEXTVAL, :btg, :btt, :bsb, :bct, :bcl, :bgc, :bso)
                        """, {'btg': btag, 'btt': btitle, 'bsb': bsub, 'bct': bcta, 'bcl': bctl, 'bgc': bgrad, 'bso': bsort})
                    conn.commit()
            except Exception:
                pass

        # 7. Always keep place_order procedure up to date (recompile on startup)
        try:
            cur.execute("""
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
""")
            conn.commit()
        except Exception:
            pass
    except Exception:
        pass


def get_db():
    global _migrated, _pool
    if _pool is None:
        from flask import current_app
        init_pool(current_app)
    if 'db_conn' not in g:
        conn = _pool.acquire()
        conn.outputtypehandler = _output_type_handler
        if not _migrated:
            _migrated = True
            _auto_migrate(conn)
        g.db_conn = conn
    return g.db_conn


def close_db(_exc=None):
    try:
        conn = g.pop('db_conn', None)
        if conn is not None and _pool is not None:
            _pool.release(conn)
    except (RuntimeError, AttributeError):
        pass
