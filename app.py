"""Interfaz web del proyecto escolar."""
import secrets
import sqlite3

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.exceptions import RequestEntityTooLarge

from alerts import check_inventory, deliver_alert
from inventory import (connect, dashboard, delete_product, import_excel, init_db,
                       list_alerts, list_movements, list_products, register_movement,
                       upsert_product)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
init_db()


def show_error(exc):
    if isinstance(exc, sqlite3.IntegrityError):
        flash("Ese código ya existe. Usa otro código o edita el producto existente.", "error")
    else:
        flash(str(exc), "error")


@app.errorhandler(RequestEntityTooLarge)
def file_too_large(_exc):
    flash("El archivo supera el límite de 2 MB.", "error")
    return redirect(url_for("inventory"))


@app.get("/")
def inventory():
    return render_template("inventory.html", page="inventario", products=list_products(),
                           summary=dashboard())


@app.post("/productos")
def add_product():
    try:
        upsert_product(request.form)
        flash("Producto registrado.", "success")
    except (ValueError, sqlite3.IntegrityError) as exc:
        show_error(exc)
    return redirect(url_for("inventory"))


@app.post("/productos/<int:product_id>/editar")
def edit_product(product_id):
    try:
        upsert_product(request.form, product_id)
        flash("Producto actualizado.", "success")
    except (ValueError, sqlite3.IntegrityError) as exc:
        show_error(exc)
    return redirect(url_for("inventory"))


@app.post("/productos/<int:product_id>/eliminar")
def remove_product(product_id):
    delete_product(product_id)
    flash("Producto eliminado. Su historial anterior se conserva.", "success")
    return redirect(url_for("inventory"))


@app.post("/productos/<int:product_id>/movimiento")
def move_stock(product_id):
    try:
        register_movement(product_id, request.form.get("tipo"), request.form.get("cantidad"))
        flash("Movimiento registrado.", "success")
    except ValueError as exc:
        show_error(exc)
    return redirect(url_for("inventory"))


@app.post("/importar")
def import_file():
    uploaded = request.files.get("archivo")
    if not uploaded or not uploaded.filename:
        flash("Selecciona un archivo .xlsx.", "error")
    elif not uploaded.filename.lower().endswith(".xlsx"):
        flash("Solo se aceptan archivos .xlsx.", "error")
    else:
        try:
            count = import_excel(uploaded.stream)
            flash(f"Importación completada: {count} producto(s) creados o actualizados.", "success")
        except ValueError as exc:
            show_error(exc)
    return redirect(url_for("inventory"))


@app.post("/revisar")
def check_now():
    result = check_inventory()
    if result["alert_id"] is None:
        flash("Revisión completa. No hay episodios nuevos de stock bajo.", "success")
    elif result["status"] == "simulado":
        flash("Alerta simulada y guardada. No se envió ningún correo real.", "info")
    elif result["status"] == "enviado":
        flash("Alerta enviada por correo y guardada.", "success")
    else:
        flash("La alerta se guardó, pero falló el correo. Puedes reintentar en Historial de alertas.", "error")
    return redirect(url_for("alerts_page"))


@app.get("/movimientos")
def movements_page():
    return render_template("movements.html", page="movimientos", movements=list_movements(),
                           summary=dashboard())


@app.get("/alertas")
def alerts_page():
    return render_template("alerts.html", page="alertas", alerts=list_alerts(),
                           summary=dashboard())


@app.post("/alertas/<int:alert_id>/reintentar")
def retry_alert(alert_id):
    try:
        status = deliver_alert(alert_id)
        flash("Reintento: " + {"simulado": "correo simulado; no se envió realmente",
                               "enviado": "correo enviado", "error": "el envío volvió a fallar"}.get(status, status) + ".",
              "error" if status == "error" else "info")
    except ValueError as exc:
        show_error(exc)
    return redirect(url_for("alerts_page"))


if __name__ == "__main__":
    app.run(debug=False)
