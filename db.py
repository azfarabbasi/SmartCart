import oracledb
from flask import g

_pool = None


def _output_type_handler(cursor, metadata):
    # Auto-fetch CLOB/BLOB columns as plain str/bytes instead of LOB objects
    # (Oracle 11.2 thick-mode default), so callers never need cur.read().
    if metadata.type_code is oracledb.DB_TYPE_CLOB:
        return cursor.var(oracledb.DB_TYPE_LONG, arraysize=cursor.arraysize)
    if metadata.type_code is oracledb.DB_TYPE_BLOB:
        return cursor.var(oracledb.DB_TYPE_LONG_RAW, arraysize=cursor.arraysize)


def init_pool(app):
    global _pool
    # Use thick mode only when ORACLE_CLIENT_LIB_DIR is set (local dev).
    # On Vercel / serverless, thin mode is used automatically (no native libs).
    oracle_client_dir = app.config.get('ORACLE_CLIENT_LIB_DIR')
    if oracle_client_dir:
        try:
            oracledb.init_oracle_client(lib_dir=oracle_client_dir)
        except oracledb.ProgrammingError:
            pass  # Already initialised
    _pool = oracledb.create_pool(
        user=app.config['DB_USER'],
        password=app.config['DB_PASSWORD'],
        dsn=app.config['DB_DSN'],
        min=2,
        max=10,
        increment=1,
        getmode=oracledb.POOL_GETMODE_WAIT,
    )


_migrated = False


def _auto_migrate(conn):
    try:
        cur = conn.cursor()
        # 1. Ensure cost_price column exists on Products
        try:
            cur.execute("SELECT cost_price FROM Products WHERE ROWNUM = 1")
        except Exception:
            try:
                cur.execute("ALTER TABLE Products ADD (cost_price NUMBER(10,2) DEFAULT 0 NOT NULL)")
                conn.commit()
            except Exception:
                pass

        # 2. Ensure min_profit_margin_floor in SiteSettings
        try:
            cur.execute("""
            MERGE INTO SiteSettings s
            USING (SELECT 'min_profit_margin_floor' AS setting_key FROM dual) d
            ON (s.setting_key = d.setting_key)
            WHEN NOT MATCHED THEN INSERT (setting_key, setting_value) VALUES ('min_profit_margin_floor', '300')
            """)
            conn.commit()
        except Exception:
            pass

        # 3. Ensure image and media columns are CLOB for Base64 storage
        media_columns = (
            ('PRODUCTS', 'IMAGE_PATH'),
            ('PRODUCTMEDIA', 'MEDIA_PATH'),
            ('PRODUCTFEEDBACK', 'MEDIA_PATH'),
            ('FEEDBACKREPLIES', 'MEDIA_PATH'),
            ('PRODUCTSUGGESTIONS', 'MEDIA_PATH'),
            ('ORDERS', 'PAYMENT_PROOF_PATH'),
        )
        for table, col in media_columns:
            try:
                cur.execute(
                    "SELECT data_type FROM user_tab_cols WHERE table_name = :t AND column_name = :c",
                    {'t': table, 'c': col},
                )
                row = cur.fetchone()
                if row and row[0] != 'CLOB':
                    temp_col = f"{col.lower()}_clob"
                    cur.execute(f"ALTER TABLE {table} ADD ({temp_col} CLOB)")
                    cur.execute(f"UPDATE {table} SET {temp_col} = {col}")
                    cur.execute(f"ALTER TABLE {table} DROP COLUMN {col}")
                    cur.execute(f"ALTER TABLE {table} RENAME COLUMN {temp_col} TO {col}")
                    conn.commit()
            except Exception:
                conn.rollback()
    except Exception:
        pass


def get_db():
    global _migrated
    if 'db_conn' not in g:
        conn = _pool.acquire()
        conn.outputtypehandler = _output_type_handler
        if not _migrated:
            _migrated = True
            _auto_migrate(conn)
        g.db_conn = conn
    return g.db_conn


def close_db(_exc=None):
    try:
        conn = g.pop('db_conn', None)
        if conn is not None:
            _pool.release(conn)
    except (RuntimeError, AttributeError):
        pass
