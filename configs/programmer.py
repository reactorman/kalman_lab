# -*- coding: utf-8 -*-
"""
Programmer Experiment Configuration

Static configuration for the Programmer experiment.

This experiment characterizes programming timing by measuring the delay
from WR_ENB going low until PROG_OUT goes low.

Resource Allocation Summary:
    V terminals (4): ICELLMEAS (Pin 5), VDD (Pin 19, 1.8V), VCC (Pin 17, 5V), ERASE_PROG (Pin 13, 5V or 0V)
        → 5270B HR SMUs (channels 2, 5-7)
    
    I terminals (3): PROG_OUT (Pin 6, current source +20µA), IREFP (Pin 10), PROG_IN (Pin 7)
        → 5270B HR SMUs (channels 1, 3-4)
    
    GNDU terminal (1): VSS (Pin 18)
        → 5270B GNDU
    
    PPG terminal (1): WR_ENB (Pin 8)
        → 81104A Channel 1 (not connected to counter)
    
    COUNTER terminal (pulse width measurement):
        → 53230A Channel 1 (from PROG_OUT SMU, Pin 6, measures pulse width: falling to rising)
        → 53230A Channel 2 (not connected)
        → Both channels connected to PROG_OUT to measure pulse width

    Unused pins connected to GNDU (15):  <-- not used, should be ok to leave floating
        Pins 1, 2, 3, 4, 9, 11, 12, 14, 15, 16, 20, 21, 22, 23, 24
        → Connected to GNDU via unused instrument channels set to 0V

Note: 4156B is NOT used in this experiment. All SMU functions are
      performed by the 5270B.

Counter Configuration:
    - Channel 1: Connected to PROG_OUT SMU output (Pin 6) - measures pulse width (falling to rising)
    - Channel 2: Not connected
    - Pulse width measurement: PROG_OUT (Pin 6) falling edge to rising edge on CH1
    - Threshold voltage: Configurable (default: 4V)

Compliance Settings:
    - Voltage sources: 1mA compliance
    - Current sources: 0.1V compliance for positive currents, 2V for non-positive
    - Current direction: "pulled" (positive = into IV meter)
"""

from .resource_types import (
    MeasurementType, InstrumentType, TerminalConfig, ExperimentConfig
)

# ============================================================================
# Programmer Experiment Terminal Configurations
# ============================================================================

PROGRAMMER_TERMINALS = {
    # ------------------------------------
    # I Terminals - Current Sources
    # Current is "pulled" (positive = into meter)
    # ------------------------------------
    "PROG_OUT": TerminalConfig(
        terminal="PROG_OUT",
        measurement_type=MeasurementType.I,
        instrument=InstrumentType.IV5270B,
        channel=1,
        description="Programming output - 5270B HR SMU current source, +20µA with 1.8V compliance (Pin 6)"
    ),
    
    # ------------------------------------
    # V Terminals - High-Resolution SMUs
    # ------------------------------------
    "ICELLMEAS": TerminalConfig(
        terminal="ICELLMEAS",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=2,
        description="Cell measurement - 5270B HR SMU, VDD/2 applied"
    ),
    
    # ------------------------------------
    # I Terminals - Current Sources (continued)
    # Current is "pulled" (positive = into meter)
    # ------------------------------------
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
        description="Programming input current - 5270B HR SMU (10nA to 100nA)"
    ),
    
    # ------------------------------------
    # GNDU Terminal - Ground Unit (5270B only)
    # ------------------------------------
    "VSS": TerminalConfig(
        terminal="VSS",
        measurement_type=MeasurementType.GNDU,
        instrument=InstrumentType.IV5270B,
        channel=0,  # GNDU is channel 0 in our convention
        description="Ground reference - 5270B GNDU (Pin 18)"
    ),
    
    # ------------------------------------
    # V Terminals - Voltage Sources (continued)
    # VDD, VCC, and ERASE_PROG are voltage sources on 5270B
    # ------------------------------------
    "VDD": TerminalConfig(
        terminal="VDD",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=5,
        description="Power supply voltage source - 5270B HR SMU Channel 5, 1.8V (Pin 19)"
    ),
    "VCC": TerminalConfig(
        terminal="VCC",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=6,
        description="VCC voltage source - 5270B HR SMU Channel 6, 5V (Pin 17)"
    ),
    "ERASE_PROG": TerminalConfig(
        terminal="ERASE_PROG",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=7,
        description="Erase/Program voltage source - 5270B HR SMU Channel 7, 5V (erase) or 0V (program) (Pin 13)"
    ),
    
    # ------------------------------------
    # PPG Terminal - Pulse Generator
    # WR_ENB: Starts at VCC, triggered goes to 0V for 1ms, 10ns rise/fall
    # ------------------------------------
    "WR_ENB": TerminalConfig(
        terminal="WR_ENB",
        measurement_type=MeasurementType.PPG,
        instrument=InstrumentType.PG81104A,
        channel=1,
        description="Write enable pulse - 81104A Channel 1 (Pin 8)"
    ),
    
    # ------------------------------------
    # COUNTER Terminal - Pulse Width Measurement
    # CH1: PROG_OUT SMU (measures pulse width: falling to rising edge)
    # CH2: Not connected
    # ------------------------------------
    "COUNTER": TerminalConfig(
        terminal="COUNTER",
        measurement_type=MeasurementType.COUNTER,
        instrument=InstrumentType.CT53230A,
        channel=1,  # CH1 connected to PROG_OUT, measures pulse width
        description="Pulse width counter - 53230A CH1 (PROG_OUT falling to rising)"
    ),
}

