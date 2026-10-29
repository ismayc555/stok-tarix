import datetime
import json
import os
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get('PORT', 8765))
HOST = '0.0.0.0'
PRODUCTION = 'PORT' in os.environ
DATABASE_URL = os.environ.get('DATABASE_URL', '')
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2
    import psycopg2.extras
    DBError = psycopg2.Error
else:
    import sqlite3
    DBError = sqlite3.Error
    _DB_PATH = ROOT / 'stock.sqlite3'


def _q(sql):
    """SQLite ? → PostgreSQL %s."""
    return sql.replace('?', '%s') if USE_PG else sql


@contextmanager
def transaction():
    if USE_PG:
        conn = psycopg2.connect(DATABASE_URL)
    else:
        conn = sqlite3.connect(_DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rows(conn, sql, params=()):
    if USE_PG:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(_q(sql), params)
            return [dict(r) for r in cur.fetchall()]
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(conn, sql, params=()):
    if USE_PG:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(_q(sql), params)
            r = cur.fetchone()
            return dict(r) if r else None
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def run(conn, sql, params=()):
    """DML (UPDATE / DELETE) → rowcount."""
    if USE_PG:
        with conn.cursor() as cur:
            cur.execute(_q(sql), params)
            return cur.rowcount
    return conn.execute(sql, params).rowcount


def insert_row(conn, item):
    """INSERT one batches row → new id."""
    columns = list(item)
    ph = ','.join(['?'] * len(columns))
    sql = f'INSERT INTO batches ({",".join(columns)}) VALUES ({ph})'
    vals = list(item.values())
    if USE_PG:
        with conn.cursor() as cur:
            cur.execute(_q(sql) + ' RETURNING id', vals)
            return cur.fetchone()[0]
    cur = conn.execute(sql, vals)
    return cur.lastrowid


def initialize():
    if USE_PG:
        create_sql = '''CREATE TABLE IF NOT EXISTS batches (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL, barcode TEXT NOT NULL, batch TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            expiry TEXT NOT NULL, location TEXT NOT NULL
        )'''
    else:
        create_sql = '''CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, barcode TEXT NOT NULL, batch TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            expiry TEXT NOT NULL, location TEXT NOT NULL
        )'''
    with transaction() as conn:
        if USE_PG:
            with conn.cursor() as cur:
                cur.execute(create_sql)
        else:
            conn.execute(create_sql)


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Məhsul məlumatları düzgün formatda deyil.')
    result = {}
    for key, limit in [('name', 160), ('barcode', 80), ('batch', 80), ('location', 100)]:
        value = data.get(key, '')
        if not isinstance(value, str) or len(value.strip()) > limit:
            raise ValueError('Mətn sahəsinin uzunluğu və ya formatı düzgün deyil.')
        result[key] = value.strip()
    if not result['name']:
        raise ValueError('Məhsulun adını daxil edin.')
    quantity = data.get('quantity')
    if type(quantity) is not int or not 1 <= quantity <= 1000000000:
        raise ValueError('Stok miqdarı müsbət tam ədəd olmalıdır.')
    expiry = data.get('expiry', '')
    if expiry == '':
        result.update(quantity=quantity, expiry='')
        return result
    if not isinstance(expiry, str):
        raise ValueError('Son istifadə tarixini daxil edin.')
    try:
        date = datetime.date.fromisoformat(expiry)
    except ValueError:
        raise ValueError('Son istifadə tarixi düzgün deyil.') from None
    if date.isoformat() != expiry or date.year < 1900:
        raise ValueError('Tarix YYYY-MM-DD formatında olmalıdır.')
    result.update(quantity=quantity, expiry=expiry)
    return result


class Handler(BaseHTTPRequestHandler):
    def send(self, status, data):
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(payload)

    def guard(self):
        if PRODUCTION:
            return True
        allowed = {f'127.0.0.1:{PORT}', f'localhost:{PORT}'}
        if self.headers.get('Host') not in allowed:
            self.send(403, {'error': 'Host qəbul edilmir.'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://{host}' for host in allowed}:
            self.send(403, {'error': 'Xarici səhifədən sorğu qəbul edilmir.'})
            return False
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            self.send(403, {'error': 'Xarici səhifədən sorğu qəbul edilmir.'})
            return False
        return True

    def do_GET(self):
        if not self.guard():
            return
        path = urlsplit(self.path).path
        if path in ('/', '/index.html'):
            fragment = (ROOT / 'index.html').read_text(encoding='utf-8')
            payload = ('<!doctype html><html lang="az"><head><meta charset="utf-8">'
                       '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
                       '</head><body>' + fragment + '</body></html>').encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload)
        elif path == '/api/batches':
            try:
                with transaction() as conn:
                    result = rows(conn, 'SELECT * FROM batches ORDER BY expiry, name')
                self.send(200, result)
            except DBError:
                self.send(500, {'error': 'Bazanı oxumaq mümkün olmadı.'})
        else:
            self.send(404, {'error': 'Ünvan tapılmadı.'})

    def mutate(self, method):
        if not self.guard():
            return
        path = urlsplit(self.path).path
        base = '/api/batches'
        record_id = None
        if method == 'POST' and path == base + '/import':
            self.import_batches()
            return
        if method == 'POST' and path == base:
            pass
        elif method in ('PUT', 'DELETE') and path.startswith(base + '/') and path[len(base) + 1:].isdigit():
            record_id = int(path[len(base) + 1:])
            if not 1 <= record_id <= 9223372036854775807:
                self.send(400, {'error': 'Partiya nömrəsi düzgün deyil.'})
                return
        else:
            self.send(404, {'error': 'Ünvan tapılmadı.'})
            return
        try:
            item = None
            if method != 'DELETE':
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('JSON məlumatı tələb olunur.')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    raise ValueError('Sorğunun ölçüsü düzgün deyil.')
                item = validate(json.loads(self.rfile.read(size)))
            with transaction() as conn:
                if method == 'POST':
                    record_id = insert_row(conn, item)
                elif method == 'PUT':
                    rc = run(conn,
                             'UPDATE batches SET ' + ','.join(k + '=?' for k in item) + ' WHERE id=?',
                             [*item.values(), record_id])
                    if not rc:
                        self.send(404, {'error': 'Partiya tapılmadı. Siyahını yeniləyin.'})
                        return
                else:
                    rc = run(conn, 'DELETE FROM batches WHERE id=?', (record_id,))
                    if not rc:
                        self.send(404, {'error': 'Partiya tapılmadı.'})
                        return
            self.send(201 if method == 'POST' else 200, {'id': record_id})
        except (ValueError, UnicodeError) as error:
            self.send(400, {'error': str(error)})
        except DBError:
            self.send(500, {'error': 'Dəyişiklik bazada saxlanılmadı.'})

    def import_batches(self):
        try:
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('JSON məlumatı tələb olunur.')
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 5000000:
                raise ValueError('Fayl 5 MB həddini keçir.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, list) or not 1 <= len(data) <= 10000:
                raise ValueError('Bir dəfə 1–10000 sətir yükləyin.')
            items = []
            for index, row in enumerate(data, 1):
                try:
                    items.append(validate(row))
                except ValueError as error:
                    raise ValueError(f'{index}-ci sətir: {error}') from None
            imported = skipped = 0
            with transaction() as conn:
                for item in items:
                    columns = list(item)
                    exists = one(conn,
                                 'SELECT id FROM batches WHERE ' + ' AND '.join(k + '=?' for k in columns),
                                 list(item.values()))
                    if exists:
                        skipped += 1
                        continue
                    insert_row(conn, item)
                    imported += 1
            self.send(200, {'imported': imported, 'skipped': skipped})
        except (ValueError, UnicodeError) as error:
            self.send(400, {'error': str(error)})
        except DBError:
            self.send(500, {'error': 'Toplu yükləmə saxlanılmadı.'})

    def do_POST(self):
        self.mutate('POST')

    def do_PUT(self):
        self.mutate('PUT')

    def do_DELETE(self):
        self.mutate('DELETE')


if __name__ == '__main__':
    initialize()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    backend = 'PostgreSQL' if USE_PG else 'SQLite'
    print(f'Stok sistemi işləyir: http://0.0.0.0:{PORT}  (PRODUCTION={PRODUCTION}, DB={backend})', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
