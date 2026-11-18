"""Limites de recorrido con el control, PWM y tramas Modbus reales del proyecto."""
import struct
import unittest
from unittest.mock import patch

# Instala los mismos perifericos simulados que la suite existente.
from test_project import Hardware, Commands, ModbusApp, clock
import config


class LimitTests(unittest.TestCase):
    def make_hardware(self, roles=(-1, 1, 0), levels=(1, 1, 1)):
        with patch.multiple(config, LIMIT_INPUT_ROLES=roles,
                            LIMIT_ACTIVE_LEVELS=levels):
            hw = Hardware()
        for pin, level in zip(hw.inputs, levels):
            pin.value(1-level)
        return hw, hw.eje, Commands(hw.eje, hw)

    def assert_stopped_closed(self, hw, e, mask):
        self.assertTrue(e.pid1.Hab & 1)
        self.assertEqual((hw.pwm.duty, e.pid1.U), (0, 0))
        self.assertEqual((hw.a.value(), hw.b.value()), (0, 0))
        self.assertEqual(e.limit_stop, mask)
        self.assertEqual(e.pid1.IVal, 0)
        self.assertEqual(e.tr.VelActual, 0)
        self.assertEqual((e.ref, e.tr.Posicion, e.tr.PosicionDeseada),
                         (hw.encoder.value(),)*3)

    def test_each_input_supports_both_directions_and_polarities(self):
        for i in range(3):
            for role, mask in ((-1, 1), (1, 2)):
                for level in (0, 1):
                    with self.subTest(input=i, role=role, active=level):
                        roles = [0]*3; roles[i] = role
                        levels = [1]*3; levels[i] = level
                        hw, e, cmd = self.make_hardware(roles, levels)
                        self.assertEqual(e.estado_limites(), 0)
                        hw.inputs[i].value(level)
                        self.assertEqual(e.estado_limites(), mask | (1 << (8+i)))
                        hw.drive(role*500)
                        self.assertEqual(hw.pwm.duty, 0)
                        cmd.execute({'CMD': 'DAX', 'PAR': -role*500})
                        self.assertEqual(e.pid1.U, -role*500)
                        e.ejec_control()
                        self.assertEqual(hw.pwm.duty, 500)

    def test_disabled_general_inputs_and_index_do_not_stop_motion(self):
        hw, e, cmd = self.make_hardware((0, 0, 0))
        for pin in hw.inputs: pin.value(1)
        cmd.execute({'CMD': 'DAX', 'PAR': 500})
        for _ in range(3): e.ejec_control()
        self.assertEqual(hw.pwm.duty, 500)
        self.assertEqual(e.estado_limites(), 0)

    def test_closed_loop_limit_stops_before_following_error_and_allows_retreat(self):
        for direction, pin, mask in ((1, 1, 2), (-1, 0, 1)):
            with self.subTest(direction=direction):
                hw, e, cmd = self.make_hardware()
                hw.encoder.value(direction*100)
                cmd.execute({'CMD': 'CIERRA'})
                cmd.execute({'CMD': 'MUEVE', 'PAR': direction*200})
                e.tr.Posicion = direction*120
                e.tr.VelActual = direction*4
                e.pid1.IVal = direction*100
                e.errorMaxParar = 1
                e.actuador(direction*300)
                hw.inputs[pin].value(1)
                hw._tick(None)
                self.assertIsNone(hw.fault)
                self.assert_stopped_closed(hw, e, mask)
                # Se mantiene detenido sin acumular error/integral.
                for _ in range(100): e.ejec_control()
                self.assert_stopped_closed(hw, e, mask)
                with self.assertRaises(ValueError):
                    cmd.execute({'CMD': 'MUEVE', 'PAR': direction*150})
                # Retirada con una sola orden, sin ABRE/CIERRA.
                e.errorMaxParar = 1000
                e.pid1.kp, e.pid1.ki, e.pid1.kd = 1, 0, 0
                e.zonaMuerta = e.cg.rango = e.tr.ErrorMinimo = 0
                cmd.execute({'CMD': 'MUEVE', 'PAR': 0})
                outputs = []
                for _ in range(30):
                    e.ejec_control(); outputs.append(e.pid1.U)
                self.assertTrue(e.pid1.Hab & 1)
                self.assertTrue(any(u*direction < 0 for u in outputs))
                self.assertTrue(all(u*direction <= 0 for u in outputs))

    def test_release_or_bounce_does_not_resume_cancelled_destination(self):
        hw, e, cmd = self.make_hardware()
        e.cierra_lazo(); e.mueve(100)
        hw.inputs[1].value(1); e.ejec_control()
        for state in (0, 1, 0, 1, 0):
            hw.inputs[1].value(state)
            e.ejec_control()
            self.assert_stopped_closed(hw, e, 2)
        # Liberado el contacto, solo una orden nueva habilita el movimiento.
        cmd.execute({'CMD': 'MUEVE', 'PAR': 100})
        self.assertEqual(e.limit_stop, 0)
        self.assertEqual(e.ref, 100)

    def test_manual_output_is_cut_even_when_commands_mark_axis_busy(self):
        hw, e, cmd = self.make_hardware()
        cmd.execute({'CMD': 'DAX', 'PAR': -700})
        hw.inputs[0].value(1); e.busy = True
        hw._tick(None)
        self.assertEqual(hw.pwm.duty, 0)
        self.assertEqual(e.limit_stop, 1)
        self.assertIsNone(hw.fault)
        e.busy = False
        with self.assertRaises(ValueError):
            cmd.execute({'CMD': 'DAX', 'PAR': -700})
        cmd.execute({'CMD': 'DAX', 'PAR': 700})
        self.assertEqual(hw.pwm.duty, 700)

    def test_limit_cuts_active_pwm_before_reading_encoder(self):
        hw, e, cmd = self.make_hardware()
        e.cierra_lazo(); e.mueve(100); e.actuador(700)
        hw.inputs[1].value(1)
        observed = []

        def sensor():
            observed.append(hw.pwm.duty)
            return 0

        e.fn_lee_sensor = sensor
        hw._tick(None)
        self.assertTrue(observed)
        self.assertEqual(observed[0], 0)
        self.assert_stopped_closed(hw, e, 2)

    def test_both_limits_block_both_directions_without_opening_loop(self):
        hw, e, cmd = self.make_hardware()
        e.cierra_lazo()
        hw.inputs[0].value(1); hw.inputs[1].value(1)
        e.ejec_control()
        self.assert_stopped_closed(hw, e, 3)
        for target in (-100, 100):
            with self.assertRaises(ValueError): e.mueve(target)
            hw.drive(target)
            self.assertEqual(hw.pwm.duty, 0)
        self.assertTrue(e.pid1.Hab & 1)

    def test_duplicate_limits_of_same_direction_are_ored(self):
        hw, e, cmd = self.make_hardware((1, 1, -1))
        for states in ((1, 0, 0), (0, 1, 0), (1, 1, 0)):
            for pin, state in zip(hw.inputs, states): pin.value(state)
            with self.assertRaises(ValueError): e.mueve(100)
            e.mueve(-100)
            self.assertEqual(e.limits.mask, 2)

    def test_tracking_is_cancelled_and_can_be_started_away_from_limit(self):
        hw, e, cmd = self.make_hardware()
        e.cierra_lazo(); e.velSeguimiento = 0.25; e.pon_modo_vel()
        hw.inputs[1].value(1); e.ejec_control()
        self.assert_stopped_closed(hw, e, 2)
        self.assertEqual(e.modo & 1, 0)
        with self.assertRaises(ValueError): e.pon_modo_vel()
        e.velSeguimiento = -0.25; e.pon_modo_vel()
        self.assertEqual(e.limit_stop, 0)
        self.assertTrue(e.modo & 1)
        e.ejec_control()
        self.assertLess(e.ofset, 0)

    def test_guard_blocks_pid_output_even_with_reference_pointing_away(self):
        hw, e, cmd = self.make_hardware()
        e.cierra_lazo(); e.mueve(-100)
        hw.inputs[1].value(1)
        # Un termino derivativo o integral no debe energizar hacia el limite.
        e.actuador(100)
        self.assert_stopped_closed(hw, e, 2)

    def test_active_limit_at_startup_and_reset_cannot_bypass_it(self):
        hw, e, cmd = self.make_hardware()
        hw.inputs[1].value(1)
        with patch.object(config, 'AUTO_CLOSE_LOOP', True): hw.start()
        self.assertTrue(hw.timer.running)
        for action in ('CIERRA', 'RESTABLECE', 'CIERRA'):
            cmd.execute({'CMD': action})
            with self.assertRaises(ValueError): e.mueve(100)
            self.assertEqual(hw.pwm.duty, 0)
        e.mueve(-100)

    def test_recipe_one_limit_on_ent3_and_home_on_ent1(self):
        hw, e, cmd = self.make_hardware((0, 0, 1), (1, 1, 0))
        e.cierra_lazo()
        cmd.execute({'CMD': 'MUEVE', 'PAR': 100})
        hw.inputs[2].value(0)
        e.ejec_control()
        self.assert_stopped_closed(hw, e, 2)
        self.assertEqual(cmd.execute({'CMD': 'EDOJ'})['LIMITS'], 0x040A)
        cmd.execute({'CMD': 'MUEVE', 'PAR': -100})
        self.assertEqual(e.limit_stop, 0)
        self.assertEqual(e.ref, -100)
        self.assertTrue(e.pid1.Hab & 1)

    def test_recipe_two_limits_and_default_home_on_ent3(self):
        with patch.object(config, 'HOME_INPUT_INDEX', 3):
            hw, e, cmd = self.make_hardware((-1, 1, 0), (0, 0, 1))
            cmd.execute({'CMD': 'BUSCAINICIO'})
        self.assertEqual(hw.home_input, 3)
        # Activar otro switch no debe registrarse como sensor de inicio.
        hw.inputs[0].value(0)
        e.ejec_control()
        self.assertEqual(e.lee_estado_busqueda_inicio(), 1)
        hw.encoder.value(123)
        hw.inputs[2].value(1)
        e.ejec_control()
        state = cmd.execute({'CMD': 'EDOJ'})
        self.assertEqual((state['BI'], state['POSINI']), (2, 123))
        self.assertEqual(hw.encoder.value(), 123)  # No puesta a cero automática.
        app = ModbusApp(cmd)
        app.update()
        self.assertEqual(app.client.get_hreg(36), 3)
        self.assertEqual(app.client.get_hreg(32), 0x0101)

    def test_shared_home_and_limit_capture_and_stop_then_retreat(self):
        hw, e, cmd = self.make_hardware()
        e.cierra_lazo()
        cmd.execute({'CMD': 'MUEVE', 'PAR': 100})
        cmd.execute({'CMD': 'BUSCAINICIO', 'ENTRADA': 2})
        hw.encoder.value(37)
        hw.inputs[1].value(1)
        e.ejec_control()
        self.assert_stopped_closed(hw, e, 2)
        state = cmd.execute({'CMD': 'EDOJ'})
        self.assertEqual((state['HOME_INPUT'], state['BI'], state['POSINI']), (2, 2, 37))
        self.assertEqual(state['LIMITS'], 522)
        cmd.execute({'CMD': 'MUEVE', 'PAR': 0})
        self.assertEqual(e.ref, 0)
        self.assertEqual(e.limit_stop, 0)
        self.assertTrue(e.pid1.Hab & 1)

    def test_limit_wait_tracks_actual_position_without_holding_pwm(self):
        hw, e, cmd = self.make_hardware()
        e.cierra_lazo()
        e.mueve(1000)
        hw.encoder.value(100)
        hw.inputs[1].value(1)
        e.ejec_control()
        self.assert_stopped_closed(hw, e, 2)
        # Inercia o desplazamiento externo tras el corte: no volver al objetivo.
        for position in (101, 105, 103):
            hw.encoder.value(position)
            e.ejec_control()
            self.assert_stopped_closed(hw, e, 2)
            self.assertEqual(e.ref, position)
        cmd.execute({'CMD': 'MUEVE', 'PAR': 90})
        self.assertEqual(e.limit_stop, 0)
        self.assertEqual(e.ref, 90)
        self.assertTrue(e.pid1.Hab & 1)

    def test_invalid_limit_configuration_is_rejected(self):
        for roles, levels in (((0, 0), (1, 1, 1)),
                              ((0, 2, 0), (1, 1, 1)),
                              ((0, 0, 0), (1, -1, 1)),
                              ((False, 0, 0), (1, 1, 1))):
            with self.subTest(roles=roles, levels=levels), self.assertRaises(ValueError):
                self.make_hardware(roles, levels)

    def test_modbus_register_32_and_json_report_limits_and_stop(self):
        hw, e, cmd = self.make_hardware()
        app = ModbusApp(cmd)
        e.cierra_lazo(); e.mueve(100)
        hw.inputs[1].value(1); e.ejec_control()
        app.update()
        status = 2 | (2 << 2) | (2 << 8)
        self.assertEqual(cmd.execute({'CMD': 'EDOJ'})['LIMITS'], status)
        uart = app.client._itf._uart
        frame = bytes([23])+struct.pack('>BHH', 3, 32, 1)
        uart.rx.extend(frame+app.client._itf._calculate_crc16(frame))
        app.poll(); clock[0] += 6000; app.poll()
        expected = bytes([23])+struct.pack('>BBH', 3, 2, status)
        self.assertEqual(uart.tx[-1], expected+app.client._itf._calculate_crc16(expected))
        self.assertTrue(app.client.get_hreg(31) & 1)


if __name__ == '__main__':
    unittest.main()
