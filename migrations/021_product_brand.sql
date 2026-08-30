-- Migration 021: Add optional brand_id to Products
BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE Products ADD (brand_id NUMBER REFERENCES Brands(brand_id))';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'CREATE INDEX idx_products_brand ON Products(brand_id)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 AND SQLCODE != -1408 THEN RAISE; END IF;
END;
/

COMMIT;
