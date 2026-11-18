#!/usr/bin/env python3
"""Copia explícita del firmware Python; nunca carga OG, docs ni pruebas."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MODULES = ('config.py', 'limits.py', 'control.py', 'hardware.py', 'commands.py',
           'modbus_app.py', 'serial_json.py', 'web_app.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True, help='Puerto USB, por ejemplo COM5')
    parser.add_argument('--with-secrets', action='store_true', help='Copiar secrets.py local')
    parser.add_argument('--dry-run', action='store_true', help='Mostrar sin conectar al ESP32')
    args = parser.parse_args()
    files = [(ROOT/name, ':'+name) for name in MODULES]
    files += [(p, ':'+p.relative_to(ROOT).as_posix())
              for p in sorted((ROOT/'lib').rglob('*.py'))]
    if args.with_secrets:
        files.append((ROOT/'secrets.py', ':secrets.py'))
    # Entradas al final; evitar activar un main incompleto durante la copia.
    files += [(ROOT/name, ':'+name) for name in ('boot.py', 'main.py')]
    for src, _ in files:
        if not src.is_file():
            parser.error('Falta archivo: '+str(src))
    def run(*words):
        command = [sys.executable, '-m', 'mpremote', 'connect', args.port, *words]
        if args.dry_run:
            print(' '.join(command))
        else:
            subprocess.run(command, check=True)
    for directory in (':lib', ':lib/umodbus'):
        # exist_ok no está en todas las variantes uos.mkdir.
        path = directory[1:]
        code = 'import os\ntry:\n os.mkdir(%r)\nexcept OSError as e:\n if e.args[0] != 17: raise' % path
        run('exec', code)
    for src, dst in files:
        run('fs', 'cp', str(src), dst)
    print('Copia terminada. Reinicia la placa cuando termine la instalación.')


if __name__ == '__main__':
    main()
