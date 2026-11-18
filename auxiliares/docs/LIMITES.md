# Límites de recorrido por ENT1–ENT3

Cada entrada general de la PCB puede conservar su uso general o actuar como límite de un sentido. La asignación se edita en `config.py` y se aplica al reiniciar. GPIO18, índice del codificador, no participa.

| Entrada | GPIO | Campo de las tuplas |
| --- | --- | --- |
| ENT1 | 33 | Primero |
| ENT2 | 4 | Segundo |
| ENT3 | 19 | Tercero |

Para recetas completas de **un límite, dos límites e inicio independiente o compartido**, consultar [INICIO_Y_LIMITES.md](INICIO_Y_LIMITES.md).

## Configuración

Los valores predeterminados no activan límites:

```python
LIMIT_INPUT_ROLES = (0, 0, 0)
LIMIT_ACTIVE_LEVELS = (1, 1, 1)
```

En `LIMIT_INPUT_ROLES`, `0` conserva una entrada general, `-1` bloquea el sentido negativo y `1` bloquea el positivo. En `LIMIT_ACTIVE_LEVELS`, `0` significa que el límite está accionado cuando el GPIO lee bajo y `1` cuando lee alto. Se valida que haya exactamente tres valores y que sean válidos antes de iniciar el control.

Ejemplo: ENT1 como límite negativo, ENT2 como positivo y ENT3 general, con ambos switches activos a nivel bajo:

```python
LIMIT_INPUT_ROLES = (-1, 1, 0)
LIMIT_ACTIVE_LEVELS = (0, 0, 1)
```

Esto es un ejemplo de asignación: medir los niveles reales de la PCB antes de copiarlo. Los niveles se refieren al GPIO, después de cualquier inversión de la electrónica de entrada. El tipo de contacto NO/NC no determina por sí solo este valor. Las entradas requieren polarización definida; `INPUT_PULL=None` conserva el uso de resistencias externas. Una desconexión de cable solo se detectará como límite si el circuito y su polaridad producen un nivel activo al desconectarse.

Positivo significa PWM con signo positivo y movimiento que aumenta las cuentas del encoder; negativo, el contrario. Izquierda/derecha dependen del montaje. Confirmar antes de conectar los switches como protección. Se pueden asignar varias entradas al mismo sentido: basta una activa para bloquearlo.

## Comportamiento del control

| Situación | Comportamiento |
| --- | --- |
| Se alcanza un límite avanzando hacia él | PWM=0, ambas direcciones bajas y lazo cerrado conservado |
| Se ordena avanzar hacia un límite activo | Orden rechazada; ese sentido sigue bloqueado |
| Se ordena retirarse del límite activo | Movimiento permitido, sin enviar ABRE/CIERRA |
| Ambos sentidos tienen un límite activo | PWM=0; ambos sentidos bloqueados |
| El contacto rebota o se libera después de una parada | El destino cancelado no se reanuda; hace falta una nueva orden permitida |

La parada cancela el destino anterior, alinea referencia y trayectoria con la posición medida, deja velocidad de trayectoria en cero y limpia integral/derivada. El modo de seguimiento se deshabilita, conservando su velocidad configurada. El temporizador y `HAB` permanecen habilitados como estaban; no hay que volver a cerrar el lazo. Mientras espera una nueva orden, el eje está habilitado pero sin par de sostén: PWM permanece en cero.

Durante la parada, `ref`, `tr.Posicion` y `tr.PosicionDeseada` pasan a la posición medida por el encoder; el objetivo anterior se descarta. Esta alineación se repite en cada ciclo mientras se espera una orden: si el motor se desplaza por inercia o por una fuerza externa, las referencias siguen la medida y el PWM permanece en cero. El PID no intenta recuperar la posición del switch ni el destino anterior. Mantener HAB habilitado permite retirarse con una nueva orden sin reabrir/cerrar el lazo; no significa mantener control de posición activo durante la espera.

La retirada en posición se solicita con `MUEVE` a un destino del lado permitido de la posición actual. Tras la retirada también se puede iniciar `HABSEG` con velocidad hacia el lado permitido. Para reanudar el seguimiento cancelado hace falta solicitarlo explícitamente; el contacto no lo reactiva por sí solo.

