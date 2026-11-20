"""Editar aquí el cableado y los valores iniciales. No se guardan cambios remotos."""
CONTROL_PERIOD_MS = 10
PWM_FREQ = 10000
ENCODER_A = 16
ENCODER_B = 17
ENCODER_PHASES = 4
ENCODER_FILTER_NS = 0
ENCODER_INDEX_PIN = 18  # Índice Z: opción 4 de inicio; no es entrada general ni límite.
ENCODER_INDEX_ENABLED = False  # Habilitar solo si se conecta/utiliza el indice.
ENCODER_INDEX_ACTIVE_LEVEL = 1  # Flanco Z: 1=ascendente, 0=descendente.
DIR_A = 26  # Revisión B; revisión 0 usaba GPIO12.
DIR_B = 14
PWM_PIN = 27
OE_PIN = 25
OE_LEVEL = 0  # Nivel original; confirmar polaridad en la electrónica externa.
INPUT_PINS = (33, 4, 19)  # PCB: ENT1=GPIO33, ENT2=GPIO04, ENT3=GPIO19; uso general.
INPUT_PULL = None  # Usar resistencias externas; lecturas físicas sin invertir.
OUTPUT_PINS = (21, 22, 23)  # PCB: SAL1=GPIO21, SAL2=GPIO22, SAL3=GPIO23.
# --- Sensor de inicio y límites: ver auxiliares/docs/INICIO_Y_LIMITES.md ---
# Las tres opciones son independientes: elegir inicio NO activa un límite.
# Predeterminada de BUSCAINICIO: número físico (1=ENT1, 2=ENT2, 3=ENT3, 4=Z).
# Ejemplo: HOME_INPUT_INDEX = 3 selecciona ENT3/GPIO19.
# El comando JSON usa exactamente la misma numeración 1..4:
# {"CMD":"BUSCAINICIO","ENTRADA":3}; Modbus: [31, 3, 0] desde offset 10.
# Sin ENTRADA (o Modbus [31,0,0]) se vuelve a esta predeterminada.
# ENT1-3: cualquier transición. Opción 4/Z: flanco ENCODER_INDEX_ACTIVE_LEVEL.
# Para usar 4: ENCODER_INDEX_ENABLED=True. No mueve ni pone encoder a cero.
# Ejemplo Z predeterminado: habilitar índice y poner HOME_INPUT_INDEX=4.
HOME_INPUT_INDEX = 1  # ENT1 / GPIO33, como en el original OG.

# Rol por entrada, SIEMPRE en orden (ENT1, ENT2, ENT3):
#  0 = general, sin protección; -1 = bloquea movimiento negativo;
# +1 = bloquea movimiento positivo. Izquierda/derecha depende del montaje.
# Sin límites:                 ( 0,  0,  0)
# Solo ENT3 como positivo:     ( 0,  0,  1)
# ENT1 negativo, ENT2 positivo:(-1,  1,  0) y ENT3 disponible para inicio.
# Se dejan deshabilitados: asignar roles solo tras comprobar el cableado real.
LIMIT_INPUT_ROLES = (0, 0, 0)

# Nivel FÍSICO leído por cada GPIO cuando su límite está ACCIONADO.
# Orden (ENT1, ENT2, ENT3): 0=activo bajo, 1=activo alto.
# Ejemplo: dos límites activos bajos en ENT1/ENT2 -> (0, 0, 1).
# En una entrada con rol 0 este nivel se ignora; no configura BUSCAINICIO.
# Medir DESPUÉS de optos/inversores de la PCB: NO/NC no basta para deducirlo.
LIMIT_ACTIVE_LEVELS = (1, 1, 1)
# Al alcanzar un límite: PWM=0, se cancela destino/seguimiento y se conserva HAB.
# Para retirarse: nueva orden MUEVE hacia el otro lado, sin ABRE/CIERRA.
# Soltar el switch no reanuda el destino cancelado. Estado: Modbus 32 / LIMITS.
MODBUS_ENABLED = True
MODBUS_ADDRESS = 23  # Aquí va la dirección Modbus del eje. Editar en cada microcontrolador.
MODBUS_UART = 1
MODBUS_TX = 32
MODBUS_RX = 35
MODBUS_BAUD = 9600
MODBUS_CTRL = 13  # DE y /RE de transceptor RS485; None para UART sin dirección.
SERIAL_JSON_ENABLED = True
WEB_ENABLED = False  # Wi-Fi/HTTP opcional en segundo plano; no condiciona el control.
WEB_PORT = 80
WIFI_SSID = ''
WIFI_PASSWORD = ''  # Preferible definir ambas en secrets.py (excluido de Git).
WIFI_TIMEOUT_MS = 15000  # Solo limita el intento web; el control ya esta iniciado.
MAX_REQUEST_BYTES = 2048
# Valores de arranque por eje. Los comentarios indican el nombre en Flask.
AUTO_CLOSE_LOOP = False         # Flask: HAB (el bit 0 indica lazo cerrado); aquí se elige el estado de arranque.
PID_KP = 0.1                    # Flask: KP
PID_KI = 0.001                  # Flask: KI
PID_KD = 0.023                  # Flask: KD
PID_IL = 1000.0                 # Flask: IL
PID_UMAX = 50000                # Flask: UMAX (UMIN = −UMAX)
PID_ERROR_MAX = 4000            # Flask: EMAX (saturación del error PID)
MAX_FOLLOWING_ERROR = 1000      # Flask: ERRORMAX (clave ERRORPARAR); 0 deshabilita el paro por error.
DEAD_ZONE = 2                   # Flask: Zona muerta (clave ZONA)
TRAJECTORY_SPEED = 4.5          # Flask: VEL, cuentas/muestra
TRAJECTORY_ACCEL = 0.05         # Flask: ACEL, cuentas/muestra²
TRAJECTORY_TOLERANCE = 10       # Flask: EMIN, tolerancia interna de trayectoria
GAIN_RANGE = 500                # Flask: RANGO
GAIN_MAGNITUDE = 1.0            # Flask: MAGNITUD
TRACKING_SPEED = 0.0            # Flask: VELSEG
MINPOS = -2147483648            # Flask: MINPOS, destino absoluto mínimo en cuentas
MAXPOS = 2147483647             # Flask: MAXPOS, destino absoluto máximo en cuentas
