#import os, machine
import uselect
import sys
import time
import json
import array
from machine import reset
from machine import Pin, Timer,Encoder, PWM


## ---------------------------



def mi_abs(val):
    if val < 0 :
        val = -val
    return val

def signo(val):
    if val >= 0 :
        return 1.0
    return -1.0

def fn_saturacion(val, sat):
    return min( sat,max(val,-sat))


class PidControl:
    kp = 0.001
    ki = 0.0
    kd = 0.0
    IVal = 0.0
    il = 1000.0
    ErrMax = 4000
    ErrAnt = 0
    UMax = 4000
    Hab = 0x1
    U = 0
        
    def __init__(self):
        pass

    
    def ejec(self, err):
        errSat = fn_saturacion( err, self.ErrMax)
        u_p = self.kp*errSat

        if self.Hab & 2 != 0 :
            u_i = self.IVal + self.ki*errSat
            self.IVal = fn_saturacion(u_i, self.il)
        else:
            self.IVal = 0.0
            u_i = 0.0

        u_d = self.kd*( errSat - self.ErrAnt )
        self.ErrAnt = errSat
        u_p = u_p + u_d + u_i
        self.U = int( fn_saturacion( u_p, self.UMax) )
        return self.U

    def restablece(self):
        self.IVal = 0.0
        self.ErrAnt = 0
        self.U = 0


class Tray:
    VelDeseada = 1.0
    AcelDeseada = 0.05
    Posicion = 0
    PosicionDeseada = 0
    VelActual = 0
    ErrorMinimo = 10
    
    def __init__(self):
        pass

    def config_trayectoria(self,vel,acel,errorMinimo):
        self.VelDeseada = vel
        self.AcelDeseada = acel
        self.Posicion = 0
        self.PosicionDeseada = 0
        self.VelActual = 0
        self.ErrorMinimo = errorMinimo


    def trapecio(self):
        vel = self.VelActual
        Error =  self.PosicionDeseada - self.Posicion

        if mi_abs(Error) <= self.ErrorMinimo or mi_abs(Error) <= mi_abs(vel) :
            self.VelActual = 0
            self.Posicion = self.PosicionDeseada
            return

        PosParar = self.VelActual  / ( 2* self.AcelDeseada )
        PosParar = PosParar * vel
        if PosParar > mi_abs(Error) : #// desacelerar
            if self.VelActual >= 0 :
                self.VelActual -= self.AcelDeseada
                if self.VelActual < 0 :
                    self.VelActual = 0.1
            else:
                self.VelActual += self.AcelDeseada
                if self.VelActual > 0 :
                    self.VelActual = -0.1

        else: ## acelerar
            self.VelActual += signo(Error) * self.AcelDeseada
            self.VelActual = fn_saturacion(self.VelActual,self.VelDeseada)

        self.Posicion += self.VelActual
        self.Posicion = int( self.Posicion )


class CGAIN:
    rango = 0.0
    magnitud = 0.01
    def __init__(self):
        pass

    def calcula(self, err):
        val = err
        if err < 0:
            val = -err
        sal = 0.0
        rango = self.rango
        magnitud = self.magnitud
        if val <= rango :
            val = 5 * ( 1.0 - val/rango ) - 3.0
            x = 1.0 + val / 256.0
            x *= x; x *= x; x*= x; x *= x
            x *= x; x *= x; x*= x; x *= x
            if x > 7.0 :
                x = 7.33
            sal = (x * magnitud) / 7.33
        return sal

    
PREPARA_BUSCA_INICIO = 1
HALLO_INICIO = 2
    
class PinInicio:
    def __init__(self, pin, fn_lee_cuenta ):
        #self.pin = Pin(pin, Pin.IN)
        self.pin = pin
        self.edo = 0
        self.val = 0
        self.cuenta_inicio = 0
        self.val_inicial = 0
        self.fn_lee_cuenta = fn_lee_cuenta

    def concluye_busca_inicio(self):
        self.edo = 0
        
    def prepara_busca_inicio(self):
        self.edo = PREPARA_BUSCA_INICIO
        self.val_inicial = self.pin.value()

    def checa_cambio_estado(self):
        if self.edo != PREPARA_BUSCA_INICIO :
            return
        edo_pin = self.pin.value()
        if edo_pin != self.val_inicial :
            self.cuenta_inicio = self.fn_lee_cuenta()
            self.edo = HALLO_INICIO




    
MODO_POS = 0
MODO_VEL = 1

