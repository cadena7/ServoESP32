"""El control local arranca independientemente de Wi-Fi y HTTP."""
import asyncio
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import main as app


async def yield_ms(ms):
    await asyncio.sleep(0)


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def check_local_control(self, wifi, web_enabled=True):
        hw = Mock(eje=object(), fault=None)
        serial = Mock()
        events = []
        polls = [0]
        hw.start.side_effect = lambda: events.append('start')

        def poll():
            polls[0] += 1
            if polls[0] == 4:
                raise RuntimeError('Fin de prueba')

        serial.poll.side_effect = poll
        serial_module = types.SimpleNamespace(SerialJSON=Mock(return_value=serial))
        modbus = Mock()
        modbus_module = types.SimpleNamespace(ModbusApp=Mock(return_value=modbus))

        async def connect():
            events.append('wifi')
            return await wifi()

        with patch.multiple(app.c, WEB_ENABLED=web_enabled, MODBUS_ENABLED=True,
                            SERIAL_JSON_ENABLED=True), \
                patch('commands.Commands', return_value=Mock()), \
                patch.dict(sys.modules, serial_json=serial_module,
                           modbus_app=modbus_module), \
                patch.object(app, 'connect_wifi', side_effect=connect), \
                patch.object(asyncio, 'sleep_ms', yield_ms, create=True):
            with self.assertRaisesRegex(RuntimeError, 'Fin de prueba'):
                await asyncio.wait_for(app.run(hw), 2)
        self.assertEqual(events[0], 'start')
        self.assertEqual(serial.poll.call_count, 4)
        self.assertEqual(modbus.poll.call_count, 4)
        hw.stop.assert_called_once()
        return events

    async def test_wifi_pending_does_not_block_local_control(self):
        cancelled = []

        async def pending():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

        events = await self.check_local_control(pending)
        self.assertIn('wifi', events)
        self.assertEqual(cancelled, [True])

    async def test_wifi_failures_do_not_stop_local_control(self):
        for error in (ValueError('Sin SSID'), OSError('Timeout Wi-Fi'),
                      ImportError('network no disponible')):
            with self.subTest(error=str(error)):
                await self.check_local_control(AsyncMock(side_effect=error))

    async def test_wifi_disabled_is_not_accessed(self):
        wifi = AsyncMock()
        events = await self.check_local_control(wifi, web_enabled=False)
        wifi.assert_not_awaited()
        self.assertEqual(events, ['start'])

    async def test_http_failure_does_not_stop_local_control(self):
        wlan = Mock()
        web = Mock(server=None)
        web.run = AsyncMock(side_effect=OSError('Puerto ocupado'))
        with patch.dict(sys.modules,
                        nanoweb=types.SimpleNamespace(Nanoweb=Mock(return_value=web)),
                        web_app=types.SimpleNamespace(WebAPI=Mock())):
            await self.check_local_control(AsyncMock(return_value=wlan))
        wlan.active.assert_called_once_with(False)

    async def test_http_success_is_closed_on_shutdown(self):
        wlan = Mock()
        web = Mock()
        web.run = AsyncMock()
        web.server.wait_closed = AsyncMock()
        with patch.dict(sys.modules,
                        nanoweb=types.SimpleNamespace(Nanoweb=Mock(return_value=web)),
                        web_app=types.SimpleNamespace(WebAPI=Mock())):
            await self.check_local_control(AsyncMock(return_value=wlan))
        web.run.assert_awaited_once()
        web.server.close.assert_called_once()
        web.server.wait_closed.assert_awaited_once()
        wlan.active.assert_called_once_with(False)

    async def test_real_connection_timeout_disables_radio(self):
        wlan = Mock()
        wlan.isconnected.return_value = False
        network = types.SimpleNamespace(STA_IF=0, WLAN=Mock(return_value=wlan))
        secrets = types.SimpleNamespace(WIFI_SSID='prueba', WIFI_PASSWORD='prueba')
        with patch.dict(sys.modules, network=network, secrets=secrets), \
                patch.object(app.c, 'WIFI_TIMEOUT_MS', 15000), \
                patch('time.ticks_ms', side_effect=[0, 15000], create=True), \
                patch('time.ticks_diff', side_effect=lambda a, b: a-b, create=True):
            with self.assertRaisesRegex(OSError, 'Timeout'):
                await app.connect_wifi()
        self.assertEqual(wlan.active.call_args_list[-1].args, (False,))


if __name__ == '__main__':
    unittest.main()
