# Protocolos

## Modbus RTU

Dirección inicial **23**, UART1, **9600 8N1**. Direcciones de registro de esta tabla son **offsets desde cero**, no referencias 4xxxx. Cada entero largo es `int32` con signo; cada parámetro flotante es IEEE754 `float32`. En ambos casos se transmite primero la palabra alta y dentro de cada palabra primero el byte alto.

Para ejecutar, escribir con función Modbus **16 / 0x10** los tres holding registers 10, 11 y 12 juntos. El registro 10 contiene el número de comando; 11 y 12 contienen sus argumentos. También se pueden escribir primero los argumentos y por último el comando mediante función 6; nunca escribir el comando antes de terminar de cargar sus argumentos.

Después de atenderlo, el firmware pone 10 a cero. La confirmación RTU de escritura significa que los registros se aceptaron, **no que terminó el movimiento ni que los parámetros pasaron la validación de aplicación**. Las órdenes inválidas se rechazan, se imprimen por consola y también se limpia 10, como protocolo sin registro de resultado específico. Leer posición y estado para dar seguimiento. Se admiten lecturas 3 y 4 y escrituras 6/16; otras funciones de biblioteca no tienen registros de aplicación asociados. Broadcast no está implementado.

| Offset | Contenido | Tipo |
| --- | --- | --- |
| 10 | Función; 0 = sin comando pendiente | uint16 |
| 11–12 | Argumento | int32 o float32 según función |
| 14–15 | Reservados del original; sin efecto | 2 × uint16 |
| 20–21 | X: posición medida | int32 |
| 22–23 | XT: posición de trayectoria truncada a entero | int32 |
| 24–25 | BI: búsqueda de inicio | int32; 0 inactiva, 1 esperando, 2 encontrada |
| 26–27 | POSINI: posición de transición de inicio | int32 |
| 28–29 | U: mando aplicado con signo | int32 |
| 30 | Bits de modo y entradas | uint16 |
| 31 | HAB: habilitación de PID | uint16 |
| 32 | LIMITS: límites activos y parada direccional | uint16 |

En 32, bits 0/1 indican límite negativo/positivo activo; bits 2/3 indican parada negativa/positiva pendiente de una nueva orden permitida; bits 8/9/10 identifican ENT1/ENT2/ENT3 configuradas como límite y activas. No confundir offset 32 con comando 32 (CANCELA). El mapa completo de estado se extiende hasta 37 (Z y entrada de inicio se describen al final); los offsets anteriores se conservan. `EDOJ` agrega el campo `LIMITS` con el mismo valor. Ejemplos y comportamiento de retirada en [LIMITES.md](LIMITES.md).

En 30, bit 0 indica seguimiento de velocidad. Bits 8, 9 y 10 son ENT1, ENT2 y ENT3 (GPIO33, 4 y 19, respectivamente; orden configurable). El bit 11 queda en cero: GPIO18 es el índice opcional del codificador y no se incluye entre las entradas generales. Son valores físicos sin invertir. En HAB, bit 0 habilita lazo y bit 1 habilita integral; el control actualiza automáticamente bit 1 según se detiene o avanza la trayectoria. Una parada por error deja HAB=0.

| Función en reg. 10 | Acción | Argumento de regs. 11–12 |
| --- | --- | --- |
| 1 | Mover a posición absoluta | int32 |
| 2 / 3 | Cerrar / abrir lazo | Ignorado |
| 4 / 5 / 6 | KP / KI / KD | float32 finito, ≥0 |
| 7 | Límite integral IL | float32, ≥0 |
| 8 | Máximo UMAX | float32 que represente un entero, 0–65535 |
| 9 / 10 | Habilitar / deshabilitar seguimiento | Ignorado |
| 20 | Aceleración | float32 positivo |
| 21 | Velocidad de trayectoria | float32 positivo |
| 22 | Velocidad de seguimiento | float32; puede ser negativa |
| 23 / 24 | Rango / magnitud de ganancia variable | float32, ≥0 |
| 30 | Restablecer, abrir lazo y poner encoder a cero | Ignorado |
| 31 | Preparar deteccion de inicio | Reg. 11: 0=config, 1=ENT1, 2=ENT2, 3=ENT3, 4=Z habilitado; reg. 12 ignorado |
| 32 | Cancelar deteccion de inicio | Ignorado |
| 50 | Mando manual, abre lazo antes de aplicar | int32, −65535 a 65535; se limita además por UMAX |
| 53 | Zona muerta | Valor absoluto de int32 |
| 54 | Error máximo de seguimiento para parar | Valor absoluto de int32; 0 deshabilita |
| 57 | Poner/borrar salidas digitales | Reg. 11: flags 0–3; reg. 12: máscara 0–7 |

