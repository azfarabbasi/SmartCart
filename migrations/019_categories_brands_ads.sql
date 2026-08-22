-- Migration 019: Categories enhancements, Brands management, and Hero Banners management

-- 1. Enhance Categories table with icon_name, image_path, sort_order
BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE Categories ADD (icon_name VARCHAR2(100) DEFAULT ''bi-tag'')';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE Categories ADD (image_path CLOB)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE Categories ADD (sort_order NUMBER DEFAULT 0)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

-- 2. Create Brands Sequence & Table
BEGIN
    EXECUTE IMMEDIATE 'CREATE SEQUENCE brands_seq START WITH 1 INCREMENT BY 1';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE '
    CREATE TABLE Brands (
        brand_id     NUMBER PRIMARY KEY,
        brand_name   VARCHAR2(100) NOT NULL,
        subtitle     VARCHAR2(150),
        logo_path    CLOB,
        badge_text   VARCHAR2(10),
        badge_color  VARCHAR2(50) DEFAULT ''brand-bg-dark'',
        search_query VARCHAR2(100),
        sort_order   NUMBER DEFAULT 0,
        is_active    NUMBER(1) DEFAULT 1,
        created_at   DATE DEFAULT SYSDATE
    )';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

-- 3. Create HeroBanners Sequence & Table
BEGIN
    EXECUTE IMMEDIATE 'CREATE SEQUENCE banners_seq START WITH 1 INCREMENT BY 1';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE '
    CREATE TABLE HeroBanners (
        banner_id      NUMBER PRIMARY KEY,
        badge_tag      VARCHAR2(100),
        title          VARCHAR2(150) NOT NULL,
        subtitle       VARCHAR2(255),
        cta_text       VARCHAR2(100) DEFAULT ''SHOP NOW'',
        cta_link       VARCHAR2(255) DEFAULT ''/#productsGrid'',
        gradient_class VARCHAR2(100) DEFAULT ''promo-gradient-autumn'',
        image_path     CLOB,
        sort_order     NUMBER DEFAULT 0,
        is_active      NUMBER(1) DEFAULT 1,
        created_at     DATE DEFAULT SYSDATE
    )';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

-- 4. Seed Initial Brands if empty
DECLARE
    v_cnt NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_cnt FROM Brands;
    IF v_cnt = 0 THEN
        INSERT INTO Brands (brand_id, brand_name, subtitle, badge_text, badge_color, search_query, sort_order)
        VALUES (brands_seq.NEXTVAL, 'Ronin', 'Audio & Power', 'RO', 'brand-bg-dark', 'Ronin', 1);

        INSERT INTO Brands (brand_id, brand_name, subtitle, badge_text, badge_color, search_query, sort_order)
        VALUES (brands_seq.NEXTVAL, 'Anker', 'Fast Chargers', 'AK', 'brand-bg-blue', 'Anker', 2);

        INSERT INTO Brands (brand_id, brand_name, subtitle, badge_text, badge_color, search_query, sort_order)
        VALUES (brands_seq.NEXTVAL, 'Apple', 'Smart Tech', 'AP', 'brand-bg-gray', 'Apple', 3);

        INSERT INTO Brands (brand_id, brand_name, subtitle, badge_text, badge_color, search_query, sort_order)
        VALUES (brands_seq.NEXTVAL, 'Samsung', 'Galaxy & Audio', 'SM', 'brand-bg-navy', 'Samsung', 4);

        INSERT INTO Brands (brand_id, brand_name, subtitle, badge_text, badge_color, search_query, sort_order)
        VALUES (brands_seq.NEXTVAL, 'Sony', 'Audio Systems', 'SN', 'brand-bg-black', 'Sony', 5);

        INSERT INTO Brands (brand_id, brand_name, subtitle, badge_text, badge_color, search_query, sort_order)
        VALUES (brands_seq.NEXTVAL, 'Audionic', 'Speakers & TWS', 'AD', 'brand-bg-red', 'Audionic', 6);

        INSERT INTO Brands (brand_id, brand_name, subtitle, badge_text, badge_color, search_query, sort_order)
        VALUES (brands_seq.NEXTVAL, 'Razer', 'Pro Gaming', 'RZ', 'brand-bg-green', 'Razer', 7);

        INSERT INTO Brands (brand_id, brand_name, subtitle, badge_text, badge_color, search_query, sort_order)
        VALUES (brands_seq.NEXTVAL, 'Baseus', 'Smart Gadgets', 'BS', 'brand-bg-yellow', 'Baseus', 8);
    END IF;
END;
/

-- 5. Seed Initial Hero Banners if empty
DECLARE
    v_cnt NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_cnt FROM HeroBanners;
    IF v_cnt = 0 THEN
        INSERT INTO HeroBanners (banner_id, badge_tag, title, subtitle, cta_text, cta_link, gradient_class, sort_order)
        VALUES (banners_seq.NEXTVAL, '🔥 AUTUMN SALE', '80% OFF', 'Top Audio, Earbuds & Smart Tech', 'SHOP NOW', '/#productsGrid', 'promo-gradient-autumn', 1);

        INSERT INTO HeroBanners (banner_id, badge_tag, title, subtitle, cta_text, cta_link, gradient_class, sort_order)
        VALUES (banners_seq.NEXTVAL, '🚚 FAST SHIPPING', 'FREE DELIVERY', 'On All Orders Above Rs 2,000 Nationwide', 'EXPLORE DEALS', '/#productsGrid', 'promo-gradient-ocean', 2);

        INSERT INTO HeroBanners (banner_id, badge_tag, title, subtitle, cta_text, cta_link, gradient_class, sort_order)
        VALUES (banners_seq.NEXTVAL, '🛡️ 100% GENUINE', 'TOP TECH BRANDS', 'Ronin, Apple, Samsung, Anker, Sony & Razer', 'VIEW BRANDS', '#brandsSection', 'promo-gradient-violet', 3);
    END IF;
END;
/

COMMIT;
