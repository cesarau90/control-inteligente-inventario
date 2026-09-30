"""Detección por episodios de stock bajo y entrega de avisos."""
import json
import os
import smtplib
from email.message import EmailMessage

from inventory import connect, now


def mail_config():
    names = ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "ALERT_TO")
    values = {name: os.getenv(name, "").strip() for name in names}
    if not any(values.values()):
        return "demo", values
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError("Configuración SMTP incompleta: faltan " + ", ".join(missing) + ".")
    return "smtp", values


def create_alert_for_new_low():
    """Reserva un aviso por cada nuevo episodio de stock bajo, de forma atómica."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE products SET low_active=0 WHERE stock_actual >= stock_minimo")
        low = db.execute("""SELECT id,codigo,nombre,stock_actual,stock_minimo FROM products
                            WHERE stock_actual < stock_minimo AND low_active=0
                            ORDER BY nombre COLLATE NOCASE""").fetchall()
        db.execute("INSERT INTO settings(key,value) VALUES('last_check',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (now(),))
        if not low:
            return None
        items = [dict(row) for row in low]
        subject = f"Alerta de inventario: {len(items)} producto(s) con stock bajo"
        lines = ["Productos por debajo del stock mínimo:", ""]
        for item in items:
            lines.append(f"• {item['codigo']} — {item['nombre']}: actual {item['stock_actual']}, mínimo {item['stock_minimo']}")
        lines.extend(["", "Generado por Control inteligente de inventario y alertas de stock."])
        body = "\n".join(lines)
        cur = db.execute("""INSERT INTO alerts(created_at,items_json,subject,body,status)
                            VALUES(?,?,?,?, 'pendiente')""", (now(), json.dumps(items, ensure_ascii=False), subject, body))
        db.executemany("UPDATE products SET low_active=1 WHERE id=?", [(item["id"],) for item in items])
        return cur.lastrowid


def deliver_alert(alert_id):
    with connect() as db:
        alert = db.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
        if alert is None:
            raise ValueError("La alerta no existe.")
        if alert["status"] not in ("pendiente", "error"):
            return alert["status"]
        # El reclamo evita que dos procesos reintenten el mismo aviso a la vez.
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute("""UPDATE alerts SET status='enviando', attempts=attempts+1,
                              last_attempt_at=?,error=NULL WHERE id=? AND status IN ('pendiente','error')""",
                             (now(), alert_id)).rowcount
        if not changed:
            return "enviando"
    try:
        mode, config = mail_config()
        if mode == "demo":
            status = "simulado"
        else:
            message = EmailMessage()
            message["Subject"] = alert["subject"]
            message["From"] = config["SMTP_FROM"]
            message["To"] = config["ALERT_TO"]
            message.set_content(alert["body"])
            port = int(os.getenv("SMTP_PORT", "587"))
            if port == 465:
                with smtplib.SMTP_SSL(config["SMTP_HOST"], port, timeout=15) as smtp:
                    smtp.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(config["SMTP_HOST"], port, timeout=15) as smtp:
                    if os.getenv("SMTP_USE_TLS", "true").lower() == "true":
                        smtp.starttls()
                    smtp.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
                    smtp.send_message(message)
            status = "enviado"
        error = None
    except Exception as exc:
        status, error = "error", str(exc)
    with connect() as db:
        db.execute("UPDATE alerts SET status=?,error=? WHERE id=?", (status, error, alert_id))
    return status


def check_inventory():
    alert_id = create_alert_for_new_low()
    return {"alert_id": alert_id, "status": deliver_alert(alert_id) if alert_id else None}
