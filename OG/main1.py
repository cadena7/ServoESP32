import machine
import json
import os
import gc
import network
import time
import sys
import asyncio
from nanoweb import HttpError, Nanoweb, send_file
from ubinascii import a2b_base64 as base64_decode

import ejex
  

def do_connect(ssid, pasw):
    wlan = network.WLAN()
    wlan.active(True)
    if not wlan.isconnected():
        print('connecting to network...')
        wlan.connect(ssid, pasw)
        while not wlan.isconnected():
            machine.idle()
    print('network config:', wlan.ipconfig('addr4'))



def get_time():
    uptime_s = int(time.ticks_ms() / 1000)
    uptime_h = int(uptime_s / 3600)
    uptime_m = int(uptime_s / 60)
    uptime_m = uptime_m % 60
    uptime_s = uptime_s % 60
    return (
        '{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(*time.localtime()),
        '{:02d}h {:02d}:{:02d}'.format(uptime_h, uptime_m, uptime_s),
    )

async def api_send_response(request, code=200, message="OK"):
    await request.write("HTTP/1.1 %i %s\r\n" % (code, message))
    await request.write("Content-Type: application/json\r\n\r\n")
    await request.write('{"status": true}')


ejex.inicia()
ejex.inicia_mod_control()
com = ejex.ComJ(ejex.ejex)

    
async def post_data(request):
    """Post data example

    Display the data sent with the request.

    You can reach this entrypoint with curl:

    By JSON:
        curl -d '{"key1":"value1", "key2":"value2"}' \
            -H "Content-Type: application/json" -X POST http://URL

    Or by url encoded data:
        curl -d "param1=value1&param2=value2" -X POST http://URL

    Because of the very simpler way the data is decoded in this example,
    I recommend you to use the JSON way to send data: it is more safe.

    If you do not want to use the JSON way, it is better to decode
    the data (multiple value for a same key, url encoded string, etc...).
    See https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/POST
    """
    await request.write("HTTP/1.1 200 Ok\r\n")

    if request.method != "POST":
        raise HttpError(request, 501, "Not Implemented")

    try:
        content_length = int(request.headers['Content-Length'])
        content_type = request.headers['Content-Type']
    except KeyError:
        raise HttpError(request, 400, "Bad Request")

    data = (await request.read(content_length)).decode()

    if content_type == 'application/json':
        data = json.loads(data)
        com.checa_cmd( data )
        print(data)
    elif content_type == 'application/x-www-form-urlencoded':
        for chunk in data.split('&'):
            key, value = chunk.split('=', 1)
            print('%s = %s' % (key, value))


async def index(request):
    await request.write(b"HTTP/1.1 200 Ok\r\n\r\n")
    await request.write("Hola Mundo\n")


naw = Nanoweb(80)

# Declare route from a dict
naw.routes = {
    '/': index,
    '/post': post_data,
}

# Declare route directly with decorator
@naw.route("/ping")
async def ping(request):
    await request.write("HTTP/1.1 200 OK\r\n\r\n")
    await request.write("pong")
    await request.write("\n[MEMORY]")
    await request.write(f"Heap Allocated:     {gc.mem_alloc()} bytes")
    await request.write(f"Heap Free:          {gc.mem_free()} bytes")
    await request.write(f"{get_time()}")

@naw.route("/edo")
async def edo(request):
    await request.write("HTTP/1.1 200 OK\r\n\r\n")
    res = json.dumps(com.eje.dict_estado())
    await request.write(f"{res}")

@naw.route("/datos")
async def edo(request):
    await request.write("HTTP/1.1 200 OK\r\n\r\n")
    for j in range(200):
        dat = [ com.eje.muestras[j*10 + k] for k in range(10)]
        await request.write( f"{dat},\n" )
    await request.write(b"OK\m")


async def loop_recibe_serie():
    print("Imicia task recibe serie")
    linea = ""
    while True:
        rec = ejex.recibe()
        if rec is "" :
            await asyncio.sleep(.01)
        linea = linea + rec
        if rec == '\n' :
            print(f"Procesa {linea}")
            try:
                obj = json.loads(linea)
            except:
                obj = None
            if obj is not None:
                com.checa_cmd( obj )
            linea=""
        await asyncio.sleep(.01)
        
    
def el_main():
    do_connect('labo1','01239876')
    loop = asyncio.get_event_loop()
    loop.create_task(naw.run())
    loop.create_task(loop_recibe_serie())
    loop.run_forever()
    

if __name__ == "__main__" :
    el_main()
    print("Aborto el_main")

    
