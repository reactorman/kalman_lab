# -*- coding: utf-8 -*-
"""
Programmer Experiment Settings

QUICK-EDIT CONFIGURATION FILE
=============================
This file contains all the tunable parameters for the Programmer experiment.
Edit these values to quickly adjust your experiment without modifying other files.

Sections:
    1. VOLTAGE SETTINGS - VDD, VCC supply voltages
    2. CURRENT LISTS - IREFP and PROG_IN sweep values
    3. PPG SETTINGS - WR_ENB pulse configuration
    4. COUNTER SETTINGS - Time interval measurement thresholds
"""
import numpy as np

# ============================================================================
# 1. VOLTAGE SETTINGS
# ============================================================================

# Power supply voltages
VDD = 1.8       # VDD voltage in volts
VCC = 5.0       # VCC voltage in volts

# Derived voltages (calculated from above)
# PROG_OUT is configured as a current source (see PROG_OUT_CURRENT below)
# ICELLMEAS is set to VDD/2

# ============================================================================
# 2. CURRENT LISTS
# ============================================================================
# Units: Amps (use scientific notation, e.g., 1e-6 = 1µA, 100e-9 = 100nA)

# PROG_OUT current source (single value, not a list)
# This is CH1 configured as a current source
PROG_OUT_CURRENT = 100e-6      # 10 µA
PROG_OUT_COMPLIANCE = VCC    # 2.0 V compliance (minimum for this current range)

# IREFP current values (list of values to sweep through)
IREFP_VALUES = [
    100e-9,     # 100 nA
]

# PROG_IN current sweep (10nA to 100nA in 10nA steps)
PROG_IN_SWEEP = {
    "start": 10e-9,     # 10 nA
    "stop": 100e-9,     # 100 nA
    "step": 10e-9,      # 10 nA step
}

# Pre-calculated PROG_IN values (for reference/override)
# Generated from: [i * 10e-9 for i in range(1, 11)]
start = 0.1e-9
stop = 100e-9
points_per_decade = 10
PROG_IN_VALUES = np.logspace(np.log10(start), np.log10(stop), int(np.log10(stop/start) * points_per_decade + 1))
    
# ============================================================================
# 3. PPG SETTINGS (WR_ENB Pulse Configuration)
# ============================================================================
# WR_ENB behavior:
#   - Idles at VCC (high)
#   - When triggered, falls to 0V
#   - Remains at 0V for pulse_width
#   - Returns to VCC
#
# Time units: Use strings like "10NS", "100NS", "1US", "1MS", "10MS"

PPG_WR_ENB = {
    # Pulse timing
    "pulse_width": "500MS",     # Duration at 0V (500 milliseconds)
    "period": "10MS",           # Period (only matters for multiple pulses)
    "rise_time": "10NS",        # Rise time (10 nanoseconds)
    "fall_time": "10NS",        # Fall time (10 nanoseconds)
    
    # Voltage levels
    "vhigh": "VCC",             # High level - use "VCC" to track VCC value
    "vlow": 0.0,                # Low level (0V when pulsing)
    
    # Pulse behavior
    "idle_state": "high",       # Idles at VCC (uses inverted polarity)
    "pulse_count": 1,           # Number of pulses per trigger
}

# ============================================================================
# 4. COUNTER SETTINGS (Pulse Width Measurement)
# ============================================================================
# Counter measures pulse width on CH1 (PROG_OUT falling to rising edge).
# CH1: PROG_OUT from SMU (measures pulse width: falling edge to rising edge)
# CH2: Not connected

COUNTER_CONFIG = {
    # Channel assignment
    "channel": 1,               # CH1 = PROG_OUT (from SMU)
    "threshold": VCC*0.8,           # Threshold voltage in volts (default: 4V)
    "start_slope": "NEG",       # Falling edge on start (NEG = negative slope)
    "stop_slope": "POS",        # Rising edge on stop (POS = positive slope)
    
    # Input settings
    "coupling": "DC",           # DC coupling for logic signals
    "impedance": 1_000_000,     # 1 MOhm input impedance
}

# ============================================================================
# COMPLIANCE SETTINGS (Usually don't need to change)
# ============================================================================

# Current compliance for voltage sources (A)
VOLTAGE_SOURCE_COMPLIANCE = 0.001   # 1 mA

# Voltage compliance for current sources (V)
CURRENT_SOURCE_COMPLIANCE = 2.0     # 2 V

# ============================================================================
# TIMING SETTINGS
# ============================================================================

# Settling time between setting currents and measurement (seconds)
SETTLING_TIME = 0.01    # 10 ms

# Wait time after PPG pulse before reading counter (seconds)
POST_PULSE_DELAY = 0.002    # 2 ms

# ============================================================================
# HELPER FUNCTION - Get all settings as dict
# ============================================================================

def get_settings():
    """Return all settings as a dictionary for easy access."""
    return {
        # Voltages
        "VDD": VDD,
        "VCC": VCC,
        # Current sources
        "PROG_OUT_CURRENT": PROG_OUT_CURRENT,
        "PROG_OUT_COMPLIANCE": PROG_OUT_COMPLIANCE,
        # Current lists
        "IREFP_VALUES": IREFP_VALUES,
        "PROG_IN_VALUES": PROG_IN_VALUES,
        "PROG_IN_SWEEP": PROG_IN_SWEEP,
        # PPG
        "PPG_WR_ENB": PPG_WR_ENB,
        # Counter
        "COUNTER_CONFIG": COUNTER_CONFIG,
        # Compliance
        "VOLTAGE_SOURCE_COMPLIANCE": VOLTAGE_SOURCE_COMPLIANCE,
        "CURRENT_SOURCE_COMPLIANCE": CURRENT_SOURCE_COMPLIANCE,
        # Timing
        "SETTLING_TIME": SETTLING_TIME,
        "POST_PULSE_DELAY": POST_PULSE_DELAY,
    }

