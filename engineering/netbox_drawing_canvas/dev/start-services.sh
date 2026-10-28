#!/bin/sh
# Start only a dedicated synthetic cluster and Redis, never system/production services.
set -eu
: "${DRAWING_PYTHON:?Set DRAWING_PYTHON to the isolated virtualenv python}"
: "${PG_BIN:?Set PG_BIN to the directory containing initdb and pg_ctl}"
: "${DRAWING_DEV_STATE:?Set DRAWING_DEV_STATE to a private directory outside the repository}"
mkdir -p "$DRAWING_DEV_STATE"
chmod 700 "$DRAWING_DEV_STATE"
if [ ! -f "$DRAWING_DEV_STATE/pgdata/PG_VERSION" ]; then
    "$PG_BIN/initdb" -D "$DRAWING_DEV_STATE/pgdata" -A trust --encoding=UTF8 --no-locale
fi
if ! "$PG_BIN/pg_ctl" -D "$DRAWING_DEV_STATE/pgdata" status >/dev/null 2>&1; then
    "$PG_BIN/pg_ctl" -D "$DRAWING_DEV_STATE/pgdata" -l "$DRAWING_DEV_STATE/postgres.log" \
        -o "-h 127.0.0.1 -p 55439 -k $DRAWING_DEV_STATE" start
fi
if [ ! -f "$DRAWING_DEV_STATE/redis.pid" ] || ! kill -0 "$(cat "$DRAWING_DEV_STATE/redis.pid")" 2>/dev/null; then
    redis-server --bind 127.0.0.1 --port 56389 --daemonize yes --dir "$DRAWING_DEV_STATE" \
        --pidfile "$DRAWING_DEV_STATE/redis.pid" --logfile "$DRAWING_DEV_STATE/redis.log"
fi
"$DRAWING_PYTHON" - <<'PY'
import getpass
import os

import psycopg
from psycopg import sql

with psycopg.connect(host='127.0.0.1', port=55439, dbname='postgres',
                     user=os.environ.get('DRAWING_DEV_DB_USER', getpass.getuser()), autocommit=True) as conn:
    for name in ('drawing_canvas', 'drawing_canvas429'):
        if not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s', [name]).fetchone():
            conn.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0").format(sql.Identifier(name)))
print('Synthetic services: PostgreSQL 127.0.0.1:55439; Redis 127.0.0.1:56389')
PY
