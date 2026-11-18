"""JSON por línea en UART0/USB; lectura acotada y sin bloquear el lazo principal."""
import sys
import select
import json


class SerialJSON:
    def __init__(self, commands, max_length=2048):
        self.commands = commands
        self.max_length = max_length
        self.buffer = ''
        self.discard = False
        self.poller = select.poll()
        self.poller.register(sys.stdin, select.POLLIN)

    def feed(self, char):
        if char == '\n':
            line, self.buffer = self.buffer, ''
            if self.discard:
                self.discard = False
                return {'error': 'Línea demasiado larga'}
            if not line.strip():
                return None
            try:
                return self.commands.execute(json.loads(line))
            except (ValueError, TypeError) as exc:
                return {'error': str(exc)}
        if not self.discard:
            if len(self.buffer) >= self.max_length:
                self.buffer = ''
                self.discard = True
            else:
                self.buffer += char
        return None

    def poll(self):
        for _ in range(32):
            if not self.poller.poll(0):
                break
            char = sys.stdin.read(1)
            if not char:
                break
            result = self.feed(char)
            if result is not None:
                # Una línea por respuesta, también para EDOJ y DAMEDATOS.
                print(json.dumps(result))
