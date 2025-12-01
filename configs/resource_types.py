# -*- coding: utf-8 -*-
"""
Resource Types and Instrument Capability Definitions

This module defines the measurement types and instrument capabilities
used for experiment configuration. These definitions guide the static
allocation of terminals to instrument channels.

Measurement Types (from CSV):
    V    - Voltage measurement/force (requires high-resolution SMU)
    I    - Current measurement/force (any SMU) - "pulled" direction
    GNDU - Ground unit (5270B GNDU only)
    VSU  - Voltage source unit (any SMU or 4156B VSU)
    PPG  - Pulse pattern generator (81104A)
    COUNTER - Frequency/time measurement (53230A)

Instrument Capabilities:
    Keysight 5270B:
        - Channels 1-4: High-Resolution SMUs (priority for V)
        - Channels 5-8: Medium-Power SMUs
        - GNDU: Ground unit (for GNDU terminals only)
    
    Agilent 4156B:
        - Channels 1-4: SMUs (for I, V, VSU)
        - Channels 21-22: VSU outputs
    
    Agilent 81104A:
        - Channels 1-2: Pulse outputs (for PPG)
    
    Keysight 53230A:
        - Channels 1-3: Counter inputs (for COUNTER)

Compliance Settings:
    - Voltage sources: 1mA (0.001A) current compliance
    - Current sources: 2V voltage compliance
    - Current direction: "pulled" (positive = flowing into IV meter)
"""

from enum import Enum, auto
from typing import Dict, List, NamedTuple


class MeasurementType(Enum):
    """Measurement function types from CSV specification."""
    V = auto()       # Voltage force/measure - requires HR SMU
    I = auto()       # Current force/measure - any SMU, "pulled" direction
    GNDU = auto()    # Ground unit - 5270B GNDU only
    VSU = auto()     # Voltage source - any SMU or 4156B VSU
    PPG = auto()     # Pulse generator - 81104A
    COUNTER = auto() # Counter input - 53230A


class InstrumentType(Enum):
    """Available instrument types."""
    IV5270B = "IV5270B"      # Keysight 5270B Precision IV Analyzer
    IV4156B = "IV4156B"      # Agilent 4156B Semiconductor Parameter Analyzer
    PG81104A = "PG81104A"    # Agilent 81104A Pulse Generator
    CT53230A = "CT53230A"    # Keysight 53230A Counter


class ChannelType(Enum):
    """Channel types within instruments."""
    HR_SMU = auto()    # High-Resolution SMU (5270B CH1-4)
    MP_SMU = auto()    # Medium-Power SMU (5270B CH5-8)
    SMU = auto()       # Standard SMU (4156B CH1-4)
    GNDU = auto()      # Ground Unit (5270B)
    VSU = auto()       # Voltage Source Unit (4156B CH21-22)
    PULSE = auto()     # Pulse output (81104A)
    COUNTER_IN = auto() # Counter input (53230A)


class ChannelInfo(NamedTuple):
    """Information about an instrument channel."""
    instrument: InstrumentType
    channel: int
    channel_type: ChannelType
    description: str


# ============================================================================
# Instrument Channel Definitions
# ============================================================================

# Keysight 5270B channels
E5270B_CHANNELS: Dict[int, ChannelInfo] = {
    1: ChannelInfo(InstrumentType.IV5270B, 1, ChannelType.HR_SMU, "5270B High-Resolution SMU 1"),
    2: ChannelInfo(InstrumentType.IV5270B, 2, ChannelType.HR_SMU, "5270B High-Resolution SMU 2"),
    3: ChannelInfo(InstrumentType.IV5270B, 3, ChannelType.HR_SMU, "5270B High-Resolution SMU 3"),
    4: ChannelInfo(InstrumentType.IV5270B, 4, ChannelType.HR_SMU, "5270B High-Resolution SMU 4"),
    5: ChannelInfo(InstrumentType.IV5270B, 5, ChannelType.MP_SMU, "5270B Medium-Power SMU 5"),
    6: ChannelInfo(InstrumentType.IV5270B, 6, ChannelType.MP_SMU, "5270B Medium-Power SMU 6"),
    7: ChannelInfo(InstrumentType.IV5270B, 7, ChannelType.MP_SMU, "5270B Medium-Power SMU 7"),
    8: ChannelInfo(InstrumentType.IV5270B, 8, ChannelType.MP_SMU, "5270B Medium-Power SMU 8"),
    0: ChannelInfo(InstrumentType.IV5270B, 0, ChannelType.GNDU, "5270B Ground Unit"),
}

