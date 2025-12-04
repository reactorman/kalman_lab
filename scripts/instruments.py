# -*- coding: utf-8 -*-
"""
Instrument Orchestration Script

This script manages all laboratory instruments:
- Initializes all instrument connections
- Executes common commands (*RST, *IDN?)
- Runs measurement sequences combining multiple instruments
- Writes all measurements to CSV (measurements/results.csv)

Usage:
    python -m scripts.instruments [--test]
    
    --test: Run in TEST_MODE (log commands without hardware)

Instruments:
    - CT53230A: Keysight 53230A Counter
    - IV4156B: Agilent 4156B IV Meter
    - IV5270B: Keysight E5270B IV Meter  
    - PG81104A: Agilent 81104A Pulse Generator
    - SR570: SRS SR570 Current Preamplifier
    - SR560: SRS SR560 Voltage Preamplifier
"""

import sys
import os
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instruments.base import (
    set_test_mode, get_test_mode, ensure_directories, 
    initialize_csv, TEST_COMMANDS_FILE, get_timing_tracker
)
from instruments import (
    CT53230A, IV4156B, IV5270B, PG81104A, SR570, SR560
)


# ============================================================================
# Configuration
# ============================================================================

# Default GPIB addresses for each instrument
# Modify these to match your setup
INSTRUMENT_ADDRESSES = {
    'CT53230A': 'GPIB0::5::INSTR',    # Counter
    'IV4156B': 'GPIB0::15::INSTR',    # 4156B IV Meter
    'IV5270B': 'GPIB0::17::INSTR',    # E5270B IV Meter
    'PG81104A': 'GPIB0::10::INSTR',   # Pulse Generator
    'SR570': 'GPIB0::8::INSTR',       # Current Preamp (via GPIB-Serial)
    'SR560': 'GPIB0::9::INSTR',       # Voltage Preamp (via GPIB-Serial)
}

# Set up logging
def setup_logging(log_level: int = logging.INFO) -> None:
    """Configure logging for the application."""
    ensure_directories()
    
    log_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'logs', 
        f'instruments_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    )
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )


# ============================================================================
# Instrument Manager Class
# ============================================================================

