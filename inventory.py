"""Persistencia y reglas de inventario; sin dependencia de la interfaz web."""
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
HEADERS = ("codigo", "nombre", "categoria", "stock_actual", "stock_minimo")


def database_path():
    return Path(os.getenv("DATABASE_PATH") or BASE_DIR / "inventario.db")


@contextmanager
def connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=30000")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                codigo TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                categoria TEXT NOT NULL,
                stock_actual INTEGER NOT NULL CHECK(stock_actual >= 0),
                stock_minimo INTEGER NOT NULL CHECK(stock_minimo >= 0),
                low_active INTEGER NOT NULL DEFAULT 0 CHECK(low_active IN (0, 1))
            );
            CREATE TABLE IF NOT EXISTS movements (
                id INTEGER PRIMARY KEY,
                product_code TEXT NOT NULL,
                product_name TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('entrada', 'salida')),
                cantidad INTEGER NOT NULL CHECK(cantidad > 0),
                stock_anterior INTEGER NOT NULL,
                stock_nuevo INTEGER NOT NULL CHECK(stock_nuevo >= 0),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL,
                items_json TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_attempt_at TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def nonnegative_int(value, label):
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{label}: escribe un número entero no negativo.")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"{label}: escribe un número entero no negativo.")
        value = int(value)
    elif isinstance(value, str):
        if not re.fullmatch(r"[0-9]+", value.strip()):
            raise ValueError(f"{label}: escribe un número entero no negativo.")
        value = int(value.strip())
    elif not isinstance(value, int):
        raise ValueError(f"{label}: escribe un número entero no negativo.")
    if value < 0:
        raise ValueError(f"{label}: escribe un número entero no negativo.")
    return value


def clean_product(data):
    result = {}
    for field in HEADERS[:3]:
        value = data.get(field)
        if value is None or not str(value).strip():
            raise ValueError(f"{field}: este campo es obligatorio.")
        result[field] = str(value).strip()
        if len(result[field]) > 120:
            raise ValueError(f"{field}: máximo 120 caracteres.")
    for field in HEADERS[3:]:
        result[field] = nonnegative_int(data.get(field), field)
    return result


def upsert_product(data, product_id=None):
    item = clean_product(data)
    with connect() as db:
        if product_id is None:
            db.execute("""INSERT INTO products (codigo,nombre,categoria,stock_actual,stock_minimo)
                          VALUES (:codigo,:nombre,:categoria,:stock_actual,:stock_minimo)""", item)
        else:
            old = db.execute("SELECT id FROM products WHERE id=?", (product_id,)).fetchone()
            if old is None:
                raise ValueError("El producto ya no existe.")
            item["id"] = product_id
            db.execute("""UPDATE products SET codigo=:codigo,nombre=:nombre,categoria=:categoria,
                          stock_actual=:stock_actual,stock_minimo=:stock_minimo,
                          low_active=CASE WHEN :stock_actual >= :stock_minimo THEN 0 ELSE low_active END
                          WHERE id=:id""", item)


def delete_product(product_id):
    with connect() as db:
        db.execute("DELETE FROM products WHERE id=?", (product_id,))


def register_movement(product_id, tipo, cantidad):
    if tipo not in ("entrada", "salida"):
        raise ValueError("El movimiento debe ser entrada o salida.")
    amount = nonnegative_int(cantidad, "cantidad")
    if amount == 0:
        raise ValueError("cantidad: debe ser mayor que cero.")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if product is None:
            raise ValueError("El producto ya no existe.")
        new_stock = product["stock_actual"] + amount * (1 if tipo == "entrada" else -1)
        if new_stock < 0:
            raise ValueError("La salida supera el stock disponible; el inventario no puede quedar negativo.")
        db.execute("""UPDATE products SET stock_actual=?,
                      low_active=CASE WHEN ? >= stock_minimo THEN 0 ELSE low_active END WHERE id=?""",
                   (new_stock, new_stock, product_id))
        db.execute("""INSERT INTO movements
                      (product_code,product_name,tipo,cantidad,stock_anterior,stock_nuevo,created_at)
                      VALUES (?,?,?,?,?,?,?)""",
                   (product["codigo"], product["nombre"], tipo, amount,
                    product["stock_actual"], new_stock, now()))
    return new_stock


def import_excel(file_stream):
    try:
        book = load_workbook(file_stream, read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError("No se pudo leer el archivo .xlsx. Comprueba que sea un Excel válido.") from exc
    try:
        sheet = book.active
        rows = sheet.iter_rows(values_only=True)
        header = next(rows, None)
        if header is None or tuple(str(x).strip().lower() if x is not None else "" for x in header) != HEADERS:
            raise ValueError("La primera fila debe contener exactamente: " + ", ".join(HEADERS) + ".")
        items = []
        errors = []
        seen = set()
        for row_number, row in enumerate(rows, start=2):
            if all(value is None or str(value).strip() == "" for value in row):
                continue
            try:
                item = clean_product(dict(zip(HEADERS, row)))
                if item["codigo"] in seen:
                    raise ValueError(f"codigo: '{item['codigo']}' aparece más de una vez en el archivo.")
                seen.add(item["codigo"])
                items.append(item)
            except ValueError as exc:
                errors.append(f"Fila {row_number}: {exc}")
        if errors:
            raise ValueError("No se importó ningún producto. Corrige estos errores:\n" + "\n".join(errors))
        if not items:
            raise ValueError("El archivo no contiene productos.")
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for item in items:
                db.execute("""INSERT INTO products (codigo,nombre,categoria,stock_actual,stock_minimo)
                              VALUES (:codigo,:nombre,:categoria,:stock_actual,:stock_minimo)
                              ON CONFLICT(codigo) DO UPDATE SET
                              nombre=excluded.nombre,categoria=excluded.categoria,
                              stock_actual=excluded.stock_actual,stock_minimo=excluded.stock_minimo,
                              low_active=CASE WHEN excluded.stock_actual >= excluded.stock_minimo
                                  THEN 0 ELSE products.low_active END""", item)
        return len(items)
    finally:
        book.close()


def list_products():
    with connect() as db:
        return db.execute("SELECT * FROM products ORDER BY nombre COLLATE NOCASE").fetchall()


def list_movements():
    with connect() as db:
        return db.execute("SELECT * FROM movements ORDER BY id DESC LIMIT 200").fetchall()


def list_alerts():
    with connect() as db:
        rows = db.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 200").fetchall()
    return [dict(row, items=json.loads(row["items_json"])) for row in rows]


def dashboard():
    with connect() as db:
        counts = db.execute("""SELECT COUNT(*) AS total,
                             SUM(CASE WHEN stock_actual < stock_minimo THEN 1 ELSE 0 END) AS low
                             FROM products""").fetchone()
        last = db.execute("SELECT value FROM settings WHERE key='last_check'").fetchone()
    return {"total": counts["total"], "low": counts["low"] or 0,
            "last_check": last["value"] if last else None}
