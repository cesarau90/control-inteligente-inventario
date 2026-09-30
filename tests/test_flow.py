import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from alerts import check_inventory, deliver_alert
from inventory import (connect, dashboard, import_excel, init_db, list_alerts,
                       list_products, register_movement, upsert_product)
from make_example import ROWS
from monitor import acquire_lock


def workbook(rows):
    book = Workbook()
    sheet = book.active
    sheet.append(("codigo", "nombre", "categoria", "stock_actual", "stock_minimo"))
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    output.seek(0)
    return output


class InventoryFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"DATABASE_PATH": str(Path(self.temp.name) / "test.db"),
                                        "SMTP_HOST": "", "SMTP_USER": "", "SMTP_PASSWORD": "",
                                        "SMTP_FROM": "", "ALERT_TO": ""})
        self.env.start()
        init_db()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_import_validation_and_update_without_duplicates(self):
        self.assertEqual(import_excel(workbook(ROWS)), 16)
        self.assertEqual(dashboard()["low"], 6)
        self.assertEqual(import_excel(workbook([("P001", "Cuaderno nuevo", "Papelería", 5, 10)])), 1)
        self.assertEqual(len(list_products()), 16)
        with connect() as db:
            self.assertEqual(db.execute("SELECT nombre FROM products WHERE codigo='P001'").fetchone()[0], "Cuaderno nuevo")
        with self.assertRaisesRegex(ValueError, "Fila 3"):
            import_excel(workbook([("P020", "Bien", "Otra", 1, 2),
                                   ("P021", "Mal", "Otra", -1, 2)]))
        with connect() as db:
            self.assertIsNone(db.execute("SELECT id FROM products WHERE codigo='P020'").fetchone())

    def test_negative_stock_and_new_alert_after_recovery(self):
        upsert_product({"codigo": "X1", "nombre": "Prueba", "categoria": "Clase",
                        "stock_actual": "2", "stock_minimo": "5"})
        product_id = list_products()[0]["id"]
        with self.assertRaisesRegex(ValueError, "no puede quedar negativo"):
            register_movement(product_id, "salida", "3")
        self.assertEqual(list_products()[0]["stock_actual"], 2)
        self.assertEqual(len(list_alerts()), 0)
        first = check_inventory()
        self.assertEqual(first["status"], "simulado")
        self.assertIsNone(check_inventory()["alert_id"])
        self.assertEqual(len(list_alerts()), 1)
        register_movement(product_id, "entrada", "3")
        self.assertEqual(dashboard()["low"], 0)
        self.assertIsNone(check_inventory()["alert_id"])
        register_movement(product_id, "salida", "1")
        second = check_inventory()
        self.assertEqual(second["status"], "simulado")
        self.assertEqual(len(list_alerts()), 2)
        self.assertNotEqual(first["alert_id"], second["alert_id"])

    def test_failed_mail_can_be_retried(self):
        upsert_product({"codigo": "X2", "nombre": "Prueba", "categoria": "Clase",
                        "stock_actual": 0, "stock_minimo": 1})
        with patch.dict(os.environ, {"SMTP_HOST": "smtp.example.org"}):
            result = check_inventory()
            self.assertEqual(result["status"], "error")
            self.assertIn("SMTP_USER", list_alerts()[0]["error"])
        self.assertEqual(deliver_alert(result["alert_id"]), "simulado")
        self.assertEqual(list_alerts()[0]["attempts"], 2)
        self.assertIsNone(check_inventory()["alert_id"])

    def test_web_import_and_views(self):
        from app import app
        client = app.test_client()
        response = client.post("/importar", data={"archivo": (workbook(ROWS), "ejemplo.xlsx")},
                               content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Importaci", response.data)
        self.assertEqual(dashboard()["total"], 16)
        self.assertEqual(client.get("/movimientos").status_code, 200)
        self.assertEqual(client.post("/revisar", follow_redirects=True).status_code, 200)
        self.assertIn(b"Simulado: no enviado", client.get("/alertas").data)

    def test_delivered_example_and_single_monitor_lock(self):
        example = Path(__file__).resolve().parents[1] / "static" / "inventario_ejemplo.xlsx"
        with example.open("rb") as file:
            self.assertEqual(import_excel(file), 16)
        self.assertEqual(dashboard()["low"], 6)
        lock = acquire_lock(Path(self.temp.name) / "monitor.lock")
        try:
            with self.assertRaisesRegex(RuntimeError, "Ya hay un monitor"):
                acquire_lock(Path(self.temp.name) / "monitor.lock")
        finally:
            lock.close()


if __name__ == "__main__":
    unittest.main()
