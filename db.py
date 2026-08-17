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
    conn = g.pop('db_conn', None)
    if conn is not None:
        _pool.release(conn)
