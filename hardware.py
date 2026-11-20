"""Adaptador para ESP32 clásico / WROOM con Encoder PCNT de MicroPython 1.26."""
from machine import Pin, PWM, Encoder, Timer, unique_id
from binascii import hexlify
import config as c
from control import Eje
from limits import TravelLimits, blocked_direction


class Hardware:
    def __init__(self):
        self.timer = None
        self.fault = None
        self.pwm = None
        self.a = Pin(c.DIR_A, Pin.OUT, value=0)
        self.b = Pin(c.DIR_B, Pin.OUT, value=0)
        self.oe = Pin(c.OE_PIN, Pin.OUT, value=c.OE_LEVEL)
        self.outputs = [Pin(p, Pin.OUT, value=0) for p in c.OUTPUT_PINS]
        self.output_levels = 0  # Niveles escritos en SAL1..3, compartidos por todos los protocolos.
        self.inputs = [Pin(p, Pin.IN, c.INPUT_PULL) for p in c.INPUT_PINS]
        # Z del codificador separado de ENT1-ENT3; sin uso de GPIO18 por defecto.
        # Captura Z separada; no pone a cero el contador ni mueve el motor.
        self.index_position = None
        self.encoder_index = (Pin(c.ENCODER_INDEX_PIN, Pin.IN, c.INPUT_PULL)
                              if c.ENCODER_INDEX_ENABLED else None)
        try:
            self.limits = TravelLimits(self.inputs, c.LIMIT_INPUT_ROLES,
                                       c.LIMIT_ACTIVE_LEVELS)
            self.pwm = PWM(Pin(c.PWM_PIN), freq=c.PWM_FREQ, duty_u16=0)
            self.encoder = Encoder(0, phase_a=Pin(c.ENCODER_A, Pin.IN),
                                   phase_b=Pin(c.ENCODER_B, Pin.IN),
                                   phases=c.ENCODER_PHASES, filter_ns=c.ENCODER_FILTER_NS)
            from commands import Commands, number
            home_input = number(c.HOME_INPUT_INDEX, 1, 4, True)
            number(c.ENCODER_INDEX_ACTIVE_LEVEL, 0, 1, True)
            self.eje = Eje(self.inputs[0], self.limits)
            self.select_home_input(home_input)
            if self.encoder_index is not None:
                trigger = (Pin.IRQ_RISING if c.ENCODER_INDEX_ACTIVE_LEVEL
                           else Pin.IRQ_FALLING)
                self.encoder_index.irq(handler=self._capture_index, trigger=trigger)
            e = self.eje
            e.device_id = hexlify(unique_id()).decode().upper()
            e.fn_lee_sensor = self.encoder.value
            e.fn_limpia_encoder = self.clear_encoder
            e.fn_actuador = self.drive
            e.abre_lazo()
            number(c.CONTROL_PERIOD_MS, 1, 1000, True)
            number(c.PWM_FREQ, 1, 40000000, True)
            number(c.MODBUS_ADDRESS, 1, 247, True)
            commands = Commands(e, self)
            # Configuraciones anteriores conservan el recorrido original.
            low, high = e.destinations
            commands.execute({'CMD': 'DESTINOS', 'MINPOS': getattr(c, 'MINPOS', low),
                              'MAXPOS': getattr(c, 'MAXPOS', high)})
            commands.execute({
                'CMD': 'CAMBIA', 'KP': c.PID_KP, 'KI': c.PID_KI, 'KD': c.PID_KD,
                'IL': c.PID_IL, 'UMAX': c.PID_UMAX, 'EMAX': c.PID_ERROR_MAX,
                'ERRORPARAR': c.MAX_FOLLOWING_ERROR, 'ZONA': c.DEAD_ZONE,
                'RANGO': c.GAIN_RANGE, 'MAGNITUD': c.GAIN_MAGNITUDE,
                'VELSEG': c.TRACKING_SPEED, 'VEL': c.TRAJECTORY_SPEED,
                'ACEL': c.TRAJECTORY_ACCEL, 'EMIN': c.TRAJECTORY_TOLERANCE})
        except BaseException:
            self.stop()
            raise

    def clear_encoder(self):
        self.encoder.value(0)
        self.index_position = None

    def _capture_index(self, pin):
        # IRQ soft: leer PCNT directamente, no la muestra anterior del control.
        position = self.encoder.value()
        self.index_position = position
        if self.home_input == 4:
            # Capturar solo el primer flanco desde BUSCAINICIO; Z_POS continúa
            # actualizándose en los pulsos posteriores. No poner encoder a cero.
            self.eje.pinInicio.captura_inicio(position)

    def index_state(self):
        position = self.index_position
        return {'Z_ENABLED': self.encoder_index is not None,
                'Z_LEVEL': self.encoder_index.value() if self.encoder_index is not None else 0,
                'Z_VALID': position is not None,
                'Z_POS': position if position is not None else 0}

    def select_home_input(self, entry=None):
        """Elegir inicio: 1..3=ENT1..ENT3; 4=índice Z del encoder (GPIO18).

        None vuelve a HOME_INPUT_INDEX. Z requiere ENCODER_INDEX_ENABLED=True;
        si está deshabilitado se rechaza sin cambiar una búsqueda anterior.
        Seleccionar cancela la detección anterior; Commands la arma enseguida.
        Las entradas generales y sus límites no cambian al elegir Z.
        """
        from commands import number
        entry = number(c.HOME_INPUT_INDEX if entry is None else entry, 1, 4, True)
        if entry == 4 and self.encoder_index is None:
            raise ValueError('Inicio por Z requiere ENCODER_INDEX_ENABLED=True')
        pin = self.encoder_index if entry == 4 else self.inputs[entry - 1]
        self.eje.pinInicio.concluye_busca_inicio()
        self.eje.pinInicio.pin = pin
        self.eje.pinInicio.por_irq = entry == 4
        self.home_input = entry

    def drive(self, value):
        value = max(-65535, min(65535, int(value)))
        # Ultima barrera tambien para mando manual y cambios entre muestras.
        if value and self.eje.inicio_bloqueado():
            value = 0
        blocked = blocked_direction(value, self.limits.sample())
        if blocked:
            self.eje.parada_limite(blocked)
            return 0
        # Quitar PWM antes de cambiar dirección, incluido el paro.
        self.pwm.duty_u16(0)
        self.a.value(1 if value < 0 else 0)
        self.b.value(1 if value > 0 else 0)
        self.pwm.duty_u16(abs(value))
        # Un flanco Z puede interrumpir una escritura de PWM ya en curso.
        if value and self.eje.inicio_bloqueado():
            self.pwm.duty_u16(0)
            self.a.value(0)
            self.b.value(0)
            return 0
        return value

    def read_inputs(self):
        # Bits 0, 1, 2: ENT1, ENT2, ENT3. El indice Z no forma parte del paquete.
        return sum(pin.value() << i for i, pin in enumerate(self.inputs))

    def output_bits(self, flags, bits):
        for i, pin in enumerate(self.outputs):
            if bits & (1 << i):
                if flags & 2:
                    pin.value(1)
                    self.output_levels |= 1 << i
                if flags & 1:
                    pin.value(0)  # El borrado tiene prioridad, igual que OG.
                    self.output_levels &= ~(1 << i)

    def _tick(self, timer):
        try:
            self.eje.ejec_control()
        except Exception as exc:
            self.fault = exc
            self.stop()

    def start(self):
        if c.AUTO_CLOSE_LOOP:
            self.eje.cierra_lazo()
        self.timer = Timer(0)
        self.timer.init(period=c.CONTROL_PERIOD_MS, mode=Timer.PERIODIC, callback=self._tick)

    def stop(self):
        if self.encoder_index is not None:
            self.encoder_index.irq(handler=None)
        if self.timer is not None:
            self.timer.deinit()
        if self.pwm is not None:
            self.pwm.duty_u16(0)
        self.a.value(0)
        self.b.value(0)
        if hasattr(self, 'eje'):
            self.eje.pid1.Hab = 0
            self.eje.pid1.restablece()
