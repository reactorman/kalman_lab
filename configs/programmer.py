# -*- coding: utf-8 -*-
"""
Programmer Experiment Configuration

Static configuration for the Programmer experiment.

This experiment characterizes programming timing by measuring the delay
from WR_ENB going low until PROG_OUT goes low.

Resource Allocation Summary:
    V terminals (2): PROG_OUT (with series resistor), ICELLMEAS
        → 5270B HR SMUs (channels 1-2)
    
    I terminals (2): IREFP, PROG_IN
        → 5270B HR SMUs (channels 3-4)
    
    GNDU terminal (1): VSS
        → 5270B GNDU
    
    PPG terminal (1): WR_ENB
        → 81104A Channel 1
    
    COUNTER terminal (time interval measurement):
        → 53230A Channel 1 (start - from PPG WR_ENB)
        → 53230A Channel 2 (stop - from PROG_OUT SMU)

Note: 4156B is NOT used in this experiment. All SMU functions are
      performed by the 5270B.

Counter Configuration:
    - Channel 1: Connected to PPG output (WR_ENB) - start event
    - Channel 2: Connected to PROG_OUT SMU output - stop event
    - Time interval measurement: WR_ENB falling edge to PROG_OUT falling edge
    - Threshold voltage: VCC/2 on both channels

Compliance Settings:
    - Voltage sources: 1mA compliance
    - Current sources: 2V compliance
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
    # V Terminals - High-Resolution SMUs
    # ------------------------------------
    "PROG_OUT": TerminalConfig(
        terminal="PROG_OUT",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=1,
        description="Programming output - 5270B HR SMU with series resistor, VCC applied"
    ),
    "ICELLMEAS": TerminalConfig(
        terminal="ICELLMEAS",
        measurement_type=MeasurementType.V,
        instrument=InstrumentType.IV5270B,
        channel=2,
        description="Cell measurement - 5270B HR SMU, VDD/2 applied"
    ),
    
    # ------------------------------------
    # I Terminals - Current Sources
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
        description="Ground reference - 5270B GNDU"
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
        description="Write enable pulse - 81104A Channel 1"
    ),
    
    # ------------------------------------
    # COUNTER Terminal - Time Interval Measurement
    # CH1: PPG output (WR_ENB) - start
    # CH2: SMU output (PROG_OUT) - stop
    # ------------------------------------
    "COUNTER": TerminalConfig(
        terminal="COUNTER",
        measurement_type=MeasurementType.COUNTER,
        instrument=InstrumentType.CT53230A,
        channel=1,  # Start channel (CH1 from PPG, CH2 from PROG_OUT)
        description="Time interval counter - 53230A (CH1=WR_ENB, CH2=PROG_OUT)"
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
# Pulse Generator Configuration for WR_ENB
# ============================================================================
# WR_ENB behavior:
#   - Starts at VCC (idle high)
#   - When triggered, falls to 0V with 10ns rise/fall time
#   - Remains at 0V for 1ms
#   - Returns to VCC

PROGRAMMER_PULSE_CONFIG = {
    "WR_ENB": {
        "default_width": "1MS",      # Pulse width: 1 millisecond at 0V
        "default_period": "10MS",    # Period (only matters for multiple pulses)
        "default_vhigh": None,       # Will be set to VCC at runtime
        "default_vlow": 0.0,         # Low level is 0V
        "default_rise": "10NS",      # 10ns rise time
        "default_fall": "10NS",      # 10ns fall time
        "idle_state": "high",        # Idle at VCC (inverted polarity)
    }
}

# ============================================================================
# Counter Configuration for Time Interval Measurement
# ============================================================================
# Counter measures time from WR_ENB going low to PROG_OUT going low
#   - Channel 1: Start event (WR_ENB falling edge from PPG)
#   - Channel 2: Stop event (PROG_OUT falling edge from SMU)
#   - Threshold: VCC/2 on both channels

PROGRAMMER_COUNTER_CONFIG = {
    "time_interval": {
        "start_channel": 1,     # CH1 connected to PPG (WR_ENB)
        "stop_channel": 2,      # CH2 connected to PROG_OUT SMU
        "coupling": "DC",       # DC coupling for logic signals
        "impedance": 1000000,   # 1 MOhm input impedance
        "threshold": None,      # Set to VCC/2 at runtime
        "slope_start": "NEG",   # Falling edge on start (WR_ENB goes low)
        "slope_stop": "NEG",    # Falling edge on stop (PROG_OUT goes low)
    }
}

# ============================================================================
# PROG_IN Current Sweep Configuration
# ============================================================================
# PROG_IN sweeps from 10nA to 100nA in steps of 10nA

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
    "VDD": 1.8,   # Power supply voltage
    "VCC": 5.0,   # VCC voltage
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
