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
# NORMALIZED VALUE SYSTEM:
# ------------------------
# X1, X2, F11, F12, IMEAS: Values between -1 and +1
#   - Actual current = IREFP/2 * (X + 1)
#   - X = -1 -> current = 0
#   - X = 0  -> current = IREFP/2
#   - X = +1 -> current = IREFP
#
# KGAIN, TRIM: Values between 0 and 1
#   - Actual current = IREFP * X
#   - X = 0 -> current = 0
#   - X = 1 -> current = IREFP
#
# IREFP: Actual current in Amps (unchanged)
# ERASE_PROG: PPG state list ["ERASE"], ["PROGRAM"], or ["ERASE", "PROGRAM"]
#
# Note: KGAIN1 and KGAIN2 are always linked (use "KGAIN" in sweep_variables)
#       TRIM1 and TRIM2 are always linked (use "TRIM" in sweep_variables)

# ============================================================================
# EXPERIMENT ENABLE FLAGS (All in one place for easy control)
# ============================================================================
EXP_ENABLE_1 = True   # Experiment 1: 4Q Multiplier
EXP_ENABLE_2 = True   # Experiment 2: 2Q Multiplier
EXP_ENABLE_3 = True   # Experiment 3: 1Q Multiplier
EXP_ENABLE_4 = True   # Experiment 4: 1Q Divider

# ============================================================================
# EXPERIMENT DEFINITIONS
# ============================================================================

EXPERIMENTS = [
    {
        "name": "4q_mult",
        "enabled": EXP_ENABLE_1,
        "fixed_values": {
            "X2": 0.0,          # Normalized: 0 -> IREFP/2
            "KGAIN": 0,       # Normalized: 0 -> 0*IREFP
            "TRIM": 1.0,        # Normalized: 0.1 -> 0.1*IREFP
            "F12": 0.0,         # Normalized: 0 -> IREFP/2
            "IREFP": 100e-9,    # Actual current in Amps
            "IMEAS": 0,      # None means IMEAS will match X1 value
            "ERASE_PROG": ["ERASE","PROGRAM"],
        },
        "sweep_variables": ["X1","F11"],
        "F11_values": [-1.0, -0.5, 0.0, 0.5, 1.0],  # Normalized -1 to +1
        "X1_values": [-1.0, -0.9, -0.8, -0.7, -0.6, -0.5, -0.4, -0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],  # Normalized -1 to +1
    },
    {
        "name": "2q_mult",
        "enabled": EXP_ENABLE_2,
        "fixed_values": {
            "X1": 0.0,          # Normalized: 0 -> IREFP/2
            "X2": 0.0,          # Normalized: 0 -> IREFP/2
            "TRIM": 1.0,        # Normalized: 0.1 -> 0.1*IREFP
            "F11": 0.0,         # Normalized: 1.0 -> IREFP
            "F12": 0.0,         # Normalized: 0 -> IREFP/2
            "IREFP": 100e-9,    # Actual current in Amps
            "ERASE_PROG": ["ERASE", "PROGRAM"],
        },
        "sweep_variables": ["KGAIN","IMEAS"],
        "KGAIN_values": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],  # Normalized -1 to +1
        "IMEAS_values": [-1.0, -0.9, -0.8, -0.7, -0.6, -0.5, -0.4, -0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],  # Normalized -1 to +1

    },
    {
        "name": "1q_mult",
        "enabled": EXP_ENABLE_3,
        "fixed_values": {
            "X2": 0.0,          # Normalized: 0 -> IREFP/2
            "KGAIN": 1.0,        # Normalized: 0.1 -> 0.1*IREFP
            "F11": 0.0,         # Normalized: 1.0 -> IREFP
            "F12": 0.0,         # Normalized: 0 -> IREFP/2
            "IREFP": 100e-9,    # Actual current in Amps
            "IMEAS": 0.0,       # Normalized: 0 -> IREFP/2
            "ERASE_PROG": ["ERASE", "PROGRAM"],
        },
        "sweep_variables": ["TRIM","IMEAS","X1"],
        "TRIM_values": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],  # Normalized 0 to 1
        "IMEAS_values": [-1.0, -0.9, -0.8, -0.7, -0.6, -0.5, -0.4, -0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],  # Normalized -1 to +1
        "X1_values": [0],  # Normalized -1 to +1
    },
        {
        "name": "1q_div",
        "enabled": EXP_ENABLE_4,
        "fixed_values": {
            "X2": 0.0,          # Normalized: 0 -> IREFP/2
            "KGAIN": 1.0,        # Normalized: 0.1 -> 0.1*IREFP
            "F11": 0.0,         # Normalized: 1.0 -> IREFP
            "F12": 0.0,         # Normalized: 0 -> IREFP/2
            "IREFP": 100e-9,    # Actual current in Amps
            "IMEAS": 0.0,       # Normalized: 0 -> IREFP/2
            "ERASE_PROG": ["ERASE", "PROGRAM"],
        },
        "sweep_variables": ["TRIM","IMEAS","X1"],
        "TRIM_values": [1.0],  # Normalized 0 to 1
        "X1_values": [-1.0, -0.9, -0.8, -0.7, -0.6, -0.5, -0.4, -0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],  # Normalized -1 to +1
        "IMEAS_values": [0],  # Normalized -1 to +1
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

