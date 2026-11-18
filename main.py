"""Entrada única de ServoESP32. Ctrl-C y errores apagan el actuador."""
import asyncio
import config as c


async def connect_wifi():
    import network
    import time
    ssid, password = c.WIFI_SSID, c.WIFI_PASSWORD
    try:
        import secrets
        ssid, password = secrets.WIFI_SSID, secrets.WIFI_PASSWORD
    except ImportError:
        pass
    if not ssid:
        raise ValueError('Configurar WIFI_SSID antes de habilitar web')
    wlan = network.WLAN(network.STA_IF)
    try:
        wlan.active(True)
        if not wlan.isconnected():
            wlan.connect(ssid, password)
        start = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) >= c.WIFI_TIMEOUT_MS:
                raise OSError('Timeout Wi-Fi')
            await asyncio.sleep_ms(100)
        print('IP:', wlan.ipconfig('addr4'))
        return wlan
    except BaseException:
        wlan.active(False)
        raise


async def optional_web(commands):
    """Wi-Fi/HTTP en segundo plano; sus fallos no detienen el control."""
    wlan = web = None
    try:
        wlan = await connect_wifi()
        from nanoweb import Nanoweb
        from web_app import WebAPI
        web = Nanoweb(WebAPI(commands).handle, c.WEB_PORT, c.MAX_REQUEST_BYTES)
        await web.run()
        while True:
            await asyncio.sleep_ms(1000)
    except Exception as exc:
        print('Web no disponible; control continua:', exc)
    finally:
        try:
            if web and web.server:
                web.server.close()
                await web.server.wait_closed()
        finally:
            if wlan is not None:
                wlan.active(False)


async def run(hw):
    from commands import Commands
    commands = Commands(hw.eje, hw)
    # Preparar comunicaciones locales antes de permitir AUTO_CLOSE_LOOP.
    modbus = serial = web_task = None
    if c.MODBUS_ENABLED:
        from modbus_app import ModbusApp
        modbus = ModbusApp(commands)
    if c.SERIAL_JSON_ENABLED:
        from serial_json import SerialJSON
        serial = SerialJSON(commands, c.MAX_REQUEST_BYTES)
    try:
        hw.start()
        print('ServoESP32 / MicroPython 1.26 / Modbus ID', c.MODBUS_ADDRESS)
        if c.WEB_ENABLED:
            web_task = asyncio.create_task(optional_web(commands))
        while True:
            if hw.fault is not None:
                raise RuntimeError('Fallo del control: ' + str(hw.fault))
            if modbus:
                modbus.poll()
            if serial:
                serial.poll()
            await asyncio.sleep_ms(1)
    finally:
        hw.stop()
        if web_task is not None:
            web_task.cancel()
            try:
                await web_task
            except asyncio.CancelledError:
                pass


def main():
    from hardware import Hardware
    hw = Hardware()
    try:
        asyncio.run(run(hw))
    finally:
        hw.stop()
        asyncio.new_event_loop()


if __name__ == '__main__':
    main()
