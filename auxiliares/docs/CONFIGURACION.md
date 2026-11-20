# Configuración y mantenimiento

`config.py` es la fuente de valores al arrancar. No se utiliza almacenamiento persistente de parámetros recibidos por comandos. Después de editar y copiar ese archivo, reiniciar la placa.

Para configurar inicio y uno o dos fines de carrera, comienza con [INICIO_Y_LIMITES.md](INICIO_Y_LIMITES.md): incluye recetas completas y la numeración física unificada de las entradas.

Para interpretar KP, KI, KD, el PWM y la trayectoria durante el ajuste, consulta la [guía de entonación PID](ENTONACION_PID.md).

## Campos principales

| Campo | Valor inicial | Qué modifica |
| --- | --- | --- |
| `CONTROL_PERIOD_MS` | 10 | Período nominal del temporizador |
| `PWM_FREQ` | 10000 | Frecuencia del PWM del puente |
| `AUTO_CLOSE_LOOP` | False | Cierre automático al arrancar; False exige `CIERRA` |
| `PID_KP`, `PID_KI`, `PID_KD` | 0.1 / 0.001 / 0.023 | Coeficientes discretos heredados |
| `PID_IL` | 1000 | Magnitud máxima del acumulador integral |
| `PID_UMAX` | 50000 | Máximo absoluto del mando; rango permitido 0–65535 |
| `PID_ERROR_MAX` | 4000 | Saturación de error usada por el PID |
| `MAX_FOLLOWING_ERROR` | 1000 | Si el error real supera este valor, abre el lazo; 0 deshabilita |
| `DEAD_ZONE` | 2 | Error menor que esta magnitud se pasa al PID como cero |
| `TRAJECTORY_SPEED` | 4.5 | Velocidad máxima, cuentas/muestra |
| `TRAJECTORY_ACCEL` | 0.05 | Aceleración, cuentas/muestra²; debe ser positiva |
| `TRAJECTORY_TOLERANCE` | 10 | Distancia final dentro de la cual se ajusta al objetivo |
| `MINPOS`, `MAXPOS` | −2147483648 / 2147483647 | Destinos absolutos en cuentas. Ambos son int32 y MINPOS debe ser menor que MAXPOS. |
| `TRACKING_SPEED` | 0 | Incremento de referencia por muestra en modo seguimiento |
| `GAIN_RANGE`, `GAIN_MAGNITUDE` | 500 / 1 | Ganancia adicional cerca de cero; rango 0 deshabilita |
| `MODBUS_ENABLED` | True | Habilita servidor RTU |
| `MODBUS_ADDRESS` | 23 | Dirección de dispositivo, 1–247; `m1.py` histórico usaba 20 |
| `MODBUS_BAUD` | 9600 | Velocidad RTU, formato 8N1 |
| `MODBUS_CTRL` | 13 | DE/RE del transceptor; None para conexión UART directa |
| `SERIAL_JSON_ENABLED` | True | Comandos JSON en la consola USB/UART0 |
| `WEB_ENABLED` | False | Intenta Wi-Fi/HTTP en segundo plano; no condiciona el arranque del control |
| `WEB_PORT` | 80 | Puerto HTTP |
| `WIFI_TIMEOUT_MS` | 15000 | Tiempo máximo del intento Wi-Fi en segundo plano; el control ya está iniciado |
| `MAX_REQUEST_BYTES` | 2048 | Máximo de una orden JSON entrante, serie/HTTP |
| `HOME_INPUT_INDEX` | 1 | Inicio predeterminado: 1=ENT1, 2=ENT2, 3=ENT3, 4=Z; no arma automáticamente |
| `ENCODER_INDEX_ENABLED` | False | Captura Z en GPIO18; requerida para usar inicio opción 4; separada de límites |
| `ENCODER_INDEX_ACTIVE_LEVEL` | 1 | Flanco Z: 1 ascendente, 0 descendente; no configura el sensor de inicio |
| `LIMIT_INPUT_ROLES` | (0, 0, 0) | Rol de ENT1–ENT3: 0 general, -1 límite negativo, 1 positivo |
| `LIMIT_ACTIVE_LEVELS` | (1, 1, 1) | Nivel activo 0/1 por GPIO para detectar cada límite |

Los valores PID son una base heredada, **no una sintonía validada para tu motor**. La integral es `I += KI * error`; la derivada es `KD * (error - error_anterior)`. No se multiplica/divide por segundos. Con 10 ms: 4.5 cuentas/muestra equivale a 450 cuentas/s y 0.05 cuentas/muestra² a 500 cuentas/s². Al cambiar el período hay que recalcular velocidades, aceleraciones, KI y KD; también cambia la ventana de captura.

El límite de error real para parar es distinto de la saturación del PID. El primero abre el lazo; el segundo limita el error numérico usado para calcular el mando. La zona muerta no borra automáticamente la integral: puede quedar un mando de sostén.

## Cableado

La PCB tiene **tres entradas generales**: `INPUT_PINS = (33, 4, 19)` corresponde a ENT1, ENT2 y ENT3 en ese orden. `OUTPUT_PINS = (21, 22, 23)` corresponde a SAL1, SAL2 y SAL3. Cualquiera de las entradas puede asignarse como límite negativo o positivo mediante `LIMIT_INPUT_ROLES`, con polaridad independiente en `LIMIT_ACTIVE_LEVELS`; por defecto todas permanecen como generales. Consultar [LIMITES.md](LIMITES.md). La detección de inicio existente utiliza ENT1 por defecto únicamente cuando se ordena `BUSCAINICIO`; no reserva una cuarta entrada.

