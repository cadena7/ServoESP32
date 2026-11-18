# Configurar el sensor de inicio y uno o dos fines de carrera

Estas funciones **ya están implementadas**. Se configuran en `config.py`, se copia ese archivo al ESP32 y se reinicia. No hace falta modificar el PID ni añadir módulos. Los límites se asignan al arrancar; no hay un comando para cambiar sus roles o polaridades en caliente. La entrada de inicio sí se puede elegir con cada orden.

## 1. Identificar las entradas

| Entrada de PCB | GPIO | Posición en las tuplas | HOME_INPUT_INDEX | ENTRADA en JSON/Modbus |
| --- | --- | --- | --- | --- |
| ENT1 | 33 | Primera | 1 | 1 |
| ENT2 | 4 | Segunda | 2 | 2 |
| ENT3 | 19 | Tercera | 3 | 3 |
| Índice Z | 18 | Separado de las tuplas de ENT | 4 | 4 |

**Toda selección de inicio usa el número impreso en la PCB: 1, 2 o 3, y la opción 4 identifica Z**, tanto `HOME_INPUT_INDEX` como `ENTRADA` y el estado HOME_INPUT/registro 36. El proyecto viene con `HOME_INPUT_INDEX=1` (ENT1/GPIO33), como OG. La conversión al índice de una lista de Python es interna y no se configura. GPIO18 es el índice Z opcional del encoder: **opción 4 de BUSCAINICIO**, sin añadir una cuarta entrada general ni un cuarto límite. SAL1/SAL2/SAL3 son GPIO21/22/23 y no intervienen en esta selección.

## 2. Elegir dónde detectar el inicio

Por defecto se usa ENT1 con `HOME_INPUT_INDEX = 1`. Para que ENT3 sea la entrada predeterminada, cambia en `config.py`:

```python
HOME_INPUT_INDEX = 3  # ENT3 / GPIO19
```

Eso solo elige el sensor: **no arma la búsqueda al arrancar**. Para armarla envía una orden JSON por línea:

```json
{"CMD":"BUSCAINICIO"}
```

Para elegir otra entrada solo para esa búsqueda, por ejemplo ENT2:

```json
{"CMD":"BUSCAINICIO","ENTRADA":2}
```

Al volver a enviar `BUSCAINICIO` sin `ENTRADA`, vuelve a la predeterminada de `config.py`. No conserva automáticamente la elección de la búsqueda anterior. Puedes rearmar antes o después de encontrar el sensor; se vuelve a tomar como referencia el nivel actual de la entrada.

En Modbus se utiliza la función de escritura múltiple **0x10** para escribir estos tres valores juntos desde el **offset 10**:

| Valores en offsets 10, 11, 12 | Acción |
| --- | --- |
| `[31, 0, 0]` | Armar con la predeterminada de config.py |
| `[31, 1, 0]` | Armar con ENT1 |
| `[31, 2, 0]` | Armar con ENT2 |
| `[31, 3, 0]` | Armar con ENT3 |
| `[31, 4, 0]` | Armar con índice Z (requiere habilitarlo) |
| `[32, 0, 0]` | Cancelar la búsqueda |

El valor de entrada va **directamente en el registro 11**: no se empaqueta como int32 o float32. El registro 12 se ignora para esta función.

### Qué hace BUSCAINICIO en ENT1–ENT3

1. Guarda el nivel físico actual del GPIO seleccionado y pone `BI=1`.
2. Sigue leyendo esa entrada en cada ciclo, incluso con el lazo abierto.
3. Ante su primer cambio de nivel, guarda la cuenta del encoder en `POSINI` y pone `BI=2`.

Detecta **cualquier transición**, ascendente o descendente. Si armas con el switch ya accionado, su liberación también cuenta como transición. `LIMIT_ACTIVE_LEVELS` no modifica este comportamiento. No hay selección de flanco o nivel activo para el sensor de inicio en esta versión.

**No mueve el motor, no lo detiene por encontrar inicio y no pone el encoder a cero.** Si necesitas buscar el sensor mediante movimiento, debes ordenar el movimiento por separado. Si ese mismo switch está configurado como fin de carrera, su protección direccional sí puede detenerlo. Un contacto de inicio usado solo como entrada general no detiene el eje.

