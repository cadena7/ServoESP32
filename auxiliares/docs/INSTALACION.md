# Instalación en ESP32 genérico

## Placa prevista

La [placa de programación Steren SKU ESP32](https://www.steren.com.mx/placa-de-programacion-tipo-esp32.html) anuncia flash de 32 Mbit (4 MB), Bluetooth 4.2 y Wi-Fi. Su ficha pública no especifica el módulo exacto y no permite asegurar la revisión de tu unidad. La selección **ESP32_GENERIC** es una inferencia para la variante clásica ESP32/WROOM, no para ESP32-C3, S2 o S3.

Antes de flashear, revisa la inscripción del blindaje y confirma el chip detectado por esptool. Si dice ESP32-WROOM-32/32D/32E y tiene 4 MB de flash, corresponde al objetivo de este proyecto. En WROVER/PSRAM, GPIO16 y GPIO17 pueden estar ocupados: no usar este cableado sin verificar. Los números de esta guía son **GPIO**, no posiciones físicas de la hilera.

MicroPython 1.26 incluye [`machine.Encoder`](https://docs.micropython.org/en/v1.26.0/library/machine.Encoder.html) para ESP32; se usa decodificación x4 como en OG. La salida usa `PWM.duty_u16`, escala 0–65535, a 10 kHz.

## Cableado conservado: revisión B

| Señal | GPIO | Observación |
| --- | --- | --- |
| Encoder A / B | 16 / 17 | Entrada de cuadratura a niveles de 3.3 V |
| Dirección A / B | 26 / 14 | Revisión 0 usaba GPIO12 para A |
| PWM | 27 | Entrada de la etapa externa; nunca conectar motor al GPIO |
| OE | 25 | Se conserva nivel 0 de OG; verificar su significado en tu circuito |
| ENT1 (uso general) | 33 | Bit 0 de entradas; detección de transición solo al ordenar búsqueda de inicio |
| ENT2 (uso general) | 4 | Bit 1 del paquete de entradas |
| ENT3 (uso general) | 19 | Bit 2 del paquete de entradas |
| Índice Z del codificador (opcional) | 18 | No es ENT4; deshabilitado por defecto y fuera del paquete de entradas |
| SAL1 / SAL2 / SAL3 | 21 / 22 / 23 | Salidas de uso general, inicialmente 0 |
| Modbus TX / RX | 32 / 35 | RX35 solo entrada, sin pull-up interno |
| Dirección RS485 | 13 | DE y /RE unidos; alto transmite, bajo recibe |
| USB / UART0 | 1 / 3 | REPL y JSON, normalmente por puente USB de la placa |

Las entradas se leen sin invertir y sin pull interno por defecto. Colocar resistencias de polarización y adaptar las señales externas a 3.3 V. Para RS485 se necesita un transceptor compatible con lógica 3.3 V, cableado A/B, referencia y terminación apropiados. El firmware solo proporciona señales a una etapa de potencia externa. Confirmar la tabla de dirección/freno del puente utilizado; PWM=0 y ambas direcciones=0 es el estado de parada de esta versión.

## Firmware

Usar la descarga **v1.26.0** de [ESP32_GENERIC](https://micropython.org/download/ESP32_GENERIC/), variante estándar para ESP32 clásico de 4 MB sin PSRAM. No seleccionar automáticamente la versión más reciente.

Instala herramientas en un entorno de la computadora. Se fija esptool 4 para que los comandos siguientes mantengan esa sintaxis:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'esptool==4.8.1' mpremote
```

En PowerShell, activa con `.venv\Scripts\Activate.ps1`; puedes usar `python` en lugar de `python3`. Cierra Thonny y otros programas que ocupen el puerto.

Sustituye `PUERTO` por `/dev/cu.usbserial-...`, `/dev/ttyUSB0` o `COM5`, y `FIRMWARE.bin` por la ruta al archivo descargado:

```sh
python -m esptool --chip esp32 --port PUERTO chip_id
python -m esptool --chip esp32 --port PUERTO flash_id
```

Con el motor sin alimentación, respalda cualquier archivo de la placa que necesites. **El siguiente comando borra toda su flash**:

```sh
python -m esptool --chip esp32 --port PUERTO erase_flash
python -m esptool --chip esp32 --port PUERTO --baud 460800 write_flash -z 0x1000 FIRMWARE.bin
```

Si no entra al cargador, mantener BOOT al iniciar la conexión y soltarlo cuando conecte. Si hay errores de transferencia, bajar a 115200. No es necesario borrar flash para actualizar solamente archivos Python.

## Cargar el proyecto

**Selección manual:** subir todos los `.py` de la raíz del proyecto y `lib/` completa, conservando las subcarpetas. No subir `auxiliares/`, `OG/`, `README.md` ni `.gitignore`. El [README principal](../../README.md) incluye la lista de archivos; las herramientas y pruebas se describen en [auxiliares/README.md](../README.md).

Desde la raíz del repositorio, revisar primero `config.py`. Para listar los archivos que se copiarán sin conectar:

```sh
python auxiliares/tools/deploy.py --port PUERTO --dry-run
```

Para copiar:

```sh
python auxiliares/tools/deploy.py --port PUERTO
python -m mpremote connect PUERTO reset
python -m mpremote connect PUERTO repl
```

La herramienta copia únicamente los módulos de ejecución y `lib/`, con `boot.py` y `main.py` al final. No copia `OG/`, documentación, pruebas ni cachés. Utiliza una placa recién preparada o retira manualmente módulos viejos que puedan interferir: la herramienta no borra archivos ajenos.

En Thonny también se pueden guardar esos mismos archivos y `lib/` en el ESP32, conservando sus nombres y estructura. `lib/umodbus/` debe ser una subcarpeta completa.

## Primera puesta en marcha

Si se usarán switches de recorrido, configurar primero sus roles y niveles activos en `config.py` siguiendo [LIMITES.md](LIMITES.md). Con la potencia desconectada, comprobar los bits activos del registro 32 y verificar el sentido positivo/negativo. Después validar parada y retirada a baja velocidad. Por defecto `LIMIT_INPUT_ROLES=(0, 0, 0)` conserva las tres entradas como generales.

1. Mantener la etapa sin alimentar, arrancar y comprobar que no hay traceback y que el PWM es cero.
2. Girar manualmente el encoder; pedir `EDOJ` y comprobar conteo y signo. Conectar las entradas y verificar los bits por Modbus.
3. Revisar con osciloscopio PWM, dirección, OE y DE/RE. No asumir que OE=0 deshabilita tu electrónica.
4. Aplicar límites conservadores de PWM (`PID_UMAX`) y probar brevemente `DAX` con la carga desacoplada. Terminar con `ABRE`.
5. Confirmar que el sentido de accionamiento corrige el error: una orden positiva debe producir conteo positivo. Si no, corregir fases del encoder o dirección del motor con el equipo apagado.
6. Ajustar PID, velocidad, aceleración y error máximo para el mecanismo. Enviar `CIERRA`, después un movimiento pequeño y finalmente `ABRE`.
7. Ejecutar las verificaciones de [PRUEBAS.md](PRUEBAS.md) antes del uso normal.

Para interrumpir la aplicación, pulsa Ctrl-C desde el REPL; el bloque de limpieza detiene PWM y temporizador. Para consultar la versión, interrumpe y ejecuta `import sys; print(sys.implementation)`.

## Web opcional

Configurar `WEB_ENABLED = True`. Crear localmente `secrets.py`:

```python
WIFI_SSID = 'tu-red'
WIFI_PASSWORD = 'tu-clave'
```

Copiar con `python auxiliares/tools/deploy.py --port PUERTO --with-secrets`. No subir ese archivo a GitHub. También existen los campos de red de `config.py`, pero no guardar claves reales en un repositorio público. El control y las comunicaciones locales arrancan sin esperar al Wi-Fi. La conexión se intenta en segundo plano durante un máximo de 15 segundos; si faltan credenciales, la red no está disponible o falla el servidor HTTP, se informa en consola y el control continúa. Al habilitar web, la IP aparece en la consola si se logra conectar. No hay reconexión automática implementada.

## Elegir el sensor de inicio y los fines de carrera

Después de comprobar los niveles físicos de ENT1–ENT3, aplicar una de las recetas de [INICIO_Y_LIMITES.md](INICIO_Y_LIMITES.md). La selección de sensor y las asignaciones de límites son independientes: BUSCAINICIO no activa ni desactiva protecciones. Copiar el `config.py` editado a la placa y reiniciar; verificar registros 30, 32 y 36 antes de mover.

Para utilizar la marca de índice de una regla/encoder como referencia de inicio, habilitar `ENCODER_INDEX_ENABLED=True` y elegir `ENTRADA:4` o `HOME_INPUT_INDEX=4`. Verificar compatibilidad de señales A/B/Z y sus niveles eléctricos antes de conectar; el índice se mantiene separado de las tres entradas generales. La [guía de inicio](INICIO_Y_LIMITES.md) detalla configuración y comportamiento por flanco.
