# Pruebas y límites de validación

## Resultado actual: 18 de noviembre de 2026

**63 pruebas aprobadas con CPython 3.14**, ejecutadas desde la raíz:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s auxiliares/tests -v
```

Resultado: `Ran 63 tests` / `OK`. Incluye comprobación de integridad completa de `OG/` contra su manifiesto SHA-256, sin modificar el original. En esta copia sí pasa esa comprobación; las advertencias antiguas de otras computadoras sobre archivos ausentes no describen el resultado actual. En un clon público sin OG, esa prueba se omite según el diseño de la suite.

Se ejecutó la suite directamente en macOS, sin adaptador especial del bucle asyncio. Los periféricos y los streams HTTP siguen siendo simulados; no se estableció una conexión HTTP real ni se cargó código en un ESP32. Los mensajes de fallo Wi-Fi/HTTP durante las pruebas son fallos provocados para verificar que no detienen el control local.

## Qué se comprobó

| Área | Verificaciones |
| --- | --- |
| Control | PID, saturación de integral/salida, trayectoria fraccionaria positiva/negativa, frenado, reset, error de seguimiento y captura |
| Inicio configurable | Selección de cada ENT1/ENT2/ENT3, retorno a la predeterminada al omitir ENTRADA, rechazo de números inválidos y registro de la posición de la muestra actual |
| Modbus de inicio | Tramas RTU con selección 1–4; selección predeterminada con 0; estado de entrada elegida en registro 36 |
| Índice Z | Ambos flancos, captura de cuenta, actualización, JSON/Modbus, invalidación por RESTABLECE y separación respecto a ENT1–ENT3 |
| Límites | Cada entrada en ambos sentidos y polaridades; generales deshabilitadas, duplicados, configuración inválida, corte PWM y conservación del lazo |
| Retirada | Rechazo del sentido bloqueado, nueva orden permitida sin ABRE/CIERRA, cancelación de trayectoria/seguimiento, ausencia de reanudación por rebote o liberación |
| Casos simultáneos | Ambos límites activos, mando manual sostenido, eje busy, corte antes de leer encoder, arranque/reset y bloqueo de mando PID hacia el límite |
| Interfaces | JSON, límites de tamaño, errores, CRC RTU, recepción fragmentada, registros fuera del mapa, solicitudes HTTP y cuerpos fragmentados |
| Arranque | Control local con Wi-Fi pendiente, ausente, fallido o deshabilitado; fallos y cierre HTTP; timeout de radio |

Se añadieron tres pruebas integradas que reproducen las recetas de [INICIO_Y_LIMITES.md](INICIO_Y_LIMITES.md):

1. Un límite positivo activo bajo en ENT3: parada y aceptación de retirada.
2. ENT1 negativo y ENT2 positivo activos bajos, con inicio predeterminado en ENT3: otra entrada no genera captura; ENT3 registra POSINI sin borrar el encoder; estados Modbus correctos.
3. ENT2 compartida como inicio y límite positivo: una activación captura posición, corta PWM conservando lazo, publica LIMITS=522 y permite retirada mediante MUEVE.

En la revisión de numeración se añadieron dos pruebas: HOME_INPUT_INDEX y comandos usan la numeración física de ENT1–ENT3, ampliada ahora con opción 4=Z, con rechazo de configuraciones inválidas y ENT1 predeterminada; y la parada por límite alinea referencias también durante desplazamiento posterior por inercia, conservando HAB y PWM=0 hasta una nueva orden permitida. Se actualizó la configuración predeterminada a HOME_INPUT_INDEX=1 y se mantiene físicamente ENT1. La selección de carga se comprueba con `python3 auxiliares/tools/deploy.py --port PRUEBA --dry-run`; debe incluir `limits.py` y omitir OG y auxiliares.

## Pendiente en hardware

No se ejecutó un intérprete MicroPython ni se conectó una placa física en esta revisión. Las pruebas no reproducen la precisión de floats del ESP32, memoria, interrupciones, ruido de entradas, polaridad de optos ni capacidad de frenado. Pasar la suite confirma las condiciones simuladas, no certifica el mecanismo.

| Comprobación | Procedimiento y resultado esperado |
| --- | --- |
| Firmware y placa | Confirmar ESP32 clásico, 4 MB y versión 1.26.0; importar machine.Encoder |
| Arranque | PWM=0 y ambas direcciones=0; HAB=0 con configuración predeterminada |
| Encoder x4 | Girar un número conocido de vueltas y contrastar cuentas/signo con resolución real |
| Entradas/salidas | Accionar cada entrada y función 57; cotejar GPIO y bits sin inversión |
| Inicio | Preparar búsqueda, cambiar entrada, confirmar BI=2 y POSINI; cancelar sin movimiento automático |
| Sentido del control | Con límite de PWM bajo y mecanismo desacoplado, verificar realimentación negativa |
| Trayectoria y PID | Órdenes pequeñas de ambos signos; revisar error, saturación, oscilación y frenado |
| Parada por error | Provocar diferencia controlada por encima del umbral, sin bloquear mecánicamente el motor; verificar PWM=0/HAB=0 |
| Ctrl-C/reset | Confirmar PWM y direcciones al salir, al reiniciar y durante pérdida de alimentación |
| RTU físico | Leer 20–31, mover mediante 0x10 y verificar DE/RE, CRC y ausencia de tramas perdidas |
| Tiempo efectivo | Medir período y jitter del callback bajo carga de Modbus, JSON, web y descarga de muestras |
| Memoria | Repetir descargas y solicitudes con web habilitada; observar gc.mem_free y estabilidad |

El temporizador ejecuta código Python con cálculos y asignaciones. No garantiza un plazo de 10 ms ni continuidad ante saturación del scheduler. UART.flush, impresión de una captura, serialización, Wi-Fi y GC pueden retrasar el callback; evitar interpretar los parámetros como tiempo real certificado. La lectura incremental RTU reduce espera ocupada, pero no resuelve por sí sola todos esos retardos. No se incluye aún watchdog físico ni supervisor independiente del PWM.


Además, repetir inicio y límites con las polaridades reales de la PCB, probar ambos sentidos y la retirada a baja velocidad. Una entrada de inicio general no detiene el motor al capturar; compartirla con un límite sí mantiene la protección direccional. Comprobar la activación con switch ya accionado al arrancar.

El temporizador ejecuta código Python y no garantiza un plazo de 10 ms. UART.flush, impresión de captura, serialización, Wi-Fi y GC pueden retrasar callbacks. Medir latencia de corte y distancia de parada con carga; PWM=0 no garantiza inmovilización mecánica. No hay watchdog físico ni supervisor independiente del PWM.

La IRQ soft del índice Z lee la cuenta al ser atendida; no es un latch hardware sincronizado al flanco. Validar latencia, error de posición y pérdida de pulsos a la frecuencia máxima prevista, con comunicaciones y GC activos.


## Inicio por Z como opción 4

Se añadieron seis pruebas en `auxiliares/tests/test_home_index.py`: captura de pulso entre ticks (ambos flancos), primer inicio frente a último diagnóstico Z, selección predeterminada 4 y retorno a ENT, cancelación/rearme/reset, rechazo de Z deshabilitado sin alterar la búsqueda previa y comando RTU 31 con selección 4 y lectura de BI/POSINI/registro 36. La suite completa pasa con 63 pruebas; la predeterminada de proyecto sigue siendo ENT1 y se conserva la integridad de OG.

No se probaron anchos de pulso ni frecuencia máxima en hardware. La simulación invoca el callback de flanco; no reproduce la cola y latencia de interrupciones soft del ESP32. Validar con la regla real, carga de comunicaciones y GC.
