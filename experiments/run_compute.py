#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Compute Experiment Execution Script

Top-level execution script for the Compute experiment.
This script:
- Imports instrument-level modules
- Loads the Compute experiment configuration
- Executes the measurement sequence with IMEAS sweeps relative to fixed X1 values
- Handles TEST_MODE for safe command logging

Usage:
    python -m experiments.run_compute [--test] [--vdd VDD] [--vcc VCC]
    
    --test: Run in TEST_MODE (log commands without hardware)
    --vdd: VDD voltage (default: 1.8V)
    --vcc: VCC voltage (default: 5.0V)

Configuration:
    Terminal mappings are defined in configs/compute.py
    This script does NOT read the CSV file at runtime.

Experiment Flow:
    1. Enable PPG in DC mode (VCC or 0V, never triggered)
    2. Enable voltage supplies (VDD, VCC via VSU)
    3. Enable fixed current supplies at specified values
    4. For each combination of fixed current values:
       - Set all fixed currents (linked pairs get same value)
       - For each X1 fixed value:
         - Set X1 to fixed value
         - Sweep IMEAS from (X1 - 20nA) to (X1 + 20nA) in 5nA steps
         - Measure OUT1 and OUT2 current during sweep

Compliance Settings:
    - Voltage sources: 1mA compliance
    - Current sources: 2V compliance
    - Current direction: "pulled" (positive = into IV meter)
