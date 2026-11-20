# ServoESP32

Control de un eje con motor DC, encoder incremental en cuadratura y etapa de potencia externa, para **ESP32 clásico / WROOM y MicroPython 1.26.0**. No es una salida de pulsos para un servomotor RC de 50 Hz.

Esta versión parte del software original conservado en `OG/`. Esa carpeta no se modifica ni se usa al ejecutar la versión nueva. La implementación activa está en la raíz.

Reporte publicado: [CI-2026-03: ServoESP32](https://ceptiaunam.blogspot.com/2026/10/ci-2026-03-servoesp32-control-de.html).

El [maestro Flask](https://github.com/cadena7/ServoESP32_Master/blob/main/README.md) se ejecuta en la computadora o Raspberry Pi y permite entonar hasta cuatro ejes por RS485.

## Archivos que se suben al ESP32

**Carga todos los archivos `.py` de la raíz y la carpeta `lib/` completa**, conservando esa misma estructura en la placa. Los archivos auxiliares se encuentran en `auxiliares/`; el original permanece en `OG/`.

| Elemento local | Destino en el ESP32 | ¿Subir? |
| --- | --- | --- |
| `boot.py`, `main.py` | Raíz de la placa | Sí |
| `config.py`, `control.py`, `hardware.py`, `commands.py`, `limits.py` | Raíz de la placa | Sí |
| `modbus_app.py`, `serial_json.py`, `web_app.py` | Raíz de la placa | Sí |
| `lib/` | `/lib/`, incluidas sus subcarpetas | Sí |
| `secrets.py`, si lo creas para Wi-Fi | Raíz de la placa | Solo si usas Wi-Fi |
| `auxiliares/` | No se carga | No |
| `OG/` | No se carga | No |
| `README.md`, `.gitignore` | No se cargan | No |

Desde la raíz del proyecto puedes cargarlo con:

```sh
python auxiliares/tools/deploy.py --port COM5
```

Sustituye `COM5` por tu puerto. La herramienta selecciona los archivos necesarios y copia `boot.py` y `main.py` al final. Para comprobar la selección sin conectar la placa, agrega `--dry-run`. Consulta [instalación](auxiliares/docs/INSTALACION.md) para preparar MicroPython o cargar desde Thonny, y [auxiliares/README.md](auxiliares/README.md) para las herramientas de computadora.

## Funciones

- PID discreto con saturación de error, integral y salida; zona muerta y parada por error de seguimiento.
- Trayectoria trapezoidal de posición, seguimiento por velocidad y ganancia variable cerca de la referencia.
- Encoder hardware PCNT, tres entradas digitales de uso general (ENT1–ENT3), tres salidas digitales (SAL1–SAL3) y captura de 1000 pares posición/error.
- Detección del cambio de estado de la entrada de inicio y almacenamiento de la posición encontrada.
- Límites de recorrido configurables en ENT1–ENT3: paro de PWM sin abrir el lazo, retirada en sentido contrario y estado Modbus/JSON.
- Modbus RTU con mapa y números de comando originales; JSON por serie y API HTTP opcional.

La búsqueda de inicio **detecta una transición**: no mueve el motor por sí misma ni pone automáticamente el encoder a cero. ENT1–ENT3 pueden usarse como límites negativos o positivos; por defecto permanecen como entradas generales hasta configurar su función y polaridad en `config.py`. Consulta [límites de recorrido](auxiliares/docs/LIMITES.md). El paro de emergencia físico sigue pendiente.

## Comenzar

1. Lee [instalación y puesta en marcha](auxiliares/docs/INSTALACION.md).
2. Revisa el cableado y edita [`config.py`](config.py). Por defecto: revisión B, Modbus ID 23, UART1 a 9600 8N1, JSON serie habilitado, Wi-Fi deshabilitado, PWM de 10 kHz y control cada 10 ms.
3. Carga MicroPython 1.26.0 y los archivos indicados en la guía.
4. Arranca con motor desconectado de la etapa de potencia y verifica entradas, encoder y PWM. El arranque deja el lazo abierto y PWM en cero.
5. Ajusta los parámetros al mecanismo antes de cerrar el lazo.

Ejemplos JSON por USB/UART0, un objeto por línea:

```json
{"CMD":"EDOJ"}
{"CMD":"CIERRA"}
{"CMD":"MUEVE","PAR":100}
{"CMD":"ABRE"}
```

`CIERRA` alinea la referencia con la posición actual. Para mover, cierra primero y envía después `MUEVE`. Los cambios de parámetros remotos duran hasta el reinicio; los valores iniciales se editan en `config.py`.

## Organización

| Archivo | Responsabilidad |
| --- | --- |
| `boot.py`, `main.py` | Estado inicial, arranque y ciclo de comunicaciones |
| `config.py` | GPIO, comunicaciones y valores de control |
| `control.py` | PID, trayectoria, ganancia variable, captura y eje |
| `hardware.py` | Encoder, PWM, temporizador y GPIO |
| `limits.py` | Interpretación de límites por entrada, polaridad y sentido bloqueado |
| `commands.py` | Validación y despacho compartido de comandos |
| `modbus_app.py` | Registros y comandos Modbus originales |
| `serial_json.py`, `web_app.py` | Interfaces JSON y HTTP |
| `lib/` | Dependencias locales necesarias para las interfaces disponibles |
| `auxiliares/tests/`, `auxiliares/tools/` | Pruebas en computadora y herramienta de carga |
| `auxiliares/docs/` | Guías, revisión y manifiesto de integridad del original |
| `OG/` | Original conservado; no se ejecuta ni se carga |

## Documentación

- [Instalación, placa Steren y cableado](auxiliares/docs/INSTALACION.md)
- [Implementar la secuencia de inicio en un maestro](auxiliares/docs/SECUENCIA_DE_INICIO.md)
- [Inicio y uno o dos fines de carrera: ejemplos completos](auxiliares/docs/INICIO_Y_LIMITES.md)
- [Cómo entonar el PID y evaluar un ensayo de escalón](auxiliares/docs/ENTONACION_PID.md)
- [Configuración y puntos de edición](auxiliares/docs/CONFIGURACION.md)
- [Límites de recorrido y retirada con lazo cerrado](auxiliares/docs/LIMITES.md)
- [Protocolo Modbus, JSON y HTTP](auxiliares/docs/PROTOCOLO.md)
- [Revisión, correcciones y compatibilidad](auxiliares/docs/REVISION.md)
- [Pruebas y validación pendiente en equipo](auxiliares/docs/PRUEBAS.md)
- [Funciones propuestas para una siguiente etapa](auxiliares/docs/PROPUESTAS.md)
- [Origen de dependencias y licencias](auxiliares/docs/TERCEROS.md)

## Pruebas

Desde la raíz, con Python 3 en la computadora:

```sh
python3 -m unittest discover -s auxiliares/tests -v
```

Se prueban la lógica y las tramas con periféricos simulados. Esto no certifica la respuesta física ni el período efectivo del control en un ESP32. Consultar las verificaciones pendientes en la guía de pruebas.

## Uso de las comunicaciones

**El controlador arranca sin Wi-Fi.** Con `WEB_ENABLED=False` no se intenta conectar. Si habilitas la web, el control y las comunicaciones locales se inician primero; Wi-Fi y HTTP se preparan en segundo plano. Sin credenciales, sin red o ante un fallo de conexión/servidor, se informa en consola y el control continúa. Esto no cambia `AUTO_CLOSE_LOOP=False`: el arranque predeterminado mantiene el lazo abierto hasta recibir `CIERRA`.

La API HTTP no tiene autenticación ni TLS; habilitarla únicamente en una red local de confianza. No publicar sus puertos en Internet. El control mediante temporizador Python no ofrece garantías de tiempo real: comunicaciones, serialización y recolección de basura pueden introducir retardos. Confirmar su comportamiento en el mecanismo real.

## Autoría y distribución

Proyecto original proporcionado por Edgar Omar Cadena Zepeda. No se asigna una licencia nueva al código original; las dependencias conservan sus avisos. Antes de distribuir el repositorio, revisar [TERCEROS.md](auxiliares/docs/TERCEROS.md). `OG/` contiene el material histórico íntegro, incluidas configuraciones que no deben darse por vigentes.

## Configurar inicio y fines de carrera

Consulta la [guía paso a paso con ejemplos completos](auxiliares/docs/INICIO_Y_LIMITES.md). Las opciones ya están implementadas en `config.py`; por defecto no hay fines de carrera habilitados.

Ejemplo: **ENT1 límite negativo, ENT2 positivo y ENT3 sensor de inicio**, suponiendo que los límites leen nivel bajo al accionarse:

```python
HOME_INPUT_INDEX = 3             # Número físico: ENT3
LIMIT_INPUT_ROLES = (-1, 1, 0)   # Orden: ENT1, ENT2, ENT3
LIMIT_ACTIVE_LEVELS = (0, 0, 1)  # Medir polaridad real antes de usar el ejemplo
```

Copiar `config.py` al ESP32 y reiniciar. Para armar inicio en la predeterminada, enviar `{"CMD":"BUSCAINICIO"}`. Para elegir otra solo para esa búsqueda, enviar `{"CMD":"BUSCAINICIO","ENTRADA":2}` (ENT2). **Configuración y comandos usan la misma numeración: 1=ENT1, 2=ENT2, 3=ENT3, 4=Z del encoder. El valor predeterminado del proyecto es HOME_INPUT_INDEX=1 (ENT1/GPIO33).** Modbus: escribir `[31,2,0]` en offsets 10–12; `[31,0,0]` usa la predeterminada.

BUSCAINICIO solo registra la posición ante la siguiente transición: no mueve, no para por sí mismo ni pone a cero el encoder. Puede compartir una entrada con un límite sin desactivar su protección. El límite cancela el destino y deja PWM=0, conservando el lazo si ya estaba cerrado; una nueva orden hacia el sentido permitido permite retirarse sin ABRE/CIERRA. Ver estado en offset Modbus 32 (`LIMITS`), BI/POSINI en 24–27 y entrada elegida en 36.

El índice Z de GPIO18 también puede elegirse como **opción 4 de BUSCAINICIO**. Se habilita con `ENCODER_INDEX_ENABLED=True`, captura posición en el flanco configurado y se consulta en registros 33–35; no reinicia el encoder. Consultar [configuración](auxiliares/docs/CONFIGURACION.md) y [protocolo](auxiliares/docs/PROTOCOLO.md).


Para usar el índice de una regla lineal/encoder como inicio, habilita en `config.py`:

```python
ENCODER_INDEX_ENABLED = True
ENCODER_INDEX_ACTIVE_LEVEL = 1  # 1=flanco ascendente, 0=descendente
# HOME_INPUT_INDEX = 4         # Opcional: Z como inicio predeterminado
```

Después de copiar la configuración y reiniciar, enviar `{"CMD":"BUSCAINICIO","ENTRADA":4}` o escribir `[31,4,0]` en offsets Modbus 10–12. `BI=2` indica que el primer flanco posterior al armado quedó registrado en `POSINI`. El índice no se agrega a las tuplas de límites: ENT1–ENT3 siguen siendo las tres entradas generales. [Ejemplo completo](auxiliares/docs/INICIO_Y_LIMITES.md#inicio-mediante-el-índice-z-de-una-regla-o-encoder-opción-4).

## Búsqueda con paro local para el banco Flask

La orden Modbus 58 usa las mismas palabras de selección que la 31. Su equivalente JSON es `{"CMD":"BUSCAINICIO_PARO","ENTRADA":1}`. El registro 30 anuncia esta función en el bit 7 y el armado o captura protegidos en el bit 6. Al capturar la primera transición, el controlador registra POSINI, indica BI=2, abre el lazo, corta PWM y bloquea la potencia hasta liberar la captura. CANCELA durante la búsqueda protegida también abre el lazo. La función histórica 31 conserva la captura sin paro. ENT1–ENT3 usan el ciclo de control y Z usa interrupción de software.

La consulta de los parámetros activos por Modbus FC04, JSON y HTTP se describe en [PROTOCOLO.md](auxiliares/docs/PROTOCOLO.md#lectura-de-parámetros-vigentes).