Consultar con `{"CMD":"EDOJ"}`:

| JSON | Offset Modbus | Significado |
| --- | --- | --- |
| `HOME_INPUT` | 36 | Fuente seleccionada: 1/2/3=ENT, 4=Z |
| `BI` | 24–25 | 0 inactiva/cancelada, 1 esperando transición, 2 encontrada |
| `POSINI` | 26–27 | Posición int32 capturada, palabra alta primero |

Leer `POSINI` como resultado de la búsqueda actual **solo cuando BI=2**: al rearmar o cancelar puede conservar un valor anterior. `CANCELA` cancela la detección, no el movimiento; para detener un movimiento explícitamente se utiliza `ABRE`. `RESTABLECE` también abre el lazo y borra el encoder: no es necesario para armar o cancelar la búsqueda.

### Inicio mediante el índice Z de una regla o encoder (opción 4)

Se admite Z como fuente de referencia además de ENT1–ENT3. El firmware sigue usando A/B para contar y Z para registrar una marca; confirmar que la interfaz de la regla corresponde a estas señales y adaptar sus niveles eléctricos a 3.3 V. Elegir Z como inicio no cambia cómo se cuentan A/B.

En `config.py`, habilita el índice y selecciona su flanco:

```python
ENCODER_INDEX_ENABLED = True
ENCODER_INDEX_ACTIVE_LEVEL = 1  # Ascendente; usar 0 para descendente
HOME_INPUT_INDEX = 1            # Se conserva ENT1 por defecto
# HOME_INPUT_INDEX = 4          # Si quieres Z como predeterminada, usa 4
```

Copia la configuración y reinicia. Para armar una búsqueda por Z:

```json
{"CMD":"BUSCAINICIO","ENTRADA":4}
```

En Modbus, escribir `[31,4,0]` desde offset 10 mediante función 0x10. Si elegiste `HOME_INPUT_INDEX=4`, también puedes enviar JSON sin ENTRADA o `[31,0,0]`. Elegir 4 sin `ENCODER_INDEX_ENABLED=True` produce un error explícito; no habilita la entrada en caliente ni modifica una búsqueda previa.

- Al armar se espera un **nuevo flanco** del tipo configurado. Una captura Z anterior no satisface la búsqueda nueva.
- La interrupción Z lee la cuenta del encoder y el **primer flanco posterior al armado** guarda `POSINI` y pone `BI=2`. Un pulso que termine entre ciclos de control también puede capturarse por esa IRQ.
- Los pulsos posteriores actualizan `Z_POS` (diagnóstico del último índice), pero no cambian `POSINI` de una búsqueda ya concluida. Para registrar un inicio nuevo, vuelve a armar.
- `CANCELA` deja de buscar inicio, pero la captura de diagnóstico Z sigue habilitada. Al cambiar la búsqueda a una ENT, Z deja de satisfacerla.
- `HOME_INPUT` / reg. 36 muestra **4**. BI y POSINI mantienen los mismos registros 24–27; Z se sigue consultando en 33–35.

No se pone el encoder a cero, no se mueve ni se detiene el motor automáticamente. A diferencia de las ENT, Z utiliza el flanco seleccionado por `ENCODER_INDEX_ACTIVE_LEVEL`, no cualquier cambio de nivel. No añadir Z a `INPUT_PINS`, `LIMIT_INPUT_ROLES` ni `LIMIT_ACTIVE_LEVELS`: esas tuplas conservan tres elementos. El paquete de entradas del registro 30 tampoco cambia; el nivel Z se consulta por separado.

La captura usa una IRQ Python soft: la posición corresponde al momento de atenderla, no a un latch hardware sincronizado al flanco. No garantiza registrar cualquier ancho/frecuencia de pulso bajo carga; medir latencia y precisión en el ESP32 con la regla real. Si hay varias marcas Z a lo largo del recorrido, se registra la primera que llegue después de armar; el firmware no identifica cuál marca física es.

## 3. Asignar uno o dos fines de carrera