class InstrumentManager:
    """
    Manages all laboratory instruments.
    
    Provides methods to initialize, reset, query, and coordinate
    multiple instruments for measurement sequences.
    """
    
    def __init__(self, addresses: Dict[str, str] = None, 
                 test_mode: bool = False):
        """
        Initialize the instrument manager.
        
        Args:
            addresses: Dictionary mapping instrument names to GPIB addresses
            test_mode: If True, run in TEST_MODE (no hardware)
        """
        self.addresses = addresses or INSTRUMENT_ADDRESSES
        self.test_mode = test_mode
        self.logger = logging.getLogger('InstrumentManager')
        
        # Set global test mode
        set_test_mode(test_mode)
        
        # Initialize PyVISA resource manager (only when not in test mode)
        if not test_mode:
            try:
                import pyvisa
                self.rm = pyvisa.ResourceManager()
                self.logger.info("PyVISA ResourceManager initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize ResourceManager: {e}")
                raise
        else:
            self.rm = None
            self.logger.info("TEST_MODE: ResourceManager not initialized")
        
        # Dictionary to hold instrument instances
        self.instruments: Dict[str, object] = {}
        
        # Initialize CSV file
        initialize_csv()
    
    def initialize_all(self) -> None:
        """Initialize all configured instruments."""
        self.logger.info("Initializing all instruments...")
        
        # Initialize each instrument type
        instrument_classes = {
            'CT53230A': CT53230A,
            'IV4156B': IV4156B,
            'IV5270B': IV5270B,
            'PG81104A': PG81104A,
            'SR570': SR570,
            'SR560': SR560,
        }
        
        for name, cls in instrument_classes.items():
            if name in self.addresses:
                try:
                    self.instruments[name] = cls(self.rm, self.addresses[name])
                    self.logger.info(f"{name} initialized at {self.addresses[name]}")
                except Exception as e:
                    self.logger.error(f"Failed to initialize {name}: {e}")
    
    def initialize_subset(self, names: List[str]) -> None:
        """
        Initialize only specified instruments.
        
        Args:
            names: List of instrument names to initialize
        """
        instrument_classes = {
            'CT53230A': CT53230A,
            'IV4156B': IV4156B,
            'IV5270B': IV5270B,
            'PG81104A': PG81104A,
            'SR570': SR570,
            'SR560': SR560,
        }
        
        for name in names:
            if name in instrument_classes and name in self.addresses:
                try:
                    cls = instrument_classes[name]
                    self.instruments[name] = cls(self.rm, self.addresses[name])
                    self.logger.info(f"{name} initialized")
                except Exception as e:
                    self.logger.error(f"Failed to initialize {name}: {e}")
    
    def reset_all(self) -> None:
        """Reset all initialized instruments to default state."""
        self.logger.info("Resetting all instruments...")
        for name, inst in self.instruments.items():
            try:
                inst.reset()
                self.logger.info(f"{name} reset")
            except Exception as e:
                self.logger.error(f"Failed to reset {name}: {e}")
    
    def idn_all(self) -> Dict[str, str]:
        """
        Query identification of all initialized instruments.
        
        Returns:
            Dictionary mapping instrument names to IDN responses
        """
        self.logger.info("Querying instrument identifications...")
        idn_responses = {}
        
        for name, inst in self.instruments.items():
            try:
                idn = inst.idn_query()
                idn_responses[name] = idn
                self.logger.info(f"{name}: {idn}")
            except Exception as e:
                self.logger.error(f"Failed to query {name} IDN: {e}")
                idn_responses[name] = f"ERROR: {e}"
        
        return idn_responses
    
    def error_check_all(self) -> Dict[str, str]:
        """
        Query error status of all initialized instruments.
        
        Returns:
            Dictionary mapping instrument names to error responses
        """
        self.logger.info("Checking instrument errors...")
        errors = {}
        
        for name, inst in self.instruments.items():
            try:
                err = inst.error_query()
                errors[name] = err
                if "0" not in err.split(",")[0]:
                    self.logger.warning(f"{name} error: {err}")
            except Exception as e:
                self.logger.error(f"Failed to query {name} error: {e}")
                errors[name] = f"QUERY_ERROR: {e}"
        
        return errors
    
    def idle_all(self) -> None:
        """Set all initialized instruments to idle state."""
        self.logger.info("Setting all instruments to idle...")
        for name, inst in self.instruments.items():
            try:
                inst.idle()
            except Exception as e:
                self.logger.error(f"Failed to idle {name}: {e}")
    
    def close_all(self) -> None:
        """Close all instrument connections."""
        self.logger.info("Closing all instrument connections...")
        for name, inst in self.instruments.items():
            try:
                inst.close()
            except Exception as e:
                self.logger.error(f"Failed to close {name}: {e}")
        self.instruments.clear()
    
    def get_instrument(self, name: str) -> Optional[object]:
        """
        Get an instrument instance by name.
        
        Args:
            name: Instrument name (e.g., 'IV5270B')
            
        Returns:
            Instrument instance or None if not found
        """
        return self.instruments.get(name)
    
    # ========================================================================
    # Measurement Sequences
    # ========================================================================
    
    def sequence_startup(self) -> None:
        """
        Standard startup sequence: reset all and query IDN.
        
        This should be called at the beginning of a measurement session
        to ensure all instruments are in a known state.
        """
        self.logger.info("=" * 60)
        self.logger.info("Starting instrument startup sequence")
        self.logger.info("=" * 60)
        
        self.reset_all()
        idn_responses = self.idn_all()
        
        self.logger.info("Startup sequence complete")
        self.logger.info("-" * 60)
        for name, idn in idn_responses.items():
            self.logger.info(f"  {name}: {idn.strip()}")
        self.logger.info("-" * 60)
    
    def sequence_shutdown(self) -> None:
        """
        Standard shutdown sequence: idle all and close connections.
        """
        self.logger.info("=" * 60)
        self.logger.info("Starting instrument shutdown sequence")
        self.logger.info("=" * 60)
        
        self.idle_all()
        self.close_all()
        
        # Log timing information in test mode
        if self.test_mode:
            tracker = get_timing_tracker()
            python_runtime, command_runtime, sweep_runtime, total_runtime = tracker.get_estimated_runtimes()
            
            self.logger.info("=" * 60)
            self.logger.info("TEST MODE RUNTIME ESTIMATION")
            self.logger.info("=" * 60)
            self.logger.info(f"Total Commands: {tracker.command_count}")
            self.logger.info(f"  - Sweep Commands (4156B/5270B): {tracker.sweep_count}")
            self.logger.info(f"  - Other Commands: {tracker.command_count - tracker.sweep_count}")
            self.logger.info("")
            self.logger.info("Runtime Breakdown:")
            self.logger.info(f"  Python Runtime:     {python_runtime:.3f} s")
            self.logger.info(f"  Command Runtime:    {command_runtime:.3f} s ({tracker.command_count - tracker.sweep_count} commands x 1 ms)")
            self.logger.info(f"  Sweep Runtime:      {sweep_runtime:.3f} s ({tracker.sweep_count} sweeps x 1 s)")
            self.logger.info(f"  ------------------------------")
            self.logger.info(f"  Total Runtime:      {total_runtime:.3f} s")
            self.logger.info("=" * 60)
        
        self.logger.info("Shutdown sequence complete")
    
    def sequence_iv_measurement(self, vd: float, vg: float, vb: float = 0,
                               use_5270b: bool = True) -> float:
        """
        Perform a spot IV measurement using the IV meter.
        
        Args:
            vd: Drain voltage
            vg: Gate voltage
            vb: Bulk voltage (default: 0)
            use_5270b: If True, use E5270B; else use 4156B
            
        Returns:
            Measured drain current in amps
        """
        if use_5270b:
            iv = self.get_instrument('IV5270B')
            if iv is None:
                self.logger.error("IV5270B not initialized")
                return 0.0
        else:
            iv = self.get_instrument('IV4156B')
            if iv is None:
                self.logger.error("IV4156B not initialized")
                return 0.0
        
        current = iv.spot_4terminal(vd, vg, vb)
        self.logger.info(f"IV measurement: Vd={vd}V, Vg={vg}V, Vb={vb}V -> Id={current}A")
        return current
    
    def sequence_pulse_stress(self, channel: int, vhigh: float, vlow: float,
                             pulse_width: str, period: str, count: int) -> None:
        """
        Apply pulse stress using the pulse generator.
        
        Args:
            channel: Pulse generator channel (1 or 2)
            vhigh: High voltage level
            vlow: Low voltage level
            pulse_width: Pulse width (e.g., "100NS")
            period: Pulse period (e.g., "1US")
            count: Number of pulses
        """
        pg = self.get_instrument('PG81104A')
        if pg is None:
            self.logger.error("PG81104A not initialized")
            return
        
        pg.pulse_stress(channel, vhigh, vlow, pulse_width, period, count)
        self.logger.info(f"Pulse stress complete: {count} pulses")
    
    def sequence_frequency_measurement(self, channel: int = 1) -> float:
        """
        Measure frequency using the counter.
        
        Args:
            channel: Counter input channel
            
        Returns:
            Measured frequency in Hz
        """
        counter = self.get_instrument('CT53230A')
        if counter is None:
            self.logger.error("CT53230A not initialized")
            return 0.0
        
        freq = counter.measure_frequency(channel)
        self.logger.info(f"Frequency measurement: {freq} Hz")
        return freq
    
    def sequence_vt_measurement(self, vd: float, target_current: float,
                               vg_start: float, vg_stop: float, vg_step: float,
                               use_5270b: bool = True) -> float:
        """
        Measure threshold voltage using constant current method.
        
        Args:
            vd: Drain voltage
            target_current: Target current for Vt definition
            vg_start: Gate voltage sweep start
            vg_stop: Gate voltage sweep stop
            vg_step: Gate voltage step
            use_5270b: If True, use E5270B; else use 4156B
            
        Returns:
            Threshold voltage in volts
        """
        if use_5270b:
            iv = self.get_instrument('IV5270B')
        else:
            iv = self.get_instrument('IV4156B')
        
        if iv is None:
            self.logger.error("IV meter not initialized")
            return float('nan')
        
        vt = iv.measure_vt_constant_current(vd, target_current, 
                                           vg_start, vg_stop, vg_step)
        self.logger.info(f"Vt measurement: {vt} V")
        return vt
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close all connections."""
        self.close_all()
        return False


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for the instrument control script."""
    parser = argparse.ArgumentParser(
        description='Laboratory Instrument Control System'
    )
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Run in TEST_MODE (log commands without hardware)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level)
    
    logger = logging.getLogger('main')
    
    if args.test:
        logger.info("=" * 60)
        logger.info("RUNNING IN TEST MODE - No hardware communication")
        logger.info(f"Commands will be logged to: {TEST_COMMANDS_FILE}")
        logger.info("=" * 60)
    
    # Create instrument manager
    with InstrumentManager(test_mode=args.test) as manager:
        # Initialize instruments
        # In TEST_MODE, all instruments can be initialized
        # In real mode, only initialize instruments that are connected
        if args.test:
            manager.initialize_all()
        else:
            # Modify this list based on your connected instruments
            manager.initialize_subset(['IV5270B', 'PG81104A'])
        
        # Run startup sequence
        manager.sequence_startup()
        
        # Example measurements (in TEST_MODE, these log commands)
        if args.test:
            # Test IV measurement
            manager.sequence_iv_measurement(vd=1.0, vg=1.0, vb=0)
            
            # Test Vt measurement
            manager.sequence_vt_measurement(
                vd=0.1, 
                target_current=1e-7,
                vg_start=0, 
                vg_stop=1.5, 
                vg_step=0.01
            )
            
            # Test pulse stress
            manager.sequence_pulse_stress(
                channel=1,
                vhigh=3.3,
                vlow=0,
                pulse_width="100NS",
                period="1US",
                count=1000
            )
            
            # Test frequency measurement
            manager.sequence_frequency_measurement()
        
        # Check for errors
        manager.error_check_all()
        
        # Shutdown
        manager.sequence_shutdown()
    
    logger.info("Instrument control session complete")


if __name__ == '__main__':
    main()

