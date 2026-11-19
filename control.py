"""Núcleo de control independiente del hardware; unidades por muestra (10 ms)."""
import array
from limits import blocked_direction

def mi_abs(val):
    if val < 0 :
        val = -val
    return val

def signo(val):
    if val >= 0 :
        return 1.0
    return -1.0

def fn_saturacion(val, sat):
    return min( sat,max(val,-sat))


class PidControl:
    def __init__(self):
        self.kp, self.ki, self.kd = 0.001, 0.0, 0.0
        self.IVal, self.il = 0.0, 1000.0
        self.ErrMax, self.ErrAnt, self.UMax = 4000, 0, 4000
        self.Hab, self.U = 1, 0


    def ejec(self, err):
        errSat = fn_saturacion( err, self.ErrMax)
        u_p = self.kp*errSat

        if self.Hab & 2 != 0 :
            u_i = self.IVal + self.ki*errSat
            self.IVal = fn_saturacion(u_i, self.il)
        else:
            self.IVal = 0.0

        u_d = self.kd*( errSat - self.ErrAnt )
        self.ErrAnt = errSat
        u_p = u_p + u_d + self.IVal
        self.U = int(fn_saturacion(u_p, self.UMax))
        return self.U

    def restablece(self):
        self.IVal = 0.0
        self.ErrAnt = 0
        self.U = 0


class Tray:
    def __init__(self):
        self.config_trayectoria(1.0, 0.05, 10)

    def config_trayectoria(self,vel,acel,errorMinimo):
        self.VelDeseada = vel
        self.AcelDeseada = acel
        self.Posicion = 0
        self.PosicionDeseada = 0
        self.VelActual = 0
        self.ErrorMinimo = errorMinimo


    def trapecio(self):
        vel = self.VelActual
        Error =  self.PosicionDeseada - self.Posicion

        if mi_abs(Error) <= self.ErrorMinimo or (Error * vel > 0 and mi_abs(Error) <= mi_abs(vel)) :
            self.VelActual = 0
            self.Posicion = self.PosicionDeseada
            return

        stopping_distance = vel * vel / (2 * self.AcelDeseada)
        if Error * vel > 0 and stopping_distance >= mi_abs(Error):
            self.VelActual = signo(vel) * max(0, mi_abs(vel) - self.AcelDeseada)
        else:
            self.VelActual = fn_saturacion(
                vel + signo(Error) * self.AcelDeseada, self.VelDeseada)

        # Una aceleración grande no debe causar sobrepaso al dar el último paso.
        if Error * self.VelActual > 0 and mi_abs(self.VelActual) >= mi_abs(Error):
            self.Posicion = self.PosicionDeseada
            self.VelActual = 0
        else:
            self.Posicion += self.VelActual


class CGAIN:
    def __init__(self):
        self.rango, self.magnitud = 0.0, 0.01

    def calcula(self, err):
        val = err
        if err < 0:
            val = -err
        sal = 0.0
        rango = self.rango
        magnitud = self.magnitud
        if rango > 0 and val <= rango :
            val = 5 * ( 1.0 - val/rango ) - 3.0
            x = 1.0 + val / 256.0
            x *= x; x *= x; x*= x; x *= x
            x *= x; x *= x; x*= x; x *= x
            if x > 7.0 :
                x = 7.33
            sal = (x * magnitud) / 7.33
        return sal


PREPARA_BUSCA_INICIO = 1
HALLO_INICIO = 2

class PinInicio:
    def __init__(self, pin, fn_lee_cuenta ):
        self.pin = pin
        self.edo = 0
        self.cuenta_inicio = 0
        self.val_inicial = 0
        self.paro_al_capturar = False
        self.fn_paro = None
        self.por_irq = False  # Opción 4/Z: captura por flanco, no por sondeo.
        self.fn_lee_cuenta = fn_lee_cuenta

    def concluye_busca_inicio(self):
        self.edo = 0
        self.paro_al_capturar = False

    def prepara_busca_inicio(self, parar=False):
        """Armar la siguiente transición ENT o el próximo flanco IRQ de Z.

        ENT1–3 detectan cualquier cambio por sondeo; Z usa el flanco configurado
        del encoder y registra desde Hardware._capture_index, incluso si el
        pulso termina antes del próximo ciclo de control. No mueve ni borra
        el encoder. cuenta_inicio solo es válida para esta búsqueda con edo=2.
        """
        self.paro_al_capturar = parar
        self.val_inicial = self.pin.value()
        self.edo = PREPARA_BUSCA_INICIO

    def captura_inicio(self, position):
        if self.edo == PREPARA_BUSCA_INICIO:
            self.cuenta_inicio = position
            self.edo = HALLO_INICIO
            if self.paro_al_capturar:
                self.fn_paro()

    def checa_cambio_estado(self):
        if self.por_irq or self.edo != PREPARA_BUSCA_INICIO:
            return
        if self.pin.value() != self.val_inicial:
            self.captura_inicio(self.fn_lee_cuenta())



