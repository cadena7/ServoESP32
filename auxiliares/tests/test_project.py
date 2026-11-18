"""Pruebas en host: lógica real y tramas RTU; machine/UART/Timer simulados."""
import asyncio
import hashlib
import importlib
import io
import json
from pathlib import Path
import struct
import sys
import time
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'lib')]


class Pin:
    IN, OUT = 0, 1
    IRQ_RISING, IRQ_FALLING = 1, 2
    def __init__(self, number=0, mode=0, pull=None, value=0):
        self.number, self.val = number, value
    def value(self, value=None):
        if value is not None:
            previous = self.val
            self.val = value
            edge = self.IRQ_RISING if value else self.IRQ_FALLING
            if previous != value and getattr(self, 'handler', None) and self.trigger == edge:
                self.handler(self)
        return self.val
    def irq(self, handler=None, trigger=0):
        self.handler, self.trigger = handler, trigger
    def on(self): self.value(1)
    def off(self): self.value(0)


class PWM:
    def __init__(self, pin, freq, duty_u16):
        self.duty = duty_u16
        self.history = []
    def duty_u16(self, value):
        if not 0 <= value <= 65535:
            raise ValueError('PWM inválido')
        self.duty = value
        self.history.append(value)


class Encoder:
    def __init__(self, *args, **kwargs): self.count = 0
    def value(self, value=None):
        if value is not None: self.count = value
        return self.count


class Timer:
    PERIODIC = 1
    def __init__(self, *args): self.running = False
    def init(self, **kwargs): self.running = True; self.callback = kwargs['callback']
    def deinit(self): self.running = False


class UART:
    def __init__(self, *args, **kwargs): self.rx = bytearray(); self.tx = []
    def any(self): return len(self.rx)
    def read(self):
        data = bytes(self.rx); self.rx.clear(); return data or None
    def write(self, data): self.tx.append(bytes(data)); return len(data)
    def flush(self): pass


machine = types.ModuleType('machine')
for cls in (Pin, PWM, Encoder, Timer, UART): setattr(machine, cls.__name__, cls)
machine.unique_id = lambda: b'\x01\x23\xab\xcd'
machine.reset = lambda: None
sys.modules['machine'] = machine
micropython = types.ModuleType('micropython')
micropython.const = lambda value: value
sys.modules['micropython'] = micropython
clock = [0]
time.ticks_us = lambda: clock[0]
time.ticks_ms = lambda: clock[0] // 1000
time.ticks_diff = lambda a, b: a - b
time.sleep_us = lambda us: None
asyncio.wait_for_ms = lambda coro, ms: asyncio.wait_for(coro, ms / 1000)

