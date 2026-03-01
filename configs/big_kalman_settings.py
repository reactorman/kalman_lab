# -*- coding: utf-8 -*-
"""
Big Kalman Experiment Settings

Edit these values to change default voltages/currents and MODE ADC scaling.
"""

# Default voltages (V)
VCC_DEFAULT = 5.0
VDD_DEFAULT = 1.8

# IMEAS: forced current (A); sinks into SMU. VCOMP = 1.8V
IMEAS_DEFAULT = 0.0

# IREFP: forced current (A); sinks into SMU
IREFP_DEFAULT = 100e-9  # 100 nA

# MODE: applied voltage is VCC/2. When measuring MODE, current is read and
# converted to a 3-bit code using IADC_REF. Assuming 000 = 0A, full range = IADC_REF.
IADC_REF_DEFAULT = 1e-6  # 1 µA full scale (adjust to match actual ADC)

# Compliance (A) for voltage sources
VOLTAGE_COMPLIANCE_DEFAULT = 0.001  # 1 mA

# Compliance (V) for current sources (IMEAS, IREFP)
CURRENT_COMPLIANCE_DEFAULT = 1.8  # VCOMP 1.8V for IMEAS
