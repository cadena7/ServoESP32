# Revisión del original y cambios

Fecha: 17 de noviembre de 2026. Base: archivos disponibles en `OG/`; no se encontró un reporte técnico dentro de esa carpeta. Las decisiones de compatibilidad se basan en el código proporcionado.

## Inventario y conservación

Se calculó SHA-256 de cada archivo original antes de trabajar; [og-sha256.json](og-sha256.json) permite verificar que el conjunto y sus bytes siguen intactos. No se ejecutaron, formatearon ni importaron módulos de OG.

| Archivo original | Tratamiento en la nueva versión |
| --- | --- |
| `main.py` + `ejexesp.py` | Base del mapa Modbus y del cableado revisión B |
| `ejex.py` | Se recuperaron todos los comandos JSON y la captura; se unificó el control con revisión B |
| `ejexesp1.py` | Duplicado que activa depuración en GPIO13; no se copia porque ese pin controla RS485 |
| `m1.py` | Variante Modbus ID 20 sin control de dirección; se consigue mediante configuración |
| `main1.py` | Se conservan las rutas web útiles, con implementación compatible y JSON corregido |
| `receptor.py` | Ensayo de eco UART/LED, ajeno al servocontrol; no se instala |
| `lib/umodbus/` | Se copian dependencias RTU, conservando avisos; se omite transporte TCP no utilizado |
| `lib/nanoweb.py` | Reemplazado por servidor reducido para rutas del proyecto, sin servir archivos del sistema |
| `.DS_Store` | Metadatos del sistema; no se copian |

La carpeta OG contiene credenciales de red escritas en una variante histórica. Se conserva íntegra según lo solicitado, pero `.gitignore` excluye `/OG/` del repositorio público por defecto. La versión ejecutable no hereda esas credenciales. No usar `git add -f OG` sin revisar qué se va a publicar. El manifiesto contiene hashes, no valores de configuración originales.

## Correcciones

| Hallazgo | Corrección |
| --- | --- |
| Posición de trayectoria convertida a int en cada muestra | Se conserva posición fraccionaria; velocidades menores de una cuenta/muestra avanzan en ambos sentidos |
| Frenado usa un salto fijo de velocidad 0.1 al cruzar cero | Frenado hasta cero sin salto y limitación del último paso; probado también con velocidad 0.01 |
| PID limita IVal pero suma el valor previo sin saturar | La salida usa la integral ya limitada |
| Ganancia variable con rango cero puede dividir entre cero | Rango cero retorna ganancia adicional cero |
| Referencia y trayectoria avanzan en lazo abierto | Se mantiene lectura de sensor/inicio y captura, sin avanzar trayectoria ni seguimiento |
| Parada por error deja U e integral con valores anteriores | Abre lazo, borra estado PID y aplica cero inmediatamente |
| Cerrar lazo conserva integral/derivada antiguas | Reinicia PID y alinea referencia con medida actual |
| Reset limpia encoder pero deja referencias antiguas | Reinicia también posición, trayectoria, offset y detección de inicio |
| Detección de inicio registra medida de la muestra anterior | Lee primero el sensor y después detecta el cambio |
| Buffer mutable declarado en la clase y último par sin usar | Buffer por instancia y uso de los 2000 elementos |
| Salida manual sin límites y dirección activa con mando cero | Saturación en UMAX y 65535; PWM cero antes del cambio de dirección y ambas direcciones bajas al parar |
| Timer local y excepciones sin paro garantizado | Timer retenido; fallo del callback desactiva timer y actuador; limpieza también en Ctrl-C y errores de aplicación; no acepta reactivación tras fallo del callback hasta reiniciar |
| Lecturas RTU con palabras ≥32768 empaquetadas como signed short | Lectura de registros uint16; int32 se reconstruye en el cliente |
| RTU espera activamente una trama incluso sin datos | Recepción incremental con comprobación de silencio entre tramas |
| RTU acepta rango que empieza en registro válido pero termina fuera | Valida rango completo antes de lectura/escritura |
| Tramas con byte-count inconsistente o tamaño inválido | Rechazo con excepción Modbus antes de desempaquetar |
| Comandos aceptan NaN, negativos incompatibles o aceleración cero | Validación compartida y cambios de parámetros completos antes de aplicarlos |
| Comando inválido puede quedar pendiente en reg. 10 | Limpieza en finally, incluido rechazo de aplicación |
| JSON serie usa `is` para comparar cadenas, espera bloqueando y no delimita respuestas | Recepción incremental con límite de tamaño y respuestas por línea |
| Web usa awrite/aclose del API antiguo y envía 200 antes de validar | Streams write/drain/close/wait_closed; estado HTTP después de procesar |
| POST puede leer cuerpo incompleto | readexactly, límite y timeout; Content-Type sin distinguir mayúsculas de nombre de cabecera |
| `/datos` genera texto JSON incompleto y terminador inválido | Devuelve un objeto DATOS con arreglo válido |
| Conexión Wi-Fi espera indefinidamente y condiciona el arranque | Control local iniciado primero; Wi-Fi/HTTP opcional en segundo plano con tiempo máximo; su fallo no detiene el control |
| ID de dispositivo constante | ID físico del ESP32 |

## Diferencias deliberadas que afectan a clientes

- Se agregan límites direccionales opcionales: roles y polaridad por ENT1–ENT3 en `config.py`, interpretados en `limits.py`. El paro pone PWM=0 sin abrir el lazo, limpia el estado PID, cancela trayectoria y seguimiento, y permite retirarse con una nueva orden hacia el sentido permitido. La liberación del contacto no reanuda el destino cancelado.
- Se agrega `LIMITS` a JSON y holding register 32 al mapa Modbus, conservando offsets 20–31 y todos los números de comando. La lectura de estado puede ampliarse de 12 a 13 registros. Ver [LIMITES.md](LIMITES.md).