"""

import sys
import os
import argparse
import logging
import itertools
import csv
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.base_experiment import ExperimentRunner
from configs.compute import (
    COMPUTE_CONFIG,
    COMPUTE_TERMINALS,
    COMPUTE_BY_TYPE,
    COMPUTE_SEQUENTIAL_PAIRS,
    COMPUTE_PULSE_CONFIG,
    COMPUTE_DEFAULTS,
    COMPUTE_ENABLE_SEQUENCE,
    COMPUTE_PPG_DC_CONFIG,
    COMPUTE_PPG_STATES,
    COMPUTE_PPG_STATE_ORDER,
    COMPUTE_LINKED_PARAMETERS,
    COMPUTE_SYNC_SWEEP_CONFIG,
    COMPUTE_SWEEP_PARAMETERS,
    COMPUTE_SYNC_SWEEP_SOURCES,
    COMPUTE_SYNC_SWEEP_TERMINALS,
    COMPUTE_FIXED_CURRENT_TERMINALS,
)
from configs.resource_types import MeasurementType, InstrumentType

# Import experiment settings (edit these in configs/compute_settings.py)
from configs import compute_settings as SETTINGS


class ComputeExperiment(ExperimentRunner):
    """
    Compute experiment runner.
    
    Performs computation mode characterization with:
    - PPG DC bias (VCC or 0V, never triggered)
    - VSU biasing on VDD, VCC
    - Fixed current supplies with user-specified combinations
    - Fixed X1 values with IMEAS sweeps (X1-20nA to X1+20nA in 5nA steps)
    - Current measurement on OUT1 and OUT2 during sweep
    
    All currents are "pulled" (positive = into IV meter).
    """
    
    def __init__(self, test_mode: bool = False, vdd: float = None, 
                 vcc: float = None):
        """
        Initialize Compute experiment.
        
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
        
        # Parameter sweep values (user will populate these)
        self.sweep_params: Dict[str, List[float]] = {
            "KGAIN": [],   # Values for KGAIN1 and KGAIN2 (linked)
            "TRIM": [],    # Values for TRIM1 and TRIM2 (linked)
            "X2": [],
            "IREFP": [],
            "F11": [],
            "F12": [],
        }
        
        # X1 fixed current values (IMEAS will sweep relative to each X1 value)
        self.x1_values: List[float] = []
        
        # Flag to track if initial setup has been done
        self._channels_initialized = False
        
        # CSV output files
        self._csv_file = None
        self._csv_writer = None
        self._csv_file_latest = None
        self._csv_writer_latest = None
        self._csv_initialized = False
    
    def set_sweep_values(self, param_name: str, values: List[float]) -> None:
        """
        Set the sweep values for a parameter.
        
        Args:
            param_name: Parameter name (KGAIN, TRIM, X2, IREFP, F11, F12)
            values: List of current values in Amps
        """
        if param_name in self.sweep_params:
            self.sweep_params[param_name] = values
            self.logger.info(f"Set {param_name} sweep values: {len(values)} points")
        else:
            raise ValueError(f"Unknown parameter: {param_name}")
    
    def set_x1_values(self, values: List[float]) -> None:
        """
        Set the fixed X1 current values.
        
        For each X1 value, IMEAS will sweep from (X1 - 20nA) to (X1 + 20nA) in 5nA steps.
        
        Args:
            values: List of X1 current values in Amps
        """
        self.x1_values = values.copy()
        self.logger.info(f"Set X1 values: {len(values)} points")
    
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
        # Channels: 0 (VSS/GNDU - automatically enabled), 1 (OUT1), 2 (OUT2), 3 (X1), 4 (IMEAS), 5 (TRIM1), 6 (TRIM2), 7 (F11), 8 (F12)
        # Note: Channel 0 is automatically enabled and will be filtered out from CN command
        iv5270b.enable_channels([0, 1, 2, 3, 4, 5, 6, 7, 8])
        channel_info = [
            f"CH0 (VSS/GNDU)", f"CH1 (OUT1)", f"CH2 (OUT2)", f"CH3 (X1)", 
            f"CH4 (IMEAS)", f"CH5 (TRIM1)", f"CH6 (TRIM2)", f"CH7 (F11)", f"CH8 (F12)"
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
        
        # Note: Measurement mode (MM) is set right before each measurement, not during initialization
        # This avoids redundant MM commands that are not used until measurements begin
        
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
    
    def setup_fixed_currents(self, current_values: Dict[str, float]) -> None:
        """
        Set all fixed current supplies to specified values.
        
        Handles linked parameters (KGAIN1/2 and TRIM1/2 get same value).
        This only changes current values - channels are already enabled.
        
        Args:
            current_values: Dict mapping parameter names to current values in Amps
                           e.g., {"KGAIN": 1e-6, "TRIM": 2e-6, "X2": 1e-6, ...}
        """
        # Handle linked parameters
        for param_name, value in current_values.items():
            if param_name in COMPUTE_LINKED_PARAMETERS:
                # Set both linked terminals to same value
                terminals = COMPUTE_LINKED_PARAMETERS[param_name]["terminals"]
                for terminal in terminals:
                    cfg = self.get_terminal_config(terminal)
                    self.set_terminal_current(terminal, value)
                    self.logger.debug(f"{param_name} (linked): {value}A -> {terminal} (CH{cfg.channel})")
            else:
                # Single terminal
                cfg = self.get_terminal_config(param_name)
                self.set_terminal_current(param_name, value)
                self.logger.debug(f"{param_name}: {value}A -> {param_name} (CH{cfg.channel})")
    
    # ========================================================================
    # Step 4: Synchronous Sweep
    # ========================================================================
    
    def setup_sync_sweep_outputs(self) -> None:
        """
        Setup OUT1 and OUT2 voltages for current measurement during sync sweep.
        
        OUT1 and OUT2 are set to VDD voltage. Called once at start.
        This only sets voltage values, channels are already enabled.
        """
        # Set OUT1 and OUT2 to VDD voltage (voltage values only, no reconfig)
        self.set_terminal_voltage("OUT1", self.vdd)
        self.set_terminal_voltage("OUT2", self.vdd)
        
        self.logger.info(f"OUT1, OUT2: Set to VDD={self.vdd}V")
    
    def execute_imeas_sweep(self, x1_value: float) -> Dict[str, Any]:
        """
        Execute IMEAS sweep relative to a fixed X1 value using instrument sweep command.
        
        X1 is set to a fixed value. IMEAS sweeps from (X1 - 20nA) to (X1 + 20nA) 
        in steps of 10nA (5 points total), while measuring current on OUT1 and OUT2.
        
        Args:
            x1_value: Fixed X1 current value in Amps
        
        Note: This method uses the instrument's built-in sweep capability (WI command)
        instead of manual loops for better performance and accuracy.
        
        Returns:
            Dictionary with sweep results including:
            - x1_value: The fixed X1 value used
            - sweep_points: List of (X1_current, IMEAS_current) tuples
            - OUT1_currents: List of measured currents
            - OUT2_currents: List of measured currents
        """
        # Get 5270B instrument (all sweep terminals are on it)
        inst = self._get_instrument(InstrumentType.IV5270B)
        
        # Get terminal configs (for channel numbers and terminal names)
        x1_cfg = self.get_terminal_config("X1")
        imeas_cfg = self.get_terminal_config("IMEAS")
        out1_cfg = self.get_terminal_config("OUT1")
        out2_cfg = self.get_terminal_config("OUT2")
        
        # Define IMEAS sweep: from (X1 - 20nA) to (X1 + 20nA) in steps of 10nA (5 points)
        imeas_start = x1_value - 20e-9
        imeas_stop = x1_value + 20e-9
        num_steps = 5  # 5 points: -20nA, -10nA, 0, +10nA, +20nA
        
        self.logger.info(f"Executing IMEAS ({imeas_cfg.terminal}) sweep for X1 ({x1_cfg.terminal}) = {x1_value}A...")
        self.logger.info(f"IMEAS ({imeas_cfg.terminal}) sweep: {imeas_start}A to {imeas_stop}A, {num_steps} steps")
        
        # Set X1 to fixed value (only set once, doesn't change during sweep)
        inst.set_current(x1_cfg.channel, x1_value, compliance=2.0)
        self.logger.debug(f"X1 ({x1_cfg.terminal}, CH{x1_cfg.channel}): Set to {x1_value}A")
        
        # Set measurement mode to sweep measurement (mode 2)
        # Measure OUT1 and OUT2 currents during sweep
        inst.set_measurement_mode(2, [out1_cfg.channel, out2_cfg.channel])
        self.logger.debug(f"Measurement mode: Sweep on OUT1 ({out1_cfg.terminal}, CH{out1_cfg.channel}) and OUT2 ({out2_cfg.terminal}, CH{out2_cfg.channel})")
        
        # Configure IMEAS current sweep using WI command
        inst.configure_current_sweep(
            channel=imeas_cfg.channel,
            start=imeas_start,
            stop=imeas_stop,
            steps=num_steps,
            compliance=2.0,
            mode=1,  # Linear sweep
            i_range=0  # Auto range
        )
        self.logger.debug(f"IMEAS ({imeas_cfg.terminal}, CH{imeas_cfg.channel}): Configured current sweep")
        
        # Execute sweep measurement
        inst.execute_measurement()
        
        # Read all sweep data
        data = inst.read_data()
        
        # Parse sweep data
        # The data format for sweep measurements is typically comma-separated values
        # Format: I1_1,I2_1,I1_2,I2_2,... (OUT1 and OUT2 currents for each sweep point)
        results = {
            "x1_value": x1_value,
            "sweep_points": [],
            "OUT1_currents": [],
            "OUT2_currents": [],
        }
        
        try:
            # Parse comma-separated values
            parts = data.split(",")
            # For each sweep point, we expect 2 values (OUT1 and OUT2 currents)
            num_points = len(parts) // 2
            if num_points == 0:
                num_points = 1  # Fallback if parsing fails
            
            # Generate IMEAS values for this sweep
            imeas_points = []
            for i in range(num_steps):
                imeas_val = imeas_start + (imeas_stop - imeas_start) * i / (num_steps - 1) if num_steps > 1 else imeas_start
                imeas_points.append(imeas_val)
            
            # Parse current values
            for i in range(min(num_points, num_steps)):
                if i * 2 + 1 < len(parts):
                    try:
                        out1_current = float(parts[i * 2].strip())
                        out2_current = float(parts[i * 2 + 1].strip())
                    except (ValueError, IndexError):
                        # Try alternative parsing if format is different
                        try:
                            # Remove any non-numeric prefixes/suffixes
                            out1_str = parts[i * 2].strip().replace("I", "").replace("A", "")
                            out2_str = parts[i * 2 + 1].strip().replace("I", "").replace("A", "")
                            out1_current = float(out1_str)
                            out2_current = float(out2_str)
                        except (ValueError, IndexError):
                            out1_current = 0.0
                            out2_current = 0.0
                else:
                    out1_current = 0.0
                    out2_current = 0.0
                
                imeas_val = imeas_points[i] if i < len(imeas_points) else imeas_start
                results["sweep_points"].append((x1_value, imeas_val))
                results["OUT1_currents"].append(out1_current)
                results["OUT2_currents"].append(out2_current)
        except (IndexError, ValueError) as e:
            self.logger.warning(f"Error parsing sweep data: {e}, data={data}")
            # Fallback: create empty results
            for i in range(num_steps):
                imeas_val = imeas_start + (imeas_stop - imeas_start) * i / (num_steps - 1) if num_steps > 1 else imeas_start
                results["sweep_points"].append((x1_value, imeas_val))
                results["OUT1_currents"].append(0.0)
                results["OUT2_currents"].append(0.0)
        
        self.logger.info(f"IMEAS ({imeas_cfg.terminal}) sweep complete: {len(results['sweep_points'])} points")
        
        return results
    
    # ========================================================================
    # Parameter Combination Iterator
    # ========================================================================
    
    def generate_parameter_combinations(self) -> List[Dict[str, float]]:
        """
        Generate all combinations of fixed current parameters.
        
        Returns:
            List of dictionaries, each containing one combination of parameter values
        """
        # Get all parameter names and their values
        param_names = []
        param_values = []
        
        for name, values in self.sweep_params.items():
            if values:  # Only include parameters with values
                param_names.append(name)
                param_values.append(values)
        
        if not param_values:
            return [{}]  # No parameters to sweep
        
        # Generate all combinations using itertools.product
        combinations = []
        for combo in itertools.product(*param_values):
            combo_dict = dict(zip(param_names, combo))
            combinations.append(combo_dict)
        
        self.logger.info(f"Generated {len(combinations)} parameter combinations")
        return combinations
    
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
    # CSV Output Management
    # ========================================================================
    
    def _initialize_csv_output(self) -> None:
        """
        Initialize CSV output file with headers for all current and voltage sources.
        
        Creates a measurements folder if it doesn't exist and sets up the CSV file
        with columns for all source values and measurement results.
        """
        if self._csv_initialized:
            return
        
        # Create measurements folder if it doesn't exist
        measurements_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "measurements"
        )
        os.makedirs(measurements_dir, exist_ok=True)
        
        # Generate CSV filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = os.path.join(
            measurements_dir,
            f"compute_{timestamp}.csv"
        )
        
        # Generate CSV filename without timestamp (overwrites each run)
        csv_filename_latest = os.path.join(
            measurements_dir,
            "compute.csv"
        )
        
        # Open CSV files for writing
        self._csv_file = open(csv_filename, 'w', newline='', encoding='utf-8')
        self._csv_writer = csv.writer(self._csv_file)
        
        self._csv_file_latest = open(csv_filename_latest, 'w', newline='', encoding='utf-8')
        self._csv_writer_latest = csv.writer(self._csv_file_latest)
        
        # Define CSV headers
        # Current sources: KGAIN1, KGAIN2, TRIM1, TRIM2, X2, IREFP, F11, F12, X1, IMEAS
        # Voltage sources: VDD, VCC, ERASE_PROG (PPG), OUT1, OUT2
        # Measurements: OUT1_current, OUT2_current
        # Metadata: PPG_state
        headers = [
            "PPG_state",
            "VDD", "VCC", "ERASE_PROG", "OUT1", "OUT2",  # Voltage sources
            "KGAIN1", "KGAIN2", "TRIM1", "TRIM2", "X2", "IREFP", "F11", "F12",  # Fixed current sources
            "X1", "IMEAS",  # Sweep current sources
            "OUT1_current", "OUT2_current"  # Measurements
        ]
        
        # Write header row to both files
        self._csv_writer.writerow(headers)
        self._csv_file.flush()
        
        self._csv_writer_latest.writerow(headers)
        self._csv_file_latest.flush()
        
        self._csv_initialized = True
        self.logger.info(f"CSV output initialized: {csv_filename}")
        self.logger.info(f"CSV latest file: {csv_filename_latest}")
    
    def _write_measurement_row(self, ppg_state: str, ppg_voltage: float,
                               fixed_currents: Dict[str, float],
                               x1_value: float, imeas_value: float,
                               out1_current: float, out2_current: float) -> None:
        """
        Write a single measurement row to CSV.
        
        Args:
            ppg_state: PPG state name ("ERASE" or "PROGRAM")
            ppg_voltage: PPG voltage in volts
            fixed_currents: Dictionary of fixed current values
            x1_value: X1 current value in Amps
            imeas_value: IMEAS current value in Amps
            out1_current: Measured OUT1 current in Amps
            out2_current: Measured OUT2 current in Amps
        """
        if not self._csv_initialized:
            self._initialize_csv_output()
        
        # Get all fixed current values (handle linked parameters)
        # KGAIN1 and KGAIN2 are linked (same value from "KGAIN" key)
        # TRIM1 and TRIM2 are linked (same value from "TRIM" key)
        kgain_value = fixed_currents.get("KGAIN", 0.0)
        trim_value = fixed_currents.get("TRIM", 0.0)
        
        # Build row data
        row = [
            ppg_state,  # PPG_state
            self.vdd,  # VDD
            self.vcc,  # VCC
            ppg_voltage,  # ERASE_PROG (PPG voltage)
            self.vdd,  # OUT1 (always at VDD)
            self.vdd,  # OUT2 (always at VDD)
            kgain_value,  # KGAIN1
            kgain_value,  # KGAIN2
            trim_value,  # TRIM1
            trim_value,  # TRIM2
            fixed_currents.get("X2", 0.0),  # X2
            fixed_currents.get("IREFP", 0.0),  # IREFP
            fixed_currents.get("F11", 0.0),  # F11
            fixed_currents.get("F12", 0.0),  # F12
            x1_value,  # X1
            imeas_value,  # IMEAS
            out1_current,  # OUT1_current
            out2_current,  # OUT2_current
        ]
        
        # Write row to both files
        self._csv_writer.writerow(row)
        self._csv_file.flush()
        
        self._csv_writer_latest.writerow(row)
        self._csv_file_latest.flush()
    
    def _close_csv_output(self) -> None:
        """Close CSV output files."""
        if self._csv_file:
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None
        
        if self._csv_file_latest:
            self._csv_file_latest.close()
            self._csv_file_latest = None
            self._csv_writer_latest = None
        
        if self._csv_initialized:
            self.logger.info("CSV output files closed")
    
    # ========================================================================
    # Main Experiment Execution
    # ========================================================================
    
    def run(self) -> dict:
        """
        Execute the Compute experiment.
        
        Instrument Lifecycle:
            - Instruments are reset ONCE at experiment start (handled by startup())
            - All channels are enabled ONCE before measurements begin
            - Voltage supplies (VDD, VCC) and outputs (OUT1, OUT2) set ONCE
            - During measurement loops, ONLY current values change on SMUs
            - Instruments are disabled ONCE at experiment end (handled by shutdown())
        
        Measurement Sequence:
            1. Initialize all channels (one-time)
            2. Setup voltage supplies and outputs (one-time)
            3. For each PPG state (ERASE at VCC, PROGRAM at 0V):
               a. Set PPG voltage (only voltage value changes)
               b. For each combination of fixed current values:
                  i.  Set fixed current values (only current values change)
                  ii. Execute synchronous sweep (only X1/IMEAS currents change)
                  iii. Record OUT1 and OUT2 currents
        
        Returns:
            Dictionary containing all measurement results
        """
        self.logger.info("=" * 60)
        self.logger.info("Executing Compute experiment measurement sequence")
        self.logger.info("=" * 60)
        
        results = {
            "experiment": "Compute",
            "parameters": {
                "VDD": self.vdd,
                "VCC": self.vcc,
            },
            "ppg_states": COMPUTE_PPG_STATE_ORDER,
            "sweep_config": {
                "X1_values": self.x1_values,
                "IMEAS_sweep": "X1-20nA to X1+20nA in 5nA steps",
            },
            "measurements": {
                "ERASE": [],    # Measurements at VCC (ERASE state)
                "PROGRAM": [],  # Measurements at 0V (PROGRAM state)
            }
        }
        
        # =====================================================================
        # ONE-TIME INITIALIZATION (done before any measurements)
        # =====================================================================
        self.logger.info("=" * 60)
        self.logger.info("ONE-TIME INITIALIZATION")
        self.logger.info("=" * 60)
        
        # Initialize CSV output
        self._initialize_csv_output()
        
        # Enable all channels on all instruments (one-time)
        self.initialize_all_channels()
        
        # Setup voltage supplies - VDD, VCC, VSS (one-time)
        self.setup_voltage_supplies()
        
        # Setup OUT1 and OUT2 at VDD voltage (one-time)
        self.setup_sync_sweep_outputs()
        
        # Set all current terminals to initial values of 0A (one-time)
        self.logger.info("Setting all current terminals to 0A initially")
        for terminal in COMPUTE_BY_TYPE[MeasurementType.I]:
            self.set_terminal_current(terminal, 0.0)
        
        self.logger.info("=" * 60)
        self.logger.info("INITIALIZATION COMPLETE - Beginning measurements")
        self.logger.info("(Only current values will change from here)")
        self.logger.info("=" * 60)
        
        # =====================================================================
        # MEASUREMENT LOOPS (only current values change)
        # =====================================================================
        
        # Generate all parameter combinations
        combinations = self.generate_parameter_combinations()
        total_measurements = len(COMPUTE_PPG_STATE_ORDER) * len(combinations) * len(self.x1_values)
        measurement_num = 0
        
        # For each PPG state (ERASE and PROGRAM)
        for ppg_state in COMPUTE_PPG_STATE_ORDER:
            self.logger.info("=" * 60)
            self.logger.info(f"PPG STATE: {ppg_state} ({COMPUTE_PPG_STATES[ppg_state]['description']})")
            self.logger.info("=" * 60)
            
            # Set PPG voltage (only voltage value changes, no reconfig)
            self.set_ppg_state(ppg_state)
            
            # For each combination, set currents and sweep
            for i, combo in enumerate(combinations):
                self.logger.info("-" * 60)
                self.logger.info(f"{ppg_state} - Combination {i+1}/{len(combinations)}")
                self.logger.info(f"Fixed currents: {combo}")
                
                # Set fixed current values (only current values change)
                self.setup_fixed_currents(combo)
                
                # For each X1 value, execute IMEAS sweep
                for x1_idx, x1_value in enumerate(self.x1_values):
                    measurement_num += 1
                    self.logger.info("-" * 40)
                    self.logger.info(f"[{measurement_num}/{total_measurements}] "
                                   f"X1 = {x1_value}A ({x1_idx+1}/{len(self.x1_values)})")
                    
                    # Execute IMEAS sweep for this X1 value
                    sweep_results = self.execute_imeas_sweep(x1_value)
                    
                    # Get PPG voltage for this state
                    ppg_voltage = self.get_ppg_state_voltage(ppg_state)
                    
                    # Write each sweep point to CSV
                    # sweep_results contains:
                    # - sweep_points: List of (X1_current, IMEAS_current) tuples
                    # - OUT1_currents: List of measured OUT1 currents
                    # - OUT2_currents: List of measured OUT2 currents
                    for sweep_idx, (x1_actual, imeas_actual) in enumerate(sweep_results["sweep_points"]):
                        # Get measured currents for this sweep point
                        if sweep_idx < len(sweep_results["OUT1_currents"]):
                            out1_current = sweep_results["OUT1_currents"][sweep_idx]
                        else:
                            out1_current = 0.0
                        
                        if sweep_idx < len(sweep_results["OUT2_currents"]):
                            out2_current = sweep_results["OUT2_currents"][sweep_idx]
                        else:
                            out2_current = 0.0
                        
                        # In test mode, use dummy measurement data but keep correct voltage/current settings
                        if self.test_mode:
                            # Use small dummy values for measurements, but keep actual voltage/current settings
                            out1_current = 1e-12  # Dummy measurement
                            out2_current = 1e-12  # Dummy measurement
                        
                        # Write row to CSV
                        self._write_measurement_row(
                            ppg_state=ppg_state,
                            ppg_voltage=ppg_voltage,
                            fixed_currents=combo,
                            x1_value=x1_actual,
                            imeas_value=imeas_actual,
                            out1_current=out1_current,
                            out2_current=out2_current
                        )
                    
                    # Store results
                    measurement = {
                        "combination_index": i,
                        "x1_index": x1_idx,
                        "x1_value": x1_value,
                        "ppg_state": ppg_state,
                        "ppg_voltage": ppg_voltage,
                        "fixed_currents": combo,
                        "sweep_results": sweep_results,
                    }
                    results["measurements"][ppg_state].append(measurement)
                    
                    # Check for errors after first measurement (first set of conditions)
                    if measurement_num == 1:
                        self.logger.info("Checking for errors after first measurement...")
                        errors = self.check_all_instrument_errors()
                        self.report_and_exit_on_errors(errors)
        
        self.logger.info("=" * 60)
        self.logger.info("Compute experiment complete")
        self.logger.info(f"Total measurements: {measurement_num} "
                        f"({len(combinations)} combinations x {len(self.x1_values)} X1 values x {len(COMPUTE_PPG_STATE_ORDER)} PPG states)")
        self.logger.info("=" * 60)
        
        # Close CSV output
        self._close_csv_output()
        
        return results
    
    # ========================================================================
    # Cleanup
    # ========================================================================
    
    def shutdown(self) -> None:
        """Override shutdown to close CSV output."""
        self._close_csv_output()
        super().shutdown()
    
    # ========================================================================
    # Legacy API (for backwards compatibility)
    # ========================================================================
    
    def setup_bias(self, ppg_state: str = "ERASE") -> None:
        """
        Legacy method - sets up initial bias conditions.
        
        Uses the one-time initialization pattern.
        
        Args:
            ppg_state: "ERASE" (VCC) or "PROGRAM" (0V), default is ERASE
        """
        # One-time channel initialization
        self.initialize_all_channels()
        
        # Setup voltage supplies
        self.setup_voltage_supplies()
        
        # Setup outputs
        self.setup_sync_sweep_outputs()
        
        # Set PPG state
        self.set_ppg_state(ppg_state)
        
        # Set all I terminals to 0A initially
        for terminal in COMPUTE_BY_TYPE[MeasurementType.I]:
            self.set_terminal_current(terminal, 0.0)
        
        self.logger.info("Legacy bias setup complete")