Para función 57, flags bit 1 pone a 1 y bit 0 borra. Si ambos están activos, prevalece borrar. La máscara selecciona SAL1/SAL2/SAL3 (GPIO21/22/23) en bits 0/1/2.

Ejemplo de codificación en Python de computadora:

```python
import struct
pos_regs = struct.unpack('>HH', struct.pack('>l', -1000))
kp_regs = struct.unpack('>HH', struct.pack('>f', 0.1))
# Escribir [1, *pos_regs] en offsets 10..12 para mover.
# Escribir [4, *kp_regs] en offsets 10..12 para cambiar KP.
```

Cerrar el lazo alinea la referencia a la medida actual. Enviar primero función 2 y después función 1. Las posiciones deben caber en int32 para publicar por Modbus.

## Lectura de parámetros vigentes

Si el bit 5 del holding register 30 está a 1, leer **33 input registers desde el offset 0 con FC04**. El bloque se genera al recibir la consulta con los valores de trabajo del eje. Puede leerse durante un fallo o con el lazo abierto. El registro 32 de FC04 es una máscara de tipos. Para el parámetro de índice i, el bit i en 1 indica int32 con signo, y en 0 indica float32 IEEE 754. Así se conservan también los umbrales enteros mayores que 2²⁴. El orden es big endian.

| Índice i | Offsets FC04 | Parámetro |
| --- | --- | --- |
| 0 | 0–1 | KP |
| 1 | 2–3 | KI |
| 2 | 4–5 | KD |
| 3 | 6–7 | IL |
| 4 | 8–9 | UMAX |
| 5 | 10–11 | EMAX |
| 6 | 12–13 | HAB |
| 7 | 14–15 | ACEL |
| 8 | 16–17 | VEL |
| 9 | 18–19 | EMIN |
| 10 | 20–21 | VELSEG |
| 11 | 22–23 | RANGO |
| 12 | 24–25 | MAGNITUD |
| 13 | 26–27 | ZONA |
| 14 | 28–29 | ERRORPARAR |
| 15 | 30–31 | UMIN |

UMIN es el límite PWM negativo efectivo, siempre igual a −UMAX y de solo lectura. EMAX satura el error de entrada al PID, EMIN es la tolerancia de trayectoria y ERRORPARAR es el umbral de paro por error de seguimiento. MINPOS y MAXPOS son destinos absolutos permitidos para MUEVE. No limitan DAX ni el seguimiento continuo. Con bit 4 activo en el holding 30, leer los cuatro holding registers 40–43 por FC03 (dos int32, mínimo y máximo). FC16 desde 40 con los cuatro registros actualiza ambos en una operación. Un par inválido devuelve excepción Modbus y conserva los valores anteriores. JSON acepta `{"CMD":"DESTINOS","MINPOS":-1000,"MAXPOS":2000}` y los publica en EDOJ y PARAMETROS. El arranque del ESP32 comienza con el rango int32 completo.

Por JSON serie, enviar `{"CMD":"PARAMETROS"}`. Con HTTP habilitado, usar `GET /parametros` o enviar el mismo comando a `POST /post`.

## JSON por línea

Un objeto JSON por línea (`\n`), consola UART0/USB. Cada orden devuelve una línea JSON; no enviar órdenes a través del REPL interactivo con el programa interrumpido. Hay mensajes de arranque/diagnóstico que el cliente puede reconocer como texto ajeno al JSON.