# ============================================================================
# Programmer Experiment Configuration
# ============================================================================

PROGRAMMER_CONFIG = ExperimentConfig(
    name="Programmer",
    description="Programming timing measurement - time from WR_ENB low to PROG_OUT low",
    terminals=PROGRAMMER_TERMINALS,
    instruments_used=[
        InstrumentType.IV5270B,
        InstrumentType.PG81104A,
        InstrumentType.CT53230A,
    ]
)

# ============================================================================
# Helper Dictionaries for Experiment Execution
# ============================================================================

# Terminals grouped by instrument for efficient setup
PROGRAMMER_BY_INSTRUMENT = {
    InstrumentType.IV5270B: {
        name: cfg for name, cfg in PROGRAMMER_TERMINALS.items()
        if cfg.instrument == InstrumentType.IV5270B
    },
    InstrumentType.PG81104A: {
        name: cfg for name, cfg in PROGRAMMER_TERMINALS.items()
        if cfg.instrument == InstrumentType.PG81104A
    },
    InstrumentType.CT53230A: {
        name: cfg for name, cfg in PROGRAMMER_TERMINALS.items()
        if cfg.instrument == InstrumentType.CT53230A
    },
}

# Terminals grouped by measurement type
PROGRAMMER_BY_TYPE = {
    MeasurementType.V: [
        name for name, cfg in PROGRAMMER_TERMINALS.items()
        if cfg.measurement_type == MeasurementType.V
    ],
    MeasurementType.I: [
        name for name, cfg in PROGRAMMER_TERMINALS.items()
        if cfg.measurement_type == MeasurementType.I
    ],
    MeasurementType.GNDU: [
        name for name, cfg in PROGRAMMER_TERMINALS.items()
        if cfg.measurement_type == MeasurementType.GNDU
    ],
    MeasurementType.PPG: [
        name for name, cfg in PROGRAMMER_TERMINALS.items()
        if cfg.measurement_type == MeasurementType.PPG
    ],
    MeasurementType.COUNTER: [
        name for name, cfg in PROGRAMMER_TERMINALS.items()
        if cfg.measurement_type == MeasurementType.COUNTER
    ],
}

