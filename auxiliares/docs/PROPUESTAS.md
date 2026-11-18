# Funciones propuestas para una etapa posterior

Estas funciones siguen pendientes. Los límites direccionales por ENT1–ENT3 ya están implementados y se describen en [LIMITES.md](LIMITES.md).

| Prioridad | Propuesta | Motivo / decisión pendiente |
| --- | --- | --- |
| Alta | Paro físico independiente | Los límites por software ya cortan PWM por sentido. Sigue pendiente definir un circuito independiente para paro de emergencia o corte de potencia, la polaridad y la actuación sobre la etapa |
| Alta | Watchdog y detección de pérdida de ciclos | El PWM hardware puede conservar el último valor si el intérprete se bloquea. Definir latencia máxima y si el corte requiere hardware independiente |
| Alta | Diagnóstico de fallo enclavado | Guardar causa de parada (error de seguimiento, encoder, temporización, comunicación) y requerir restablecimiento explícito según el mecanismo |
| Media | Registro Modbus de resultado de comando | Distinguir orden aceptada, rechazada y terminada; hoy reg. 10=0 solo indica que se atendió |
| Media | Timeout de mando manual / comunicaciones | Evitar DAX sostenido por pérdida del cliente; decidir si seguimiento autónomo debe continuar cuando se desconecta el maestro |
| Media | Límites de posición y velocidad en unidades físicas | Incorporar conversión cuentas↔mm/grados/arcsec y límites específicos del mecanismo |
| Media | Persistencia de parámetros validada | Guardado explícito, versión de formato y copia recuperable; evitar escribir flash en cada ajuste |
| Media | Procedimiento completo de homing | Definir dirección, velocidad, timeout, rebote, segunda aproximación y relación con índice del encoder; actualmente solo se detecta una transición |
| Media | Medición de tiempo de control | Contadores de ciclos omitidos, duración máxima y jitter; con resultados decidir si trasladar el lazo crítico a código nativo |
| Baja | Captura con longitud válida y descarga por bloques | Conservar compatibilidad con los 2000 enteros y añadir metadatos sin grandes copias ni largos bloqueos de consola |
| Baja | Reconexión Wi-Fi y autenticación de API | Necesario si se utiliza fuera de un banco controlado; definir uso local o acceso remoto |
| Baja | Herramienta de escritorio para calibración | Leer estado, ajustar PID, graficar datos y controlar versiones de parámetros |

Antes de agregar funciones de movimiento o protección hace falta confirmar la etapa de potencia, la polaridad de OE, la resolución del encoder y los límites físicos del eje. Las pruebas de banco de la versión actual deben preceder a esa ampliación.
