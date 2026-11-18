# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()

from machine import Pin

oe = Pin(25,Pin.OUT)
oe.value(0)
p12 = Pin(12,Pin.OUT)
p12.value(0)
p14 = Pin(14,Pin.OUT)
p14.value(0)
