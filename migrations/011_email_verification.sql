ALTER TABLE Users ADD (
    email_verified NUMBER(1) DEFAULT 0 NOT NULL,
    verification_code VARCHAR2(6),
    verification_code_expires DATE
);

-- Existing accounts registered before this feature existed shouldn't be
-- locked out retroactively -- only new registrations go through the flow.
UPDATE Users SET email_verified = 1 WHERE email_verified = 0;
COMMIT;
