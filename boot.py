"""Estado inicial: PWM y direcciones desenergizados antes de cargar la aplicación."""
from machine import Pin
import config

Pin(config.PWM_PIN, Pin.OUT, value=0)
Pin(config.DIR_A, Pin.OUT, value=0)
Pin(config.DIR_B, Pin.OUT, value=0)
Pin(config.OE_PIN, Pin.OUT, value=config.OE_LEVEL)