GPIO18 es el indice Z opcional. Configurar `ENCODER_INDEX_ENABLED = True` para capturar cada flanco seleccionado por `ENCODER_INDEX_ACTIVE_LEVEL` (1 ascendente, 0 descendente); por defecto esta deshabilitado. La captura guarda la cuenta PCNT en `Z_POS`; `Z_VALID` indica si ya hubo un pulso. No borra el encoder ni mueve el motor. `RESTABLECE` invalida la captura anterior. Modbus publica Z en registros 33-35, separados de ENT1-ENT3; JSON/HTTP lo incluye en `EDOJ` junto con `Z_ENABLED` y `Z_LEVEL`. Se usa una interrupcion Python soft: la cuenta corresponde al momento de atenderla, sin captura hardware sincronizada al flanco. Validar precision y frecuencia de pulsos bajo carga en el ESP32 antes de usarla como referencia precisa.

Todos los GPIO se cambian en `config.py`: `ENCODER_A/B`, `DIR_A/B`, `PWM_PIN`, `OE_PIN`, `INPUT_PINS`, `OUTPUT_PINS` y parámetros UART. `HOME_INPUT_INDEX` selecciona una entrada de `INPUT_PINS`; los bits de entradas siguen el orden de esa tupla. `INPUT_PULL` puede configurarse con un valor de `machine.Pin` si se necesita; inicialmente `None` conserva entradas sin polarización interna. GPIO35 no admite pull interno.

`OE_LEVEL=0` reproduce OG. No se cambia automáticamente a otro nivel en un fallo porque no se conoce la polaridad de la electrónica externa; el paro pone PWM y ambas direcciones en cero. Si se requiere deshabilitación por OE, revisar el circuito antes de modificar `Hardware.stop()`.

## Dónde editar cada comportamiento

| Cambio | Lugar |
| --- | --- |
| Parámetros por defecto, placa o comunicaciones | `config.py` |
| Ajuste de PID, trayectoria o ganancia | `control.py`: `PidControl`, `Tray`, `CGAIN` |
| Secuencia de control y política de parada | `control.py`: `Eje.ejec_control` |
| Polaridad, tabla de puente o lectura del encoder | `hardware.py` |
| Asignación y nivel de límites de recorrido | `config.py`; interpretación en `limits.py` y parada/rearme en `control.py` |
| Nuevo comando compartido o validación | `commands.py` |
| Nuevos registros o función Modbus | `modbus_app.py` y `auxiliares/docs/PROTOCOLO.md` |
| Ruta HTTP | `web_app.py` |
| Lectura y límite de línea JSON | `serial_json.py` |

Las comunicaciones comparten el mismo eje. Si se utilizan varias a la vez, las órdenes se aplican en el orden en que se atienden; no hay arbitraje de propietario. La bandera interna `busy` hace que el callback omita una muestra mientras se modifica o consulta el estado por comandos. Evitar descargar datos continuamente durante movimientos exigentes.

## Seleccionar entrada de inicio

`HOME_INPUT_INDEX = 1`, `2`, `3` o `4` selecciona ENT1, ENT2, ENT3 o Z como predeterminada al arrancar y en cada BUSCAINICIO sin ENTRADA. Para elegir por orden: `{"CMD":"BUSCAINICIO","ENTRADA":3}` usa ENT3; ENTRADA admite enteros 1–4; 4 requiere ENCODER_INDEX_ENABLED=True. Modbus: escribir `[31,3,0]` desde offset 10. Usar `[31,0,0]` para la predeterminada. `HOME_INPUT` (JSON) o registro 36 indica la entrada seleccionada, numerada 1–4. ENT1–ENT3 detectan cualquier cambio respecto al nivel al armar; Z captura el primer flanco configurado posterior al armado. No realiza una secuencia automática de homing.


Los roles y polaridades de límites se editan solo en `config.py` y requieren copia y reinicio; no son parámetros de `CAMBIA`. La entrada de inicio se puede elegir en cada orden. En ENT1–ENT3 no existe ajuste de flanco activo para BUSCAINICIO; Z (opción 4) sí utiliza ENCODER_INDEX_ACTIVE_LEVEL. Las tres funciones (inicio, límites y Z) se configuran de forma independiente.


Pese al nombre histórico `HOME_INPUT_INDEX`, su valor es el **número de fuente de inicio** (1–3=ENT1–ENT3, 4=Z), igual al campo ENTRADA y al registro 36. El predeterminado es `1` (ENT1/GPIO33), como OG. Al migrar un config.py de la versión anterior: antiguo 0 → nuevo 1, antiguo 1 → nuevo 2, antiguo 2 → nuevo 3. El valor 0 ya no se admite en este campo. En Modbus, `[31,0,0]` sigue siendo el atajo para usar la predeterminada; no selecciona una entrada 0.

Para habilitar inicio por Z: `ENCODER_INDEX_ENABLED=True`, elegir el flanco y opcionalmente `HOME_INPUT_INDEX=4`; o enviar `{"CMD":"BUSCAINICIO","ENTRADA":4}`. Ver el ejemplo de [INICIO_Y_LIMITES.md](INICIO_Y_LIMITES.md). El valor predeterminado activo del proyecto permanece en 1 (ENT1) y Z deshabilitado.