| CMD | Campos / respuesta |
| --- | --- |
| `MUEVE` | `PAR`: posición int32 |
| `CIERRA`, `ABRE` | Sin campos adicionales |
| `DAX` | `PAR`: mando entero con signo |
| `CAMBIA` | Uno o varios parámetros de la tabla inferior |
| `EDOJ` | Estado con X, XT, XD, U, E, HAB, MODO, VSEG, BI, POSINI, ID, LIMITS, HOME_INPUT y campos Z |
| `HABSEG`, `DESHABSEG` | Habilitar/deshabilitar seguimiento |
| `RESTABLECE` | Abre lazo, reinicia PID, encoder y referencias; no cierra lazo |
| `BUSCAINICIO` | `ENTRADA` opcional: 1=ENT1, 2=ENT2, 3=ENT3, 4=Z habilitado; omitida usa HOME_INPUT_INDEX |
| `CANCELA` | Cancelar deteccion de transicion |
| `RCD` | Reiniciar índice de captura |
| `DAMEDATOS` | `{"DATOS":[posición,error,...]}`: siempre 2000 enteros |
| `MRST` | Detiene el motor y reinicia el microcontrolador |
| `SALIDAS` | `FLAGS` y `BITS`, como función Modbus 57 |

`CAMBIA` acepta `KP`, `KI`, `KD`, `IL`, `UMAX`, `EMAX`, `HAB`, `ACEL`, `VEL`, `EMIN`, `VELSEG`, `RANGO`, `MAGNITUD`, `ZONA` y `ERRORPARAR`. Se valida toda la orden antes de aplicar cambios. No se aceptan NaN, infinito, booleanos ni cadenas como números. HAB admite enteros 0–3. Cambiar KP ya no provoca el cierre implícito del lazo de la versión JSON antigua.

Respuesta normal de órdenes: `{"status":true}`; error: `{"error":"..."}`. `MRST` puede reiniciar antes de enviar respuesta. XT puede contener fracciones en JSON; Modbus lo publica truncado. `ID` es el identificador físico del ESP32, no una constante heredada.

La captura almacena 1000 pares de posición/error sin sobrescribir. A 10 ms cubre unos 10 s, también en lazo abierto. `RCD` rearma la adquisición, pero no borra las muestras antiguas; esperar la ventana necesaria antes de descargar un conjunto nuevo completo. Las descargas producen una copia coherente al momento de pedirla.

Ejemplo de configuración:

```json
{"CMD":"CAMBIA","KP":0.1,"KI":0.001,"KD":0.023,"UMAX":1000}
```

## HTTP opcional

| Método y ruta | Resultado |
| --- | --- |
| `GET /` | Información y rutas |
| `GET /ping` | Pong, memoria libre y tiempo por contador modular |
| `GET /edo` | Estado del eje |
| `GET /datos` | Captura en JSON válido, igual a DAMEDATOS |
| `POST /post` | Ejecutar objeto de comandos; Content-Type application/json |

```sh
curl http://IP_DEL_ESP32/edo
curl -H 'Content-Type: application/json' -d '{"CMD":"ABRE"}' http://IP_DEL_ESP32/post
```

Respuestas JSON con Content-Length y cierre de conexión. Errores 400, 404, 405 o 408 según solicitud. No se admiten cargas chunked ni formularios URL encoded; la variante histórica solo imprimía esos formularios y no los ejecutaba. Cuerpo máximo 2048 bytes configurable, cabeceras totales 2048 bytes, línea HTTP máxima 512 bytes y espera de lectura de 3 s por operación. Hasta dos manejadores activos; conexiones adicionales se cierran. La descarga de datos ya no usa el formato incompleto `[...],` y terminador inválido de OG: adaptar los clientes que lo esperaban. `uptime_ms_modulo` está sujeto al rango modular de `ticks_ms`; no es un reloj de larga duración.

## Estado de indice Z y entrada de inicio

Los registros 20-32 conservan sus direcciones. El bit 11 del registro 30 sigue en cero; Z se consulta por separado:

| Offset | Contenido | Tipo |
| --- | --- | --- |
| 33 | Z: bit 0 habilitado, bit 1 nivel fisico, bit 2 captura valida | uint16 |
| 34-35 | Ultima posicion capturada en flanco Z | int32, palabra alta primero |
| 36 | Fuente de BUSCAINICIO: 1/2/3=ENT, 4=Z | uint16 |
| 37 | Niveles escritos en SAL1, SAL2 y SAL3 por el firmware (bits 0, 1 y 2). Sin realimentación de la carga. | uint16 |

