# Dependencias y autoría

## umodbus

Se copia desde `OG/lib/umodbus`, sin descargar otra versión. El valor de versión se conserva en `lib/umodbus/version.py`. Los encabezados de varios módulos atribuyen código a Pycom Limited y mencionan GNU GPL versión 3 o posterior con términos adicionales; los enlaces originales permanecen en los archivos. La carpeta entregada no incluye el texto completo de esos términos. No se declara una licencia global inventada para el conjunto ni se atribuye el código de terceros al autor del proyecto.

Se conservan `__init__.py`, `version.py`, `serial.py`, `common.py`, `functions.py`, `modbus.py`, `const.py` y `typing.py`: son dependencias del transporte RTU. El módulo de tipos evita depender de typing de CPython. Se excluye `tcp.py` porque el proyecto no utiliza Modbus TCP.

Cambios locales respecto de OG:

- `serial.py`: DE/RE inicial en cero y recepción incremental cuando process consulta sin bloqueo.
- `common.py`: validación de tamaño y byte-count de solicitudes RTU.
- `modbus.py`: palabras de lectura sin signo y validación completa de rangos de acceso.

Antes de publicar o redistribuir, verificar las condiciones y aportar los textos de licencia exigidos por esos autores. No se añaden licencias nuevas sobre material original sin indicación de su titular.

## nanoweb

El nombre de archivo se conserva dentro de `lib/` para ubicar el servidor HTTP, pero su contenido se reemplaza por un servidor mínimo escrito para esta revisión. Ya no incluye plantillas, comodines ni servicio de archivos de ejemplo: las funciones del servocontrol se exponen mediante rutas explícitas de `web_app.py`. La API interna antigua de Nanoweb no se presenta como compatible.

## Fuentes técnicas consultadas

- [Placa Steren SKU ESP32](https://www.steren.com.mx/placa-de-programacion-tipo-esp32.html)
- [Firmware oficial ESP32_GENERIC](https://micropython.org/download/ESP32_GENERIC/)
- [MicroPython 1.26: ESP32](https://docs.micropython.org/en/v1.26.0/esp32/quickref.html)
- [MicroPython 1.26: Encoder](https://docs.micropython.org/en/v1.26.0/library/machine.Encoder.html)
- [MicroPython 1.26: PWM](https://docs.micropython.org/en/v1.26.0/library/machine.PWM.html)
- [MicroPython 1.26: asyncio](https://docs.micropython.org/en/v1.26.0/library/asyncio.html)

Consulta: 17 de noviembre de 2026. La identificación definitiva del módulo se hace sobre la placa física, no mediante la ficha comercial.
