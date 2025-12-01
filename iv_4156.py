#!/usr/bin/python

import visa
import time
import ProPlus
import math
rm = visa.ResourceManager()
#rm.timeout = 250000
#del rm.timeout  #No timeout
iv = rm.open_resource('GPIB0::15::INSTR')   ###  Agilent 4156B/C I-V meter
#iv.delay=1
#iv.read_termination='\n'
#iv.write_termination="\n\r"
#del iv.timeout
iv.timeout = 90000
sm1 = rm.open_resource('GPIB0::22::INSTR')   ###  Agilent E5250A switch matrix, top
del sm1.timeout
#sm1.timeout = 60000
sm2 = rm.open_resource('GPIB0::23::INSTR')   ###  Agilent E5250A switch matrix, bottom (TODO: Implement Check/config for when not being used e.g. MB45 Measurements)
del sm2.timeout
#sm2.timeout = 60000

#iv.write("*RST")
#iv.write("US")  ###  Puts 4156 in FLEX command mode

def id():
  print(iv.query("*IDN?"))
  print(sm1.query("*IDN?"))
  print(sm2.query("*IDN?"))

def reset():
  iv.write("*RST")
  sm1.write("*RST")
  sm2.write("*RST")
  time.sleep(5)
  #iv.write("US42 16")  ###  Puts 4156 in FLEX command mode
  iv.write("US")  ###  Puts 4156 in FLEX command mode

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
def disconnect_single(inp,out):  ###  Generic connect function for SM1
  blade = 1
  while (out > 12):
    blade = blade + 1
    out = out - 12
  inp  = "%02d" % inp
  out  = "%02d" % out
  sm1.write("ROUT:OPEN (@{0}{1}{2})".format(blade,inp,out))
  sm2.write("ROUT:OPEN (@{0}{1}{2})".format(blade,inp,out))
def single_bias_setup(channel,bias): #To be used for custom measurements(SRAM,etc.)
    iv.write("DV,{0},{1},100e-3".format(channel,bias))
def enable_bias():
    iv.write("XE")

def turnon_vsu():
  iv.write("CN 21,22")
  iv.write("DV 21,0,2.5")
  iv.write("DV 22,0,2.5")

#def turnon_vsu(voltage,vsu):
#  iv.write("CN 2#{0}".format(vsu))
#  iv.write("DV 2#{0},0,#{1}".format(vsu,voltage))

def autorange_calc(itar):
    res=0 #Default is 11
    if itar>1e-9:
        res+=1 #12
    if itar>10e-9:
        res+=1 #13
    #if itar>100e-9:
    #    res+=1 #14
    #if itar>1e-6:
    #    res+=1 #15
    #if itar>10e-6:
    #    res+=1 #16
    #if itar>100e-6:
    #    res+=1 #17
    #if itar>1e-3:
    #    res+=1 #18
    #if itar>10e-3:
    #    res+=1 #19
    #if itar>100e-3:
    #    res+=1 #20 #
    return res

def meas_ccvt(vd,itar,start,stop,step,polarity):   ###
  iv.write("CN 1,2,3,4")
  iv.write("MM 14")
  iv.write("LSVM 0")
  iv.write("LSTM 0,0")
  autorange = 11 #Min Auto Range
  autorange+=autorange_calc(itar*11)
  iv.write("LGI 4,{0},{2},{1}".format(polarity,itar,autorange))
  iv.write("RI 4,{0}".format(autorange) )
  iv.write("LSV 2,11,{0},{1},{2},0.1".format(start,stop,step))
  iv.write("DV 4,11,{0},0.1".format(vd))
  iv.write("DV 3,11,0,0.1")
  iv.write("DV 1,11,0,0.1")
  iv.write("WM 2,2")
  iv.write("XE")      ### Measure
  #time.sleep(1)
  iv.write("RMD?")    ### Read meas buffer
  #time.sleep(1)

  #iv.write("ERR?")
  #print "Err1: | " + iv.read()
  temp1="fail"
  try:
      temp1 = iv.read().split(",")
  except:
      print("meas_ccvt failed!")
      return "fail"
  if len(temp1) == 3:
    temp2 = temp1[1].split("v")
    if len(temp2) == 2:
      meas = float(temp2[1].rstrip())
    else:
      meas = "fail"
  else:
    meas = "fail"
  iv.write("CL")   ### No argument, disables all units
  return meas

