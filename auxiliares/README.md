# Archivos auxiliares

Esta carpeta contiene material para consultar y ejecutar en la computadora. **No se sube al ESP32.** El firmware está en los archivos `.py` de la raíz del proyecto y en `lib/`.

| Carpeta | Contenido |
| --- | --- |
| [docs/](docs/) | Instalación, cableado, configuración, protocolos y revisión |
| [tests/](tests/) | Pruebas del control y comunicaciones con periféricos simulados |
| [tools/](tools/) | Herramienta para cargar el firmware mediante mpremote |

Ejecuta estos comandos desde la raíz del proyecto, un nivel por encima de esta carpeta:

```sh
python -m unittest discover -s auxiliares/tests -v
python auxiliares/tools/deploy.py --port COM5 --dry-run
python auxiliares/tools/deploy.py --port COM5
```

Sustituye `COM5` por el puerto de tu placa. Para copiar también el archivo opcional `secrets.py`, que se crea en la raíz del proyecto, agrega `--with-secrets`. La herramienta encuentra el firmware a partir de su propia ubicación y no copia documentación, pruebas ni el original.

Comienza con la [guía de instalación](docs/INSTALACION.md). El [README principal](../README.md) enumera exactamente qué archivos cargar y el [registro de pruebas](docs/PRUEBAS.md) distingue las verificaciones en computadora de las pendientes en hardware.

Para asignar ENT1–ENT3 como límites negativos o positivos y consultar su estado Modbus, lee [límites de recorrido](docs/LIMITES.md). Las pruebas específicas se encuentran en `tests/test_limits.py`.

Para elegir el sensor de inicio y combinarlo con uno o dos switches, consulta [INICIO_Y_LIMITES.md](docs/INICIO_Y_LIMITES.md). Incluye ejemplos listos para adaptar en `config.py`, comandos JSON y valores Modbus.
