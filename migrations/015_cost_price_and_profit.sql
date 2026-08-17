-- Add Cost Price to Products for calculating profit margin and revenue differences
ALTER TABLE Products ADD (cost_price NUMBER(10,2) DEFAULT 0 NOT NULL);

-- Update AdminInventoryView to include cost_price
CREATE OR REPLACE VIEW AdminInventoryView AS
SELECT p.product_id, p.name, c.category_name,
       p.price, p.cost_price, p.stock, p.description
FROM Products p JOIN Categories c ON p.category_id = c.category_id;
