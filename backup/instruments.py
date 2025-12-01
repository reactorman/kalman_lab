# -*- coding: utf-8 -*-
"""
Created on Thu Jul 28 23:03:05 2022

@author: chamberlain
"""

import pyvisa
import e5270
import _81104a

rm = pyvisa.ResourceManager()

#
instruments = []

iv = e5270.E5270(rm)
pg = _81104a._81104A(rm)
instruments = [iv, pg]


# Returns identification status of all instruments
def idn():
    idn_str = []
    for inst in instruments:
        idn_str.append(inst.idn())


# Returns error status of all instruments
def error_check():
    err_str = []
    for inst in instruments:
        err_str.append(inst.err())


def meas_vt(vt_options):
    iv.meas_cc(**vt_options)


def pulse():
    iv.idle()


def cycle(cycles):
    iv.idle()
    for _ in range(cycles):
        iv.idle()
        # erase(vb,vg,time)
        # program(vg,vb,time)
