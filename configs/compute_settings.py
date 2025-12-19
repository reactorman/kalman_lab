# -*- coding: utf-8 -*-
"""
Compute Experiment Settings

QUICK-EDIT CONFIGURATION FILE
=============================
This file contains all the tunable parameters for the Compute experiment.
Edit these values to quickly adjust your experiment without modifying other files.

Sections:
    1. VOLTAGE SETTINGS - VDD, VCC supply voltages
    2. CURRENT LISTS - Fixed current sweep values for each parameter
    3. SYNCHRONOUS SWEEP - X1 and IMEAS sweep ranges
    4. PPG SETTINGS - Pulse generator DC mode voltages
"""

# ============================================================================
# 1. VOLTAGE SETTINGS
# ============================================================================

# Power supply voltages
VDD = 1.8       # VDD voltage in volts
VCC = 5.0       # VCC voltage in volts

# ============================================================================
# 2. CURRENT LISTS (Fixed Current Sweep Parameters)
# ============================================================================
# These currents are iterated through in all combinations.
# Each combination triggers a full synchronous sweep of X1/IMEAS.
# Units: Amps (use scientific notation, e.g., 1e-6 = 1µA, 100e-9 = 100nA)

# KGAIN current values (applied to both KGAIN1 and KGAIN2 - they are linked)
KGAIN_VALUES = [
    0e-9,       # 1 µA
    5e-9,
    10e-9,       # 2 µA
    20e-9,       # 5 µA
]

# TRIM current values (applied to both TRIM1 and TRIM2 - they are linked)
TRIM_VALUES = [
    1e-9,
    5e-9,
    10e-9,       # 1 µA
    50e-9,       # 2 µA
]

# X2 current values
X2_VALUES = [
    5e-9,
    10e-9,       # 1 µA
]

# IREFP current values
IREFP_VALUES = [
    10e-9,
    100e-9,       # 1 µA
]

# F11 current values
F11_VALUES = [
    100e-9,       # 1 µA
]

# F12 current values
F12_VALUES = [
    5e-9,
    10e-9,       # 1 µA
]

# ============================================================================
# 3. X1 FIXED VALUES AND IMEAS SWEEP CONFIGURATION
# ============================================================================
# X1 is set to fixed current values. For each X1 value, IMEAS sweeps from
# (X1 - IMEAS_RANGE_OFFSET) to (X1 + IMEAS_RANGE_OFFSET) in IMEAS_NUM_STEPS steps.
# Units: Amps

# X1 fixed current values (list of values to iterate through)
X1_VALUES = [
    10e-9,
    20e-9, 
    30e-9,
    40e-9,
    50e-9,
    60e-9,
    70e-9,
    80e-9,
    90e-9,
]

# IMEAS sweep configuration (relative to each X1 value)
# IMEAS sweeps from (X1 - IMEAS_RANGE_OFFSET) to (X1 + IMEAS_RANGE_OFFSET)
IMEAS_RANGE_OFFSET = 20e-9    # ±20nA around X1 value
IMEAS_NUM_STEPS = 100           # Number of sweep points (step size = 2*IMEAS_RANGE_OFFSET/(IMEAS_NUM_STEPS-1))

# ============================================================================
# 4. PPG SETTINGS (DC Mode for ERASE_PROG)
# ============================================================================
# PPG operates in DC mode only (no pulses).
# All measurements are done in both ERASE and PROGRAM states.

# ERASE state: PPG outputs VCC
# PROGRAM state: PPG outputs 0V
PPG_ERASE_VOLTAGE = "VCC"   # Use string "VCC" to track VCC value, or set explicit voltage
PPG_PROGRAM_VOLTAGE = 0.0   # 0V for program state

# PPG state order for measurements (both states are always measured)
PPG_STATE_ORDER = ["ERASE", "PROGRAM"]

# ============================================================================
# COMPLIANCE SETTINGS (Usually don't need to change)
# ============================================================================

# Current compliance for voltage sources (A)
VOLTAGE_SOURCE_COMPLIANCE = 0.001   # 1 mA

# Voltage compliance for current sources (V)
CURRENT_SOURCE_COMPLIANCE = 0.1     # 2 V

# ============================================================================
# HELPER FUNCTION - Get all settings as dict
# ============================================================================

def get_settings():
    """Return all settings as a dictionary for easy access."""
    return {
        # Voltages
        "VDD": VDD,
        "VCC": VCC,
        # Current lists
        "KGAIN": KGAIN_VALUES,
        "TRIM": TRIM_VALUES,
        "X2": X2_VALUES,
        "IREFP": IREFP_VALUES,
        "F11": F11_VALUES,
        "F12": F12_VALUES,
        # X1 and IMEAS
        "X1_VALUES": X1_VALUES,
        "IMEAS_RANGE_OFFSET": IMEAS_RANGE_OFFSET,
        "IMEAS_NUM_STEPS": IMEAS_NUM_STEPS,
        # PPG
        "PPG_ERASE_VOLTAGE": PPG_ERASE_VOLTAGE,
        "PPG_PROGRAM_VOLTAGE": PPG_PROGRAM_VOLTAGE,
        "PPG_STATE_ORDER": PPG_STATE_ORDER,
        # Compliance
        "VOLTAGE_SOURCE_COMPLIANCE": VOLTAGE_SOURCE_COMPLIANCE,
        "CURRENT_SOURCE_COMPLIANCE": CURRENT_SOURCE_COMPLIANCE,
    }

