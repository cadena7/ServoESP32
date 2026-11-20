# Cómo entonar un eje de posición con ServoESP32

Un movimiento tiene tres posiciones de interés. El maestro envía un **destino** en cuentas de encoder. En cada muestra, el generador de trayectoria calcula una **referencia intermedia** (`XT`) según la velocidad y la aceleración permitidas. El encoder mide la **posición real** (`X`). El PID usa el error de seguimiento `XT − X` para calcular el mando firmado `U`, expresado en unidades de PWM.

Por ejemplo, con destino 1000, referencia 250 y posición 245, el error que ve el controlador es **5 cuentas**. Si X sigue de cerca a XT pero ambos tardan en llegar a 1000, revisar VEL y ACEL antes de subir KP. Si XT avanza y X se queda atrás, observar el error y cuánto mando está aplicando el controlador.

## Qué calcula el PID en cada muestra

El firmware comprueba primero el error de seguimiento sin modificar. Después aplica la ganancia variable, la zona muerta y el recorte a ±EMAX. Llamando `e[k]` al error resultante, el cálculo de [control.py](../../control.py) equivale a lo siguiente:

```text
P = KP × e[k]
I = limitar(I_anterior + KI × e[k], −IL, +IL)   cuando la integral está habilitada
I = 0                                          cuando está deshabilitada
D = KD × (e[k] − e[k−1])
U = entero(limitar(P + I + D, −UMAX, +UMAX))
```

El bit 0 de HAB habilita el lazo. El controlador actualiza el bit 1 para habilitar la integral cuando la velocidad de trayectoria es cero y deshabilitarla durante el recorrido. Abrir o cerrar el lazo reinicia el acumulador y la memoria derivativa. La derivada usa la diferencia de errores entre muestras, sin filtro derivativo dedicado. La limitación de la integral mediante IL y la saturación del mando mediante UMAX son dos operaciones independientes.

Las ganancias KI y KD ya incluyen la escala temporal propia del algoritmo discreto. Si se parte de ganancias continuas de un PID paralelo con las mismas unidades de error y mando, la equivalencia por Euler es `KI = Ki_continua × Ts` y `KD = Kd_continua / Ts`, con Ts en segundos. El período nominal de fábrica es 10 ms. Cambiarlo altera tanto el control como las velocidades expresadas por muestra.

## Parámetros y efecto observable

| Panel o protocolo | Nombre en config.py | Qué cambia en el eje |
| --- | --- | --- |
| KP | PID_KP | Mando proporcional al error actual. Aumentarlo da más corrección por cuenta. Un exceso puede producir sobrepaso u oscilación. |
| KI, IL | PID_KI, PID_IL | KI acumula mando ante error sostenido cuando la integral está habilitada. IL limita la magnitud de esa contribución, en unidades de PWM. Ayudan a corregir error residual bajo carga. |
| KD | PID_KD | Responde al cambio de error. Puede amortiguar la llegada. La cuantización del encoder también produce diferencias entre muestras y puede causar variaciones rápidas del PWM. |
| UMAX, UMIN | PID_UMAX | Límite simétrico del mando firmado, de 0 a 65535 en magnitud. UMIN se deriva de −UMAX. El porcentaje de ciclo útil correspondiente al mando es aproximadamente 100 × abs(U) / 65535. U no mide corriente ni par. |
| EMAX | PID_ERROR_MAX | Limita el error que entra al cálculo P/I/D. El lazo puede seguir cerrado aunque el cálculo alcance ese límite. |
| ERRORPARAR (ERRORMAX en el panel) | MAX_FOLLOWING_ERROR | Abre el lazo cuando el valor absoluto del error de seguimiento original supera el umbral en cuentas. Cero deshabilita esa comprobación. |
| ZONA | DEAD_ZONE | Si el valor absoluto del error original es menor que ZONA, el PID recibe error cero. Una integral ya acumulada aún puede sostener mando. Una zona amplia admite mayor error residual. |
| RANGO, MAGNITUD | GAIN_RANGE, GAIN_MAGNITUDE | Modifican el error que recibe el PID cerca del destino. RANGO fija la ventana en cuentas y MAGNITUD escala la corrección adicional. Afectan P, I y D. RANGO = 0 desactiva esta función para caracterizar el PID base. |
| VEL, ACEL | TRAJECTORY_SPEED, TRAJECTORY_ACCEL | Velocidad máxima en cuentas/muestra y aceleración en cuentas/muestra² del generador de trayectoria. A 10 ms, VEL = 4.5 equivale a 450 cuentas/s y ACEL = 0.05 a 500 cuentas/s². |
| EMIN | TRAJECTORY_TOLERANCE | Distancia en cuentas que permite al generador completar la referencia final. La llegada física se verifica aparte con X. La búsqueda de inicio tiene además su propia tolerancia en el maestro. |
| VELSEG | TRACKING_SPEED | Incremento firmado de referencia por muestra al activar seguimiento continuo. Para caracterizar un movimiento de posición, desactivar el seguimiento. |
| MINPOS, MAXPOS | MINPOS, MAXPOS | Extremos permitidos para un destino absoluto de MUEVE. El mando PWM manual y el seguimiento continuo quedan fuera de esa comprobación. |