from control import Eje, PidControl, Tray, CGAIN
from commands import Commands
from hardware import Hardware
from modbus_app import ModbusApp, int_to_regs, regs_to_int
from serial_json import SerialJSON


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.hw = Hardware(); self.e = self.hw.eje
        self.cmd = Commands(self.e, self.hw)
    def test_original_unchanged(self):
        if not (ROOT/'OG').is_dir():
            self.skipTest('Original local no incluido en el repositorio público')
        manifest = json.loads((ROOT/'auxiliares/docs/og-sha256.json').read_text())
        actual = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (ROOT/'OG').rglob('*') if p.is_file()}
        self.assertEqual(manifest, actual)
    def test_boot_is_open_and_zero(self):
        self.assertEqual(self.e.pid1.Hab, 0)
        self.assertEqual(self.hw.pwm.duty, 0)
    def test_fractional_trajectory_both_directions(self):
        for target in (10, -10):
            tr = Tray(); tr.config_trayectoria(.25, .05, 0)
            tr.PosicionDeseada = target
            for _ in range(300): tr.trapecio()
            self.assertAlmostEqual(tr.Posicion, target)
    def test_reverse_trajectory(self):
        tr = Tray(); tr.config_trayectoria(4.5, .05, 0)
        tr.PosicionDeseada = 100
        for _ in range(20): tr.trapecio()
        tr.PosicionDeseada = -100
        for _ in range(1000): tr.trapecio()
        self.assertAlmostEqual(tr.Posicion, -100)
    def test_small_speed_with_large_acceleration(self):
        tr = Tray(); tr.config_trayectoria(.01, .05, 0)
        tr.PosicionDeseada = 1
        for _ in range(300):
            tr.trapecio()
            self.assertLessEqual(abs(tr.VelActual), .01)
        self.assertAlmostEqual(tr.Posicion, 1)
    def test_invalid_startup_config_fails_before_start(self):
        import config
        from unittest.mock import patch
        with patch.object(config, 'TRAJECTORY_ACCEL', 0):
            with self.assertRaises(ValueError): Hardware()
    def test_pid_integral_is_clamped_in_output(self):
        pid = PidControl(); pid.kp = pid.kd = 0
        pid.ki = 100; pid.il = 5; pid.UMax = 1000; pid.Hab = 3
        self.assertEqual(pid.ejec(100), 5)
        self.assertEqual(pid.IVal, 5)
    def test_pid_and_buffers_are_independent(self):
        other = Eje(Pin()); self.e.muestras[0] = 42
        self.e.pid1.IVal = 8
        self.assertEqual(other.muestras[0], 0)
        self.assertEqual(other.pid1.IVal, 0)
    def test_zero_gain_range(self):
        self.assertEqual(CGAIN().calcula(0), 0)
    def test_close_resets_pid_and_aligns_sensor(self):
        self.hw.encoder.value(123); self.e.pid1.IVal = 77
        self.cmd.execute({'CMD':'CIERRA'})
        self.assertEqual(self.e.ref, 123)
        self.assertEqual(self.e.pid1.IVal, 0)
    def test_tracking_and_reset(self):
        self.cmd.execute({'CMD':'CIERRA'})
        self.cmd.execute({'CMD':'CAMBIA', 'VELSEG': .25})
        self.cmd.execute({'CMD':'HABSEG'})
        for _ in range(4): self.e.ejec_control()
        self.assertEqual(self.e.ofset, 1)
        self.cmd.execute({'CMD':'DESHABSEG'})
        self.hw.encoder.value(123)
        self.cmd.execute({'CMD':'RESTABLECE'})
        self.assertEqual(self.hw.encoder.value(), 0)
        self.assertEqual(self.e.ref, 0)
        self.assertEqual(self.e.pid1.Hab, 0)
    def test_home_uses_current_sample(self):
        self.cmd.execute({'CMD':'BUSCAINICIO'})
        self.hw.encoder.value(99); self.hw.inputs[0].value(1)
        self.e.ejec_control()
        self.assertEqual(self.e.lee_pos_inicio(), 99)
        self.assertEqual(self.e.lee_estado_busqueda_inicio(), 2)
        self.cmd.execute({'CMD':'CANCELA'})
        self.assertEqual(self.e.lee_estado_busqueda_inicio(), 0)
    def test_home_all_inputs_and_invalid_selection(self):
        for entry in (1, 2, 3):
            self.cmd.execute({'CMD': 'BUSCAINICIO', 'ENTRADA': entry})
            for i, pin in enumerate(self.hw.inputs):
                if i != entry - 1: pin.value(1 - pin.value())
            self.e.ejec_control()
            self.assertEqual(self.e.lee_estado_busqueda_inicio(), 1)
            pin = self.hw.inputs[entry - 1]
            self.hw.encoder.value(100 * entry)
            pin.value(1 - pin.value())
            self.e.ejec_control()
            self.assertEqual(self.e.lee_pos_inicio(), 100 * entry)
            self.assertEqual(self.cmd.execute({'CMD': 'EDOJ'})['HOME_INPUT'], entry)
        for entry in (0, 4, -1, True, 1.5, '2'):
            with self.assertRaises(ValueError):
                self.cmd.execute({'CMD': 'BUSCAINICIO', 'ENTRADA': entry})
        from unittest.mock import patch
        import config
        with patch.object(config, 'HOME_INPUT_INDEX', 2):
            self.cmd.execute({'CMD': 'BUSCAINICIO'})
        self.assertIs(self.e.pinInicio.pin, self.hw.inputs[1])

    def test_home_config_uses_physical_numbers_and_defaults_to_ent1(self):
        from unittest.mock import patch
        import config
        self.assertEqual(config.HOME_INPUT_INDEX, 1)
        self.assertEqual(self.hw.home_input, 1)
        for entry in (1, 2, 3):
            with patch.object(config, 'HOME_INPUT_INDEX', entry):
                hw = Hardware()
                cmd = Commands(hw.eje, hw)
                self.assertIs(hw.eje.pinInicio.pin, hw.inputs[entry - 1])
                cmd.execute({'CMD': 'BUSCAINICIO', 'ENTRADA': 1})
                cmd.execute({'CMD': 'BUSCAINICIO'})
                self.assertEqual(cmd.execute({'CMD': 'EDOJ'})['HOME_INPUT'], entry)
                self.assertIs(hw.eje.pinInicio.pin, hw.inputs[entry - 1])
        for entry in (0, 4, -1, True, 1.5, '2'):
            with patch.object(config, 'HOME_INPUT_INDEX', entry):
                with self.assertRaises(ValueError): Hardware()

    def test_index_capture_polarity_status_and_reset(self):
        from unittest.mock import patch
        import config
        for level in (0, 1):
            with patch.object(config, 'ENCODER_INDEX_ENABLED', True), \
                 patch.object(config, 'ENCODER_INDEX_ACTIVE_LEVEL', level):
                hw = Hardware()
            cmd = Commands(hw.eje, hw)
            self.assertFalse(cmd.execute({'CMD': 'EDOJ'})['Z_VALID'])
            hw.encoder_index.value(1 - level)
            hw.encoder.value(-123)
            hw.encoder_index.value(level)
            state = cmd.execute({'CMD': 'EDOJ'})
            self.assertEqual((state['Z_VALID'], state['Z_POS']), (True, -123))
            self.assertEqual(hw.encoder.value(), -123)
            app = ModbusApp(cmd); app.update()
            self.assertEqual(app.client.get_hreg(33), 5 | level << 1)
            self.assertEqual(regs_to_int(app.client.get_hreg(34), app.client.get_hreg(35)), -123)
            hw.encoder.value(456)
            hw.encoder_index.value(1 - level)
            self.assertEqual(hw.index_state()['Z_POS'], -123)
            hw.encoder_index.value(level)
            self.assertEqual(hw.index_state()['Z_POS'], 456)
            cmd.execute({'CMD': 'RESTABLECE'})
            self.assertFalse(cmd.execute({'CMD': 'EDOJ'})['Z_VALID'])
            hw.stop()
            self.assertIsNone(hw.encoder_index.handler)
    def test_error_stop_resets_output(self):
        self.e.cierra_lazo(); self.hw.encoder.value(2000)
        self.e.ejec_control()
        self.assertEqual(self.e.pid1.Hab, 0)
        self.assertEqual(self.hw.pwm.duty, 0)
        self.assertEqual(self.e.pid1.U, 0)
    def test_capture_fills_all_pairs(self):
        self.e.cierra_lazo()
        for _ in range(1005): self.e.ejec_control()
        self.assertEqual(self.e.cuentaDatos, 2000)
        self.cmd.execute({'CMD':'RCD'})
        self.assertEqual(self.e.cuentaDatos, 0)
        self.assertEqual(len(self.cmd.execute({'CMD':'DAMEDATOS'})['DATOS']), 2000)
    def test_drive_clamps_and_open_stops_manual(self):
        self.hw.drive(-999999)
        self.assertEqual(self.hw.pwm.duty, 65535)
        self.cmd.execute({'CMD':'DAX', 'PAR': -100})
        self.assertEqual(self.e.dict_estado()['U'], -100)
        self.cmd.execute({'CMD':'ABRE'})
        self.assertEqual(self.hw.pwm.duty, 0)
        self.assertEqual((self.hw.a.value(),self.hw.b.value()),(0,0))
    def test_invalid_parameters_are_atomic(self):
        for obj in ({'CMD':'CAMBIA','KP':5,'ACEL':0}, {'CMD':'CAMBIA','KI':float('nan')},
                    {'CMD':'CAMBIA','VEL':-1}, {'CMD':'CAMBIA','UMAX':65536},
                    {'CMD':'CAMBIA','HAB':1.5}, {'CMD':'MUEVE','PAR':True},
                    {'CMD':'MUEVE','PAR':2**31}, {'CMD':'DAX','PAR':'10'},
                    {'CMD':'CAMBIA','INVALID':1}, {'CMD':'INVALID'}, []):
            with self.subTest(obj=obj), self.assertRaises(ValueError): self.cmd.execute(obj)
        self.assertEqual(self.e.pid1.kp, .1)
        self.assertFalse(self.e.busy)
    def test_outputs_and_input_packing(self):
        self.assertEqual([p.number for p in self.hw.inputs], [33, 4, 19])
        self.assertEqual([p.number for p in self.hw.outputs], [21, 22, 23])
        self.assertIsNone(self.hw.encoder_index)
        self.cmd.execute({'CMD':'SALIDAS','FLAGS':2,'BITS':7})
        self.assertEqual([p.value() for p in self.hw.outputs],[1,1,1])
        self.cmd.execute({'CMD':'SALIDAS','FLAGS':3,'BITS':2})
        self.assertEqual([p.value() for p in self.hw.outputs],[1,0,1])
        for p in self.hw.inputs: p.value(1)
        self.assertEqual(self.hw.read_inputs(),7)
    def test_optional_encoder_index_is_separate_from_inputs(self):
        from unittest.mock import patch
        import config
        with patch.object(config, 'ENCODER_INDEX_ENABLED', True):
            hw = Hardware()
        self.assertEqual(hw.encoder_index.number, 18)
        hw.encoder_index.value(1)
        self.assertEqual(hw.read_inputs(), 0)
        for i, pin in enumerate(hw.inputs):
            pin.value(1)
            self.assertEqual(hw.read_inputs(), 1 << i)
            pin.value(0)
        app = ModbusApp(Commands(hw.eje, hw))
        for pin in hw.inputs: pin.value(1)
        app.update()
        self.assertEqual(app.client.get_hreg(30) & 0x0F00, 0x0700)
    def test_timer_failure_stops_motor(self):
        self.hw.start(); self.hw.drive(300)
        def fail(): raise ValueError('sensor')
        self.e.fn_lee_sensor = fail
        self.hw._tick(self.hw.timer)
        self.assertIsNotNone(self.hw.fault)
        self.assertFalse(self.hw.timer.running)
        self.assertEqual(self.hw.pwm.duty,0)
        with self.assertRaises(ValueError):
            self.cmd.execute({'CMD':'DAX','PAR':300})
        self.assertEqual(self.hw.pwm.duty,0)
    def test_json_line_errors_and_recovery(self):
        serial = SerialJSON.__new__(SerialJSON)
        serial.commands = self.cmd; serial.max_length = 100
        serial.buffer = ''; serial.discard = False
        def feed(line):
            result = None
            for ch in line: result = serial.feed(ch)
            return result
        self.assertIn('error', feed('bad\n'))
        self.assertIn('error', feed('x'*120+'\n'))
        self.assertEqual(feed('{"CMD":"MUEVE","PAR":34}\n'),{'status':True})
        self.assertEqual(self.e.ref,34)


