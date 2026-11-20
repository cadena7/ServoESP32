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
        from commands import READBACK, active_value

        class ServoRTU(ModbusRTU):
            def _process_read_access(client, request, reg_type):
                if reg_type == 'HREGS' and 40 <= request.register_addr < 44:
                    start = request.register_addr - 40
                    end = start + request.quantity
                    if end > 4:
                        return request.send_exception(2)
                    low, high = commands.eje.destinations
                    return request.send_response((int_to_regs(low) + int_to_regs(high))[start:end], signed=False)
                if reg_type != 'IREGS':
                    return super()._process_read_access(request, reg_type)
                # Bloque virtual: ninguna copia permanente ni trabajo en el PID.
                start = request.register_addr
                end = start + request.quantity
                types_offset = 2 * len(READBACK)
                if end > types_offset + 1:
                    return request.send_exception(2)
                words = []
                types = 0
                for i, name in enumerate(READBACK):
                    offset = 2 * i
                    in_range = offset < end and offset + 1 >= start
                    if not in_range and end <= types_offset:
                        continue
                    value = active_value(commands.eje, name)
                    integer = isinstance(value, int) and -2147483648 <= value <= 2147483647
                    if integer:
                        types |= 1 << i
                    if in_range:
                        raw = struct.pack('>l' if integer else '>f', value)
                        hi, lo = struct.unpack('>HH', raw)
                        if offset >= start:
                            words.append(hi)
                        if offset + 1 < end:
                            words.append(lo)
                if end > types_offset:
                    words.append(types)
                request.send_response(words, signed=False)

            def _process_write_access(client, request, reg_type):
                if reg_type == 'HREGS' and request.register_addr == 40:
                    if request.function != 16 or request.quantity != 4:
                        return request.send_exception(3)
                    low, high = struct.unpack('>ll', request.data)
                    try:
                        commands.execute({'CMD': 'DESTINOS', 'MINPOS': low, 'MAXPOS': high})
                    except ValueError:
                        return request.send_exception(3)
                    return request.send_response()
                return super()._process_write_access(request, reg_type)

        self.commands = commands
        self.client = ServoRTU(addr=c.MODBUS_ADDRESS, pins=(c.MODBUS_TX, c.MODBUS_RX),
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
        elif fn in (51, 52):
            low, high = self.commands.eje.destinations
            value = regs_to_int(a, b)
            obj = {'CMD': 'DESTINOS', 'MINPOS': value if fn == 52 else low,
                   'MAXPOS': value if fn == 51 else high}
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
        # Bit 5: lectura de parámetros FC04. Bits 7/6: inicio protegido/armado.
        capabilities = 0x10 | 0x20 | 0x80 | (0x40 if self.commands.eje.pinInicio.paro_al_capturar else 0)
        regs.extend((edo['MODO'] | capabilities | self.commands.hardware.read_inputs() << 8,
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