## Ensayo de escalón reproducible

1. **Preparar el eje.** Registrar la configuración inicial, la carga, el período de muestreo y la resolución del encoder. Elegir dos posiciones dentro del recorrido conocido, con margen para detenerse. Verificar el sentido del mando y del encoder antes de cerrar el lazo. Conservar un límite de PWM adecuado para el mecanismo.
2. **Medir una referencia inicial.** Cerrar el lazo en la posición actual y ordenar un desplazamiento corto. Registrar tiempo, destino, XT, X y U cuando estén disponibles. Repetir el mismo movimiento en ambos sentidos. Mantener constantes amplitud, carga, VEL y ACEL al comparar ganancias.
3. **Ajustar la respuesta proporcional.** Para una primera caracterización, usar KI y KD en cero y desactivar la ganancia variable. Partir de una KP baja apropiada para el eje y aumentarla en incrementos pequeños. Observar el retraso de X respecto de XT y el sobrepaso. Si U permanece en ±UMAX y el error crece, revisar carga, fricción y exigencia de trayectoria antes de seguir elevando ganancias.
4. **Ajustar la llegada.** Si aparece sobrepaso, ensayar una KD pequeña y comparar el asentamiento y la variación de U cerca del destino. Si el eje queda estable con error residual bajo carga, revisar ZONA y añadir KI gradualmente con IL acotado. Repetir el movimiento después de cada cambio. Holgura o fricción pueden dar resultados distintos según el sentido.
5. **Evaluar con un criterio de uso.** Definir una banda de error en cuentas y cuánto tiempo debe permanecer el eje dentro. Registrar el sobrepaso máximo, el tiempo desde la orden hasta que X permanece en esa banda, el error residual y cualquier saturación o apertura del lazo. Repetir con la carga y el recorrido previstos. El panel sondea más despacio que el PID; una gráfica del maestro puede omitir oscilaciones entre lecturas.
6. **Guardar el resultado por eje.** Copiar los valores aceptados a [config.py](../../config.py), cargarlo en el ESP32 y reiniciar. En el firmware nuevo, verificar los parámetros vigentes por FC04 o con el comando JSON `PARAMETROS`. MINPOS y MAXPOS también se leen por FC03 en 40–43. Revisar si el maestro escribe un perfil al arrancar o al restablecer el eje, pues esas escrituras cambian los valores en RAM.

Para implementar la confirmación de llegada y la puesta a cero en la aplicación, consultar la [secuencia de búsqueda de inicio](SECUENCIA_DE_INICIO.md). Los formatos de lectura y escritura están en el [protocolo](PROTOCOLO.md).