def main():
    """Main entry point for Compute experiment."""
    parser = argparse.ArgumentParser(
        description='Run Compute Experiment'
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
    # 
    # Settings are loaded from configs/compute_settings.py
    # Edit that file to change current lists, sweep ranges, and PPG settings
    with ComputeExperiment(
        test_mode=args.test,
        vdd=args.vdd,
        vcc=args.vcc,
    ) as experiment:
        
        # Load sweep parameter values from settings file
        experiment.set_sweep_values("KGAIN", SETTINGS.KGAIN_VALUES)
        experiment.set_sweep_values("TRIM", SETTINGS.TRIM_VALUES)
        experiment.set_sweep_values("X2", SETTINGS.X2_VALUES)
        experiment.set_sweep_values("IREFP", SETTINGS.IREFP_VALUES)
        experiment.set_sweep_values("F11", SETTINGS.F11_VALUES)
        experiment.set_sweep_values("F12", SETTINGS.F12_VALUES)
        
        # Set X1 fixed current values from settings
        experiment.set_x1_values(SETTINGS.X1_VALUES)
        
        # Run experiment
        results = experiment.run()
    
    # Print summary
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"Experiment: {results['experiment']}")
    print(f"Parameters: VDD={results['parameters']['VDD']}V, "
          f"VCC={results['parameters']['VCC']}V")
    print(f"PPG States: {', '.join(results['ppg_states'])}")
    
    total_erase = len(results['measurements']['ERASE'])
    total_program = len(results['measurements']['PROGRAM'])
    print(f"Measurements in ERASE state (VCC): {total_erase}")
    print(f"Measurements in PROGRAM state (0V): {total_program}")
    print(f"Total measurements: {total_erase + total_program}")
    
    if results['measurements']['ERASE']:
        first = results['measurements']['ERASE'][0]
        if 'sweep_points' in first['sweep_results']:
            # IMEAS sweep structure
            num_points = len(first['sweep_results']['sweep_points'])
            x1_val = first['sweep_results'].get('x1_value', 'N/A')
            print(f"IMEAS sweep: {num_points} points per X1 value")
            print(f"  (X1 = {x1_val}A, IMEAS sweeps from X1-20nA to X1+20nA in 5nA steps)")
    print("=" * 60)


if __name__ == '__main__':
    main()
