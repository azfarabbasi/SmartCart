-- Extends SiteSettings (already created in 008) with contact info, site
-- copy/messages, an optional sitewide announcement banner, and the
-- payment amounts shown on the checkout page -- so all of it is
-- admin-editable from /admin/settings instead of hardcoded in templates
-- or environment config.
INSERT INTO SiteSettings VALUES ('contact_phone', '+923312344418');
INSERT INTO SiteSettings VALUES ('contact_email', 'azfar.aa.abbasi@gmail.com');
INSERT INTO SiteSettings VALUES ('whatsapp_number', '923312344418');
INSERT INTO SiteSettings VALUES ('hero_title', 'Welcome to SmartCart');
INSERT INTO SiteSettings VALUES ('hero_subtitle', 'Browse our full catalog - no account needed to look around.');
INSERT INTO SiteSettings VALUES ('checkout_notice', 'Orders are dispatched once payment is verified. You''ll receive an email once your payment is confirmed.');
INSERT INTO SiteSettings VALUES ('site_announcement', '');
INSERT INTO SiteSettings VALUES ('footer_note', '');
INSERT INTO SiteSettings VALUES ('cod_advance_amount', '300');
INSERT INTO SiteSettings VALUES ('cashback_points', '400');
COMMIT;
