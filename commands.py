"""Validación y despacho común para JSON, HTTP y Modbus."""
import math

# campo: objeto destino, atributo, mínimo, máximo; None = sin límite.
PARAMETERS = {
    'KP': ('pid1', 'kp', 0, None), 'KI': ('pid1', 'ki', 0, None),
    'KD': ('pid1', 'kd', 0, None), 'IL': ('pid1', 'il', 0, None),
    'UMAX': ('pid1', 'UMax', 0, 65535), 'EMAX': ('pid1', 'ErrMax', 0, None),
    'HAB': ('pid1', 'Hab', 0, 3), 'ACEL': ('tr', 'AcelDeseada', 1e-12, None),
    'VEL': ('tr', 'VelDeseada', 1e-12, None), 'EMIN': ('tr', 'ErrorMinimo', 0, None),
    'VELSEG': (None, 'velSeguimiento', None, None),
    'RANGO': ('cg', 'rango', 0, None), 'MAGNITUD': ('cg', 'magnitud', 0, None),
    'ZONA': (None, 'zonaMuerta', 0, None),
    'ERRORPARAR': (None, 'errorMaxParar', 0, None),
}


def number(value, low=None, high=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Se requiere un número')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError('Número no finito o demasiado grande')
    if low is not None and value < low or high is not None and value > high:
        raise ValueError('Valor fuera de rango')
    if integer and int(value) != value:
        raise ValueError('Se requiere un entero')
    return int(value) if integer else value


class Commands:
    def __init__(self, eje, hardware):
        self.eje = eje
        self.hardware = hardware

    def execute(self, obj):
        if not isinstance(obj, dict) or 'CMD' not in obj:
            raise ValueError('Se requiere un objeto con CMD')
        if self.hardware.fault is not None and obj['CMD'] not in ('ABRE', 'EDOJ', 'DAMEDATOS'):
            raise ValueError('Fallo de control: reiniciar y revisar el equipo')
        e = self.eje
        e.busy = True
        try:
            cmd = obj['CMD']
            if cmd == 'MUEVE':
                e.mueve(number(obj.get('PAR'), -2147483648, 2147483647, True))
            elif cmd == 'DAX':
                u = number(obj.get('PAR'), -65535, 65535, True)
                e.mando_manual(u)
            elif cmd == 'CAMBIA':
                updates = []
                for name, value in obj.items():
                    if name == 'CMD':
                        continue
                    if name not in PARAMETERS:
                        raise ValueError('Parámetro desconocido: ' + name)
                    target, attr, low, high = PARAMETERS[name]
                    val = number(value, low, high, name in ('HAB', 'UMAX'))
                    updates.append((getattr(e, target) if target else e, attr, val))
                # Validar todo antes de modificar el primer campo.
                for target, attr, value in updates:
                    if attr == 'Hab':
                        if value & 1 and not e.pid1.Hab & 1:
                            e.cierra_lazo()
                        elif not value & 1:
                            e.abre_lazo()
                    setattr(target, attr, value)
            elif cmd == 'EDOJ':
                state = e.dict_estado()
                state.update(self.hardware.index_state())
                state['HOME_INPUT'] = self.hardware.home_input
                return state
            elif cmd in ('BUSCAINICIO', 'BUSCAINICIO_PARO'):
                # ENTRADA=1..3 (ENT) o 4 (Z); omitida -> HOME_INPUT_INDEX.
                # Seleccionar/armar no inicia movimiento ni deshabilita límites.
                self.hardware.select_home_input(obj.get('ENTRADA'))
                e.inicia_busqueda_inicio(cmd == 'BUSCAINICIO_PARO')
            elif cmd == 'CANCELA' and e.pinInicio.paro_al_capturar:
                e.para_inicio()
                e.cancela_busqueda_inicio()
                e.pinInicio.paro_al_capturar = False
            elif cmd == 'DAMEDATOS':
                return {'DATOS': list(e.muestras)}
            elif cmd == 'RCD':
                e.cuentaDatos = 0
            elif cmd == 'SALIDAS':
                flags = number(obj.get('FLAGS'), 0, 3, True)
                bits = number(obj.get('BITS'), 0, 7, True)
                self.hardware.output_bits(flags, bits)
            elif cmd == 'MRST':
                e.abre_lazo()
                from machine import reset
                reset()
            else:
                methods = {'CIERRA': e.cierra_lazo, 'ABRE': e.abre_lazo,
                           'HABSEG': e.pon_modo_vel, 'DESHABSEG': e.quita_modo_vel,
                           'RESTABLECE': e.restablece,
                           'CANCELA': e.cancela_busqueda_inicio}
                if cmd not in methods:
                    raise ValueError('Comando desconocido')
                methods[cmd]()
            return {'status': True}
        finally:
            e.busy = False
