ALTER TABLE Products ADD (
    delivery_time_text VARCHAR2(100),
    free_delivery NUMBER(1) DEFAULT 0 NOT NULL
);
