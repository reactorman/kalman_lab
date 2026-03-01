# -*- coding: utf-8 -*-
"""
Big Kalman Experiment Configuration

Uses only the 5270B and the E5250A switch matrix. Switch matrix has 3 blades
of 12 channels each (36 outputs), with VCC (input 1) and VSS (input 2).

Pinout (fixture / switch matrix control):
    1: ADDR4       — E5250A control (GPIB in this setup)
    2: ADDR3       — E5250A control
    3: ADDR2       — E5250A control
    4: ADDR1       — E5250A control
    5: ADDR0       — E5250A control
    6: VCC         — SMU2; apply VCC (default 5V); measure IVCC if requested
    7: VSS         — Hardwired to GNDU; no code (see remarks)
    8: VDD         — SMU3; apply VDD (default 1.8V)
    9: IMEAS       — SMU4; force IMEAS (current, sinks into SMU); VCOMP 1.8V; measure VIMEAS if requested
   10: IREFP       — SMU5; force IREFP (current, sinks into SMU); measure VREFP if requested
   11: CLK         — E5250A control
   12: ARRAY_WR    — E5250A control
   13: MODE        — SMU6; apply VCC/2; when MODE requested, measure current → 3-bit IADC_REF code
   14: MODE_EN     — E5250A control
   15: CELLMEAS    — SMU1; apply VDD; measure ICELLMEAS when requested

SMU7: Apply VCC whenever applying VCC to SMU2; current on SMU7 never measured.

Remarks:
    - VSS (pin 7) is hardwired to GNDU. GNDU does not need to be enabled or have code.
    - E5250A is controlled via GPIB (driver: instruments/sw_e5250a.py).
    - Blade mapping: pins 1–12 = blade 1 outputs 1–12; 13–24 = blade 2 outputs 1–12; 25–36 = blade 3 outputs 1–12.
"""

from .resource_types import (
    MeasurementType, InstrumentType, TerminalConfig, ExperimentConfig
)

# ============================================================================
# Big Kalman Terminal Configurations (5270B channels only)
# ============================================================================

BIG_KALMAN_TERMINALS = {
    "VCC": TerminalConfig(
        terminal="VCC",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=2,
        description="VCC voltage - 5270B SMU2 (Pin 6); default 5V; IVCC measured here if requested",
    ),
    "VSS": TerminalConfig(
        terminal="VSS",
        measurement_type=MeasurementType.GNDU,
        instrument=InstrumentType.IV5270B,
        channel=0,
        description="VSS - hardwired to GNDU (Pin 7); no code",
    ),
    "VDD": TerminalConfig(
        terminal="VDD",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=3,
        description="VDD voltage - 5270B SMU3 (Pin 8); default 1.8V",
    ),
    "IMEAS": TerminalConfig(
        terminal="IMEAS",
        measurement_type=MeasurementType.I,
        instrument=InstrumentType.IV5270B,
        channel=4,
        description="IMEAS current - 5270B SMU4 (Pin 9); sinks current; VCOMP 1.8V; VIMEAS measured here if requested",
    ),
    "IREFP": TerminalConfig(
        terminal="IREFP",
        measurement_type=MeasurementType.I,
        instrument=InstrumentType.IV5270B,
        channel=5,
        description="IREFP current - 5270B SMU5 (Pin 10); sinks current; VREFP measured here if requested",
    ),
    "MODE": TerminalConfig(
        terminal="MODE",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=6,
        description="MODE - 5270B SMU6 (Pin 13); apply VCC/2; measure current for 3-bit IADC_REF code when MODE requested",
    ),
    "CELLMEAS": TerminalConfig(
        terminal="CELLMEAS",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=1,
        description="CELLMEAS - 5270B SMU1 (Pin 15); apply VDD; measure ICELLMEAS when requested",
    ),
}

# SMU7 is VCC duplicate (no terminal; applied in experiment when applying VCC)
BIG_KALMAN_SMU7_VCC_CHANNEL = 7

# ============================================================================
# Experiment Config
# ============================================================================

BIG_KALMAN_CONFIG = ExperimentConfig(
    name="BigKalman",
    description="Big Kalman experiment - 5270B + E5250A switch matrix; VCC/VSS inputs; test modes TBD",
    terminals=BIG_KALMAN_TERMINALS,
    instruments_used=[
        InstrumentType.IV5270B,
        InstrumentType.SW_E5250A,
    ],
)

# ============================================================================
# Helpers
# ============================================================================

BIG_KALMAN_BY_INSTRUMENT = {
    InstrumentType.IV5270B: {
        name: cfg for name, cfg in BIG_KALMAN_TERMINALS.items()
        if cfg.instrument == InstrumentType.IV5270B
    },
    InstrumentType.SW_E5250A: {},
}

BIG_KALMAN_BY_TYPE = {
    MeasurementType.V: [
        name for name, cfg in BIG_KALMAN_TERMINALS.items()
        if cfg.measurement_type == MeasurementType.V
    ],
    MeasurementType.I: [
        name for name, cfg in BIG_KALMAN_TERMINALS.items()
        if cfg.measurement_type == MeasurementType.I
    ],
    MeasurementType.GNDU: [
        name for name, cfg in BIG_KALMAN_TERMINALS.items()
        if cfg.measurement_type == MeasurementType.GNDU
    ],
}
