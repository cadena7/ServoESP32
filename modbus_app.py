"""Mapa de registros legado: palabras altas primero, int32/float32 big endian."""
import struct
import config as c


def int_to_regs(value):
    return struct.unpack('>HH', struct.pack('>l', int(value)))


def regs_to_int(a, b):
    return struct.unpack('>l', struct.pack('>HH', a, b))[0]


def regs_to_float(a, b):
    return struct.unpack('>f', struct.pack('>HH', a, b))[0]


class ModbusApp:
    def __init__(self, commands):
        from umodbus.serial import ModbusRTU
        self.commands = commands
        self.client = ModbusRTU(addr=c.MODBUS_ADDRESS, pins=(c.MODBUS_TX, c.MODBUS_RX),
                                baudrate=c.MODBUS_BAUD, ctrl_pin=c.MODBUS_CTRL,
                                uart_id=c.MODBUS_UART)
        self.client.setup_registers(registers={'HREGS': {
            'FN': {'register': 10, 'len': 3, 'val': [0]*3},
            'PARAM': {'register': 14, 'len': 2, 'val': [0]*2},
            'ESTADO': {'register': 20, 'len': 18, 'val': [0]*18}}})

    def dispatch(self, fn, a, b):
        simple = {2: 'CIERRA', 3: 'ABRE', 9: 'HABSEG', 10: 'DESHABSEG',
                  30: 'RESTABLECE', 31: 'BUSCAINICIO', 32: 'CANCELA'}
        floats = {4: 'KP', 5: 'KI', 6: 'KD', 7: 'IL', 8: 'UMAX',
                  20: 'ACEL', 21: 'VEL', 22: 'VELSEG', 23: 'RANGO', 24: 'MAGNITUD'}
        if fn in (31, 58):
            # Escribir [31, entrada, 0] en offsets 10..12 mediante función 0x10.
            # Reg. 11 es selección directa (0=config, 1..3=ENT, 4=Z), NO un int32.
            # Reg. 36 informa la selección; reg. 24..25 informa BI (0/1/2).
            obj = {'CMD': 'BUSCAINICIO_PARO' if fn == 58 else 'BUSCAINICIO'}
            if a:
                obj['ENTRADA'] = a  # 0=config; 1..3=ENT1..ENT3; 4=Z.
        elif fn in simple:
            obj = {'CMD': simple[fn]}
        elif fn in floats:
            obj = {'CMD': 'CAMBIA', floats[fn]: regs_to_float(a, b)}
        elif fn in (1, 50):
            obj = {'CMD': 'MUEVE' if fn == 1 else 'DAX', 'PAR': regs_to_int(a, b)}
        elif fn in (53, 54):
            obj = {'CMD': 'CAMBIA', 'ZONA' if fn == 53 else 'ERRORPARAR': abs(regs_to_int(a, b))}
        elif fn == 57:
            obj = {'CMD': 'SALIDAS', 'FLAGS': a, 'BITS': b}
        else:
            raise ValueError('Función Modbus desconocida')
        return self.commands.execute(obj)

    def update(self):
        edo = self.commands.eje.dict_estado()
        regs = []
        for key in ('X', 'XT', 'BI', 'POSINI', 'U'):
            regs.extend(int_to_regs(edo[key]))
        home_stop = 0x80 | (0x40 if self.commands.eje.pinInicio.paro_al_capturar else 0)
        regs.extend((edo['MODO'] | home_stop | self.commands.hardware.read_inputs() << 8,
                     edo['HAB'], edo['LIMITS']))
        z = self.commands.hardware.index_state()
        regs.append(int(z['Z_ENABLED']) | int(z['Z_LEVEL']) << 1 | int(z['Z_VALID']) << 2)
        regs.extend(int_to_regs(z['Z_POS']))
        regs.append(self.commands.hardware.home_input)
        regs.append(self.commands.hardware.output_levels)
        self.client.set_hreg(20, regs)

    def poll(self):
        self.update()  # Estado disponible antes de responder a una lectura.
        if self.client.process():
            fn = self.client.get_hreg(10)
            if fn:
                try:
                    self.dispatch(fn, self.client.get_hreg(11), self.client.get_hreg(12))
                except ValueError as exc:
                    # Error de aplicación: la trama RTU ya fue aceptada por la biblioteca.
                    print('Comando Modbus rechazado:', exc)
                finally:
                    self.client.set_hreg(10, [0])
            self.update()
