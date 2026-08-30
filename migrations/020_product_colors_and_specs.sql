-- Migration 020: Product Color Variants, Technical Specifications, Highlights & Box Contents

-- 1. Create ProductColors table & sequence
BEGIN
    EXECUTE IMMEDIATE 'CREATE SEQUENCE productcolors_seq START WITH 1 INCREMENT BY 1';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE '
    CREATE TABLE ProductColors (
        color_id       NUMBER PRIMARY KEY,
        product_id     NUMBER NOT NULL REFERENCES Products(product_id),
        color_name     VARCHAR2(100) NOT NULL,
        color_code     VARCHAR2(30) DEFAULT ''#000000'',
        image_path     CLOB,
        stock          NUMBER DEFAULT 0,
        sort_order     NUMBER DEFAULT 0,
        created_at     DATE DEFAULT SYSDATE
    )';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'CREATE INDEX idx_productcolors_product ON ProductColors(product_id, sort_order)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 AND SQLCODE != -1408 THEN RAISE; END IF;
END;
/

-- 2. Add technical_specs, highlights, and box_contents to Products
BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE Products ADD (technical_specs CLOB)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE Products ADD (highlights VARCHAR2(1000))';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE Products ADD (box_contents VARCHAR2(1000))';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

-- 3. Add selected_color to Cart and OrderItems
BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE Cart ADD (selected_color VARCHAR2(100))';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE OrderItems ADD (selected_color VARCHAR2(100))';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

COMMIT;
