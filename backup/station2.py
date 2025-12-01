#!/usr/bin/python

from Gpib import *

iv = Gpib(0,15)   ###  Agilent 4156B/C I-V meter
ppg = Gpib(0,10)  ###  Agilent 81104A Pule-pattern generator
sm1 = Gpib(0,22)  ###  Agilent E5250A switch matrix, top 
sm2 = Gpib(0,23)  ###  Agilent E5250A switch matrix, bottom

iv.write("US")  ###  Puts 4156 in FLEX command mode
ppg.write(":DISP OFF")  ### Speeds up command execution

def id():
  iv.write("*IDN?")
  print iv.read(100)
  ppg.write("*IDN?")
  print ppg.read(100)
  sm1.write("*IDN?")
  print sm1.read(100)
  sm2.write("*IDN?")
  print sm2.read(100)

def reset():
  iv.write("*RST")
  ppg.write("*RST")
  sm1.write("*RST")
  sm2.write("*RST")
  iv.write("US")  ###  Puts 4156 in FLEX command mode
  ppg.write(":DISP OFF")  ### Speeds up command execution

def errorcheck():
  iv.write(":SYST:ERR?")
  print iv.read(100)
  ppg.write(":SYST:ERR?")
  print ppg.read(100)
  sm1.write(":SYST:ERR?")
  print sm1.read(100)
  sm2.write(":SYST:ERR?")
  print sm2.read(100)

def erase():
  ### Caution:  ":DIG:PATT OFF" sets ":TRIG:COUN 1" to ":TRIG:COUN 2", so use them in correct order
  ppg.write(":OUTP1 OFF")    ###  Turn off outputs just in case they are on somehow
  ppg.write(":OUTP2 OFF")
  ppg.write(":OUTP1:POL INV")  ### Set polarities, NORM is at low by default
  ppg.write(":OUTP2:POL NORM") ### INV is at high by default
  ppg.write(":VOLT1:HIGH 0")  ###  Set high and low voltages on each output
  ppg.write(":VOLT1:LOW -1.9")  
  ppg.write(":VOLT2:HIGH 3.35")  
  ppg.write(":VOLT2:LOW 0")  
  #ppg.write(":PULS:PER 100MS")  ### This is irelevant since triggering will be manual
  ppg.write(":PULS:WIDT1 6MS")  ### Sets erase pulse width 
  ppg.write(":PULS:WIDT2 6MS")
  ppg.write(":PULS:TRAN1 50US") ### Transition edge, by default specifies leading edge.  By default
  ppg.write(":PULS:TRAN2 50US") ###  leading edge = trailing edge 
  ppg.write(":ARM:SOUR MAN")  ###  Sets up a manual trigger: *TRG 
  ppg.write(":DIG:PATT OFF") ### This should be off by default but the manual always specifies so I do too 
  ppg.write(":TRIG:COUN 1")   ###  Specifies a single pulse after trigger
  ppg.write(":TRIG:SOUR IMM") ### Once triggered the pulse will be immediate
  ppg.write(":OUTP1 ON")    ###  Turning on outputs
  ppg.write(":OUTP2 ON")
  ppg.write("*TRG")      ###  Triggers the programmed pulse
  ppg.write(":OUTP1 OFF")    ###  Turn off outputs 
  ppg.write(":OUTP2 OFF")

def program():
  ### Caution:  ":DIG:PATT OFF" sets ":TRIG:COUN 1" to ":TRIG:COUN 2", so use them in correct order
  ppg.write(":OUTP1 OFF")    ###  Turn off outputs just in case they are on somehow
  ppg.write(":OUTP2 OFF")
  ppg.write(":OUTP1:POL NORM")  ### Set polarities, NORM is at low by default
  ppg.write(":OUTP2:POL INV") ### INV is at high by default
  ppg.write(":VOLT1:HIGH 3.35")  
  ppg.write(":VOLT1:LOW 0")  
  ppg.write(":VOLT2:HIGH 0")  ###  Set high and low voltages on each output
  ppg.write(":VOLT2:LOW -1.9")  
  #ppg.write(":PULS:PER 100MS")  ### This is irelevant since triggering will be manual
  ppg.write(":PULS:WIDT1 2MS")  ### Sets program pulse width 
  ppg.write(":PULS:WIDT2 2MS")
  ppg.write(":PULS:TRAN1 50US") ### Transition edge, by default specifies leading edge.  By default
  ppg.write(":PULS:TRAN2 50US") ###  leading edge = trailing edge 
  ppg.write(":ARM:SOUR MAN")  ###  Sets up a manual trigger: *TRG 
  ppg.write(":DIG:PATT OFF") ### This should be off by default but the manual always specifies so I do too 
  ppg.write(":TRIG:COUN 1")   ###  Specifies a single pulse after trigger
  ppg.write(":TRIG:SOUR IMM") ### Once triggered the pulse will be immediate
  ppg.write(":OUTP1 ON")    ###  Turning on outputs
  ppg.write(":OUTP2 ON")
  ppg.write("*TRG")      ###  Triggers the programmed pulse
  ppg.write(":OUTP1 OFF")    ###  Turn off outputs 
  ppg.write(":OUTP2 OFF")