Las tuplas siempre siguen el orden **(ENT1, ENT2, ENT3)**:

| Valor en LIMIT_INPUT_ROLES | Función |
| --- | --- |
| `0` | Entrada general, sin protección de recorrido |
| `-1` | Límite negativo: impide mando hacia cuentas decrecientes |
| `1` | Límite positivo: impide mando hacia cuentas crecientes |

Positivo/negativo dependen del signo real del motor y encoder; no equivalen automáticamente a derecha/izquierda. La comprobación final bloquea el **signo del mando PWM**, por lo que debe estar verificado que mando positivo aumenta las cuentas del encoder.

`LIMIT_ACTIVE_LEVELS` indica el nivel físico del GPIO **cuando el switch está accionado**, después de optos o inversores de la PCB: `0` activo bajo, `1` activo alto. Medirlo; el tipo de contacto NO/NC por sí solo no determina la polaridad vista por el ESP32. En las entradas con rol 0, ese campo no tiene efecto.

### Ejemplo A: un fin de carrera en ENT3

Si solo necesitas bloquear el extremo positivo con ENT3 y el GPIO lee 0 al accionarlo:

```python
HOME_INPUT_INDEX = 1             # ENT1 como sensor de inicio predeterminado
LIMIT_INPUT_ROLES = (0, 0, 1)    # ENT3 positivo; ENT1/ENT2 generales
LIMIT_ACTIVE_LEVELS = (1, 1, 0)  # ENT3 activo bajo
```

No hay protección negativa en este ejemplo. Para que ese único switch sea negativo, cambia los roles a `(0, 0, -1)`. Si el switch se ve activo alto en el GPIO, cambia los niveles a `(1, 1, 1)`.

### Ejemplo B: dos fines de carrera y un sensor de inicio independiente

ENT1 en el extremo negativo, ENT2 en el positivo y ENT3 como sensor de inicio. Suponiendo ambos límites activos bajos:

```python
HOME_INPUT_INDEX = 3             # Inicio en ENT3 / GPIO19
LIMIT_INPUT_ROLES = (-1, 1, 0)   # ENT1 negativo, ENT2 positivo, ENT3 general
LIMIT_ACTIVE_LEVELS = (0, 0, 1)  # Límites activos bajos; el tercer valor se ignora
```

Arma la detección de ENT3 con `{"CMD":"BUSCAINICIO"}` o escribe `[31,0,0]` desde offset 10. **Estos niveles son ejemplos; no se aplicaron a tu configuración actual.**

### Ejemplo C: usar el mismo switch como inicio y límite

Con la asignación del ejemplo B, envía `{"CMD":"BUSCAINICIO","ENTRADA":2}` para observar ENT2 como inicio. ENT2 sigue siendo límite positivo: no hay que poner su rol a cero ni se desactiva su protección al seleccionarla como inicio. Se puede registrar `POSINI` y detener el movimiento positivo con la misma activación. También se puede elegir Z mediante `ENTRADA:4`, conservando las protecciones de ENT1–ENT3.

## 4. Qué pasa al alcanzar un límite y cómo salir

Al llegar al límite en el sentido bloqueado:

- PWM pasa a cero y ambas direcciones quedan bajas.
- Si el lazo estaba cerrado, permanece habilitado; no se manda `ABRE` automáticamente.
- Se cancela el destino, se limpia la integral y se detiene el seguimiento. Mientras espera otra orden, el PWM sigue en cero: **no hay par de sostén**.
- Soltar o rebotar el contacto no reanuda el destino cancelado.

### Qué sucede con la referencia y el lazo

Sí: al detectar el límite se descarta el destino anterior y se cambian **la referencia `ref`, la posición de trayectoria y el destino de trayectoria** a la posición actual del encoder. Además se pone a cero la velocidad, se limpia el PID y se cancela seguimiento.

Mientras espera otra orden, el programa mantiene `limit_stop` y **fuerza PWM=0 sin ejecutar el PID normal**. Cada ciclo vuelve a alinear las referencias a la medida actual. Por ejemplo, si el destino era 2000 y se detectó el switch en X=1000, las referencias pasan a 1000. Si por inercia termina en 1003, pasan a 1003 y el PWM sigue en cero: no intenta llegar a 2000 ni volver a 1000.