class ModbusTests(unittest.TestCase):
    def setUp(self):
        self.hw = Hardware(); self.cmd = Commands(self.hw.eje,self.hw)
        self.app = ModbusApp(self.cmd)
        self.itf = self.app.client._itf
        self.uart = self.itf._uart
    def frame(self, pdu):
        data = bytes([23])+pdu
        return data+self.itf._calculate_crc16(data)
    def exchange(self, frame):
        # Fragmentación realista: recepción en dos iteraciones y silencio de bus.
        self.uart.rx.extend(frame[:3]); self.app.poll()
        clock[0] += 1000
        self.uart.rx.extend(frame[3:]); self.app.poll()
        clock[0] += 6000
        self.app.poll()
        return self.uart.tx[-1] if self.uart.tx else b''
    def test_int_roundtrip(self):
        for value in (-2**31,-123,-1,0,1,2**31-1):
            self.assertEqual(regs_to_int(*int_to_regs(value)),value)
    def test_rtu_multiple_register_move_and_clear(self):
        a,b = int_to_regs(-123456)
        response = self.exchange(self.frame(struct.pack('>BHHBHHH',16,10,3,6,1,a,b)))
        self.assertEqual(response,self.frame(struct.pack('>BHH',16,10,3)))
        self.assertEqual(self.hw.eje.ref,-123456)
        self.assertEqual(self.app.client.get_hreg(10),0)
    def test_rtu_read_negative_position_unsigned_words(self):
        self.hw.eje.pos = -123456
        response = self.exchange(self.frame(struct.pack('>BHH',3,20,2)))
        self.assertEqual(response,self.frame(struct.pack('>BBHH',3,4,*int_to_regs(-123456))))
    def test_crc_bad_is_ignored(self):
        response = self.exchange(self.frame(struct.pack('>BHH',6,10,2))[:-1]+b'\x00')
        self.assertEqual(response,b'')
        self.assertEqual(self.hw.eje.pid1.Hab,0)
    def test_invalid_command_cleared(self):
        self.exchange(self.frame(struct.pack('>BHH',6,10,999)))
        self.assertEqual(self.app.client.get_hreg(10),0)
    def test_malformed_byte_count_returns_exception(self):
        response = self.exchange(self.frame(struct.pack('>BHHBHHH',16,10,3,5,1,0,20)))
        self.assertEqual(response, self.frame(bytes([0x90,3])))
        self.assertEqual(self.hw.eje.ref, 0)
    def test_register_range_rejected_before_write(self):
        response = self.exchange(self.frame(struct.pack('>BHHBHHHH',16,10,4,8,1,0,20,30)))
        self.assertEqual(response, self.frame(bytes([0x90,2])))
        self.assertEqual(self.hw.eje.ref, 0)
    def test_register_range_rejected_on_read(self):
        response = self.exchange(self.frame(struct.pack('>BHH',3,37,2)))
        self.assertEqual(response, self.frame(bytes([0x83,2])))
    def test_output_levels_readback(self):
        self.app.dispatch(57, 2, 5)
        self.app.dispatch(57, 1, 1)
        response = self.exchange(self.frame(struct.pack('>BHH',3,37,1)))
        self.assertEqual(response, self.frame(struct.pack('>BBH',3,2,4)))

    def test_all_function_dispatches(self):
        for fn in (2,3,9,10,30,31,32): self.app.dispatch(fn,0,0)
        for fn in (4,5,6,7,8,20,21,22,23,24):
            a,b=struct.unpack('>HH',struct.pack('>f',2.0))
            self.app.dispatch(fn,a,b)
        for fn in (1,50,53,54): self.app.dispatch(fn,*int_to_regs(5))
        self.app.dispatch(57,2,7)
        with self.assertRaises(ValueError): self.app.dispatch(999,0,0)
    def test_modbus_home_selection_and_status(self):
        for entry in (1, 2, 3):
            self.exchange(self.frame(struct.pack('>BHHBHHH', 16, 10, 3, 6, 31, entry, 0)))
            self.assertIs(self.hw.eje.pinInicio.pin, self.hw.inputs[entry - 1])
            self.assertEqual(self.app.client.get_hreg(36), entry)
        self.app.dispatch(31, 0, 0)
        self.assertIs(self.hw.eje.pinInicio.pin, self.hw.inputs[0])
        with self.assertRaises(ValueError): self.app.dispatch(31, 4, 0)


class WebTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_partial_body_and_bad_requests(self):
        from nanoweb import Nanoweb
        from web_app import WebAPI
        hw = Hardware(); api = WebAPI(Commands(hw.eje,hw))
        server = Nanoweb(api.handle)
        class Writer:
            def __init__(self): self.data = bytearray(); self.closed=False
            def write(self,data): self.data.extend(data)
            async def drain(self): pass
            def close(self): self.closed=True
            async def wait_closed(self): pass
        async def call(request):
            reader = asyncio.StreamReader(); writer = Writer()
            # readexactly must assemble body across arbitrary TCP fragmentation.
            async def deliver():
                for i in range(0,len(request),7):
                    reader.feed_data(request[i:i+7]); await asyncio.sleep(0)
                reader.feed_eof()
            task=asyncio.create_task(deliver())
            await server.handle(reader,writer); await task
            self.assertTrue(writer.closed)
            return bytes(writer.data)
        body=b'{"CMD":"MUEVE","PAR":42}'
        response=await call(b'POST /post HTTP/1.1\r\ncontent-type: application/json\r\ncontent-length: '+str(len(body)).encode()+b'\r\n\r\n'+body)
        self.assertIn(b'200 OK',response); self.assertEqual(hw.eje.ref,42)
        for request,status in ((b'GET /absent HTTP/1.1\r\n\r\n',b'404'),
                               (b'GET /post HTTP/1.1\r\n\r\n',b'405'),
                               (b'POST /post HTTP/1.1\r\nContent-Length: -1\r\n\r\n',b'400'),
                               (b'POST /post HTTP/1.1\r\nContent-Length: 99999\r\n\r\n',b'400')):
            self.assertIn(status,await call(request))


if __name__ == '__main__': unittest.main()