def spot_4t(vd,vg,vb,meas_node=4):   ### Spot drain current measurement
  iv.write("CN 1,2,3,4")
  iv.write("MM 1,{0}".format(meas_node))      ### I measurement on SMU4
  #iv.write("SLI 3")
  iv.write("DV 1,0,{0},100E-3".format(vb))
  iv.write("DV 2,0,{0},100E-3".format(vg))
  iv.write("DV 3,0,0,100E-3")
  iv.write("DV 4,0,{0},100E-3".format(vd))
  iv.write("XE")      ### Measure
  iv.write("RMD?")    ### Read meas buffer
  meas = float(iv.read().split("I")[1].rstrip())  ### Print out measurement
  iv.write("CL")   ### No argument, disables all units
  return meas

#Same as spot4t but forces current
def spot_4t_i(vd,vg,vb,meas_node=4):   ### Spot drain current measurement
  iv.write("CN 1,2,3,4")
  iv.write("MM 1,{0}".format(meas_node))      ### I measurement on SMU4
  #iv.write("SLI 3")
  iv.write("DI 1,0,{0},100E-3".format(vb))
  iv.write("DI 2,0,{0},100E-3".format(vg))
  iv.write("DI 3,0,0,100E-3")
  iv.write("DI 4,0,{0},100E-3".format(vd))
  iv.write("XE")      ### Measure
  iv.write("RMD?")    ### Read meas buffer
  meas = float(iv.read().split("V")[1].rstrip())  ### Print out measurement
  iv.write("CL")   ### No argument, disables all units
  return meas

def spot_4t_sram(vd,vg,vb):   ### Spot drain current measurement (SRAM ONLY)
  iv.write("CN 1,2,3,4")
  iv.write("MM 1,4")      ### I measurement on SMU4
  iv.write("SLI 3")
  iv.write("DV 3,0,{0},100E-3".format(vd))
  iv.write("DV 2,0,{0},100E-3".format(vg))
  iv.write("DV 1,0,0,100E-3")
  iv.write("DV 4,0,{0},100E-3".format(vd))
  iv.write("XE")      ### Measure
  iv.write("RMD?")    ### Read meas buffer
  val=iv.read().rstrip()
  #print val
  #meas = max(map(lambda x: float(x.split("I")[1]),val.split(",") )) ### Print out measurement
  meas = float(val.split("I")[1])  ### Print out measurement
  iv.write("CL")   ### No argument, disables all units
  return meas

#Jswe changed meas node from 3 to 4
def spot_2t(voltage,meas_node=4):   ### Spot measurement
  iv.write("CN 3,4")      ### Enable SMU3/4
  iv.write("MM 1,{0}".format(node))      ### I measurement on SMU4
  iv.write("DV 3,0,0,100E-3")    ### Apply 0V SMU4
  iv.write("DV 4,0,{0},100E-3".format(voltage)) ### Apply voltage, SMU4
  iv.write("XE")      ### Measure
  iv.write("RMD?")    ### Read meas buffer
  meas = float(iv.read().split("I")[1].rstrip())  ### Print out measurement
  iv.write("CL")   ### No argument, disables all units
  return meas

def sweep4t(vd,vg,vb,outputs):  #Decided to format start/stop/step when passing values
  iv.write("CN 1,2,3,4")
  outputs_str = map(str,outputs)
  ch_outputs = ",".join(outputs_str)
  vd=str(vd)
  vg=str(vg)
  vb=str(vb)
  sizevd=len(vd.split(","))
  sizevg=len(vg.split(","))
  sizevb=len(vb.split(","))
  if (sizevd>1 and sizevg>1) or (sizevg>1 and sizevb>1) or (sizevd>1 and sizevb>1):
      raise(Exception, "I only support one sweep at a time!")  #TODO: Implement p-sweeps(done in PP_dat Class)
  iv.write("MM 2, {0}".format(ch_outputs))
  if sizevd>1:   #Looking For Start,Stop,Step
      iv.write("WV 4,1,0,{0},100E-3".format(vd))  ###Drain
  else:
      iv.write("DV 4,0,{0},100E-3".format(vd))  ###Drain
  iv.write("DV 3,0,0,100E-3")               ###Source
  if sizevg>1:   #Looking For Start,Stop,Step
      iv.write("WV 2,1,0,{0},100E-3".format(vg))  ###Gate
  else:
      iv.write("DV 2,0,{0},100E-3".format(vg))  ###Gate
  if sizevb>1:   #Looking For Start,Stop,Step
      iv.write("WV 1,1,0,{0},100E-3".format(vb))  ###Bulk
  else:
      iv.write("DV 1,0,{0},100E-3".format(vb))  ###Bulk
  iv.write("RI 4, 12")
  iv.write("XE")      ### Measure
  iv.write("RMD?")    ### Read meas buffer
  meas=iv.read()
  iv.write("CL")
  return meas


