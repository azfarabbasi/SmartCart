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
    image_path VARCHAR2(255)
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