La protección también corta un mando manual sostenido cuando se acciona el límite. `DAX` conserva su significado original de mando en lazo abierto; usarlo para retirarse no equivale a un movimiento con PID. En todos los modos, antes de aplicar PWM se verifica también su signo: integral o derivada no pueden producir un mando hacia un límite activo. `CIERRA`, `RESTABLECE` y el cambio de parámetros no anulan los contactos activos.

La búsqueda `BUSCAINICIO` puede observar cualquiera de ENT1–ENT3: por defecto usa `HOME_INPUT_INDEX` (1/2/3, por defecto 1=ENT1), o se selecciona por orden con `ENTRADA` (1/2/3). Por ejemplo, `{"CMD":"BUSCAINICIO","ENTRADA":2}` vigila ENT2. Compartir entrada con un límite no desactiva su protección ni realiza homing automático. La polaridad de los límites no elige el flanco de búsqueda: esta registra cualquier transición.

## Estado por Modbus y JSON

El nuevo holding register **32** (offset desde cero) contiene el mismo entero que `EDOJ["LIMITS"]` y la respuesta HTTP `/edo`. Los offsets 20–31 conservan su significado. Leer 20–32 requiere 13 registros; leer 32 solo requiere uno. El número de comando 32 en el registro 10 sigue siendo CANCELA de búsqueda de inicio; no debe confundirse con el offset de estado.

| Bit | Máscara | Significado cuando vale 1 |
| --- | --- | --- |
| 0 | `0x0001` | Límite negativo activo |
| 1 | `0x0002` | Límite positivo activo |
| 2 | `0x0004` | Parada en sentido negativo; esperando una orden nueva |
| 3 | `0x0008` | Parada en sentido positivo; esperando una orden nueva |
| 8 | `0x0100` | ENT1 configurada como límite y activa |
| 9 | `0x0200` | ENT2 configurada como límite y activa |
| 10 | `0x0400` | ENT3 configurada como límite y activa |

Los bits 2–3 conservan la parada aunque el contacto se libere y se limpian al aceptar una nueva orden de movimiento permitida. No son un historial persistente en flash. Los bits 0–1 y 8–10 muestran los niveles activos actuales; las entradas configuradas como generales no activan esos bits. Por ejemplo, `0x020A` significa límite positivo en ENT2 y parada positiva pendiente de una orden nueva. El registro 30 mantiene las lecturas físicas sin invertir de ENT1–ENT3, con independencia de su configuración como límites.

No se agrega un nuevo comando de movimiento: Modbus usa los comandos existentes de posición, seguimiento y mando manual. Una orden hacia el sentido bloqueado se rechaza por la aplicación; como en el protocolo anterior, el acuse de escritura RTU y registro 10=0 no certifican aceptación. Consultar LIMITS, HAB, X y XT.

## Validación en banco

Primero comprobar sin potencia que cada switch activa el bit y sentido previstos; después, con movimiento lento y recorrido disponible, probar aproximación, parada, retirada sin abrir lazo, rebote, ambos límites y arranque con switch ya accionado. Comprobar también el corte durante DAX y la cancelación de seguimiento.

Es un paro por software: se comprueba en el ciclo nominal de 10 ms y al aplicar PWM. Los retardos del intérprete pueden aumentar la respuesta; no hay garantía de corte en 10 ms. PWM=0 elimina el mando, pero la distancia de parada depende de la inercia, el puente y el mecanismo. No sustituye un corte físico independiente o un paro de emergencia. No se utiliza un retardo de antirrebote que posponga la detección del nivel activo; el destino cancelado no se restaura al liberar el contacto.

La búsqueda de inicio también admite la opción **4=índice Z (GPIO18)** cuando está habilitado. Esta opción no agrega un límite ni modifica roles de ENT1–ENT3. Por ejemplo, dos límites en ENT1/ENT2 pueden coexistir con inicio por Z. Ver [INICIO_Y_LIMITES.md](INICIO_Y_LIMITES.md).