class Eje:
    ref = 0
    pos = 0
    velSeguimiento = 0.0
    modo = 0
    ofset = 0.0
    muestras = array.array('i',  (0 for _ in range(2000)))
    cuentaDatos = 0
    errorMaxParar = 1000
    zonaMuerta = 2
    
    def __init__(self, pinInic):
        self.cg = CGAIN()
        self.cg.rango = 500
        self.cg.magnitud = 1.0
        self.tr = Tray()
        self.tr.config_trayectoria( 4.5,0.05,10.0)
        self.pid1 = PidControl()
        self.fn_lee_sensor = None
        self.fn_actuador = None
        self.fn_limpia_encoder = None
        self.pinInicio = PinInicio(pinInic, self.eje_lee_pos )

    def cambia_zona_muerta(self, val):
        self.zonaMuerta = val
        
    def cambia_error_max_parar(self, val):
        self.errorMaxParar = val
        
    def inicia_busqueda_inicio(self):
        self.pinInicio.prepara_busca_inicio()

    def cancela_busqueda_inicio(self):
        self.pinInicio.concluye_busca_inicio()

    def checa_busqueda_inicio(self):
        self.pinInicio.checa_cambio_estado()

    def lee_pos_inicio(self):
        ### regresa la posicion donde encontro el cambio
        ## de estado del pin de inicio
        return self.pinInicio.cuenta_inicio

    def lee_estado_busqueda_inicio(self):
        return self.pinInicio.edo

        
    def eje_lee_pos(self):
        return self.pos
    
    def mueve(self, pos):
        self.ref = pos
        self.ofset = 0.0
        
    def calcula_ref(self):
        #global MODO_POS
        global MODO_VEL
        if (self.modo & MODO_VEL) != 0 :
            self.ofset += self.velSeguimiento
        refx = self.ref + self.ofset
        self.tr.PosicionDeseada = refx

    def lee_sensor(self):
        if self.fn_lee_sensor is None:
            return 0
        return self.fn_lee_sensor()

    def limpia_encoder(self):
        if self.fn_limpia_encoder is None:
            return 0
        return self.fn_limpia_encoder()

    
    def actuador(self, u):
        if self.fn_actuador is None:
            return
        self.fn_actuador(u)

    def ejec_control(self):
        self.calcula_ref()
        self.checa_busqueda_inicio()
        refx = self.tr.Posicion
        self.pos = self.lee_sensor()
        err = refx - self.pos
        ## el cambio de ganancia
        err1 = err
        magErr = abs(err1)
        if (self.errorMaxParar > 0 )  and (magErr > self.errorMaxParar) :
            self.pid1.Hab &= 0xfffe;
            self.actuador(0)
        if self.cg.rango != 0 :
            kp1 = self.cg.calcula(err)
            err = (1.0 + kp1)*err
        # captura datos
        if self.cuentaDatos < 1998 :
            self.muestras[self.cuentaDatos] = self.pos
            self.cuentaDatos += 1
            self.muestras[self.cuentaDatos] = int(err1)
            self.cuentaDatos += 1

        if magErr < self.zonaMuerta :
            err = 0            
        if (self.pid1.Hab & 1) != 0 :
            u = self.pid1.ejec(err)
            self.actuador(u)
        if self.tr.VelActual == 0 :
            self.pid1.Hab |= 0x2
        else:
            self.pid1.Hab = (self.pid1.Hab | 2) ^ 2
        self.tr.trapecio()
        

    def restablece(self):
        self.abre_lazo()
        self.limpia_encoder()

        

    def cierra_lazo(self):
        self.tr.VelActual = 0
        self.tr.PosicionDeseada = self.lee_sensor()
        self.tr.Posicion = self.tr.PosicionDeseada
        self.ref =  self.tr.PosicionDeseada
        self.ofset = 0.0
        self.pid1.Hab = 1

    def abre_lazo(self):
        self.pid1.Hab = 0
        time.sleep(.02)
        self.pid1.U = 0
        self.actuador(0)

    def pon_modo_vel(self):
        global MODO_VEL
        self.modo = self.modo | MODO_VEL
        

    def quita_modo_vel(self):
        global MODO_VEL
        self.modo = (self.modo | MODO_VEL) ^ MODO_VEL
        
        
    def dict_estado(self):
        d = {}
        d['X'] = self.pos
        d['XT'] = self.tr.Posicion
        d['XD'] = self.ref
        d['U'] = self.pid1.U
        d['E'] =  self.tr.Posicion- self.pos
        d['HAB'] = self.pid1.Hab
        d['MODO'] = self.modo
        d['VSEG'] = self.velSeguimiento
        d['BI'] = self.pinInicio.edo
        d['POSINI'] = self.pinInicio.cuenta_inicio
        d['ID'] = "93DADF728BA062F1"          
        return d
            
        

## EL encoder 0
f_a = Pin(16,Pin.IN)
f_b = Pin(17,Pin.IN)
enc0 = Encoder(0, phase_a=f_a, phase_b=f_b, phases=4)

def lee_encoder_0():
    global enc0
    return enc0.value()

