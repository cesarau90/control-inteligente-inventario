# Control inteligente de inventario y alertas de stock

Miniproyecto escolar con Flask, SQLite y openpyxl. Permite administrar productos, registrar entradas y salidas, importar Excel y revisar el stock automáticamente. La palabra “inteligente” se refiere a reglas claras de stock mínimo; este proyecto no usa inteligencia artificial.

## Requisitos

- Windows 10 u 11 y Python 3.10 o superior, instalado con la opción **Add python.exe to PATH**.
- Una terminal PowerShell.
- Una cuenta SMTP solo si se desean correos reales. Sin ella funciona el modo de demostración.

## Instalación paso a paso en Windows

**Inicio fácil en este equipo:** haz doble clic en `Iniciar Inventario.bat`. Abre la página en el navegador y activa el monitor automático en la misma ejecución. Mantén la ventana de comandos abierta. Al cerrarla con `Ctrl+C`, se detienen la página y ese monitor.

Si estás usando este mismo equipo y la carpeta `.deps` aún existe, puedes abrir la interfaz directamente desde PowerShell con `powershell -ExecutionPolicy Bypass -File .\iniciar_demo.ps1`. Deja esa terminal abierta. En otra terminal, `powershell -ExecutionPolicy Bypass -File .\iniciar_demo.ps1 -Monitor` inicia la revisión automática. Si copias el proyecto a otro equipo, sigue la instalación estándar siguiente.

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Si `py` no está disponible, instala Python desde python.org y vuelve a abrir PowerShell. También puedes reemplazar `py` por `python` si ese comando funciona en tu equipo.

El archivo `.env` puede quedarse como está para la demostración. Para cambiar el intervalo, edita `CHECK_INTERVAL_SECONDS` (mínimo 10 segundos); el monitor lee el valor al iniciar.

### Terminal 1: interfaz web

```powershell
.\.venv\Scripts\python.exe app.py
```

Abre `http://127.0.0.1:5000` en el navegador. Importa `static\inventario_ejemplo.xlsx` desde la sección **Importar desde Excel**. Contiene 16 productos, incluidos seis con stock bajo. También se puede descargar desde la interfaz.

### Terminal 2: monitoreo automático

Con la primera terminal abierta, abre otra PowerShell en la misma carpeta y ejecuta:

```powershell
.\.venv\Scripts\python.exe monitor.py
```

El proceso revisa inmediatamente y luego cada `CHECK_INTERVAL_SECONDS`, aunque nadie tenga abierta la página. Déjalo en ejecución para seguir monitoreando; `Ctrl+C` lo detiene. `monitor.py --once` hace una sola revisión. Un bloqueo de proceso impide iniciar dos monitores a la vez. Flask no crea monitores, por lo que su recargador de desarrollo tampoco los duplica. El botón **Revisar inventario ahora** funciona con o sin el monitor.

## Correos reales y modo de demostración

En `.env`, deja vacíos `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` y `ALERT_TO` para el modo de demostración. La aplicación crea y guarda el asunto, el cuerpo y los productos afectados, y marca la alerta como **“Simulado: no enviado”**. No se entrega ningún correo.

Para activar el correo real, completa las cinco variables con los datos de tu proveedor SMTP. `SMTP_PORT=587` y `SMTP_USE_TLS=true` usan STARTTLS; el puerto 465 usa SSL. `ALERT_TO` es el destinatario. Usa una contraseña de aplicación si el proveedor la requiere. Nunca guardes contraseñas en el código ni subas `.env` al repositorio. Reinicia la interfaz y el monitor después de cambiar `.env`.

Si la configuración está incompleta o falla SMTP, la alerta queda con estado **Error de envío** y el motivo aparece en el historial. El botón **Reintentar envío** usa el correo ya guardado. Una revisión periódica no crea otro aviso para el mismo episodio de stock bajo.

## Uso

1. Registra productos a mano o importa el Excel. La importación revisa todas las filas antes de guardar; si alguna falla, no se guarda ninguna. Un código existente se actualiza.
2. Usa **Movimiento** para registrar entradas o salidas. Una salida que dejaría el stock negativo se rechaza.
3. Pulsa **Revisar inventario ahora** o espera al monitor.
4. Consulta **Historial de alertas** para ver los productos, el contenido del correo, el resultado y los intentos. Consulta **Movimientos** para ver entradas y salidas.

La tabla resalta productos cuando `stock_actual < stock_minimo`. La igualdad no cuenta como stock bajo. Si un producto se recupera (`stock_actual >= stock_minimo`) y después vuelve a caer, se genera una alerta nueva. El historial de movimientos y alertas se conserva aunque se elimine un producto.

## Flujo

**Revisar inventario → detectar stock bajo → generar una alerta por episodio nuevo → enviar o simular correo → guardar resultado e historial.**

Los datos se guardan en `inventario.db`, creado automáticamente al iniciar. El archivo está excluido de Git. El proyecto limita los Excel a 2 MB y exige las columnas `codigo`, `nombre`, `categoria`, `stock_actual`, `stock_minimo` en ese orden.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas cubren importación y actualización sin duplicados, validación de archivos sin cambios parciales, rechazo de stock negativo, detección de stock bajo, no duplicación de alertas, nueva alerta después de reabastecer y reintento tras un fallo de configuración SMTP. Para regenerar el Excel de ejemplo: `.\.venv\Scripts\python.exe make_example.py`.

## Guion breve para exponer en clase

1. Abre Inventario e importa el Excel de ejemplo. Señala un producto resaltado y los contadores del resumen.
2. Pulsa **Revisar inventario ahora**. Abre el historial y muestra que el aviso dice **Simulado: no enviado** y contiene el correo generado.
3. Revisa otra vez: el historial no crece porque no se repite el mismo aviso.
4. Da entrada suficiente a un producto para alcanzar su mínimo; luego registra una salida para dejarlo bajo el mínimo otra vez.
5. Revisa de nuevo: aparece una alerta nueva para esa nueva caída. Intenta una salida mayor que el stock para mostrar que se rechaza.
6. Explica que `monitor.py` realiza estas revisiones periódicamente aunque la página esté cerrada, y que completar `.env` activa los envíos reales.
