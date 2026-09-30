"""Inicia la interfaz y un monitor independiente con una sola orden."""
import argparse
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# El Python incluido con pgAdmin en este equipo usa un paquete local de
# dependencias. Con un entorno virtual normal se usan las dependencias de este.
try:
    import flask  # noqa: F401
    import openpyxl  # noqa: F401
    import dotenv  # noqa: F401
    use_local_deps = False
except ModuleNotFoundError:
    sys.path.insert(0, str(BASE_DIR / ".deps"))
    use_local_deps = True

from app import app


def main():
    parser = argparse.ArgumentParser(description="Inicia la página y el monitor")
    parser.add_argument("--no-browser", action="store_true", help="No abrir el navegador automáticamente")
    args = parser.parse_args()

    paths = [str(BASE_DIR)]
    if use_local_deps:
        paths.append(str(BASE_DIR / ".deps"))
    monitor_code = f"import sys,runpy;sys.path[:0]={paths!r};runpy.run_path({str(BASE_DIR / 'monitor.py')!r},run_name='__main__')"
    log = open(BASE_DIR / "monitor.log", "a", encoding="utf-8")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    monitor = subprocess.Popen([sys.executable, "-c", monitor_code], cwd=BASE_DIR,
                               stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
    time.sleep(0.5)
    if monitor.poll() is None:
        print("Monitor automático iniciado; revisa cada 60 segundos por defecto.", flush=True)
    else:
        print("El monitor no arrancó. Puede haber otro monitor activo; consulta monitor.log.", flush=True)
    print("Página: http://127.0.0.1:5000/", flush=True)
    print("Mantén esta ventana abierta. Ctrl+C detiene la página y su monitor.", flush=True)
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000/")).start()
    try:
        app.run(host="127.0.0.1", port=5000, debug=False)
    finally:
        if monitor.poll() is None:
            monitor.terminate()
            try:
                monitor.wait(timeout=5)
            except subprocess.TimeoutExpired:
                monitor.kill()
                monitor.wait()
        log.close()


if __name__ == "__main__":
    main()