#Keeping it simple,  force Ie, measure Vbe
def vbe(curr):
  iv.write("CN 1,2,3,4")
  iv.write("MM 1,4")      ### V measurement on SMU4
  iv.write("DI 1,0,0,100E-3")
  iv.write("DI 2,0,0,100E-3")
  iv.write("DI 3,0,0,100E-3")
  iv.write("DI 4,0,{0},100E-3".format(curr))
  iv.write("XE")      ### Measure
  iv.write("RMD?")    ### Read meas buffer
  #This will definitely need debugging
  meas = float(iv.read().split("V")[1].rstrip())  ### Print out measurement
  iv.write("CL")   ### No argument, disables all units
  return meas


def beta(curr):
  ic_str = spot_4t_i(curr,0,0,3)
  ib_str = spot_4t_i(curr,0,0,2)
  ic=float(ic_str)
  ib=float(ib_str)
  meas = ic/ib
  return meas


def maxgmvt(vd,vg,vb,type):
  outputs = [4]
  raw_meas = sweep4t(vd,vg,vb,outputs)
  datfile = ProPlus.parse_sweep(raw_meas,vg,"g",vb,"b",vd,"d",type,"Id-Vg")[0]
  x_data_str = datfile.xsweep()
  y_data_str = datfile.ysweep()
  x_data = [float(i) for i in x_data_str]
  y_data = [float(i) for i in y_data_str]
  gm_data = []
  for index, val in enumerate(y_data):
    if index > len(y_data) - 2:
      break
    gm = (y_data[index+1] - val) / (x_data[index+1] - x_data[index])
    gm_data.append(gm)
  peak_gm = max(gm_data)
  peak_gm_idx = gm_data.index(peak_gm)
  peak_gm_vg = (x_data[peak_gm_idx] + x_data[peak_gm_idx+1])/2.0
  peak_gm_id = (y_data[peak_gm_idx] + y_data[peak_gm_idx+1])/2.0
  max_gm_vt = peak_gm_vg - peak_gm_id/peak_gm - float(vd)/2.0
  return max_gm_vt

def maxgmsqrtidvt(vd,vg,vb,type):
  outputs = [4]
  raw_meas = sweep4t(vd,vg,vb,outputs)
  datfile = ProPlus.parse_sweep(raw_meas,vg,"g",vb,"b",vd,"d",type,"Id-Vg")[0]
  x_data_str = datfile.xsweep()
  y_data_str = datfile.ysweep()
  x_data = [float(i) for i in x_data_str]
  y_data = [math.sqrt(abs(float(i))) for i in y_data_str]
  gm_data = []
  for index, val in enumerate(y_data):
    if index > len(y_data) - 2:
      break
    gm = (y_data[index+1] - val) / (x_data[index+1] - x_data[index])
    gm_data.append(gm)
  peak_gm = min(gm_data) if type == "pmos" else max(gm_data)
  #print("Peakgm: "+str(peak_gm))
  peak_gm_idx = gm_data.index(peak_gm)
  peak_gm_vg = (x_data[peak_gm_idx] + x_data[peak_gm_idx+1])/2.0
  #print("Peakgm_vg: "+str(peak_gm_vg))
  peak_gm_id = (y_data[peak_gm_idx] + y_data[peak_gm_idx+1])/2.0
  max_gm_vt = peak_gm_vg - peak_gm_id/peak_gm
  return max_gm_vt

def idle():
  iv.write("CL")   ### No argument, disables all units
  disconnect()    ### Both switch matrices open all switches
