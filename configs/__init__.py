# -*- coding: utf-8 -*-
"""
Experiment Configuration Package

Contains static configuration files for each experiment, generated based on
the instrument_config.csv design specification.

Each configuration file defines:
- Terminal to instrument/channel mappings
- Measurement functions for each terminal
- Resource allocation following priority rules

Configuration files are human-readable Python dictionaries.
The CSV file is NOT read at runtime - these configurations are pre-generated.
"""

from .resource_types import MeasurementType, InstrumentType, ChannelType
from .compute import COMPUTE_CONFIG
from .programmer import PROGRAMMER_CONFIG

__all__ = [
    'MeasurementType',
    'InstrumentType', 
    'ChannelType',
    'COMPUTE_CONFIG',
    'PROGRAMMER_CONFIG',
]