# Agilent 4156B channels
A4156B_CHANNELS: Dict[int, ChannelInfo] = {
    1: ChannelInfo(InstrumentType.IV4156B, 1, ChannelType.SMU, "4156B SMU 1"),
    2: ChannelInfo(InstrumentType.IV4156B, 2, ChannelType.SMU, "4156B SMU 2"),
    3: ChannelInfo(InstrumentType.IV4156B, 3, ChannelType.SMU, "4156B SMU 3"),
    4: ChannelInfo(InstrumentType.IV4156B, 4, ChannelType.SMU, "4156B SMU 4"),
    21: ChannelInfo(InstrumentType.IV4156B, 21, ChannelType.VSU, "4156B Voltage Source Unit 1"),
    22: ChannelInfo(InstrumentType.IV4156B, 22, ChannelType.VSU, "4156B Voltage Source Unit 2"),
}

# Agilent 81104A channels
A81104A_CHANNELS: Dict[int, ChannelInfo] = {
    1: ChannelInfo(InstrumentType.PG81104A, 1, ChannelType.PULSE, "81104A Pulse Output 1"),
    2: ChannelInfo(InstrumentType.PG81104A, 2, ChannelType.PULSE, "81104A Pulse Output 2"),
}

# Keysight 53230A channels
K53230A_CHANNELS: Dict[int, ChannelInfo] = {
    1: ChannelInfo(InstrumentType.CT53230A, 1, ChannelType.COUNTER_IN, "53230A Counter Input 1"),
    2: ChannelInfo(InstrumentType.CT53230A, 2, ChannelType.COUNTER_IN, "53230A Counter Input 2"),
    3: ChannelInfo(InstrumentType.CT53230A, 3, ChannelType.COUNTER_IN, "53230A Counter Input 3"),
}


# ============================================================================
# Measurement Type to Valid Channel Type Mapping
# ============================================================================

VALID_CHANNEL_TYPES: Dict[MeasurementType, List[ChannelType]] = {
    # V requires high-resolution, but can use any SMU
    MeasurementType.V: [
        ChannelType.HR_SMU,  # Highest priority
        ChannelType.MP_SMU,
        ChannelType.SMU,
    ],
    # I can use any SMU - current is "pulled" (into meter)
    MeasurementType.I: [
        ChannelType.HR_SMU,
        ChannelType.MP_SMU,
        ChannelType.SMU,
    ],
    # GNDU must use GNDU
    MeasurementType.GNDU: [
        ChannelType.GNDU,
    ],
    # VSU can use VSU channels or SMUs
    MeasurementType.VSU: [
        ChannelType.VSU,
        ChannelType.HR_SMU,
        ChannelType.MP_SMU,
        ChannelType.SMU,
    ],
    # PPG must use pulse generator
    MeasurementType.PPG: [
        ChannelType.PULSE,
    ],
    # COUNTER must use counter input
    MeasurementType.COUNTER: [
        ChannelType.COUNTER_IN,
    ],
}


# ============================================================================
# Terminal Configuration Structure
# ============================================================================

class TerminalConfig(NamedTuple):
    """Configuration for a single terminal."""
    terminal: str           # Logical terminal name (from CSV Terminals column)
    measurement_type: MeasurementType  # V, I, GNDU, VSU, PPG, COUNTER
    instrument: InstrumentType  # Which instrument
    channel: int            # Channel number on that instrument
    description: str        # Human-readable description


class ExperimentConfig(NamedTuple):
    """Complete configuration for an experiment."""
    name: str                           # Experiment name
    description: str                    # Human-readable description
    terminals: Dict[str, TerminalConfig]  # Terminal name -> config
    instruments_used: List[InstrumentType]  # List of instruments needed


# ============================================================================
# Default Compliance Settings
# ============================================================================

# Voltage source compliance: 1mA
VOLTAGE_COMPLIANCE_DEFAULT = 0.001  # Amps

# Current source compliance: 2V (limits negative voltage on current sources)
CURRENT_COMPLIANCE_DEFAULT = 2.0  # Volts
