# -*- coding: utf-8 -*-
"""
Sonos Experiment Configuration

Static configuration for the Sonos experiment.
No counter; only ICELLMEAS before/after. cell_init sets ICELLMEAS to target
via WR_ENB pulse width (prog_in=0). PROG_IDEAL uses list of WR_ENB times;
PROG_ACTUAL uses constant WR_ENB time and list of PROG_IN currents.

Resource Allocation Summary:
    Same as Programmer except COUNTER is not used.
    V terminals: ICELLMEAS, VDD, VCC, ERASE_PROG → 5270B
    I terminals: PROG_OUT, IREFP, PROG_IN → 5270B
    GNDU: VSS → 5270B
    PPG: WR_ENB → 81104A
"""

from .resource_types import (
    MeasurementType, InstrumentType, TerminalConfig, ExperimentConfig
)

# ============================================================================
# Sonos Experiment Terminal Configurations (same as Programmer, no counter)
# ============================================================================

SONOS_TERMINALS = {
    "PROG_OUT": TerminalConfig(
        terminal="PROG_OUT",
        measurement_type=MeasurementType.I,
        instrument=InstrumentType.IV5270B,
        channel=1,
        description="Programming output - 5270B HR SMU current source (Pin 6)"
    ),
    "ICELLMEAS": TerminalConfig(
        terminal="ICELLMEAS",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=2,
        description="Cell measurement - 5270B HR SMU, VDD/2 applied"
    ),
    "IREFP": TerminalConfig(
        terminal="IREFP",
        measurement_type=MeasurementType.I,
        instrument=InstrumentType.IV5270B,
        channel=3,
        description="Reference current P - 5270B HR SMU"
    ),
    "PROG_IN": TerminalConfig(
        terminal="PROG_IN",
        measurement_type=MeasurementType.I,
        instrument=InstrumentType.IV5270B,
        channel=4,
        description="Programming input current - 5270B HR SMU"
    ),
    "VSS": TerminalConfig(
        terminal="VSS",
        measurement_type=MeasurementType.GNDU,
        instrument=InstrumentType.IV5270B,
        channel=0,
        description="Ground reference - 5270B GNDU (Pin 18)"
    ),
    "VDD": TerminalConfig(
        terminal="VDD",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=5,
        description="Power supply voltage - 5270B HR SMU (Pin 19)"
    ),
    "VCC": TerminalConfig(
        terminal="VCC",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=6,
        description="VCC voltage - 5270B HR SMU (Pin 17)"
    ),
    "ERASE_PROG": TerminalConfig(
        terminal="ERASE_PROG",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=7,
        description="Erase/Program - 5270B HR SMU, 5V (erase) or 0V (program) (Pin 13)"
    ),
    "WR_ENB": TerminalConfig(
        terminal="WR_ENB",
        measurement_type=MeasurementType.PPG,
        instrument=InstrumentType.PG81104A,
        channel=1,
        description="Write enable pulse - 81104A Channel 1 (Pin 8)"
    ),
}

# ============================================================================
# Sonos Experiment Configuration (no counter)
# ============================================================================

SONOS_CONFIG = ExperimentConfig(
    name="Sonos",
    description="Sonos ICELLMEAS characterization: cell_init, PROG_IDEAL, PROG_ACTUAL (no counter)",
    terminals=SONOS_TERMINALS,
    instruments_used=[
        InstrumentType.IV5270B,
        InstrumentType.PG81104A,
    ]
)

# ============================================================================
# Helper Dictionaries
# ============================================================================

SONOS_BY_INSTRUMENT = {
    InstrumentType.IV5270B: {
        name: cfg for name, cfg in SONOS_TERMINALS.items()
        if cfg.instrument == InstrumentType.IV5270B
    },
    InstrumentType.PG81104A: {
        name: cfg for name, cfg in SONOS_TERMINALS.items()
        if cfg.instrument == InstrumentType.PG81104A
    },
}

SONOS_BY_TYPE = {
    MeasurementType.V: [
        name for name, cfg in SONOS_TERMINALS.items()
        if cfg.measurement_type == MeasurementType.V
    ],
    MeasurementType.I: [
        name for name, cfg in SONOS_TERMINALS.items()
        if cfg.measurement_type == MeasurementType.I
    ],
    MeasurementType.GNDU: [
        name for name, cfg in SONOS_TERMINALS.items()
        if cfg.measurement_type == MeasurementType.GNDU
    ],
    MeasurementType.PPG: [
        name for name, cfg in SONOS_TERMINALS.items()
        if cfg.measurement_type == MeasurementType.PPG
    ],
}

# ============================================================================
# PPG (WR_ENB) default config - width set dynamically in cell_init and steps
# ============================================================================

SONOS_PULSE_CONFIG = {
    "WR_ENB": {
        "default_width": "100MS",   # Max 100ms for cell_init
        "default_period": "200MS", # > pulse width
        "default_vlow": 0.0,
        "default_rise": "10NS",
        "default_fall": "10NS",
        "idle_state": "high",
    }
}

# ============================================================================
# Default Voltages
# ============================================================================

SONOS_DEFAULTS = {
    "VDD": 1.8,
    "VCC": 5.0,
    "ERASE_PROG_ERASE": 5.0,
    "ERASE_PROG_PROGRAM": 0.0,
}