# ============================================================================
# Pulse Generator Configuration for WR_ENB (Pin 8)
# ============================================================================
# WR_ENB (Pin 8) behavior:
#   - Starts at VCC (idle high)
#   - When triggered, falls to 0V with 10ns rise/fall time
#   - Remains at 0V for 1ms
#   - Returns to VCC
#
# Note: ERASE_PROG (Pin 13) is now a voltage source on 5270B Channel 7,
#       not a PPG terminal. It is set to 5V for erase or 0V for program.

PROGRAMMER_PULSE_CONFIG = {
    "WR_ENB": {
        "default_width": "500MS",    # Pulse width: 500 milliseconds at 0V
        "default_period": "10MS",    # Period (only matters for multiple pulses)
        "default_vhigh": None,       # Will be set to VCC at runtime
        "default_vlow": 0.0,         # Low level is 0V
        "default_rise": "10NS",      # 10ns rise time
        "default_fall": "10NS",      # 10ns fall time
        "idle_state": "high",        # Idle at VCC (inverted polarity)
    }
}

# ============================================================================
# Counter Configuration for Pulse Width Measurement
# ============================================================================
# Counter measures pulse width on CH1 (PROG_OUT falling to rising edge)
#   - Channel 1: PROG_OUT from SMU (Pin 6) - measures pulse width
#   - Channel 2: Not connected
#   - Threshold: Configurable (default: 4V)
#   - Note: PPG (WR_ENB) is not connected to the counter

PROGRAMMER_COUNTER_CONFIG = {
    "pulse_width": {
        "channel": 1,           # CH1 connected to PROG_OUT SMU (Pin 6)
        "coupling": "DC",       # DC coupling for logic signals
        "impedance": 1000000,   # 1 MOhm input impedance
        "threshold": None,      # Set from settings at runtime (default: 4V)
        "start_slope": "NEG",   # Falling edge on start (PROG_OUT goes low)
        "stop_slope": "POS",    # Rising edge on stop (PROG_OUT goes high)
    }
}

# ============================================================================
# PROG_IN (Pin 7) Current Sweep Configuration
# ============================================================================
# PROG_IN (Pin 7) sweeps from 10nA to 100nA in steps of 10nA

PROGRAMMER_PROG_IN_SWEEP = {
    "start": 10e-9,     # 10 nA
    "stop": 100e-9,     # 100 nA
    "step": 10e-9,      # 10 nA step
    "values": [i * 10e-9 for i in range(1, 11)],  # [10nA, 20nA, ..., 100nA]
}

# ============================================================================
# IREFP Values Configuration
# ============================================================================
# IREFP has a list of values (user-configurable)

PROGRAMMER_IREFP_VALUES = []  # User will populate this list

# ============================================================================
# Default Voltage Values
# ============================================================================

PROGRAMMER_DEFAULTS = {
    "VDD": 1.8,   # Power supply voltage (Pin 19)
    "VCC": 5.0,   # VCC voltage (Pin 17)
    "ERASE_PROG_ERASE": 5.0,   # ERASE_PROG voltage for erase state (Pin 13)
    "ERASE_PROG_PROGRAM": 0.0, # ERASE_PROG voltage for program state (Pin 13)
}

# ============================================================================
# Enable Sequence
# ============================================================================
# Order of enabling: PPG first, then voltage sources, then current sources

PROGRAMMER_ENABLE_SEQUENCE = [
    "PPG",      # 1. Pulse generator (WR_ENB at VCC)
    "VOLTAGE",  # 2. Voltage sources (PROG_OUT at VCC, ICELLMEAS at VDD/2)
    "CURRENT",  # 3. Current sources (IREFP, PROG_IN)
]

# ============================================================================
# Measurement Recording Configuration
# ============================================================================
# What to record for each measurement point:
#   - All current settings (IREFP, PROG_IN values)
#   - Starting ICELLMEAS current
#   - Final ICELLMEAS current
#   - Pulse width (time interval from counter)

PROGRAMMER_RECORD_FIELDS = [
    "IREFP",
    "PROG_IN",
    "ICELLMEAS_START",
    "ICELLMEAS_FINAL",
    "PULSE_WIDTH",
]
