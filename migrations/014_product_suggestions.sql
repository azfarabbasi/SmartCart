CREATE TABLE ProductSuggestions (
    suggestion_id NUMBER PRIMARY KEY,
    user_id       NUMBER NOT NULL REFERENCES Users(user_id),
    description   VARCHAR2(1000),
    media_path    VARCHAR2(255),
    media_type    VARCHAR2(10),
    status        VARCHAR2(20) DEFAULT 'new' NOT NULL,
    created_at    DATE DEFAULT SYSDATE
);
CREATE SEQUENCE productsuggestions_seq START WITH 1 INCREMENT BY 1;
CREATE INDEX idx_productsuggestions_created ON ProductSuggestions(created_at);
