CREATE TABLE ProductMedia (
    media_id    NUMBER PRIMARY KEY,
    product_id  NUMBER NOT NULL REFERENCES Products(product_id),
    media_path  VARCHAR2(255) NOT NULL,
    media_type  VARCHAR2(10) NOT NULL,
    sort_order  NUMBER DEFAULT 0,
    created_at  DATE DEFAULT SYSDATE,
    CONSTRAINT chk_productmedia_type CHECK (media_type IN ('image','video'))
);
CREATE SEQUENCE productmedia_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_productmedia_product ON ProductMedia(product_id, sort_order);
