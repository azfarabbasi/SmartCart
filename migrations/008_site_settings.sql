CREATE TABLE SiteSettings (
    setting_key   VARCHAR2(50) PRIMARY KEY,
    setting_value VARCHAR2(500)
);
INSERT INTO SiteSettings VALUES ('bank_name', 'PLEASE SET IN ADMIN PORTAL');
INSERT INTO SiteSettings VALUES ('bank_account_title', 'PLEASE SET IN ADMIN PORTAL');
INSERT INTO SiteSettings VALUES ('bank_account_number', 'PLEASE SET IN ADMIN PORTAL');
INSERT INTO SiteSettings VALUES ('bank_iban', 'PLEASE SET IN ADMIN PORTAL');
COMMIT;
