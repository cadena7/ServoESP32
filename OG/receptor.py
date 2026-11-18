from machine import Pin, UART
import time

# UART2: libre para GPIO17 (TX) y GPIO16 (RX)
uart = UART(2, baudrate=115200, tx=17, rx=16)

led = Pin(2, Pin.OUT)  # LED en GPIO2

for i in range(5):
    led.on()
    time.sleep(0.5)
    led.off()




while True:
    if uart.any() > 0:
        ch = uart.readline()
        print("Recibido:", ch)

        if ch and b'on' in ch:
            uart.write(b'Led On!\n')
            led.on()
        elif ch and b'off' in ch:
            uart.write(b'Led Off!\n')
            led.off()
        else:
            uart.write(b'Recibi: ' + ch + b'\n')
    time.sleep(0.1)