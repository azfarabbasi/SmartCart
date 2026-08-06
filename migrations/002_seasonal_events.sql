CREATE TABLE SeasonalEvents (
    event_id       NUMBER PRIMARY KEY,
    event_name     VARCHAR2(100) NOT NULL,
    start_date     DATE NOT NULL,
    end_date       DATE NOT NULL,
    boost_weight   NUMBER(4,2) DEFAULT 1.20,
    is_approximate NUMBER(1) DEFAULT 1,
    notes          VARCHAR2(255)
);
CREATE SEQUENCE seasonalevents_seq START WITH 1 INCREMENT BY 1;

-- Ramadan/Eid dates are lunar-calendar estimates (moon-sighting dependent, can shift +/-1 day) --
-- flagged is_approximate=1, admin-editable via /admin/seasonal-events once official dates are announced.
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Ramadan 2026', DATE '2026-02-18', DATE '2026-03-19', 1.10, 1, 'Approx. - confirm via moon sighting');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Eid-ul-Fitr 2026', DATE '2026-03-20', DATE '2026-03-22', 1.40, 1, 'Approx. - 1 Shawwal 1447 AH');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Eid-ul-Adha 2026', DATE '2026-05-27', DATE '2026-05-29', 1.35, 1, 'Approx. - 10 Dhu al-Hijjah 1447 AH');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Pakistan Independence Day 2026', DATE '2026-08-14', DATE '2026-08-14', 1.15, 0, 'Fixed date');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, '11.11 Sale 2026', DATE '2026-11-11', DATE '2026-11-11', 1.50, 0, 'Fixed date');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Ramadan 2027', DATE '2027-02-08', DATE '2027-03-09', 1.10, 1, 'Approx.');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Eid-ul-Fitr 2027', DATE '2027-03-10', DATE '2027-03-12', 1.40, 1, 'Approx.');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Eid-ul-Adha 2027', DATE '2027-05-17', DATE '2027-05-19', 1.35, 1, 'Approx.');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, 'Pakistan Independence Day 2027', DATE '2027-08-14', DATE '2027-08-14', 1.15, 0, 'Fixed date');
INSERT INTO SeasonalEvents VALUES (seasonalevents_seq.NEXTVAL, '11.11 Sale 2027', DATE '2027-11-11', DATE '2027-11-11', 1.50, 0, 'Fixed date');
COMMIT;

CREATE TABLE ForecastCache (
    cache_id          NUMBER PRIMARY KEY,
    generated_at       DATE DEFAULT SYSDATE,
    horizon             VARCHAR2(10),
    predicted_total     NUMBER(12,2),
    pct_change          NUMBER(6,2),
    confidence_pct      NUMBER(5,2),
    sufficiency_level   VARCHAR2(20),
    details_json        CLOB
);
CREATE SEQUENCE forecastcache_seq START WITH 1 INCREMENT BY 1;
