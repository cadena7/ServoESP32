"""Rutas de la variante web original, con respuestas JSON completas."""
import json
import time
import gc


class WebAPI:
    def __init__(self, commands):
        self.commands = commands
        self.started = time.ticks_ms()

    def handle(self, method, path, headers, body):
        if path not in ('/', '/ping', '/edo', '/datos', '/post'):
            return 404, {'error': 'Ruta desconocida'}
        if method != ('POST' if path == '/post' else 'GET'):
            return 405, {'error': 'Método no permitido'}
        if path == '/post':
            if headers.get('content-type', '').split(';')[0].strip() != 'application/json':
                raise ValueError('Usar Content-Type: application/json')
            return 200, self.commands.execute(json.loads(body.decode()))
        if path == '/edo':
            return 200, self.commands.execute({'CMD': 'EDOJ'})
        if path == '/datos':
            return 200, self.commands.execute({'CMD': 'DAMEDATOS'})
        if path == '/ping':
            return 200, {'pong': True, 'heap_free': gc.mem_free(),
                         'uptime_ms_modulo': time.ticks_diff(time.ticks_ms(), self.started)}
        return 200, {'project': 'ServoESP32', 'routes': ['/ping', '/edo', '/datos', '/post']}
