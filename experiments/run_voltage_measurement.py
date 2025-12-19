#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Voltage Measurement Experiment Execution Script

Top-level execution script for measuring voltages on current sources.
This script:
- Uses the same setup as run_compute
- Sets all current sources to 20e-9 A
- Performs spot measurements of voltages on all current sources
- Writes results to CSV in measurements folder

Usage:
    python -m experiments.run_voltage_measurement [--test] [--vdd VDD] [--vcc VCC]
    
    --test: Run in TEST_MODE (log commands without hardware)
    --vdd: VDD voltage (default: 1.8V)
    --vcc: VCC voltage (default: 5.0V)

Configuration:
    Terminal mappings are defined in configs/compute.py
    This script uses the same configuration as run_compute.

Experiment Flow:
    1. Enable PPG in DC mode (VCC or 0V, never triggered)
    2. Enable voltage supplies (VDD, VCC via VSU)
    3. Enable fixed current supplies at 20e-9 A
    4. Measure voltages on all current source terminals
    5. Write CSV with current source names and voltages

Compliance Settings:
    - Voltage sources: 1mA compliance
    - Current sources: 2V compliance
    - Current direction: "pulled" (positive = into IV meter)
"""

import sys
import os
import argparse
import logging
import csv
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.base_experiment import ExperimentRunner
from configs.compute import (
    COMPUTE_CONFIG,
    COMPUTE_TERMINALS,
    COMPUTE_BY_TYPE,
    COMPUTE_DEFAULTS,
    COMPUTE_ENABLE_SEQUENCE,
    COMPUTE_PPG_DC_CONFIG,
    COMPUTE_PPG_STATES,
    COMPUTE_PPG_STATE_ORDER,
    COMPUTE_LINKED_PARAMETERS,
    COMPUTE_FIXED_CURRENT_TERMINALS,
)
from configs.resource_types import MeasurementType, InstrumentType

# Import experiment settings (edit these in configs/compute_settings.py)
from configs import compute_settings as SETTINGS


class VoltageMeasurementExperiment(ExperimentRunner):
    """
    Voltage measurement experiment runner.
    
    Performs voltage measurements on current sources with:
    - PPG DC bias (VCC or 0V, never triggered)
    - VSU biasing on VDD, VCC
    - All current sources set to 20e-9 A
    - Spot voltage measurements on all current source terminals
    - CSV output with current source names and voltages
    
    All currents are "pulled" (positive = into IV meter).
    """
    
    def __init__(self, test_mode: bool = False, vdd: float = None, 
                 vcc: float = None):
        """
        Initialize Voltage Measurement experiment.
        
        Args:
            test_mode: If True, log commands without hardware
            vdd: VDD voltage in volts (default: 1.8V)
            vcc: VCC voltage in volts (default: 5.0V)
        
        Note:
            PPG voltage is controlled by state (ERASE=VCC, PROGRAM=0V).
            All measurements are automatically done in both states.
            
        Instrument Lifecycle:
            - All instruments are reset ONCE at experiment start (in startup())
            - All channels are enabled ONCE before measurements begin
            - Only current values change during measurement loops
            - All instruments are disabled ONCE at experiment end (in shutdown())
        """
        super().__init__(COMPUTE_CONFIG, test_mode)
        self.vdd = vdd if vdd is not None else COMPUTE_DEFAULTS["VDD"]
        self.vcc = vcc if vcc is not None else COMPUTE_DEFAULTS["VCC"]
        
        # Current value for all current sources
        self.current_value = 20e-9  # 20 nA
        
        # Flag to track if initial setup has been done
        self._channels_initialized = False
        
        # Results storage
        self.measurement_results: List[Dict[str, Any]] = []
    
    # ========================================================================
    # Initial Setup - Called ONCE at experiment start
    # ========================================================================
    
    def initialize_all_channels(self) -> None:
        """
        Enable all channels on all instruments ONCE at experiment start.
        
        This method is called once before any measurements begin.
        After this, only current/voltage values change - no re-initialization.
        """
        if self._channels_initialized:
            self.logger.debug("Channels already initialized, skipping")
            return
        
        self.logger.info("-" * 40)
        self.logger.info("Initializing all channels (one-time setup)")
        
        # Get instrument references
        iv5270b = self._get_instrument(InstrumentType.IV5270B)
        iv4156b = self._get_instrument(InstrumentType.IV4156B)
        
        # Enable all 5270B channels used in this experiment
        # Channels: 0 (VSS/GNDU - automatically enabled), 5 (TRIM1), 6 (TRIM2), 7 (F11), 8 (F12)
        # Note: Channel 0 is automatically enabled and will be filtered out from CN command
        iv5270b.enable_channels([0, 5, 6, 7, 8])
        channel_info = [
            f"CH0 (VSS/GNDU)", f"CH5 (TRIM1)", f"CH6 (TRIM2)", 
            f"CH7 (F11)", f"CH8 (F12)"
        ]
        self.logger.info(f"5270B: Enabled channels: {', '.join(channel_info)}")
        
        # Enable all 4156B channels used in this experiment
        # Channels: 1 (X2), 2 (KGAIN1), 3 (KGAIN2), 4 (IREFP), 21 (VDD VSU), 22 (VCC VSU)
        iv4156b.enable_channels([1, 2, 3, 4, 21, 22])
        channel_info = [
            f"CH1 (X2)", f"CH2 (KGAIN1)", f"CH3 (KGAIN2)", f"CH4 (IREFP)", 
            f"CH21 (VDD)", f"CH22 (VCC)"
        ]
        self.logger.info(f"4156B: Enabled channels: {', '.join(channel_info)}")
        
        self._channels_initialized = True
        self.logger.info("All channels initialized")
        
        # Check for errors after channel initialization
        errors = self.check_all_instrument_errors()
        self.report_and_exit_on_errors(errors)
    
    # ========================================================================
    # Step 2: Voltage Supply Setup
    # ========================================================================
    
    def setup_voltage_supplies(self) -> None:
        """Configure voltage supplies (VDD, VCC, VSS). Called once at start."""
        self.logger.info("-" * 40)
        self.logger.info("Setting up voltage supplies (one-time)")
        
        # Enable GNDU (ground reference)
        self.enable_gndu("VSS")
        
        # Set VSU terminals
        self.set_terminal_voltage("VDD", self.vdd)
        self.set_terminal_voltage("VCC", self.vcc)
        
        self.logger.info(f"Voltage supplies: VDD={self.vdd}V, VCC={self.vcc}V, VSS=GND")
    
    # ========================================================================
    # Step 3: Fixed Current Supply Setup
    # ========================================================================
    
    def setup_all_current_sources(self) -> None:
        """
        Set all fixed current supplies to 20e-9 A.
        
        Handles linked parameters (KGAIN1/2 and TRIM1/2 get same value).
        This only changes current values - channels are already enabled.
        """
        self.logger.info("-" * 40)
        self.logger.info(f"Setting all current sources to {self.current_value}A")
        
        # Set all fixed current terminals to the same value
        for terminal in COMPUTE_FIXED_CURRENT_TERMINALS:
            cfg = self.get_terminal_config(terminal)
            self.set_terminal_current(terminal, self.current_value)
            self.logger.debug(f"{terminal} (CH{cfg.channel}): Set to {self.current_value}A")
        
        self.logger.info("All current sources set to 20e-9 A")
    
    # ========================================================================
    # Step 4: Voltage Measurement on Current Sources
    # ========================================================================
    
    def measure_terminal_voltage(self, terminal: str) -> float:
        """
        Measure voltage on a current source terminal.
        
        When a channel is set to current mode, we can still read the voltage
        by performing a spot measurement. The measurement data contains both
        voltage and current information.
        
        Args:
            terminal: Terminal name (must be a current source terminal)
            
        Returns:
            Measured voltage in volts
        """
        cfg = self.get_terminal_config(terminal)
        
        if cfg.measurement_type != MeasurementType.I:
            raise ValueError(f"Terminal {terminal} is not a current terminal")
        
        inst = self._get_instrument(cfg.instrument)
        
        # Perform spot measurement
        if cfg.instrument == InstrumentType.IV5270B:
            inst.set_measurement_mode(1, [cfg.channel])
            inst.execute_measurement()
            data = inst.read_data()
            # Parse voltage from measurement data
            # Format is typically "V<voltage>,I<current>" or "V<voltage> I<current>"
            try:
                # Try comma-separated format first
                if "," in data:
                    voltage_part = data.split(",")[0]
                else:
                    # Try space-separated
                    voltage_part = data.split()[0]
                
                # Extract voltage value (format: V<value>)
                if "V" in voltage_part:
                    voltage = float(voltage_part.split("V")[1].strip())
                else:
                    # Try alternative parsing
                    voltage = float(voltage_part.replace("V", "").strip())
            except (IndexError, ValueError) as e:
                self.logger.warning(f"Could not parse voltage from {terminal}: {data}, error: {e}")
                voltage = 0.0
        elif cfg.instrument == InstrumentType.IV4156B:
            inst.set_measurement_mode(1, [cfg.channel])
            inst.execute_measurement()
            data = inst.read_measurement_data()
            # Parse voltage from measurement data
            try:
                # Try comma-separated format first
                if "," in data:
                    voltage_part = data.split(",")[0]
                else:
                    # Try space-separated
                    voltage_part = data.split()[0]
                
                # Extract voltage value (format: V<value>)
                if "V" in voltage_part:
                    voltage = float(voltage_part.split("V")[1].strip())
                else:
                    # Try alternative parsing
                    voltage = float(voltage_part.replace("V", "").strip())
            except (IndexError, ValueError) as e:
                self.logger.warning(f"Could not parse voltage from {terminal}: {data}, error: {e}")
                voltage = 0.0
        else:
            voltage = 0.0
        
        self.logger.info(f"{terminal} (CH{cfg.channel}): Voltage = {voltage} V")
        return voltage
    
    def measure_all_current_source_voltages(self) -> Dict[str, float]:
        """
        Measure voltages on all current source terminals.
        
        Returns:
            Dictionary mapping terminal names to measured voltages
        """
        self.logger.info("-" * 40)
        self.logger.info("Measuring voltages on all current sources")
        
        voltages = {}
        
        # Measure voltage on each current source terminal
        for terminal in COMPUTE_FIXED_CURRENT_TERMINALS:
            voltage = self.measure_terminal_voltage(terminal)
            voltages[terminal] = voltage
        
        self.logger.info(f"Completed voltage measurements on {len(voltages)} current sources")
        return voltages
    
    # ========================================================================
    # PPG State Control
    # ========================================================================
    
    def get_ppg_state_voltage(self, state_name: str) -> float:
        """
        Get the voltage for a PPG state.
        
        Args:
            state_name: "ERASE" or "PROGRAM"
            
        Returns:
            Voltage in volts (VCC value for ERASE, 0.0 for PROGRAM)
        """
        state_config = COMPUTE_PPG_STATES.get(state_name)
        if state_config is None:
            raise ValueError(f"Unknown PPG state: {state_name}")
        
        voltage = state_config["voltage"]
        if voltage == "VCC":
            return self.vcc
        return voltage
    
    def set_ppg_state(self, state_name: str) -> None:
        """
        Set the PPG to a specific state (ERASE or PROGRAM).
        
        This only changes the DC voltage level - no reinitialization.
        
        Args:
            state_name: "ERASE" (VCC) or "PROGRAM" (0V)
        """
        voltage = self.get_ppg_state_voltage(state_name)
        state_desc = COMPUTE_PPG_STATES[state_name]["description"]
        
        self.logger.info(f"Setting PPG state: {state_name} at {voltage}V")
        self.set_ppg_dc_mode("ERASE_PROG", voltage)
    
    # ========================================================================
    # CSV Output
    # ========================================================================
    
    def write_voltage_csv(self, voltages: Dict[str, float], ppg_state: str) -> str:
        """
        Write voltage measurements to CSV file.
        
        Args:
            voltages: Dictionary mapping terminal names to voltages
            ppg_state: PPG state name (ERASE or PROGRAM)
            
        Returns:
            Path to the created CSV file
        """
        # Create measurements directory if it doesn't exist
        measurements_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "measurements"
        )
        os.makedirs(measurements_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"current_source_voltages_{ppg_state}_{timestamp}.csv"
        filepath = os.path.join(measurements_dir, filename)
        
        # Write CSV file
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(["Current_Source", "Voltage_V"])
            
            # Write data rows (sorted by terminal name for consistency)
            for terminal in sorted(voltages.keys()):
                writer.writerow([terminal, voltages[terminal]])
        
        self.logger.info(f"Wrote voltage measurements to: {filepath}")
        return filepath
    
    # ========================================================================
    # Main Experiment Execution
    # ========================================================================
    
    def run(self) -> dict:
        """
        Execute the Voltage Measurement experiment.
        
        Instrument Lifecycle:
            - Instruments are reset ONCE at experiment start (handled by startup())
            - All channels are enabled ONCE before measurements begin
            - Voltage supplies (VDD, VCC) set ONCE
            - Current sources set to 20e-9 A ONCE
            - Voltage measurements performed for each PPG state
            - Instruments are disabled ONCE at experiment end (handled by shutdown())
        
        Measurement Sequence:
            1. Initialize all channels (one-time)
            2. Setup voltage supplies (one-time)
            3. Set all current sources to 20e-9 A (one-time)
            4. For each PPG state (ERASE at VCC, PROGRAM at 0V):
               a. Set PPG voltage
               b. Measure voltages on all current sources
               c. Write CSV with results
        
        Returns:
            Dictionary containing all measurement results
        """
        self.logger.info("=" * 60)
        self.logger.info("Executing Voltage Measurement experiment")
        self.logger.info("=" * 60)
        
        results = {
            "experiment": "VoltageMeasurement",
            "parameters": {
                "VDD": self.vdd,
                "VCC": self.vcc,
                "current_value": self.current_value,
            },
            "ppg_states": COMPUTE_PPG_STATE_ORDER,
            "measurements": {
                "ERASE": {},
                "PROGRAM": {},
            },
            "csv_files": {
                "ERASE": None,
                "PROGRAM": None,
            }
        }
        
        # =====================================================================
        # ONE-TIME INITIALIZATION (done before any measurements)
        # =====================================================================
        self.logger.info("=" * 60)
        self.logger.info("ONE-TIME INITIALIZATION")
        self.logger.info("=" * 60)
        
        # Enable all channels on all instruments (one-time)
        self.initialize_all_channels()
        
        # Setup voltage supplies - VDD, VCC, VSS (one-time)
        self.setup_voltage_supplies()
        
        # Set all current sources to 20e-9 A (one-time)
        self.setup_all_current_sources()
        
        self.logger.info("=" * 60)
        self.logger.info("INITIALIZATION COMPLETE - Beginning measurements")
        self.logger.info("=" * 60)
        
        # =====================================================================
        # MEASUREMENT LOOPS (only PPG voltage changes)
        # =====================================================================
        
        # For each PPG state (ERASE and PROGRAM)
        for ppg_state in COMPUTE_PPG_STATE_ORDER:
            self.logger.info("=" * 60)
            self.logger.info(f"PPG STATE: {ppg_state} ({COMPUTE_PPG_STATES[ppg_state]['description']})")
            self.logger.info("=" * 60)
            
            # Set PPG voltage (only voltage value changes, no reconfig)
            self.set_ppg_state(ppg_state)
            
            # Measure voltages on all current sources
            voltages = self.measure_all_current_source_voltages()
            
            # Store results
            results["measurements"][ppg_state] = voltages
            
            # Write CSV file
            csv_path = self.write_voltage_csv(voltages, ppg_state)
            results["csv_files"][ppg_state] = csv_path
            
            # Check for errors after measurements
            self.logger.info("Checking for errors after measurements...")
            errors = self.check_all_instrument_errors()
            self.report_and_exit_on_errors(errors)
        
        self.logger.info("=" * 60)
        self.logger.info("Voltage Measurement experiment complete")
        self.logger.info("=" * 60)
        
        return results


def main():
    """Main entry point for Voltage Measurement experiment."""
    parser = argparse.ArgumentParser(
        description='Run Voltage Measurement Experiment'
    )
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Run in TEST_MODE (log commands without hardware)'
    )
    parser.add_argument(
        '--vdd',
        type=float,
        default=SETTINGS.VDD,
        help=f'VDD voltage in volts (default: {SETTINGS.VDD})'
    )
    parser.add_argument(
        '--vcc',
        type=float,
        default=SETTINGS.VCC,
        help=f'VCC voltage in volts (default: {SETTINGS.VCC})'
    )
    args = parser.parse_args()
    
    # Create experiment instance
    # Note: All measurements are automatically done in both PPG states:
    #   - ERASE state (PPG at VCC)
    #   - PROGRAM state (PPG at 0V)
    with VoltageMeasurementExperiment(
        test_mode=args.test,
        vdd=args.vdd,
        vcc=args.vcc,
    ) as experiment:
        
        # Run experiment
        results = experiment.run()
    
    # Print summary
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"Experiment: {results['experiment']}")
    print(f"Parameters: VDD={results['parameters']['VDD']}V, "
          f"VCC={results['parameters']['VCC']}V")
    print(f"Current source value: {results['parameters']['current_value']}A")
    print(f"PPG States: {', '.join(results['ppg_states'])}")
    
    for ppg_state in results['ppg_states']:
        print(f"\n{ppg_state} State:")
        voltages = results['measurements'][ppg_state]
        for terminal, voltage in sorted(voltages.items()):
            print(f"  {terminal}: {voltage:.6f} V")
        print(f"  CSV file: {results['csv_files'][ppg_state]}")
    
    print("=" * 60)


if __name__ == '__main__':
    main()
