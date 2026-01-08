# -*- coding: utf-8 -*-
"""
Compute Experiment Settings

QUICK-EDIT CONFIGURATION FILE
=============================
This file contains all the tunable parameters for the Compute experiment.
Edit these values to quickly adjust your experiment without modifying other files.

Sections:
    1. VOLTAGE SETTINGS - VDD, VCC supply voltages
    2. PPG SETTINGS - Pulse generator DC mode voltages
    3. COMPLIANCE SETTINGS - Voltage and current compliance limits
    4. EXPERIMENT DEFINITIONS - Named experiments with enable flags
"""

# ============================================================================
# 1. VOLTAGE SETTINGS
# ============================================================================

# Power supply voltages
VDD = 1.8       # VDD voltage in volts
VCC = 5.0       # VCC voltage in volts

# ============================================================================
# 2. PPG SETTINGS (DC Mode for ERASE_PROG)
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
# 3. COMPLIANCE SETTINGS (Usually don't need to change)
# ============================================================================

# Current compliance for voltage sources (A)
VOLTAGE_SOURCE_COMPLIANCE = 0.001   # 1 mA

# Voltage compliance for current sources (V)
CURRENT_SOURCE_COMPLIANCE = 0.1     # 2 V

# ============================================================================
# 4. EXPERIMENT DEFINITIONS
# ============================================================================
# Each experiment defines:
#   - name: Experiment name (printed to CSV and logfile)
#   - enabled: Boolean flag to enable/disable the experiment
#   - fixed_values: Dictionary of fixed parameter values (all parameters except sweep_variables)
#   - sweep_variables: List of variable names to sweep (either 1 or 2 variables)
#
# Available variables: X1, X2, KGAIN (for KGAIN1/KGAIN2 linked), TRIM (for TRIM1/TRIM2 linked),
#                      F11, F12, IREFP, IMEAS, ERASE_PROG (PPG state: "ERASE" or "PROGRAM")
#
# Note: KGAIN1 and KGAIN2 are always linked (use "KGAIN" in sweep_variables)
#       TRIM1 and TRIM2 are always linked (use "TRIM" in sweep_variables)
#       ERASE_PROG is a list of PPG state names: ["ERASE"], ["PROGRAM"], or ["ERASE", "PROGRAM"]

# ============================================================================
# EXPERIMENT ENABLE FLAGS (All in one place for easy control)
# ============================================================================
EXP_ENABLE_1 = True   # Experiment 1: Sweep X1
EXP_ENABLE_2 = True   # Experiment 2: Sweep X2
EXP_ENABLE_3 = True   # Experiment 3: Sweep KGAIN
EXP_ENABLE_4 = True   # Experiment 4: Sweep IREFP
EXP_ENABLE_5 = True   # Experiment 5: Sweep X1 and X2
EXP_ENABLE_6 = True   # Experiment 6: Sweep KGAIN and TRIM

# ============================================================================
# EXPERIMENT DEFINITIONS
# ============================================================================

EXPERIMENTS = [
    {
        "name": "Sweep_X1",
        "enabled": EXP_ENABLE_1,
        "fixed_values": {
            "X2": 10e-9,
            "KGAIN": 10e-9,
            "TRIM": 10e-9,
            "F11": 100e-9,
            "F12": 10e-9,
            "IREFP": 100e-9,
            "IMEAS": None,  # None means IMEAS will match X1 value
            "ERASE_PROG": ["ERASE", "PROGRAM"],  # Both states
        },
        "sweep_variables": ["X1"],
        "X1_values": [10e-9, 20e-9, 30e-9, 40e-9, 50e-9, 60e-9, 70e-9, 80e-9, 90e-9],
    },
    {
        "name": "Sweep_X2",
        "enabled": EXP_ENABLE_2,
        "fixed_values": {
            "X1": 50e-9,
            "KGAIN": 10e-9,
            "TRIM": 10e-9,
            "F11": 100e-9,
            "F12": 10e-9,
            "IREFP": 100e-9,
            "IMEAS": 50e-9,
            "ERASE_PROG": ["ERASE", "PROGRAM"],  # Both states
        },
        "sweep_variables": ["X2"],
        "X2_values": [5e-9, 10e-9, 15e-9, 20e-9, 25e-9, 30e-9],
    },
    {
        "name": "Sweep_KGAIN",
        "enabled": EXP_ENABLE_3,
        "fixed_values": {
            "X1": 50e-9,
            "X2": 10e-9,
            "TRIM": 10e-9,
            "F11": 100e-9,
            "F12": 10e-9,
            "IREFP": 100e-9,
            "IMEAS": 50e-9,
            "ERASE_PROG": ["ERASE", "PROGRAM"],  # Both states
        },
        "sweep_variables": ["KGAIN"],
        "KGAIN_values": [0e-9, 5e-9, 10e-9, 15e-9, 20e-9],
    },
    {
        "name": "Sweep_IREFP",
        "enabled": EXP_ENABLE_4,
        "fixed_values": {
            "X1": 50e-9,
            "X2": 10e-9,
            "KGAIN": 10e-9,
            "TRIM": 10e-9,
            "F11": 100e-9,
            "F12": 10e-9,
            "IMEAS": 50e-9,
            "ERASE_PROG": ["ERASE", "PROGRAM"],  # Both states
        },
        "sweep_variables": ["IREFP"],
        "IREFP_values": [10e-9, 50e-9, 100e-9, 150e-9, 200e-9],
    },
    {
        "name": "Sweep_X1_X2",
        "enabled": EXP_ENABLE_5,
        "fixed_values": {
            "KGAIN": 10e-9,
            "TRIM": 10e-9,
            "F11": 100e-9,
            "F12": 10e-9,
            "IREFP": 100e-9,
            "IMEAS": None,  # None means IMEAS will match X1 value
            "ERASE_PROG": ["ERASE", "PROGRAM"],  # Both states
        },
        "sweep_variables": ["X1", "X2"],
        "X1_values": [30e-9, 40e-9, 50e-9, 60e-9, 70e-9],
        "X2_values": [5e-9, 10e-9, 15e-9, 20e-9],
    },
    {
        "name": "Sweep_KGAIN_TRIM",
        "enabled": EXP_ENABLE_6,
        "fixed_values": {
            "X1": 50e-9,
            "X2": 10e-9,
            "F11": 100e-9,
            "F12": 10e-9,
            "IREFP": 100e-9,
            "IMEAS": 50e-9,
            "ERASE_PROG": ["ERASE", "PROGRAM"],  # Both states
        },
        "sweep_variables": ["KGAIN", "TRIM"],
        "KGAIN_values": [0e-9, 5e-9, 10e-9, 15e-9, 20e-9],
        "TRIM_values": [1e-9, 5e-9, 10e-9, 25e-9, 50e-9],
    },
]

# ============================================================================
# HELPER FUNCTION - Get all settings as dict
# ============================================================================

def get_settings():
    """Return all settings as a dictionary for easy access."""
    return {
        # Voltages
        "VDD": VDD,
        "VCC": VCC,
        # PPG
        "PPG_ERASE_VOLTAGE": PPG_ERASE_VOLTAGE,
        "PPG_PROGRAM_VOLTAGE": PPG_PROGRAM_VOLTAGE,
        "PPG_STATE_ORDER": PPG_STATE_ORDER,
        # Compliance
        "VOLTAGE_SOURCE_COMPLIANCE": VOLTAGE_SOURCE_COMPLIANCE,
        "CURRENT_SOURCE_COMPLIANCE": CURRENT_SOURCE_COMPLIANCE,
        # Experiments
        "EXPERIMENTS": EXPERIMENTS,
    }

