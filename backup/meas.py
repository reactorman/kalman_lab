#!/usr/bin/python

import visa
rm = visa.ResourceManager()
iv = rm.open_resource('GPIB0::17::INSTR')   ###  Keysight E5270B I=V meter
sm1 = rm.open_resource('GPIB0::22::INSTR')   ###  Agilent E5250A switch matrix, top
sm2 = rm.open_resource('GPIB0::23::INSTR')   ###  Agilent E5250A switch matrix, bottom

def id():
  print(iv.query("*IDN?"))
  print(sm1.query("*IDN?"))
  print(sm2.query("*IDN?"))

def reset():
  iv.write("*RST")
  sm1.write("*RST")
  sm2.write("*RST")

def disconnect():  ###  Disonnects all switches for SM1 and SM2
  sm1.write(":ROUT:OPEN:CARD ALL")
  sm2.write(":ROUT:OPEN:CARD ALL")

def connect(inp,out):  ###  Generic connect function for SM1
  blade = 1  
  while (out > 12):
    blade = blade + 1
    out = out - 12
  inp  = "%02d" % inp
  out  = "%02d" % out
  sm1.write("ROUT:CLOS (@{0}{1}{2})".format(blade,inp,out))
  sm2.write("ROUT:CLOS (@{0}{1}{2})".format(blade,inp,out))

def meas_ccvt(vd,itar,start,stop,step,polarity):   ### 
  iv.write("CN 1,2,3,4")    
  iv.write("MM 14")     
  iv.write("LSM 2,3")  
  iv.write("LSVM 1")  
  iv.write("LSTM 0,0")  
  iv.write("LGI 4,{0},11,{1}".format(polarity,itar))  
  iv.write("LSV 2,11,{0},{1},{2},0.1".format(start,stop,step))  
  #iv.write("LSSV 2,1,0,0.1")  
  iv.write("DV 4,11,{0},0.1".format(vd))
  iv.write("DV 3,11,0,0.1")
  iv.write("DV 1,11,0,0.1")
  iv.write("XE")      ### Measure
  meas = float(iv.read().split(",")[0].split("V")[1].rstrip())  ### Print out measurement
  iv.write("CL")   ### No argument, disables all units
  return meas

def sweep(vd,start,stop,step):   ### 
  iv.write("CN 1,2,3,4")    
  iv.write("MM 2,4")     
  iv.write("DV 1,11,0,0.1")
  iv.write("WV 2,1,0,0,1,101")  
  #iv.write("WV 2,1,0,{0},{1},{2}".format(start,stop,step))  
  iv.write("DV 3,11,0")
  iv.write("DV 4,11,3.3")
  #iv.write("DV 4,11,{0},0.1".format(vd))
  iv.write("XE")      ### Measure
  #meas = iv.read()  ### Print out measurement
  meas = "done"
  iv.write("CL")   ### No argument, disables all units
  return meas

def spot_4t(vd,vg):   ### Spot drain current measurement
  iv.write("CN 1,2,3,4")    
  iv.write("MM 1,4")      ### I measurement on SMU4
  iv.write("DV 1,0,0,100E-3")  
  iv.write("DV 2,0,{0},100E-3".format(vg))
  iv.write("DV 3,0,0,100E-3") 
  iv.write("DV 4,0,{0},100E-3".format(vd))
  iv.write("XE")      ### Measure
  meas = float(iv.read().split("I")[1].rstrip())  ### Print out measurement
  iv.write("CL")   ### No argument, disables all units
  return meas

def spot_2t(voltage):   ### Spot drain current measurement
  iv.write("CN 3,4")      ### Enable SMU3/4
  iv.write("MM 1,3")      ### I measurement on SMU3
  iv.write("DV 4,0,0,100E-3")    ### Apply 0V SMU4
  iv.write("DV 3,0,{0},100E-3".format(voltage)) ### Apply voltage, SMU3
  iv.write("XE")      ### Measure
  meas = float(iv.read().split("I")[1].rstrip())  ### Print out measurement
  iv.write("CL")   ### No argument, disables all units
  return meas

def idle():
  iv.write("CL")   ### No argument, disables all units
  disconnect()    ### Both switch matrices open all switches 
