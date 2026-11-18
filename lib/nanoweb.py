"""Servidor HTTP mínimo para MicroPython 1.26; rutas explícitas, sin archivos estáticos.

Sustituye el adaptador antiguo de OG que dependía de awrite/aclose.
"""
import asyncio
import json


class Nanoweb:
    def __init__(self, handler, port=80, max_body=2048):
        self.handler = handler
        self.port = port
        self.max_body = max_body
        self.server = None
        self.active = 0

    async def _line(self, reader):
        data = bytearray()
        while len(data) <= 512:
            ch = await reader.read(1)
            if not ch:
                raise EOFError('Fin de conexión')
            data.extend(ch)
            if ch == b'\n':
                return bytes(data)
        raise ValueError('Línea HTTP demasiado larga')

    async def handle(self, reader, writer):
        self.active += 1
        try:
            if self.active > 2:
                return
            try:
                method, url, version = (await asyncio.wait_for_ms(self._line(reader), 3000)).decode().split()
                if version not in ('HTTP/1.0', 'HTTP/1.1') or len(url) > 128:
                    raise ValueError('Solicitud inválida')
                headers = {}
                size = 0
                while True:
                    line = await asyncio.wait_for_ms(self._line(reader), 3000)
                    size += len(line)
                    if size > 2048 or not line:
                        raise ValueError('Cabeceras inválidas')
                    if line == b'\r\n':
                        break
                    key, value = line.decode().split(':', 1)
                    headers[key.lower()] = value.strip()
                if 'transfer-encoding' in headers:
                    raise ValueError('Transfer-Encoding no soportado')
                length = int(headers.get('content-length', '0'))
                if not 0 <= length <= self.max_body:
                    raise ValueError('Cuerpo demasiado grande')
                body = await asyncio.wait_for_ms(reader.readexactly(length), 3000) if length else b''
                code, result = self.handler(method, url.split('?', 1)[0], headers, body)
            except (ValueError, TypeError, KeyError) as exc:
                code, result = 400, {'error': str(exc)}
            except (asyncio.TimeoutError, EOFError):
                code, result = 408, {'error': 'Solicitud incompleta'}
            payload = json.dumps(result).encode()
            reasons = {200: 'OK', 400: 'Bad Request', 404: 'Not Found',
                       405: 'Method Not Allowed', 408: 'Request Timeout'}
            writer.write(('HTTP/1.1 %d %s\r\nContent-Type: application/json\r\n'
                          'Content-Length: %d\r\nConnection: close\r\n\r\n' %
                          (code, reasons.get(code, 'Error'), len(payload))).encode())
            writer.write(payload)
            await writer.drain()
        except OSError:
            pass
        finally:
            self.active -= 1
            writer.close()
            await writer.wait_closed()

    async def run(self):
        self.server = await asyncio.start_server(self.handle, '0.0.0.0', self.port, backlog=2)
        return self.server
