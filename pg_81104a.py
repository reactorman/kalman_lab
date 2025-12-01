#!/usr/bin/python


class _81104A:
    def __init__(self, rm):
        self.pg = rm.open_resource("GPIB0::10::INSTR")
        self.pg.timeout = 5000
        self.reset()

    def reset(self):
        self.pg.write("*RST")
        self.pg.write(":DISP OFF")  ### Speeds up command execution

    def idn(self):
        return self.pg.query("*IDN?")

    def err(self):
        self.pg.write(":SYST:ERR?")
        return self.pg.read()

    def idle(self):
        self.pg.write(":OUTP1 OFF")  ###  Turn off outputs
        self.pg.write(":OUTP2 OFF")

    def pulse2ch(
        self,
        pw=None,
        period="1US",
        rise="1US",
        vhigh1=None,
        vlow1=None,
        default1="low",
        vhigh2=None,
        vlow2=None,
        default2="low",
        count=1,
    ):
        self.pg.write(":ARM:SOUR MAN")  ###  Sets up a manual trigger: *TRG
        ### Caution:  ":DIG:PATT OFF" sets ":TRIG:COUN 1" to ":TRIG:COUN 2", so use them in correct order
        self.pg.write(":DIG:PATT OFF")
        ###  Specifies a single pulse after trigger
        self.pg.write(f":TRIG:COUN {count}")
        ### Once triggered the pulse will be immediate
        self.pg.write(":TRIG:SOUR IMM")
        self.pg.write(f":PULS:PER {period}")

        if vhigh1 != None and vlow1 != None:
            ### Set polarities, NORM is at low by default
            if default1 == "low":
                self.pg.write(":OUTP1:POL NORM")
            else:
                self.pg.write(":OUTP1:POL INV")

            self.pg.write(f":VOLT1:HIGH {vhigh1}")
            self.pg.write(f":VOLT1:LOW {vlow1}")
            self.pg.write(f":PULS:WIDT1 {pw}")  ### Sets pulse width
            ### Transition edge, by default specifies leading edge.
            self.pg.write(f":PULS:TRAN1 {rise}")
            self.pg.write(":OUTP1 ON")

        if vhigh2 != None and vlow2 != None:
            if default2 == "low":
                self.pg.write(":OUTP2:POL NORM")
            else:
                self.pg.write(":OUTP2:POL INV")

            self.pg.write(f":VOLT2:HIGH {vhigh2}")
            self.pg.write(f":VOLT2:LOW {vlow2}")
            self.pg.write(f":PULS:WIDT2 {pw}")
            ### Transition edge, by default specifies leading edge.
            self.pg.write(f":PULS:TRAN2 {rise}")
            self.pg.write(":OUTP2 ON")

        self.pg.write("*TRG")  ###  Triggers the programmed pulse
        self.idle()

    def pulse1ch(
        self,
        pw=None,
        period="1US",
        rise="1US",
        vhigh=None,
        vlow=None,
        default="low",
        count=1,
    ):
        self.pg.write(":ARM:SOUR MAN")  ###  Sets up a manual trigger: *TRG
        ### Caution:  sets ":TRIG:COUN 1" to ":TRIG:COUN 2", so use them in correct order
        self.pg.write(":DIG:PATT OFF")
        ###  Specifies a single pulse after trigger
        self.pg.write(f":TRIG:COUN {count}")
        ### Once triggered the pulse will be immediate
        self.pg.write(":TRIG:SOUR IMM")
        self.pg.write(f":PULS:PER {period}")

        if vhigh == None or vlow == None:
            return "Error: voltages not specified."

        ### Set polarities, NORM is at low by default
        if default == "low":
            self.pg.write(":OUTP1:POL NORM")
        else:
            self.pg.write(":OUTP1:POL INV")

        self.pg.write(f":VOLT1:HIGH {vhigh}")
        self.pg.write(f":VOLT1:LOW {vlow}")
        self.pg.write(f":PULS:WIDT1 {pw}")  ### Sets pulse width
        ### Transition edge, by default specifies leading edge.
        self.pg.write(f":PULS:TRAN1 {rise}")
        self.pg.write(":OUTP1 ON")

        self.pg.write("*TRG")  ###  Triggers the programmed pulse
        self.idle()