- Cableado confirmado de PCB: ENT1/ENT2/ENT3 = GPIO33/4/19 y SAL1/SAL2/SAL3 = GPIO21/22/23. GPIO18 se separa como índice opcional del codificador, deshabilitado por defecto. El registro 30 publica solo las tres entradas generales en bits 8–10; el bit 11 ya no refleja GPIO18 y queda en cero.

- Arranque con lazo abierto (`AUTO_CLOSE_LOOP=False`); para reproducir el cierre automático original existe esa opción.
- Cableado único revisión B: dirección A en GPIO26 e inicio en GPIO33. En la variante JSON antigua eran GPIO12 y GPIO4 respectivamente; editar configuración si ese es el hardware utilizado.
- Los parámetros se validan y KP ya no abre/cierra el lazo implícitamente. Una orden inválida se rechaza sin aplicar parcialmente otros campos.
- La salida cero usa ambas direcciones bajas. Confirmar la semántica del puente físico.
- Todas las órdenes JSON reciben respuesta por línea. Estado y datos conservan sus nombres principales; se agregan ABRE y SALIDAS para exponer funciones que ya existían en Modbus.
- `/datos` y `/post` devuelven JSON válido, no el texto defectuoso anterior. La raíz web conserva acceso de diagnóstico, con información de rutas en vez del saludo de ejemplo.
- El control y las comunicaciones se unifican; no se conservan nombres internos como `ejexesp.init_ejex` o `ComJ` como API de importación. Las interfaces externas son las documentadas.

Las propuestas de funciones nuevas están separadas en [PROPUESTAS.md](PROPUESTAS.md); no están implementadas como parte de esta revisión.


## Revisión de configuración de inicio y límites — 18 de noviembre de 2026

Se verificó la versión actual sin modificar OG. Ya estaban implementadas la selección de inicio en ENT1/ENT2/ENT3, la configuración de límites por entrada y nivel activo, el paro direccional con conservación del lazo y la retirada con una nueva orden permitida. No se cambian las asignaciones activas ni se introduce otra función de movimiento.

Se ampliaron comentarios de `config.py` y docstrings del selector de inicio, la detección de transición y la parada/estado de límites. Se explica la diferencia entre índice 0–2 en configuración y entrada 1–3 en comandos; selección por defecto frente a temporal; polaridad física; inicio compartido con límite; y diferencia entre offset 32 y comando 32.

Nueva guía [INICIO_Y_LIMITES.md](INICIO_Y_LIMITES.md), con ejemplos de un límite, dos límites e inicio independiente o compartido; enlaces y aclaraciones en README, instalación, configuración, límites y protocolo. Se corrigió una frase del protocolo que describía el mapa completo solo hasta 32: actualmente llega hasta 36.

Resultado actual: **55 pruebas aprobadas**, incluidas tres combinaciones integradas nuevas y la integridad de OG. La guía [PRUEBAS.md](PRUEBAS.md) consolida la validación vigente; cifras anteriores de este registro son antecedentes de otras revisiones. Pendiente validación física en ESP32.


## Numeración de inicio unificada y aclaración de parada por límite

A partir de esta revisión, `HOME_INPUT_INDEX` usa 1=ENT1, 2=ENT2 y 3=ENT3, igual que ENTRADA en comandos y HOME_INPUT/registro 36. El valor por defecto es 1 (ENT1/GPIO33), conservando el sensor del original. El nombre del campo se mantiene para facilitar localizarlo. Las referencias anteriores de este historial a índices 0–2 describen la versión previa; al reutilizar un config antiguo deben convertirse a 1–3.

Los comandos Modbus/JSON no cambian. `[31,0,0]` conserva el atajo de selección predeterminada. Los roles/polaridades de límites siguen sin habilitarse por defecto.

Se documenta el comportamiento existente de parada: descarta objetivo anterior, alinea referencia y trayectoria con la medida, limpia PID y fuerza PWM=0. Mientras espera una nueva orden, vuelve a alinear cada ciclo, sin par de sostén; conserva el bit de lazo para aceptar retirada sin ABRE/CIERRA. No se modifica esa política de control.

Pruebas agregadas de numeración/configuración y desplazamiento tras activar un límite. Resultado actualizado en PRUEBAS.md.


## Inicio por índice Z (opción 4)

Se agrega selección 4=Z en GPIO18 a HOME_INPUT_INDEX, ENTRADA de JSON/HTTP y reg. 11 del comando Modbus 31. Requiere ENCODER_INDEX_ENABLED=True; se conserva predeterminada ENT1 y no cambian las tres entradas generales, límites ni offsets de estado. El original OG leía GPIO18 en el paquete de entradas, pero construía el eje con ENT1 como sensor de inicio; la selección de Z como inicio es una ampliación explícita.

La captura de inicio Z se resuelve en el callback existente del índice: registra el primer flanco configurado posterior al armado, incluso si el pulso termina antes del tick de control. Z_POS continúa reflejando el último flanco. ENT1–ENT3 mantienen detección por sondeo de cualquier transición. No se hace cero automático ni movimiento de búsqueda. Las menciones anteriores de Z excluido como sensor de inicio describen versiones anteriores.

Documentación actualizada y seis pruebas de regresión nuevas. Resultado: 63 pruebas aprobadas en host, incluida integridad de OG; pendiente validación temporal y eléctrica con encoder/regla real en ESP32.
