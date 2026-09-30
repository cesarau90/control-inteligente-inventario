"""Monitor independiente de Flask. Ejecutar: python monitor.py"""
import argparse
import os
import time
from pathlib import Path

from alerts import check_inventory
from inventory import BASE_DIR, init_db


def acquire_lock(path):
    try:
        handle = open(path, "a+b")
        handle.seek(0)
        if handle.read(1) == b"":
            handle.seek(0)
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if "handle" in locals():
            handle.close()
        raise RuntimeError("Ya hay un monitor en ejecución para este proyecto.") from None
    return handle


def main():
    parser = argparse.ArgumentParser(description="Monitor periódico del inventario")
    parser.add_argument("--once", action="store_true", help="Ejecutar una sola revisión")
    args = parser.parse_args()
    try:
        interval = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
    except ValueError:
        parser.error("CHECK_INTERVAL_SECONDS debe ser un número entero.")
    if interval < 10:
        parser.error("CHECK_INTERVAL_SECONDS debe ser al menos 10.")
    init_db()
    if args.once:
        print(check_inventory(), flush=True)
        return
    lock = acquire_lock(Path(BASE_DIR) / "monitor.lock")
    print(f"Monitor iniciado. Revisión cada {interval} segundos. Ctrl+C para detener.", flush=True)
    try:
        while True:
            print(f"Revisión: {check_inventory()}", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Monitor detenido.", flush=True)
    finally:
        lock.close()


if __name__ == "__main__":
    main()