def disconnect():  ###  Disonnects all switches for SM1 and SM2
  sm1.write(":ROUT:OPEN:CARD ALL")
  sm2.write(":ROUT:OPEN:CARD ALL")

def connect1(channel):  ###  Generic connect function for SM1
  sm1.write("ROUT:CLOS (@{0})".format(channel))

def connect2(channel):  ###  Generic connect function for SM2
  sm2.write("ROUT:CLOS (@{0})".format(channel))

def flashconnect():  ### Prepare for erase/program operations
  disconnect()
  sm2.write("ROUT:CLOS (@10502)")  ### Connects gate to PPG output 1
  sm2.write("ROUT:CLOS (@10601,10603:10612)")  ### Connects everything else to PPG output 2

def spotconnect(drain):  ### Prepare for spot measurement
  disconnect()
  sm1.write("ROUT:CLOS (@10201:10212)")  ### Connect everything to ground
  sm2.write("ROUT:CLOS (@10201:10212)")  ### Connect everything to ground
  spot_term = "%02d" % drain
  sm1.write("ROUT:OPEN (@102{0})".format(spot_term))  ### Disconnect drain terminal
  sm1.write("ROUT:CLOS (@101{0})".format(spot_term))  ### Connect drain terminal to SMU3
  sm2.write("ROUT:OPEN (@102{0})".format(spot_term))  ### Disconnect drain terminal
  sm2.write("ROUT:CLOS (@101{0})".format(spot_term))  ### Connect drain terminal to SMU3

def sweepconnect(drain,gate):  ### Prepare for sweep measurement
  disconnect()
  sm1.write("ROUT:CLOS (@10301:10312)")  ### Connect everything to ground
  sm2.write("ROUT:CLOS (@10301:10312)")  ### Connect everything to ground
  drain_term = "%02d" % drain
  gate_term = "%02d" % gate
  sm1.write("ROUT:OPEN (@103{0})".format(drain_term))  ### Disconnect drain terminal
  sm1.write("ROUT:CLOS (@101{0})".format(drain_term))  ### Connect drain terminal to SMU3
  sm1.write("ROUT:OPEN (@103{0})".format(gate_term))  ### Disconnect gate terminal
  sm1.write("ROUT:CLOS (@102{0})".format(gate_term))  ### Connect gate terminal to SMU4
  sm2.write("ROUT:OPEN (@103{0})".format(drain_term))  ### Disconnect drain terminal
  sm2.write("ROUT:CLOS (@101{0})".format(drain_term))  ### Connect drain terminal to SMU3
  sm2.write("ROUT:OPEN (@103{0})".format(gate_term))  ### Disconnect gate terminal
  sm2.write("ROUT:CLOS (@102{0})".format(gate_term))  ### Connect gate terminal to SMU4

def spot(voltage):   ### Spot drain current measurement
  iv.write("CN 3,4")      ### Enable SMU3/4
  iv.write("MM 1,3")      ### I measurement on SMU3
  iv.write("DV 4,0,0")    ### Apply 0V SMU4
  iv.write("DV 3,0,{0}".format(voltage)) ### Apply voltage, SMU3
  iv.write("XE")      ### Measure
  iv.write("RMD?")    ### Read meas buffer
  print iv.read(100)  ### Print out measurement
  iv.write("CL")   ### No argument, disables all units

def hispot(voltage):   ### High-speed spot drain current measurement
  iv.write("CN 3,4")      ### Enable SMU3/4
  iv.write("DV 4,0,0")    ### Apply 0V SMU4
  iv.write("DV 3,0,{0}".format(voltage)) ### Apply voltage, SMU3
  iv.write("TI? 3") ### Hi-speed spot current measurement on SMU3
  print iv.read(100)  ### Print out measurement
  iv.write("CL")   ### No argument, disables all units

###  VAR is the node being swept (VG/VD), Fix is the fixed voltage not being swept, VB=VS=0V
def sweep(var,fix,start,stop,step):   ### Sweep
  iv.write("CN 1,3,4")      ### Enable SMU1/3/4
  iv.write("MM 2,3")      ### I measurement on SMU3
  iv.write("DV 1,0,0")    ### Apply 0V SMU1

  if "vd" == var:
    iv.write("DV 4,0,{0}".format(fix)) ### Apply voltage, SMU4
    iv.write("WV 3,1,0,{0},{1},{2}".format(start,stop,step)) ### Apply sweep, SMU3
  elif "vg" == var:  
    iv.write("DV 3,0,{0}".format(fix)) ### Apply voltage, SMU3
    iv.write("WV 4,1,0,{0},{1},{2}".format(start,stop,step)) ### Apply sweep, SMU4
  else:
    print "Acceptable sweeps are vd and vg"
    raise

  iv.write("XE")      ### Measure
  iv.write("RMD?")    ### Read meas buffer
  print iv.read(1000)  ### Print out measurement
  iv.write("CL")   ### No argument, disables all units

