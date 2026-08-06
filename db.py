import oracledb
from flask import g

_pool = None


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
        g.db_conn = _pool.acquire()
    return g.db_conn


def close_db(_exc=None):
    conn = g.pop('db_conn', None)
    if conn is not None:
        _pool.release(conn)