Por eso «lazo cerrado conservado» significa que permanece el bit de habilitación para poder retirarse mediante una nueva orden. **No significa que sostenga activamente la posición con par.** El estado de espera solo se rearma al aceptar una nueva orden permitida; al retirarse se vuelve a ejecutar el control normal. Esto no pone el encoder a cero ni reemplaza POSINI de la búsqueda de inicio.

Para retirarte con PID, envía una **nueva posición absoluta** al lado permitido de la posición actual, sin abrir/cerrar el lazo. Ejemplo: si se alcanzó el límite positivo en X=1000, puedes enviar:

```json
{"CMD":"MUEVE","PAR":900}
```

900 es solo un ejemplo en cuentas de encoder; elegir una posición válida para tu mecanismo. No significa retroceder 900 cuentas. Si solo se usa Modbus, escribe el comando 1 y la codificación int32 de 900 en offsets 10–12; la tabla de [PROTOCOLO.md](PROTOCOLO.md) explica esa codificación.

Con el límite positivo activo se rechaza un destino mayor que X; con el negativo activo se rechaza uno menor. Si están activos ambos extremos, ambos sentidos quedan bloqueados. `DAX` también respeta límites, pero es mando manual en lazo abierto. Estas reglas no cambian el estado inicial: si arrancaste con lazo abierto, necesitas `CIERRA` antes de solicitar movimiento con PID.

## 5. Verlo por Modbus o JSON

Leer holding register **32** (offset desde cero) o `EDOJ["LIMITS"]`:

| Máscara | Significado |
| --- | --- |
| `0x0001` / `0x0002` | Límite negativo / positivo activo ahora |
| `0x0004` / `0x0008` | Parada negativa / positiva pendiente de una nueva orden |
| `0x0100` / `0x0200` / `0x0400` | ENT1 / ENT2 / ENT3 configurada como límite y activa |

Ejemplo B: llegar al positivo de ENT2 produce `LIMITS=0x020A` (**522 decimal**). Si se suelta el switch sin nueva orden, los bits de activo desaparecen pero queda `0x0008` de parada. Una orden permitida rearma el movimiento; mientras el contacto permanezca activo, el bit de límite actual seguirá encendido.

No confundir el **offset de estado 32** con el **comando 32** escrito en registro 10: este último cancela BUSCAINICIO. El registro 30 siempre muestra niveles físicos de ENT1–ENT3, sin invertir, en bits 8–10. Un límite activo bajo tiene un bit físico de entrada a 0 y un bit de límite activo a 1: es correcto.

## 6. Aplicar y comprobar

1. Con el motor sin potencia, medir cada entrada accionada y libre, editar `config.py` y copiarlo a la placa; reiniciar.
2. Consultar registros 30, 32 y 36 o `EDOJ`. Confirmar entrada, rol y polaridad antes de permitir movimiento.
3. Armar BUSCAINICIO en cada entrada prevista y comprobar BI/POSINI con cambios manuales del sensor.
4. Con velocidad y PWM conservadores, comprobar parada y retirada, ambos sentidos y switch ya accionado al arrancar. No forzar un impacto físico para probarlo.

Las verificaciones automatizadas son con periféricos simulados; falta validar el hardware real. El corte es por software, nominalmente revisado cada 10 ms y al aplicar PWM; la latencia y la distancia de frenado dependen del intérprete, la electrónica y la inercia. Ver [LIMITES.md](LIMITES.md) y [PRUEBAS.md](PRUEBAS.md).


## Migración desde la numeración anterior

Si reutilizas un `config.py` previo a esta unificación, cambia los antiguos valores 0/1/2 de `HOME_INPUT_INDEX` por 1/2/3 respectivamente. El nombre de la variable se conserva, pero ahora significa número de entrada física. No cambian el cableado, el orden de las tuplas de límites, los números de bits ni los comandos JSON/Modbus. El 0 de `[31,0,0]` sigue significando «usar la predeterminada»; no es ENT0.