# Los pins de entrada
ent1 = Pin(33, Pin.IN)
ent2 = Pin(4, Pin.IN)
ent3 = Pin(19, Pin.IN)
entind = Pin(18, Pin.IN)

# Los pins de salida
sal1 = Pin( 21, Pin.OUT)
sal2 = Pin( 22, Pin.OUT)
sal3 = Pin( 23, Pin.OUT)

sal1.value(0)
sal2.value(0)
sal3.value(0)

def lee_entradas_0():
    val = (0,1)[ent1.value()]
    val = val | (0,2)[ent2.value()]
    val = val | (0,4)[ent3.value()]
    val = val | (0,8)[entind.value()]
    return val

def setbit1():
    sal1.value(1)

def setbit2():
    sal2.value(1)

def setbit3():
    sal3.value(1)

def clrbit1():
    sal1.value(0)

def clrbit2():
    sal2.value(0)

def clrbit3():
    sal3.value(0)

    

## El actuador 0
# s1 = Pin(12,Pin.OUT) # Rev 0
s1 = Pin(26,Pin.OUT) # Rev B
s2 = Pin(14,Pin.OUT)
pwm0 =  PWM(Pin(27), 10000, duty_u16=0)

def actuador_0(val):
    if val < 0 :
        val = -val
        s1.value(1)
        s2.value(0)
    else:
        s1.value(0)
        s2.value(1)
    pwm0.duty_u16( val ) 

        
ejex = Eje(ent1) #usando ent como el pin de inicio
#pindeb = Pin(13, Pin.OUT)




def tarea_control(arg):
    global ejex
    #pindeb.value(1)
    ejex.ejec_control()
    #pindeb.value(0)
    

def limpia_encoder_0():
    enc0.value(0)
    
def inicia_mod_control():
    global ejex
    #enc0.value(0)
    limpia_encoder_0()
    actuador_0(0)
    ejex.fn_lee_sensor = lee_encoder_0
    ejex.fn_actuador = actuador_0
    ejex.fn_limpia_encoder = limpia_encoder_0
    ejex.tr.PosicionDeseada = 0
    ejex.pid1.kp = 0.1
    ejex.pid1.ki = 0.001
    ejex.pid1.kd = 0.023
    ejex.pid1.il = 1000.0
    ejex.pid1.UMax = 50000
    ejex.pid1.ErrMax = 4000
    ejex.pid1.Hab = 0x1
    tim0 = Timer(0)
    tim0.init(period=10, mode=Timer.PERIODIC, callback=tarea_control)
    #tim1 = Timer(1)
    #tim1.init(period=1000, mode=Timer.PERIODIC, callback=tarea_pinta)

    
def p(e):
    posd = e.tr.Posicion
    ref = e.ref
    pos = e.pos
    vd = e.tr.VelActual
    u = e.pid1.U
    err = posd - pos
    print(f"XT:{posd} X:{pos} XD:{ref} VX:{vd} UX:{u} EX={err}")

def tarea_pinta(arg):
    global ejex
    p(ejex)
    

def test1():
    t1 = Tray()
    t1.config_trayectoria( 4.5,0.00096,10.0)

    t1.Posicion = 99000
    t1.PosicionDeseada = 100000
    
    for i in range(200):
        t1.trapecio()
        print(f"i={i} P:{t1.Posicion} V:{t1.VelActual}")
  
    t1.PosicionDeseada = 99000;

    for i in range(200):
        t1.trapecio()
        print(f"i={i} P:{t1.Posicion} V:{t1.VelActual}")

    pid1 = PidControl()
    pid1.kp = 1.0
    pid1.ki = 0.001
    pid1.kd = 0.023
    pid1.il = 1000.0
    pid1.UMax = 3000
    pid1.ErrMax = 4000
    pid1.Hab = 0x1

    # Prueba de tiempo de calculo
    t1.PosicionDeseada = 100000
    ref = 100000

    for i in range(1000):
        #pindeb.value(1)
        t1.trapecio()
        sal = pid1.ejec(ref - t1.Posicion)
        #pindeb.value(0)
        

## ---------------------------


## COM
## -------------------



def manda(st):
    nt = 0
    n = len(st)
    for c in st:
        sys.stdout.write(c)
        nt = nt+1
        if nt > 10 :
            nt = 0
            time.sleep(.001)

def recibe(spoll):
    c = (sys.stdin.read(1) if spoll.poll(0) else "")
    return c
    

def inicia():
    pass


def recibe_linea(spoll):
    linea = ""
    while True:
        rec = recibe(spoll)
        if rec is "":
            time.sleep(.01)
            continue
        linea = linea+rec
        if rec == '\n':
            break
    return linea


