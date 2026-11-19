"""Inicio por índice Z: flanco IRQ, sin añadir una cuarta entrada de límites."""
import struct
import unittest
from unittest.mock import patch
import test_project as env
import config


class IndexHomeTests(unittest.TestCase):
    def make_hardware(self, default=1, level=1):
        with patch.multiple(config, ENCODER_INDEX_ENABLED=True,
                            HOME_INPUT_INDEX=default, ENCODER_INDEX_ACTIVE_LEVEL=level):
            hw = env.Hardware()
        return hw, hw.eje, env.Commands(hw.eje, hw)

    def pulse(self, hw, position, level=1):
        hw.encoder_index.value(1 - level)
        hw.encoder.value(position)
        hw.encoder_index.value(level)
        hw.encoder_index.value(1 - level)

    def test_short_pulse_captures_first_home_without_control_tick(self):
        for level in (0, 1):
            with self.subTest(level=level):
                hw, e, cmd = self.make_hardware(level=level)
                self.pulse(hw, 10, level)  # Captura Z anterior no satisface búsqueda nueva.
                cmd.execute({'CMD': 'BUSCAINICIO', 'ENTRADA': 4})
                self.assertEqual(e.pinInicio.edo, 1)
                self.pulse(hw, -123, level)  # Pulso termina antes del tick de control.
                hw.encoder.value(999)
                e.ejec_control()
                state = cmd.execute({'CMD': 'EDOJ'})
                self.assertEqual((state['HOME_INPUT'], state['BI'], state['POSINI']), (4, 2, -123))
                self.assertEqual(hw.encoder.value(), 999)
                self.pulse(hw, 456, level)
                state = cmd.execute({'CMD': 'EDOJ'})
                self.assertEqual(state['POSINI'], -123)  # Primer flanco de búsqueda.
                self.assertEqual(state['Z_POS'], 456)  # Último flanco de diagnóstico Z.
                self.assertEqual(len(hw.inputs), 3)
                self.assertEqual(hw.read_inputs(), 0)
                self.assertEqual(e.estado_limites(), 0)

    def test_default_four_arms_z_and_explicit_selection_can_return_to_ent(self):
        hw, e, cmd = self.make_hardware(default=4)
        with patch.object(config, 'HOME_INPUT_INDEX', 4):
            self.assertEqual(hw.home_input, 4)
            cmd.execute({'CMD': 'BUSCAINICIO'})
            self.pulse(hw, 55)
            self.assertEqual((e.pinInicio.edo, e.lee_pos_inicio()), (2, 55))
            cmd.execute({'CMD': 'BUSCAINICIO', 'ENTRADA': 2})
            self.pulse(hw, 66)
            self.assertEqual(e.pinInicio.edo, 1)
            hw.inputs[1].value(1)
            e.ejec_control()
            self.assertEqual(e.lee_pos_inicio(), 66)
            cmd.execute({'CMD': 'BUSCAINICIO'})
            self.assertEqual(hw.home_input, 4)
            self.assertEqual(e.pinInicio.edo, 1)

    def test_cancel_rearm_and_reset_do_not_capture_when_inactive(self):
        hw, e, cmd = self.make_hardware()
        cmd.execute({'CMD': 'BUSCAINICIO', 'ENTRADA': 4})
        cmd.execute({'CMD': 'CANCELA'})
        self.pulse(hw, 100)
        self.assertEqual(e.pinInicio.edo, 0)
        cmd.execute({'CMD': 'BUSCAINICIO', 'ENTRADA': 4})
        self.pulse(hw, 200)
        self.assertEqual((e.pinInicio.edo, e.lee_pos_inicio()), (2, 200))
        cmd.execute({'CMD': 'RESTABLECE'})
        self.pulse(hw, 300)
        self.assertEqual((e.pinInicio.edo, e.lee_pos_inicio()), (0, 0))

    def test_selecting_z_disabled_preserves_previous_search(self):
        hw = env.Hardware()
        cmd = env.Commands(hw.eje, hw)
        cmd.execute({'CMD': 'BUSCAINICIO', 'ENTRADA': 2})
        with self.assertRaisesRegex(ValueError, 'ENCODER_INDEX_ENABLED'):
            cmd.execute({'CMD': 'BUSCAINICIO', 'ENTRADA': 4})
        self.assertEqual(hw.home_input, 2)
        self.assertEqual(hw.eje.pinInicio.edo, 1)
        with patch.object(config, 'HOME_INPUT_INDEX', 4):
            with self.assertRaisesRegex(ValueError, 'ENCODER_INDEX_ENABLED'):
                env.Hardware()

    def test_protected_search_stops_ent_and_z_without_master(self):
        for source in (1, 2, 3, 4):
            with self.subTest(source=source):
                hw, eje, cmd = self.make_hardware()
                app = env.ModbusApp(cmd)
                app.dispatch(58, source, 0)
                cmd.execute({'CMD': 'DAX', 'PAR': 120})
                self.assertGreater(hw.pwm.duty, 0)
                hw.encoder.value(24)
                if source == 4:
                    self.pulse(hw, 24)
                else:
                    hw.inputs[source-1].value(1)
                    eje.ejec_control()
                self.assertEqual((hw.pwm.duty, eje.pid1.Hab, eje.pinInicio.cuenta_inicio), (0, 0, 24))
                cmd.execute({'CMD': 'DAX', 'PAR': 120})
                self.assertEqual(hw.pwm.duty, 0)
                app.update()
                self.assertEqual(app.client.get_hreg(30) & 0xc0, 0xc0)
                app.dispatch(32, 0, 0)
                app.update()
                self.assertEqual(app.client.get_hreg(30) & 0xc0, 0x80)
                self.assertEqual(hw.pwm.duty, 0)

    def test_only_configured_z_edge_completes_home(self):
        for level in (0, 1):
            hw, e, cmd = self.make_hardware(level=level)
            hw.encoder_index.value(level)
            cmd.execute({'CMD': 'BUSCAINICIO', 'ENTRADA': 4})
            hw.encoder_index.value(1 - level)
            e.ejec_control()
            self.assertEqual(e.pinInicio.edo, 1)
            hw.encoder.value(88)
            hw.encoder_index.value(level)
            self.assertEqual((e.pinInicio.edo, e.lee_pos_inicio()), (2, 88))

    def test_modbus_four_selection_default_and_capture_registers(self):
        hw, e, cmd = self.make_hardware()
        app = env.ModbusApp(cmd)
        itf = app.client._itf
        data = bytes([23]) + struct.pack('>BHHBHHH', 16, 10, 3, 6, 31, 4, 0)
        itf._uart.rx.extend(data + itf._calculate_crc16(data))
        app.poll(); env.clock[0] += 6000; app.poll()
        self.assertEqual(app.client.get_hreg(36), 4)
        self.assertEqual(e.pinInicio.edo, 1)
        self.pulse(hw, -54321)
        app.update()
        self.assertEqual(env.regs_to_int(app.client.get_hreg(24), app.client.get_hreg(25)), 2)
        self.assertEqual(env.regs_to_int(app.client.get_hreg(26), app.client.get_hreg(27)), -54321)
        self.assertEqual(app.client.get_hreg(30) & 0xF00, 0)
        app.dispatch(32, 0, 0)
        self.assertEqual(e.pinInicio.edo, 0)
        app.dispatch(31, 0, 0)
        self.assertEqual(hw.home_input, 1)  # Predeterminada sigue siendo ENT1.


if __name__ == '__main__':
    unittest.main()
