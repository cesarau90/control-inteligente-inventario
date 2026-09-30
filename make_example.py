"""Regenera el Excel de ejemplo. Ejecutar con python make_example.py."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from inventory import HEADERS

ROWS = [
    ("P001", "Cuaderno profesional", "Papelería", 24, 8),
    ("P002", "Lápiz HB", "Papelería", 40, 15),
    ("P003", "Bolígrafo azul", "Papelería", 7, 12),
    ("P004", "Borrador blanco", "Papelería", 18, 6),
    ("P005", "Regla 30 cm", "Papelería", 3, 8),
    ("P006", "Marcador permanente", "Papelería", 12, 5),
    ("P007", "Carpeta tamaño carta", "Oficina", 9, 10),
    ("P008", "Grapadora", "Oficina", 5, 3),
    ("P009", "Caja de grapas", "Oficina", 14, 4),
    ("P010", "Notas adhesivas", "Oficina", 2, 7),
    ("P011", "Memoria USB 32 GB", "Tecnología", 11, 5),
    ("P012", "Cable USB-C", "Tecnología", 4, 6),
    ("P013", "Mouse inalámbrico", "Tecnología", 8, 4),
    ("P014", "Pilas AA", "Electrónica", 20, 10),
    ("P015", "Calculadora básica", "Electrónica", 1, 3),
    ("P016", "Cinta adhesiva", "Oficina", 16, 5),
]


def main():
    book = Workbook()
    sheet = book.active
    sheet.title = "Inventario"
    sheet.append(HEADERS)
    for row in ROWS:
        sheet.append(row)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="136C60")
    for column, width in {"A": 13, "B": 28, "C": 18, "D": 17, "E": 17}.items():
        sheet.column_dimensions[column].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    path = Path(__file__).resolve().parent / "static" / "inventario_ejemplo.xlsx"
    path.parent.mkdir(exist_ok=True)
    book.save(path)
    print(f"Creado: {path}")


if __name__ == "__main__":
    main()
