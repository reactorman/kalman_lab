# -*- coding: utf-8 -*-
"""
Base Experiment Runner

Provides common functionality for all experiment execution scripts.
Handles instrument initialization, bias setup, and measurement coordination
based on experiment configuration files.
"""

import sys
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyvisa

from instruments.base import (
    set_test_mode, get_test_mode, ensure_directories,
    initialize_csv, TEST_COMMANDS_FILE, LOG_DIR
)
from instruments import CT53230A, IV4156B, IV5270B, PG81104A, SR570, SR560
from configs.resource_types import (
    MeasurementType, InstrumentType, TerminalConfig, ExperimentConfig
)


# Default GPIB addresses
DEFAULT_ADDRESSES = {
    InstrumentType.CT53230A: 'GPIB0::5::INSTR',
    InstrumentType.IV4156B: 'GPIB0::15::INSTR',
    InstrumentType.IV5270B: 'GPIB0::17::INSTR',
    InstrumentType.PG81104A: 'GPIB0::10::INSTR',
}


class ExperimentRunner:
    """
    Base class for running experiments with configured terminal mappings.
    
    Provides:
    - Instrument initialization based on experiment config
    - Terminal-based bias setup using logical names
    - Measurement coordination across instruments
    - TEST_MODE support for all operations
    """
    
    def __init__(self, config: ExperimentConfig, test_mode: bool = False,
                 addresses: Dict[InstrumentType, str] = None):
        """
        Initialize the experiment runner.
        
        Args:
            config: ExperimentConfig defining terminal mappings
            test_mode: If True, log commands without hardware access
            addresses: Optional custom GPIB addresses
        """
        self.config = config
        self.test_mode = test_mode
        self.addresses = addresses or DEFAULT_ADDRESSES
        
        # Set up logging
        ensure_directories()
        log_file = os.path.join(
            LOG_DIR,
            f'{config.name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        )
        
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(f'Experiment.{config.name}')
        
        # Set global test mode
        set_test_mode(test_mode)
        
        if test_mode:
            self.logger.info("=" * 60)
            self.logger.info("RUNNING IN TEST MODE - No hardware communication")
            self.logger.info(f"Commands logged to: {TEST_COMMANDS_FILE}")
            self.logger.info("=" * 60)
        
        # Initialize PyVISA
        self.rm = None
        if not test_mode:
            try:
                self.rm = pyvisa.ResourceManager()
                self.logger.info("PyVISA ResourceManager initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize ResourceManager: {e}")
                raise
        
        # Instrument instances (created on demand)
        self._instruments: Dict[InstrumentType, Any] = {}
        
        # Terminal states (voltage/current values)
        self._terminal_states: Dict[str, float] = {}
        
        # Initialize CSV
        initialize_csv()
    
    def _get_instrument(self, inst_type: InstrumentType):
        """Get or create an instrument instance."""
        if inst_type not in self._instruments:
            address = self.addresses.get(inst_type)
            if address is None:
                raise ValueError(f"No address configured for {inst_type}")
            
            # Create instrument based on type
            inst_classes = {
                InstrumentType.CT53230A: CT53230A,
                InstrumentType.IV4156B: IV4156B,
                InstrumentType.IV5270B: IV5270B,
                InstrumentType.PG81104A: PG81104A,
            }
            
            cls = inst_classes.get(inst_type)
            if cls is None:
                raise ValueError(f"Unknown instrument type: {inst_type}")
            
            self._instruments[inst_type] = cls(self.rm, address)
            self.logger.info(f"Initialized {inst_type.value} at {address}")
        
        return self._instruments[inst_type]
    
    def initialize_instruments(self) -> None:
        """Initialize all instruments needed for this experiment."""
        self.logger.info(f"Initializing instruments for {self.config.name} experiment")
        
        for inst_type in self.config.instruments_used:
            try:
                self._get_instrument(inst_type)
            except Exception as e:
                self.logger.error(f"Failed to initialize {inst_type}: {e}")
                raise
    
    def reset_all(self) -> None:
        """Reset all instruments to default state."""
        self.logger.info("Resetting all instruments...")
        for inst_type, inst in self._instruments.items():
            try:
                inst.reset()
                self.logger.info(f"{inst_type.value} reset")
            except Exception as e:
                self.logger.error(f"Failed to reset {inst_type.value}: {e}")
    
    def idn_all(self) -> Dict[str, str]:
        """Query identification of all instruments."""
        idn_responses = {}
        for inst_type, inst in self._instruments.items():
            try:
                idn = inst.idn_query()
                idn_responses[inst_type.value] = idn
            except Exception as e:
                self.logger.error(f"Failed to query {inst_type.value} IDN: {e}")
                idn_responses[inst_type.value] = f"ERROR: {e}"
        return idn_responses
    
    def idle_all(self) -> None:
        """Set all instruments to idle state."""
        self.logger.info("Setting all instruments to idle...")
        for inst_type, inst in self._instruments.items():
            try:
                inst.idle()
            except Exception as e:
                self.logger.error(f"Failed to idle {inst_type.value}: {e}")
    
    def close_all(self) -> None:
        """Close all instrument connections."""
        self.logger.info("Closing all instrument connections...")
        for inst_type, inst in self._instruments.items():
            try:
                inst.close()
            except Exception as e:
                self.logger.error(f"Failed to close {inst_type.value}: {e}")
        self._instruments.clear()
    
    # ========================================================================
    # Terminal-Based Operations
    # ========================================================================
    
    def get_terminal_config(self, terminal: str) -> TerminalConfig:
        """Get configuration for a terminal by name."""
        if terminal not in self.config.terminals:
            raise ValueError(f"Unknown terminal: {terminal}")
        return self.config.terminals[terminal]
    
    def set_terminal_voltage(self, terminal: str, voltage: float,
                            compliance: float = 0.1) -> None:
        """
        Set voltage on a terminal (V or VSU type).
        
        Args:
            terminal: Logical terminal name
            voltage: Voltage to set in volts
            compliance: Current compliance in amps
        """
        cfg = self.get_terminal_config(terminal)
        
        if cfg.measurement_type not in [MeasurementType.V, MeasurementType.VSU]:
            raise ValueError(f"Terminal {terminal} is not a voltage terminal")
        
        inst = self._get_instrument(cfg.instrument)
        
        if cfg.instrument == InstrumentType.IV5270B:
            inst.set_voltage(cfg.channel, voltage, compliance)
        elif cfg.instrument == InstrumentType.IV4156B:
            if cfg.channel in [21, 22]:  # VSU channels
                inst.set_vsu_voltage(cfg.channel, voltage)
            else:
                inst.set_voltage(cfg.channel, voltage, compliance)
        
        self._terminal_states[terminal] = voltage
        self.logger.info(f"{terminal}: Set to {voltage}V")
    
    def set_terminal_current(self, terminal: str, current: float,
                            compliance: float = 10.0) -> None:
        """
        Set current on a terminal (I type).
        
        Args:
            terminal: Logical terminal name
            current: Current to set in amps
            compliance: Voltage compliance in volts
        """
        cfg = self.get_terminal_config(terminal)
        
        if cfg.measurement_type != MeasurementType.I:
            raise ValueError(f"Terminal {terminal} is not a current terminal")
        
        inst = self._get_instrument(cfg.instrument)
        
        if cfg.instrument == InstrumentType.IV5270B:
            inst.set_current(cfg.channel, current, compliance)
        elif cfg.instrument == InstrumentType.IV4156B:
            inst.set_current(cfg.channel, current, compliance)
        
        self._terminal_states[terminal] = current
        self.logger.info(f"{terminal}: Set to {current}A")
    
    def enable_gndu(self, terminal: str) -> None:
        """
        Enable GNDU terminal.
        
        Args:
            terminal: GNDU terminal name
        """
        cfg = self.get_terminal_config(terminal)
        
        if cfg.measurement_type != MeasurementType.GNDU:
            raise ValueError(f"Terminal {terminal} is not a GNDU terminal")
        
        inst = self._get_instrument(cfg.instrument)
        # GNDU is enabled by connecting it
        inst.enable_channels([cfg.channel])
        self.logger.info(f"{terminal}: GNDU enabled")
    
    def set_pulse(self, terminal: str, vhigh: float, vlow: float,
                 width: str, period: str = "1US", count: int = 1) -> None:
        """
        Configure and trigger pulse on PPG terminal.
        
        Args:
            terminal: PPG terminal name
            vhigh: High voltage level
            vlow: Low voltage level
            width: Pulse width (e.g., "100NS")
            period: Pulse period (e.g., "1US")
            count: Number of pulses
        """
        cfg = self.get_terminal_config(terminal)
        
        if cfg.measurement_type != MeasurementType.PPG:
            raise ValueError(f"Terminal {terminal} is not a PPG terminal")
        
        inst = self._get_instrument(cfg.instrument)
        inst.pulse_single_channel(
            pulse_width=width,
            period=period,
            vhigh=vhigh,
            vlow=vlow,
            count=count,
            channel=cfg.channel
        )
        self.logger.info(f"{terminal}: Pulse {width} @ {vhigh}V, x{count}")
    
    def measure_frequency(self, terminal: str, record: bool = True) -> float:
        """
        Measure frequency on COUNTER terminal.
        
        Args:
            terminal: COUNTER terminal name
            record: If True, record to CSV
            
        Returns:
            Measured frequency in Hz
        """
        cfg = self.get_terminal_config(terminal)
        
        if cfg.measurement_type != MeasurementType.COUNTER:
            raise ValueError(f"Terminal {terminal} is not a COUNTER terminal")
        
        inst = self._get_instrument(cfg.instrument)
        freq = inst.measure_frequency(cfg.channel, record=record)
        self.logger.info(f"{terminal}: Frequency = {freq} Hz")
        return freq
    
    def measure_terminal_current(self, terminal: str, 
                                record: bool = True) -> float:
        """
        Measure current on a terminal.
        
        Args:
            terminal: Terminal name
            record: If True, record to CSV
            
        Returns:
            Measured current in amps
        """
        cfg = self.get_terminal_config(terminal)
        inst = self._get_instrument(cfg.instrument)
        
        # Perform spot measurement
        if cfg.instrument == InstrumentType.IV5270B:
            inst.set_measurement_mode(1, [cfg.channel])
            inst.execute_measurement()
            data = inst.read_data()
            try:
                current = float(data.split("I")[1].strip())
            except (IndexError, ValueError):
                current = 0.0
        elif cfg.instrument == InstrumentType.IV4156B:
            inst.set_measurement_mode(1, [cfg.channel])
            inst.execute_measurement()
            data = inst.read_measurement_data()
            try:
                current = float(data.split("I")[1].strip())
            except (IndexError, ValueError):
                current = 0.0
        else:
            current = 0.0
        
        if record:
            inst.record_measurement(f"{terminal}_Current", current, "A")
        
        self.logger.info(f"{terminal}: Current = {current} A")
        return current
    
    # ========================================================================
    # Experiment Lifecycle
    # ========================================================================
    
    def startup(self) -> None:
        """Standard experiment startup sequence."""
        self.logger.info("=" * 60)
        self.logger.info(f"Starting {self.config.name} experiment")
        self.logger.info("=" * 60)
        
        self.initialize_instruments()
        self.reset_all()
        
        idn = self.idn_all()
        for name, response in idn.items():
            self.logger.info(f"  {name}: {response.strip()}")
    
    def shutdown(self) -> None:
        """Standard experiment shutdown sequence."""
        self.logger.info("=" * 60)
        self.logger.info(f"Shutting down {self.config.name} experiment")
        self.logger.info("=" * 60)
        
        self.idle_all()
        self.close_all()
        
        self.logger.info("Experiment shutdown complete")
    
    def run(self) -> None:
        """
        Execute the experiment.
        
        Override this method in subclasses to define experiment-specific
        measurement sequences.
        """
        raise NotImplementedError("Subclasses must implement run()")
    
    def __enter__(self):
        """Context manager entry."""
        self.startup()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()
        return False

