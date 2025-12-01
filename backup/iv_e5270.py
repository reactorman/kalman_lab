# -*- coding: utf-8 -*-
"""
Created on Thu Jul 28 23:03:05 2022

@author: chamberlain
"""
import sys


class E5270:
    def __init__(self, rm):
        self.reset()
        self.iv = rm.open_resource("GPIB0::17::INSTR")
        self.iv.timeout = 20000

    def reset(self):
        self.iv.write("*RST")

    def idn(self):
        return self.iv.query("*IDN?")

    def err(self):
        temp = self.iv.query("ERR?").split(",")[0]
        if temp != "0":
            return self.iv.query("EMG? {}".format(temp))
        else:
            return "The E5270 returns no error messages"

    def idle(self):
        self.iv.write("CL")  ### No argument, disables all units

    # Sweep until a current is found
    def meas_cc(
        self,
        itar,
        start,
        stop,
        step,
        meas_ch,
        vsweep,
        mode="linear",
        voltages=None,
        currents=None,
    ):
        # It isn't clear what happens if ITAR is negative.
        if start > stop:
            polarity = 0
        else:
            polarity = 1

        if mode == "linear":
            self.iv.write("MM 14")  # linear search
            self.iv.write("LSVM 1")  # output formatting
            self.iv.write("LSTM 0,0")  # hold/delay, default is 0
            self.iv.write(f"LGI {meas_ch},{polarity},11,{itar}")
            self.iv.write(f"LSV {vsweep},11,{start},{stop},{step},0.1")
            self.iv.write("LSM 2,3")  # Enables abort and sets post condition
        elif mode == "binary":
            self.iv.write("MM 15")  # binary search
            self.iv.write("BSVM 1")  # output formatting
            self.iv.write("BST 0,0")  # hold/delay, default is 0
            self.iv.write(f"BGI {meas_ch},{polarity},11,{itar}")
            self.iv.write(f"BSV {vsweep},11,{start},{stop},{step},0.1")
            self.iv.write("BSM 0,2,3")  # Enables abort and sets post condition
        else:
            sys.exit("meas_cc called with invalid mode on E5270")

        self.set_bias(voltages, currents, [vsweep])
        self.sample()  ### Measure
        meas = float(
            self.iv.read().split(",")[0].split("V")[1].rstrip()
        )  ### Print out measurement
        self.idle()
        return meas

    # Re-factor to parameterize things
    def sweep(self, vd, start, stop, step):  ###
        self.iv.write("CN 1,2,3,4")
        self.iv.write("MM 2,4")
        self.iv.write("DV 1,11,0,0.1")
        self.iv.write("WV 2,1,0,0,1,101")
        # self.iv.write("WV 2,1,0,{0},{1},{2}".format(start,stop,step))
        self.iv.write("DV 3,11,0")
        self.iv.write("DV 4,11,3.3")
        # self.iv.write("DV 4,11,{0},0.1".format(vd))
        self.iv.write("XE")  ### Measure
        # meas = iv.read()  ### Print out measurement
        meas = "done"
        self.iv.write("CL")  ### No argument, disables all units
        return meas

    # Re-factor to parameterize things
    def spot_4t(self, vd, vg):  ### Spot drain current measurement
        self.iv.write("CN 1,2,3,4")
        self.iv.write("MM 1,4")  ### I measurement on SMU4
        self.iv.write("DV 1,0,0,100E-3")
        self.iv.write("DV 2,0,{0},100E-3".format(vg))
        self.iv.write("DV 3,0,0,100E-3")
        self.iv.write("DV 4,0,{0},100E-3".format(vd))
        self.iv.write("XE")  ### Measure
        meas = float(
            self.iv.read().split("I")[1].rstrip()
        )  ### Print out measurement
        self.iv.write("CL")  ### No argument, disables all units
        return meas

    # Re-factor to parameterize things
    def spot_2t(self, voltage):  ### Spot drain current measurement
        self.iv.write("CN 3,4")  ### Enable SMU3/4
        self.iv.write("MM 1,3")  ### I measurement on SMU3
        self.iv.write("DV 4,0,0,100E-3")  ### Apply 0V SMU4
        self.iv.write(
            "DV 3,0,{0},100E-3".format(voltage)
        )  ### Apply voltage, SMU3
        self.iv.write("XE")  ### Measure
        meas = float(
            self.iv.read().split("I")[1].rstrip()
        )  ### Print out measurement
        self.iv.write("CL")  ### No argument, disables all units
        return meas

    # FIX: Currently Icomp/Vcomp default to 0.1A/1V.
    # Sets CN and then DV/DI.
    # Others can be anything not set to a fixed voltage/current.
    def set_bias(self, voltages, currents, others):
        all_ch = others
        all_force = []
        for ch, volt in enumerate(voltages, start=1):
            if volt is None:
                continue
            all_ch.append(ch)
            all_force.append(f"DV {ch},0,{volt},100E-3")
        for ch, current in enumerate(currents, start=1):
            if current is None:
                continue
            all_ch.append(ch)
            all_force.append(f"DI {ch},0,{current},1")

        # Must write CN before DV/DI
        channels = ",".join(str(i) for i in all_ch)
        self.iv.write(f"CN {channels}")
        for force in all_force:
            self.iv.write(force)

    # Re-factor to parameterize things
    def high_speed_sample_setup(self, voltage, samples):
        self.iv.write("CN 1,2,3,4,6")  ### Enable SMU1/2
        self.iv.write("CMM 1,2")
        self.iv.write("CMM 2,2")
        self.iv.write("CMM 3,2")
        self.iv.write("AAD 1,0")
        self.iv.write("AAD 2,0")
        self.iv.write("AAD 3,0")
        self.iv.write("RV 1,-11")
        self.iv.write("RV 2,-11")
        self.iv.write("RV 3,-11")
        self.iv.write("AIT 0,1,1")
        self.iv.write(
            "MM 16,1,2,3"
        )  ### Multi-channel sweep measurement on CH 1,2,3
        self.iv.write(
            "DV 4,0,{0},100E-3".format(voltage)
        )  ### Apply voltage, SMU4
        self.iv.write("WV 6,1,0,0,1,{}".format(samples))

    def sample(self):  ### Spot drain current measurement
        self.iv.write("XE")  ### Measure
        return self.iv.read()  ### Print out measurement
