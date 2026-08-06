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
    oracledb.init_oracle_client(lib_dir=app.config['ORACLE_CLIENT_LIB_DIR'])
    _pool = oracledb.create_pool(
        user=app.config['DB_USER'],
        password=app.config['DB_PASSWORD'],
        dsn=app.config['DB_DSN'],
        min=2,
        max=10,
        increment=1,
        getmode=oracledb.POOL_GETMODE_WAIT,
    )


def get_db():
    if 'db_conn' not in g:
        conn = _pool.acquire()
        conn.outputtypehandler = _output_type_handler
        g.db_conn = conn
    return g.db_conn


def close_db(_exc=None):
    conn = g.pop('db_conn', None)
    if conn is not None:
        _pool.release(conn)
