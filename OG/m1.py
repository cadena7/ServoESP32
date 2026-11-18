
from machine import Pin
#import os
import random
import struct
from umodbus import version
from umodbus.serial import ModbusRTU
import ejexesp as drv

class COMX:
    register_definitions = {
        "HREGS": {
            "FN":{
                "register":10,
                "len":3,
                "val":[0,0,0]
            },
            "PARAM":{
                "register":14,
                "len":2,
                "val":[0,0]
            },
            "ESTADO":{
                "register":20,
                "len":12,
                "val":[0,0,0,0,0,0,0,0,0,0,0,0]
            }
        }
    }
    

    def __init__(self, slave_addr):
        self.slave_addr = slave_addr
        self.client = self.config_com()
        drv.init_ejex()
        self.ejex = drv.ejex

    def config_com(self):
        uart_id = 1
        rtu_pins = (32, 35) # (tx,rx)
        slave_addr = self.slave_addr
        baudrate=9600
        client = ModbusRTU(
            addr=slave_addr,
            pins=rtu_pins, 
            baudrate=baudrate,      
            uart_id=uart_id )
        client.setup_registers(registers=self.register_definitions)
        return client

    def lee_hreg(self, regno):
        return self.client.get_hreg(regno)

    def mueve_cb(self, params):
        param = conv_regs_2_int(params[1],params[2])
        print("MUEVE x=", param)
        self.ejex.mueve( param )
        
    def cierra_cb(self):
        print("CIERRA LAZO")
        self.ejex.cierra_lazo()

    def abre_cb(self):
        print("ABRE LAZO")
        self.ejex.abre_lazo()

    def cambia_kp_cb(self,params):
        pf = conv_regs_2_float(params[1],params[2])
        print("KP=", pf)
        self.ejex.pid1.kp = pf

    def cambia_param_pid_cb(self,params):
        fn = params[0]
        pf = conv_regs_2_float(params[1],params[2])
        if fn == 4:
            print("KP=", pf)
            self.ejex.pid1.kp = pf
        if fn == 5:
            print("KI=", pf)
            self.ejex.pid1.ki = pf
        if fn == 6:
            print("KD=", pf)
            self.ejex.pid1.kd = pf
        if fn == 7:
            print("IL=", pf)
            self.ejex.pid1.il = pf
        if fn == 8:
            print("UMAX=", pf)
            self.ejex.pid1.UMax = int(pf)
        
        
    def cambia_param_tray_cb(self,params):
        fn = params[0]
        pf = conv_regs_2_float(params[1],params[2])
        if fn == 20:
            print("ACEL=", pf)
            self.ejex.tr.AcelDeseada = pf
        if fn == 21:
            print("VEL=", pf)
            self.ejex.tr.VelDeseada = pf
        if fn == 22:
            print("VELSEG=", pf)
            self.ejex.velSeguimiento = pf
        if fn == 23:
            print("RANGO=", pf)
            self.ejex.cg.rango = pf
        if fn == 24:
            print("MAG=", pf)
            self.ejex.cg.magnitud = pf
        
    def da_cb(self,params):
        self.abre_cb()
        p = conv_regs_2_int(params[1],params[2])
        print("DA=",p)
        self.ejex.actuador( p )


    def cmds_rst_bi_cbi(self,params):
        fn = params[0]
        if fn == 9:
            print("MODO VEL")
            self.ejex.pon_modo_vel()
        if fn == 10:
            print("QUITA MODO VEL")
            self.ejex.quita_modo_vel()
        if fn == 30:
            print("RST")
            self.ejex.restablece()
        if fn == 31:
            print("PONE BUSCA INICIO")
            self.ejex.inicia_busqueda_inicio()
        if fn == 32:
            print("CANCELA BUSCA INICIO")
            self.ejex.cancela_busqueda_inicio()
        
    def atiende(self, params):
        fn = params[0]
        if fn == 1:
            self.mueve_cb(params)
        if fn == 2:
            self.cierra_cb()
        if fn == 3:
            self.abre_cb()
        if fn in [4,5,6,7,8]:
            self.cambia_param_pid_cb(params)
        if fn in [20,21,22,23,24] :
            self.cambia_param_tray_cb(params)
        if fn in [9,10,30,31,32] :
            self.cmds_rst_bi_cbi(params)
        if fn == 50:
            self.da_cb(params)
                
        # pone en 0 la fn fn=0
        self.client.set_hreg(10,[0])
        

def pinta_info(com):
    print("OK")
    d = com.ejex.dict_estado()
    print("X=",d["X"], "XT=", d["XT"], "U=",d["U"])

def lee_hrd_actualiza_modbus_regs( com ):
    n1 = random.randint(1,2)
    n2 = random.randint(0,65000)
    edo = com.ejex.dict_estado()
    (x1,x2) = conv_int_2_regs( int( edo["X"] ) )
    (xt1,xt2) = conv_int_2_regs( int( edo["XT"] ) )
    (bi1,bi2) = conv_int_2_regs( int( edo["BI"] ) )
    (posi1,posi2) = conv_int_2_regs( int( edo["POSINI"] ) )
    (u1,u2) = conv_int_2_regs( int( edo["U"] ) )
    modo = edo["MODO"]
    hab = edo["HAB"]
    r1 = (x1,x2,xt1,xt2,bi1,bi2,posi1,posi2,u1,u2,modo,hab )
    com.client.set_hreg(20,r1)
    

def conv_regs_2_int(p0,p1):
    px = struct.pack('>HH',p0,p1)
    param = struct.unpack('>l',px)[0]
    return param

def conv_regs_2_float(p0,p1):
    px = struct.pack('>HH',p0,p1)
    paramf = struct.unpack('>f',px)[0]
    return paramf
    
def conv_int_2_regs(p):
    r = struct.pack(">l",p)
    r1 = struct.unpack(">HH", r)
    return r1

def conv_float_2_regs(nf):
    regs = struct.pack('>f', nf )
    r1 = struct.unpack('>HH',regs )
    return r1


    
    

def interactua_con_hrd(com):
    fn = com.client.get_hreg(10)
    if fn == 0 :
        return
    p0 = com.client.get_hreg(11)
    p1 = com.client.get_hreg(12)
    com.atiende((fn,p0,p1))
    return
    paramf = 0.0
    param = 0
    if fn == 1:
        param = conv_regs_2_int(p0,p1)
        com.ejex.mueve( param )
    if fn == 2 :
        paramf = conv_regs_2_float(p0,p1)
    print("fn=",fn," ",p0," ",p1," ",param, " ",paramf)
    com.client.set_hreg(10,[0])
    
    
def test_loop(comx):
    dt=0
    oe = Pin(25,Pin.OUT)
    print("Baja OE")
    oe.value(0)
    while True:
        try:
            dt = dt + 1
            if dt > 100 :
                pinta_info(comx)
                dt=0
                lee_hrd_actualiza_modbus_regs( comx )
            result = comx.client.process()
            if result:
                #comx.checa_estado_y_actua()
                lee_hrd_actualiza_modbus_regs( comx )
                interactua_con_hrd( comx )
        except KeyboardInterrupt:
            print('KeyboardInterrupt, stopping client...')
            break
        except Exception as e:
            print('Exception during execution: {}'.format(e))

def el_main():            
    com = COMX(20) # el 20 es el id del device modbus
    test_loop(com)

if __name__ == "__main__":
    el_main()