class ComJ:
    def __init__(self, eje=None):
        self.eje = eje
        spoll = uselect.poll()
        spoll.register(sys.stdin, uselect.POLLIN)
        self.spoll = spoll

    def recibe_js(self):
        linea = recibe_linea(self.spoll)
        try:
            obj = json.loads( linea )
        except:
            obj = None
        if obj is not None:
            self.checa_cmd(obj)
        

    def checa_cmd(self, obj):
        if "CMD" in obj:
            #manda(f'DECOD:{obj["CMD"]}')
            if obj["CMD"] == "MUEVE" :
                self.cmd_mueve(obj)
            if obj["CMD"] == "EDOJ" :
                self.cmd_estado(obj)
            if obj["CMD"] == "CAMBIA" :
                self.cmd_cambia(obj)
            if obj["CMD"] == "DAX" :
                self.cmd_dax(obj)
            if obj["CMD"] == "CIERRA" :
                self.cmd_cierra(obj)
            if obj["CMD"] == "HABSEG" :
                self.cmd_hab_seg(obj)
            if obj["CMD"] == "DESHABSEG" :
                self.cmd_deshab_seg(obj)
            if obj["CMD"] == "RESTABLECE" :
                self.cmd_reset(obj)
            if obj["CMD"] == "DAMEDATOS" :
                self.cmd_dame_datos()
            if obj["CMD"] == "RCD" :
                self.cmd_reset_cuenta_datos()
            if obj["CMD"] == "BUSCAINICIO" :
                self.cmd_prep_busca_inicio()
            if obj["CMD"] == "CANCELA" :
                self.cmd_cancela_busca_inicio()
            if obj["CMD"] == "MRST" :
                reset()
            
    def cmd_prep_busca_inicio(self):
        self.eje.inicia_busqueda_inicio()

    def cmd_cancela_busca_inicio(self):
        self.eje.cancela_busqueda_inicio()

    def cmd_reset_cuenta_datos(self):
        self.eje.cuentaDatos = 0

    def cmd_reset(self,obj):
        if  self.eje is None:
            ## Bo hace nada
            return
        self.eje.restablece()
        
                
    def cmd_hab_seg(self,obj):
        if  self.eje is None:
            ## Bo hace nada
            return
        self.eje.pon_modo_vel()
        
        
    def cmd_deshab_seg(self,obj):
        if  self.eje is None:
            ## Bo hace nada
            return
        self.eje.quita_modo_vel()


    def cmd_cambia(self,obj):
        if  self.eje is None:
            ## Bo hace nada
            return
        if "KP" in obj:
            self.eje.abre_lazo()
            self.eje.pid1.kp = obj['KP']
            self.eje.cierra_lazo()
        if "KI" in obj:
            self.eje.pid1.ki = obj['KI']
        if "KD" in obj:
            self.eje.pid1.kd = obj['KD']
        if "IL" in obj:
            self.eje.pid1.il = obj['IL']
        if "EMAX" in obj:
            self.eje.pid1.ErrMax = obj['EMAX']
        if "HAB" in obj:
            self.eje.pid1.Hab = obj['HAB']
        if "ACEL" in obj:
            self.eje.tr.AcelDeseada = obj['ACEL']
        if "VEL" in obj:
            self.eje.tr.VelDeseada = obj['VEL']
        if "EMIN" in obj:
            self.eje.tr.ErrorMinimo = obj['EMIN']
        if "VELSEG" in obj:
            self.eje.velSeguimiento = obj['VELSEG']
        if "RANGO" in obj:
            self.eje.cg.rango = obj['RANGO']
        if "MAGNITUD" in obj:
            self.eje.cg.magnitud = obj['MAGNITUD']
            



    def cmd_dax(self, obj):
        if "PAR" in obj and self.eje is not None:
            self.eje.abre_lazo()
            self.eje.actuador( obj['PAR'] )

    def cmd_cierra(self,obj):
        if self.eje is not None:
            self.eje.cierra_lazo()

    def cmd_dame_datos(self):
        d = {}
        l = []
        for i in range(2000):
            l.append( self.eje.muestras[i] )
        d["DATOS"] = l
        manda(json.dumps(d))
                
    def cmd_mueve(self,obj):
        #manda('CMD MUEVE\n')
        #manda(json.dumps(obj))
        if "PAR" in obj and self.eje is not None:
            self.eje.mueve( obj["PAR"] )

    def cmd_estado(self,obj):
        #manda("ESTADO\n")
        if  self.eje is not None:
            d = self.eje.dict_estado()
            manda(json.dumps(d))
            

## COM FIN
## -------------------


def init_ejex():
    inicia()
    print("Hola mundo ESP EJEX\n")
    time.sleep(1.5)
    print("Iniciando\n")
    inicia_mod_control()
    

# if __name__ == "__main__" :
#     inicia()
#     manda("Hola mundo\n")
#     time.sleep(1.5)
#     manda("Iniciando\n")
#     inicia_mod_control()
#     com = ComJ(ejex)
#     while True:
#         com.recibe_js()
