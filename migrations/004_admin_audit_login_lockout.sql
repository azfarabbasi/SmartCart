CREATE TABLE AdminAuditLog (
    audit_id      NUMBER PRIMARY KEY,
    admin_user_id NUMBER REFERENCES Users(user_id),
    action        VARCHAR2(100) NOT NULL,
    target_type   VARCHAR2(50),
    target_id     NUMBER,
    details       VARCHAR2(1000),
    ip_address    VARCHAR2(45),
    created_at    DATE DEFAULT SYSDATE
);
CREATE SEQUENCE adminauditlog_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_auditlog_created ON AdminAuditLog(created_at);

CREATE TABLE LoginAttempts (
    attempt_id   NUMBER PRIMARY KEY,
    email        VARCHAR2(100) NOT NULL,
    ip_address   VARCHAR2(45),
    success      NUMBER(1) DEFAULT 0,
    attempted_at DATE DEFAULT SYSDATE
);
CREATE SEQUENCE loginattempts_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_loginattempts_email_time ON LoginAttempts(email, attempted_at);