`EDOJ` y GET /edo agregan `Z_ENABLED`, `Z_LEVEL`, `Z_VALID`, `Z_POS` y `HOME_INPUT`. Z_POS=0 sin captura valida; comprobar siempre Z_VALID. Cada pulso actualiza la ultima posicion; RESTABLECE invalida la captura. Habilitar con ENCODER_INDEX_ENABLED y seleccionar flanco con ENCODER_INDEX_ACTIVE_LEVEL en config.py. No hay puesta a cero automatica al recibir Z. La IRQ soft introduce latencia: no equivale a un latch hardware de posicion.


## Ejemplos de inicio y límites

La [guía de inicio y límites](INICIO_Y_LIMITES.md) reúne las configuraciones de uno o dos switches. Las asignaciones y polaridades de límites se cambian en `config.py`, no por comandos `CAMBIA` ni escribiendo su registro de estado.

Para inicio por ENT3, escribir `[31,3,0]` desde offset 10 con función 0x10; para cancelar, `[32,0,0]`. El registro 11 contiene la selección directa, sin empaquetar int32. `HOME_INPUT_INDEX=3` corresponde a esa misma ENT3, pero es la predeterminada utilizada con `[31,0,0]` o JSON sin ENTRADA. Cada orden sin selección vuelve a la configuración, aunque la anterior haya elegido otra entrada.

La búsqueda no mueve, no para ni pone a cero por sí misma. BI=1 espera cualquier transición; BI=2 confirma captura de POSINI. Una entrada ya accionada al armar puede producir captura al liberarse. No interpretar un POSINI antiguo como captura nueva mientras BI no sea 2. CANCELA solo cancela la detección y no detiene un movimiento.

Ejemplo: ENT1 negativo y ENT2 positivo activos bajos, ENT3 general. Al alcanzar ENT2 en sentido positivo, registro 32=522 (`0x020A`): positivo activo, parada positiva y ENT2 activa como límite. El registro 31 mantiene el bit de lazo si estaba cerrado. Para retirarse desde X=1000, enviar comando 1 con destino absoluto 900 (u otro destino seguro menor que X), sin ABRE/CIERRA. Liberar el contacto sin nueva orden no reanuda el destino anterior.

Configuración y comandos de inicio usan 1/2/3 para ENT1/ENT2/ENT3 y 4 para Z. La predeterminada del proyecto es `HOME_INPUT_INDEX=1` (ENT1/GPIO33). El 0 en reg. 11 de la función 31 es solo el atajo para esa predeterminada.


### BUSCAINICIO por índice Z

Habilitar `ENCODER_INDEX_ENABLED=True` y configurar `ENCODER_INDEX_ACTIVE_LEVEL` antes de reiniciar. Escribir **[31,4,0]** en offsets 10–12 (función RTU 0x10) o enviar `{"CMD":"BUSCAINICIO","ENTRADA":4}` por JSON/HTTP. `HOME_INPUT_INDEX=4` permite usar el comando sin selección; con Z deshabilitado se rechaza la opción 4.

El primer flanco configurado después de armar captura POSINI y pone BI=2; reg. 36=4 identifica la fuente. POSINI no cambia en pulsos posteriores hasta rearmar, mientras Z_POS (34–35) sí sigue actualizándose. CANCELA cancela búsqueda, no el diagnóstico Z. No se pone a cero automáticamente el encoder ni se agrega un bit de entrada general al registro 30. La captura es por IRQ soft y requiere validación temporal en la placa. Ver [INICIO_Y_LIMITES.md](INICIO_Y_LIMITES.md).

## Búsqueda con paro local para el banco Flask

La orden Modbus 58 usa las mismas palabras de selección que la 31. Su equivalente JSON es `{"CMD":"BUSCAINICIO_PARO","ENTRADA":1}`. El registro 30 anuncia esta función en el bit 7 y el armado o captura protegidos en el bit 6. Al capturar la primera transición, el controlador registra POSINI, indica BI=2, abre el lazo, corta PWM y bloquea la potencia hasta liberar la captura. CANCELA durante la búsqueda protegida también abre el lazo. La función histórica 31 conserva la captura sin paro. ENT1–ENT3 usan el ciclo de control y Z usa interrupción de software.