MODO_POS = 0
MODO_VEL = 1

class Eje:
    def __init__(self, pinInic, limits=None):
        self.destinations = (-2147483648, 2147483647)
        self.limits = limits
        self.limit_stop = 0  # Direccion detenida; espera una nueva orden permitida.
        self.ref = self.pos = self.modo = self.cuentaDatos = 0
        self.velSeguimiento = self.ofset = 0.0
        self.errorMaxParar = 1000
        self.zonaMuerta = 2
        self.busy = False
        self.device_id = ""
        self.muestras = array.array('i', (0 for _ in range(2000)))
        self.cg = CGAIN()
        self.cg.rango = 500
        self.cg.magnitud = 1.0
        self.tr = Tray()
        self.tr.config_trayectoria( 4.5,0.05,10.0)
        self.pid1 = PidControl()
        self.fn_lee_sensor = None
        self.fn_actuador = None
        self.fn_limpia_encoder = None
        self.pinInicio = PinInicio(pinInic, self.eje_lee_pos )
        self.pinInicio.fn_paro = self.para_inicio

    def cambia_zona_muerta(self, val):
        self.zonaMuerta = val

    def cambia_error_max_parar(self, val):
        self.errorMaxParar = val

    def inicio_bloqueado(self):
        return self.pinInicio.paro_al_capturar and self.pinInicio.edo == HALLO_INICIO

    def para_inicio(self):
        self.abre_lazo()
        self.quita_modo_vel()
        self._alinea_parada_limite()

    def inicia_busqueda_inicio(self, parar=False):
        self.pinInicio.prepara_busca_inicio(parar)

    def cancela_busqueda_inicio(self):
        self.pinInicio.concluye_busca_inicio()

    def checa_busqueda_inicio(self):
        self.pinInicio.checa_cambio_estado()

    def lee_pos_inicio(self):
        ### regresa la posicion donde encontro el cambio
        ## de estado del pin de inicio
        return self.pinInicio.cuenta_inicio

    def lee_estado_busqueda_inicio(self):
        return self.pinInicio.edo


    def eje_lee_pos(self):
        return self.pos

    def mueve(self, pos):
        if not self.destinations[0] <= pos <= self.destinations[1]:
            raise ValueError("Destino fuera del recorrido configurado")
        self.checa_limites()
        mask = self.limits.sample() if self.limits else 0
        if blocked_direction(pos - self.lee_sensor(), mask):
            raise ValueError('Destino hacia un limite activo')
        self.limit_stop = 0
        self.ref = pos
        self.ofset = 0.0

    def _alinea_parada_limite(self):
        """Cancelar el objetivo y llevar todas las referencias a la medida actual.

        Mientras limit_stop siga activo se repite en cada ciclo: no es un PID
        sosteniendo la posición de activación, sino espera con PWM forzado a 0.
        """
        self.pos = self.lee_sensor()
        self.ref = self.tr.Posicion = self.tr.PosicionDeseada = self.pos
        self.ofset = self.tr.VelActual = 0
        self.pid1.restablece()

    def parada_limite(self, direction):
        """Parar sin abrir lazo; direction: bit 0 negativo, bit 1 positivo.

        Se cancela el objetivo para impedir reanudación al soltar/rebotar el
        switch. MUEVE o HABSEG permitidos rearman; mientras tanto no hay par
        de sostén. La detección de inicio sigue activa y puede usar ese switch.
        """
        # Conserva Hab y el timer. Cancela el destino/seguimiento, sin auto-reanudar.
        self.limit_stop |= direction
        # Cortar antes de leer encoder o reorganizar la trayectoria.
        self.actuador(0)
        self.quita_modo_vel()
        self._alinea_parada_limite()

    def checa_limites(self):
        if self.limits is None:
            return
        mask = self.limits.sample()
        direction = blocked_direction(self.pid1.U, mask)
        if mask == 3:
            direction = 3  # Ambos extremos: ninguna direccion permitida.
        elif mask and self.pid1.Hab & 1 and not self.limit_stop:
            direction |= blocked_direction(self.tr.VelActual, mask)
            if self.modo & MODO_VEL:
                direction |= blocked_direction(self.velSeguimiento, mask)
            if not direction:
                pos = self.lee_sensor()
                direction |= blocked_direction(self.tr.Posicion - pos, mask)
                direction |= blocked_direction(self.ref + self.ofset - pos, mask)
        if direction:
            self.parada_limite(direction)

    def mando_manual(self, u):
        self.checa_limites()
        self.abre_lazo()  # DAX conserva su semantica de mando en lazo abierto.
        mask = self.limits.sample() if self.limits else 0
        if blocked_direction(u, mask):
            raise ValueError('Mando hacia un limite activo')
        if u:
            self.limit_stop = 0
        self.actuador(u)

    def estado_limites(self):
        """Reg. 32 / LIMITS: bits 0..1 activos, 2..3 parada, 8..10 entradas.

        Los activos son instantáneos; la parada se mantiene hasta una orden
        permitida. No confundir este offset 32 con comando 32 (CANCELA inicio).
        """
        mask = self.limits.sample() if self.limits else 0
        inputs = self.limits.active_inputs if self.limits else 0
        return mask | (self.limit_stop << 2) | (inputs << 8)

    def calcula_ref(self):
        if (self.modo & MODO_VEL) != 0 :
            self.ofset += self.velSeguimiento
        refx = self.ref + self.ofset
        self.tr.PosicionDeseada = refx

    def lee_sensor(self):
        if self.fn_lee_sensor is None:
            return 0
        return self.fn_lee_sensor()

    def limpia_encoder(self):
        if self.fn_limpia_encoder is None:
            return 0
        return self.fn_limpia_encoder()


    def actuador(self, u):
        if self.fn_actuador is None:
            return
        self.pid1.U = int(fn_saturacion(u, self.pid1.UMax))
        applied = self.fn_actuador(self.pid1.U)
        if applied is not None:
            self.pid1.U = applied

    def ejec_control(self):
        # Vigilar tambien durante una orden larga y en modo manual.
        self.checa_limites()
        if self.pinInicio.paro_al_capturar and self.pinInicio.edo == PREPARA_BUSCA_INICIO and not self.pinInicio.por_irq:
            self.pos = self.lee_sensor()
            self.checa_busqueda_inicio()
        if self.inicio_bloqueado():
            self.para_inicio()
            return
        if self.busy:
            return
        self.pos = self.lee_sensor()
        self.checa_busqueda_inicio()
        if self.limit_stop:
            self._alinea_parada_limite()
            self.actuador(0)
            self._capture(0)
            return
        if not (self.pid1.Hab & 1):
            self._capture(self.tr.Posicion - self.pos)
            return  # Capturar también en modo manual, sin avanzar la trayectoria.
        self.calcula_ref()
        refx = self.tr.Posicion
        err = refx - self.pos
        ## el cambio de ganancia
        err1 = err
        magErr = abs(err1)
        if (self.errorMaxParar > 0 )  and (magErr > self.errorMaxParar) :
            self.abre_lazo()
            return
        if self.cg.rango != 0 :
            kp1 = self.cg.calcula(err)
            err = (1.0 + kp1)*err
        self._capture(err1)

        if magErr < self.zonaMuerta :
            err = 0
        if (self.pid1.Hab & 1) != 0 :
            u = self.pid1.ejec(err)
            self.actuador(u)
        if self.tr.VelActual == 0 :
            self.pid1.Hab |= 0x2
        else:
            self.pid1.Hab = (self.pid1.Hab | 2) ^ 2
        self.tr.trapecio()


    def _capture(self, error):
        if self.cuentaDatos < len(self.muestras) - 1:
            self.muestras[self.cuentaDatos] = self.pos
            self.muestras[self.cuentaDatos + 1] = int(error)
            self.cuentaDatos += 2

    def restablece(self):
        self.abre_lazo()
        self.limpia_encoder()
        self.pos = self.ref = self.ofset = 0
        self.tr.Posicion = self.tr.PosicionDeseada = self.tr.VelActual = 0
        self.pinInicio.concluye_busca_inicio()
        self.pinInicio.cuenta_inicio = 0



    def cierra_lazo(self):
        self.pid1.restablece()
        self.pos = self.lee_sensor()
        self.tr.VelActual = 0
        self.tr.PosicionDeseada = self.pos
        self.tr.Posicion = self.tr.PosicionDeseada
        self.ref =  self.tr.PosicionDeseada
        self.ofset = 0.0
        self.pid1.Hab = 1

    def abre_lazo(self):
        self.pid1.Hab = 0
        self.pid1.restablece()
        self.actuador(0)

    def pon_modo_vel(self):
        self.checa_limites()
        mask = self.limits.sample() if self.limits else 0
        if blocked_direction(self.velSeguimiento, mask):
            raise ValueError('Seguimiento hacia un limite activo')
        if self.velSeguimiento:
            self.limit_stop = 0
        self.modo = self.modo | MODO_VEL


    def quita_modo_vel(self):
        self.modo = (self.modo | MODO_VEL) ^ MODO_VEL


    def dict_estado(self):
        d = {}
        d['X'] = self.pos
        d['XT'] = self.tr.Posicion
        d['XD'] = self.ref
        d['U'] = self.pid1.U
        d['E'] =  self.tr.Posicion- self.pos
        d['HAB'] = self.pid1.Hab
        d['MODO'] = self.modo
        d['VSEG'] = self.velSeguimiento
        d['BI'] = self.pinInicio.edo
        d['POSINI'] = self.pinInicio.cuenta_inicio
        d['ID'] = self.device_id
        d['LIMITS'] = self.estado_limites()
        return d



