# -*- coding: utf-8 -*-
"""
Sonos Experiment Settings

QUICK-EDIT CONFIGURATION FILE
=============================
Tunable parameters for the Sonos experiment: cell_init, PROG_IDEAL, PROG_ACTUAL.
No counter; only ICELLMEAS before/after. Erase mode increases ICELLMEAS,
program mode decreases it.

Sections:
    1. VOLTAGE SETTINGS - VDD, VCC
    2. CELL_INIT - target error, max WR_ENB pulse, mapping function
    3. TEST LIMITS - IMAX, IMIN for both test types
    4. PROG_IDEAL - list of WR_ENB pulse times (seconds)
    5. PROG_ACTUAL - constant WR_ENB time (ms), list of PROG_IN currents
"""
import numpy as np

# ============================================================================
# 1. VOLTAGE SETTINGS
# ============================================================================

VDD = 1.8       # VDD voltage in volts
VCC = 5.0       # VCC voltage in volts

# PROG_OUT current source (same role as programmer)
PROG_OUT_CURRENT = 10e-6      # Amps
PROG_OUT_COMPLIANCE = VCC     # V

# ============================================================================
# 2. CELL_INIT
# ============================================================================
# cell_init sets ICELLMEAS to a target current: prog_in=0, WR_ENB pulse width
# from mapping(icellmeas_measured, target). Pulse capped at WR_ENB_MAX_PULSE_SEC.
# Runs until |ICELLMEAS - target| <= TARGET_ERROR.

TARGET_ERROR = 0.5e-9   # Amps; convergence tolerance for cell_init (e.g. 0.5 nA)

WR_ENB_MAX_PULSE_SEC = 0.1   # 100 ms max; pulse never higher


def cell_init_pulse_time(icellmeas_measured: float, target_current: float) -> float:
    """
    Mapping: (ICELLMEAS measured, target current) -> WR_ENB pulse time in seconds.
    Used by cell_init. Return value is capped at WR_ENB_MAX_PULSE_SEC by the caller.
    Override this function in this file to match your device.

    Args:
        icellmeas_measured: Current ICELLMEAS in Amps
        target_current: Target ICELLMEAS in Amps

    Returns:
        Pulse time in seconds (will be capped at 100 ms in run_sonos)
    """
    delta = abs(target_current - icellmeas_measured)
    if delta <= 0:
        return 0.0
    # Placeholder: linear scaling 1e-9 A -> 10 ms, scale proportionally
    # Replace with your calibration: e.g. table lookup or fitted model
    time_sec = (delta / 1e-9) * 0.01   # 1 nA error -> 10 ms
    return min(time_sec, WR_ENB_MAX_PULSE_SEC)


# ============================================================================
# 3. TEST LIMITS (both PROG_IDEAL and PROG_ACTUAL)
# ============================================================================
# Program phase: start at IMAX, steps until IMIN.
# Erase phase: start at IMIN, steps until IMAX (test stopped by user or limit).

IMAX = 500e-9    # Amps (e.g. 500 nA) - upper limit
IMIN = 50e-9     # Amps (e.g. 50 nA)  - lower limit

# ============================================================================
# 4. PROG_IDEAL
# ============================================================================
# PROG_IN = 0. WR_ENB pulled low for each time in the list (seconds).
# Pulse time capped at 100 ms. One pulse per step until IMIN (program) / IMAX (erase).

PROG_IDEAL_WR_ENB_TIMES_SEC = [
    0.010,   # 10 ms
    0.020,   # 20 ms
    0.050,   # 50 ms
    0.100,   # 100 ms
]

# ============================================================================
# 5. PROG_ACTUAL
# ============================================================================
# WR_ENB constant pulse width (ms). PROG_IN swept through list (Amps).

PROG_ACTUAL_WR_ENB_MS = 100   # Constant WR_ENB pulse width in milliseconds

PROG_ACTUAL_PROG_IN_LIST = np.array([
    10e-9, 20e-9, 30e-9, 40e-9, 50e-9, 60e-9, 70e-9, 80e-9, 90e-9, 100e-9
])   # Amps; adjust to your sweep

# ============================================================================
# TIMING
# ============================================================================

SETTLING_TIME = 0.01      # Seconds after setting currents
POST_PULSE_DELAY = 0.002  # Seconds after WR_ENB before measure
CELL_INIT_MAX_ITERATIONS = 200   # Safety limit for cell_init loop

# ============================================================================
# HELPER
# ============================================================================

def get_settings():
    """Return all settings as a dictionary."""
    return {
        "VDD": VDD,
        "VCC": VCC,
        "TARGET_ERROR": TARGET_ERROR,
        "WR_ENB_MAX_PULSE_SEC": WR_ENB_MAX_PULSE_SEC,
        "IMAX": IMAX,
        "IMIN": IMIN,
        "PROG_IDEAL_WR_ENB_TIMES_SEC": PROG_IDEAL_WR_ENB_TIMES_SEC,
        "PROG_ACTUAL_WR_ENB_MS": PROG_ACTUAL_WR_ENB_MS,
        "PROG_ACTUAL_PROG_IN_LIST": PROG_ACTUAL_PROG_IN_LIST,
        "SETTLING_TIME": SETTLING_TIME,
        "POST_PULSE_DELAY": POST_PULSE_DELAY,
        "CELL_INIT_MAX_ITERATIONS": CELL_INIT_MAX_ITERATIONS,
    }
