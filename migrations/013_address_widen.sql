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
