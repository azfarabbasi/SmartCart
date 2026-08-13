-- ============================================================
-- Sample Users for SmartCart
-- Admin password: admin123  |  All other users password: user123
-- ============================================================

-- Admin User
INSERT INTO Users (user_id, name, email, password, role, created_at, email_verified)
VALUES (users_seq.NEXTVAL, 'Admin User', 'admin@smartcart.com',
        'scrypt:32768:8:1$TKCJzbeCXmvl25s6$bc9ec3623195d3e066375dc081a8860b8f4fad22741d167c81dcb38eacfd9578286b3c056d0fedfa06e13b88d2e960dce3eaad9a61229fad681ec1d30b67838d',
        'admin', SYSDATE, 1);

-- Customer Users
INSERT INTO Users (user_id, name, email, password, role, created_at, email_verified)
VALUES (users_seq.NEXTVAL, 'Ali Khan', 'ali.khan@gmail.com',
        'scrypt:32768:8:1$NPAZEoWEtfY13uNp$3bc130dbe9ebbd01229065e108ab017c58130ba68fc46059766927b2b15929d0ccfa418d3d91a549be02ea2bcdb4b3157272bd8a39dc41d4d7786e34a4fb93d4',
        'customer', SYSDATE, 1);

INSERT INTO Users (user_id, name, email, password, role, created_at, email_verified)
VALUES (users_seq.NEXTVAL, 'Sara Ahmed', 'sara.ahmed@gmail.com',
        'scrypt:32768:8:1$3ousEOPMbswDFGgT$f74f3383978818b827e12cf3e6df9313df6c4f3baaec3bcad701925f72fdb5490d2dccf65b3284ba71e17d086b779cbf21f0886051e46be99f92ceec43cb4bd5',
        'customer', SYSDATE, 1);

INSERT INTO Users (user_id, name, email, password, role, created_at, email_verified)
VALUES (users_seq.NEXTVAL, 'Hassan Raza', 'hassan.raza@gmail.com',
        'scrypt:32768:8:1$G0uC7cCxKGAD7NZM$8236ffe68ffafc0379977dc7f0f2a57015f01296a1348af01d9a9726e8ed4b11a8215461ac28de99604604f0f3cf5fbe951b0cf6ae30baed0ebfdf185fb4efa9',
        'customer', SYSDATE, 1);

COMMIT;

-- ============================================================
-- Sample Products (across different categories)
-- ============================================================

INSERT INTO Products (product_id, category_id, name, price, stock, description)
VALUES (products_seq.NEXTVAL, 1, 'Wireless Bluetooth Earbuds', 2499.00, 50, 'Premium TWS earbuds with active noise cancellation and 24hr battery life');

INSERT INTO Products (product_id, category_id, name, price, stock, description)
VALUES (products_seq.NEXTVAL, 1, 'USB-C Fast Charger 65W', 1299.00, 80, 'GaN fast charger compatible with laptops, phones and tablets');

INSERT INTO Products (product_id, category_id, name, price, stock, description)
VALUES (products_seq.NEXTVAL, 2, 'Premium Cotton T-Shirt', 899.00, 100, 'Soft 100% cotton crew neck t-shirt available in multiple colors');

INSERT INTO Products (product_id, category_id, name, price, stock, description)
VALUES (products_seq.NEXTVAL, 2, 'Slim Fit Jeans', 1799.00, 60, 'Stretchable slim fit denim jeans with modern wash');

INSERT INTO Products (product_id, category_id, name, price, stock, description)
VALUES (products_seq.NEXTVAL, 3, 'Python Programming Guide', 599.00, 40, 'Comprehensive guide to Python programming for beginners and intermediates');

INSERT INTO Products (product_id, category_id, name, price, stock, description)
VALUES (products_seq.NEXTVAL, 7, 'Stainless Steel Water Bottle', 499.00, 120, 'Double-wall insulated bottle keeps drinks cold 24hrs or hot 12hrs');

INSERT INTO Products (product_id, category_id, name, price, stock, description)
VALUES (products_seq.NEXTVAL, 8, 'Cricket Bat - English Willow', 4999.00, 25, 'Grade A English willow cricket bat with premium grip');

INSERT INTO Products (product_id, category_id, name, price, stock, description)
VALUES (products_seq.NEXTVAL, 9, 'Moisturizing Face Cream', 349.00, 90, 'Daily moisturizer with SPF 30 protection for all skin types');

INSERT INTO Products (product_id, category_id, name, price, stock, description)
VALUES (products_seq.NEXTVAL, 14, 'Smartphone Pro Max 256GB', 89999.00, 15, 'Flagship smartphone with 6.7" AMOLED display, 108MP camera');

INSERT INTO Products (product_id, category_id, name, price, stock, description)
VALUES (products_seq.NEXTVAL, 15, 'Gaming Laptop 16GB RAM', 159999.00, 10, 'RTX 4060 graphics, 15.6" 144Hz display, 512GB SSD');

COMMIT;
