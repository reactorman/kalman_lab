# -*- coding: utf-8 -*-
"""
Kalman Experiment Settings
==========================

Quick-edit configuration file for the Kalman-style closed-loop experiment
implemented in `experiments/run_kalman.py`.

All currents are specified in Amps.

Key ideas:
- X1, X2, IMEAS are constrained to the same bounds.
- TRIM1/TRIM2 and KGAIN1/KGAIN2 are independent (not linked).
- IMEAS is generated as a bounded random walk starting from IMEAS_INITIAL.
"""

# ============================================================================
# 1. VOLTAGE SETTINGS
# ============================================================================

VDD_DEFAULT = 1.8   # VDD voltage in volts
VCC_DEFAULT = 5.0   # VCC voltage in volts

# ============================================================================
# 2. CURRENT BOUNDS (APPLY TO X1, X2, IMEAS)
# ============================================================================

# Bounds for X1, X2 and IMEAS (in Amps)
MIN_CURRENT = 0.1e-9   # 0.1 nA
MAX_CURRENT = 100e-9   # 100 nA

# ============================================================================
# 3. TIME STEP
# ============================================================================

# Time step between successive IMEAS points (seconds)
# Used by the IMEAS generation routine and to scale time-dependent
# parameters such as KGAIN2 and F12 below.
TIME_STEP = 0.01  # seconds

# ============================================================================
# 4. REFERENCE / FIXED CURRENTS
# ============================================================================

# IREFP reference current (A)
IREFP_DEFAULT = 100e-9  # 100 nA

# Initial current settings for fixed bias currents (A)
TRIM1_INITIAL = 20e-9
TRIM2_INITIAL = 20e-9
KGAIN1_INITIAL = 25e-9
KGAIN2_PER_SEC = 25e-9           # base KGAIN2 rate (A / s)
KGAIN2_INITIAL = KGAIN2_PER_SEC * TIME_STEP
F11_INITIAL = 1.0
F12_PER_SEC = 0.0                # base F12 rate (unitless / s)
F12_INITIAL = F12_PER_SEC * TIME_STEP

# Initial X currents (A) – will be updated during the loop but start here
X1_INITIAL = 10e-9
X2_INITIAL = 10e-9

# ============================================================================
# 5. IMEAS TEST VECTOR GENERATION
# ============================================================================

# Starting IMEAS value (A) – must satisfy MIN_CURRENT <= IMEAS_INITIAL <= MAX_CURRENT
IMEAS_INITIAL = 10e-9

# Number of IMEAS points to generate (including the initial value)
IMEAS_NUM_POINTS = 50

# Maximum relative random step per point for the random walk.
# Each new value is approximately:
#     IMEAS_next ≈ IMEAS_prev * (1 + uniform(-IMEAS_MAX_REL_STEP, IMEAS_MAX_REL_STEP))
IMEAS_MAX_REL_STEP = 0.2  # ±20 % per step

# Optional additive Gaussian noise per step (A). Set to 0.0 to disable.
IMEAS_NOISE_STD = 0.0

# Optional RNG seed for reproducibility (set to None for non-deterministic runs)
RNG_SEED = 12345



