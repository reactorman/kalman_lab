#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Compute Experiment Execution Script

Top-level execution script for the Compute experiment.
This script:
- Imports instrument-level modules
- Loads the Compute experiment configuration
- Executes spot measurements of OUT1 and OUT2 with fixed X1 and IMEAS values
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
         - Set IMEAS to fixed value (same as X1)
         - Measure OUT1 and OUT2 current (spot measurement, no sweep)

Compliance Settings:
    - Voltage sources: 1mA compliance
    - Current sources: 0.1V compliance for positive currents, 2V for non-positive
    - Current direction: "pulled" (positive = into IV meter)
"""

import sys
import os
import argparse
import logging
import itertools
import csv
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.base_experiment import ExperimentRunner, CURRENT_SOURCE_COMPLIANCE
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
    - Fixed X1 and IMEAS values with spot measurements
    - Current measurement on OUT1 and OUT2 (single spot measurement, no sweeps)
    
    All currents are "pulled" (positive = into IV meter).
    Positive currents use 0.1V compliance (they get negated when sent to instrument).
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
        
        # X1 fixed current values (IMEAS will be set to same value for spot measurements)
        self.x1_values: List[float] = []
        
        # Flag to track if initial setup has been done
        self._channels_initialized = False
        
        # CSV output files
        self._csv_file = None
        self._csv_writer = None
        self._csv_file_latest = None
        self._csv_writer_latest = None
        self._csv_initialized = False
        
        # PPG state tracking (None = not initialized yet)
        self._current_ppg_state = None
    
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
        
        For each X1 value, IMEAS will be set to the same value and a spot measurement
        of OUT1 and OUT2 will be performed.
        
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
        
        # Get all used channels from terminal configs
        used_5270b_channels = set()
        used_4156b_channels = set()
        
        for terminal_name, terminal_cfg in COMPUTE_TERMINALS.items():
            if terminal_cfg.instrument == InstrumentType.IV5270B:
                used_5270b_channels.add(terminal_cfg.channel)
            elif terminal_cfg.instrument == InstrumentType.IV4156B:
                used_4156b_channels.add(terminal_cfg.channel)
        
        # Enable all 5270B channels (1-8) - Channel 0 (GNDU) is automatically enabled
        all_5270b_channels = list(range(1, 9))  # Channels 1-8
        iv5270b.enable_channels(all_5270b_channels)
        
        # Set unused 5270B channels to 0V (connected to GNDU)
        unused_5270b_channels = [ch for ch in all_5270b_channels if ch not in used_5270b_channels]
        for ch in unused_5270b_channels:
            iv5270b.set_voltage(ch, 0.0, compliance=0.001)  # 0V with 1mA compliance
            self.logger.debug(f"5270B CH{ch}: Set to 0V (connected to GNDU)")
        
        channel_info = []
        for ch in sorted(used_5270b_channels):
            if ch == 0:
                channel_info.append(f"CH0 (VSS/GNDU)")
            else:
                term_name = next((name for name, cfg in COMPUTE_TERMINALS.items() 
                                if cfg.instrument == InstrumentType.IV5270B and cfg.channel == ch), f"CH{ch}")
                channel_info.append(f"CH{ch} ({term_name})")
        for ch in unused_5270b_channels:
            channel_info.append(f"CH{ch} (GNDU)")
        self.logger.info(f"5270B: Enabled channels: {', '.join(channel_info)}")
        
        # Enable all 4156B SMU channels (1-4) and VSU channels (21-22)
        all_4156b_channels = [1, 2, 3, 4, 21, 22]
        iv4156b.enable_channels(all_4156b_channels)
        
        # Set unused 4156B channels to 0V (connected to GNDU)
        unused_4156b_channels = [ch for ch in all_4156b_channels if ch not in used_4156b_channels]
        for ch in unused_4156b_channels:
            if ch <= 4:  # SMU channel
                iv4156b.set_voltage(ch, 0.0, compliance=0.001)  # 0V with 1mA compliance
                self.logger.debug(f"4156B CH{ch}: Set to 0V (connected to GNDU)")
            # VSU channels (21-22) don't need to be set to 0V if unused
        
        channel_info = []
        for ch in sorted(used_4156b_channels):
            term_name = next((name for name, cfg in COMPUTE_TERMINALS.items() 
                            if cfg.instrument == InstrumentType.IV4156B and cfg.channel == ch), f"CH{ch}")
            channel_info.append(f"CH{ch} ({term_name})")
        for ch in unused_4156b_channels:
            if ch <= 4:  # Only log SMU channels
                channel_info.append(f"CH{ch} (GNDU)")
        self.logger.info(f"4156B: Enabled channels: {', '.join(channel_info)}")
        
        # Set wait time for spot measurements on 5270B
        # WAT 2,1,0.01 = mode 2 (user-defined), hold=1s, delay=0.01s
        iv5270b.set_wait_time(2, 1, 0.01)
        self.logger.info("5270B: Wait time configured for spot measurements")
        
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
    
    # Variables that use normalized values (-1 to +1) with formula: IREFP/2 * (X + 1)
    NORMALIZED_HALF_VARS = {"X1", "X2", "F11", "F12", "IMEAS"}
    
    # Variables that use normalized values (0 to 1) with formula: IREFP * X
    NORMALIZED_FULL_VARS = {"KGAIN", "TRIM"}
    
    def convert_normalized_to_current(self, param_name: str, normalized_value: float, 
                                      irefp: float) -> float:
        """
        Convert a normalized value to actual current based on IREFP.
        
        Args:
            param_name: Parameter name (X1, X2, KGAIN, etc.)
            normalized_value: Normalized value (-1 to +1 or 0 to 1)
            irefp: IREFP current value in Amps
        
        Returns:
            Actual current in Amps
        
        Conversion rules:
            X1, X2, F11, F12, IMEAS: current = IREFP/2 * (X + 1)  where X is -1 to +1
            KGAIN, TRIM: current = IREFP * X  where X is 0 to 1
            IREFP: unchanged (already in Amps)
        """
        if param_name in self.NORMALIZED_HALF_VARS:
            # X1, X2, F11, F12, IMEAS: IREFP/2 * (X + 1)
            return (irefp / 2.0) * (normalized_value + 1.0)
        elif param_name in self.NORMALIZED_FULL_VARS:
            # KGAIN, TRIM: IREFP * X
            return irefp * normalized_value
        else:
            # IREFP, ERASE_PROG: unchanged
            return normalized_value
    
    def convert_combo_to_currents(self, combo: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert all normalized values in a combo dictionary to actual currents.
        
        Args:
            combo: Dictionary with parameter names and normalized values
        
        Returns:
            Dictionary with parameter names and actual current values in Amps
        """
        # Get IREFP value (must be present in combo or use default)
        irefp = combo.get("IREFP", 100e-9)  # Default 100nA if not specified
        
        converted = {}
        for param_name, value in combo.items():
            if param_name == "ERASE_PROG":
                # ERASE_PROG is not a current, pass through
                converted[param_name] = value
            elif value is None:
                # None values (like IMEAS=None) pass through
                converted[param_name] = None
            else:
                # Convert normalized value to actual current
                converted[param_name] = self.convert_normalized_to_current(param_name, value, irefp)
        
        return converted
    
    def set_terminal_current(self, terminal: str, current: float,
                            compliance: float = None) -> None:
        """
        Override set_terminal_current to use 0.1V compliance for positive currents.
        
        Positive currents get negated later when sent to the instrument, so we use
        0.1V compliance for all positive currents as requested.
        
        Args:
            terminal: Logical terminal name
            current: Current to set in amps (positive = into meter)
            compliance: Voltage compliance in volts (default: 0.1V for positive, 2V for non-positive)
        """
        # For positive currents (which get negated later), use 0.1V compliance
        if compliance is None:
            if current > 0:
                compliance = 0.1  # 0.1V for positive currents
            else:
                compliance = CURRENT_SOURCE_COMPLIANCE  # 2V default for non-positive
        
        # Call parent method with the determined compliance
        super().set_terminal_current(terminal, current, compliance)
    
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
    # Step 4: Output Setup and Spot Measurement
    # ========================================================================
    
    def setup_sync_sweep_outputs(self) -> None:
        """
        Setup OUT1 and OUT2 voltages for current measurement.
        
        OUT1 and OUT2 are set to VDD voltage. Called once at start.
        This only sets voltage values, channels are already enabled.
        """
        # Set OUT1 and OUT2 to VDD voltage (voltage values only, no reconfig)
        self.set_terminal_voltage("OUT1", self.vdd)
        self.set_terminal_voltage("OUT2", self.vdd)
        
        self.logger.info(f"OUT1, OUT2: Set to VDD={self.vdd}V")
    
    def execute_spot_measurement(self, x1_value: float, imeas_value: float = None) -> Dict[str, Any]:
        """
        Execute spot measurement of OUT1 and OUT2 with fixed X1 and IMEAS values.
        
        X1 and IMEAS are set to fixed values, then OUT1 and OUT2 currents are measured once.
        No sweeps are performed - only a single spot measurement.
        
        Args:
            x1_value: Fixed X1 current value in Amps
            imeas_value: Fixed IMEAS current value in Amps (default: same as x1_value)
        
        Returns:
            Dictionary with spot measurement results including:
            - x1_value: The fixed X1 value used
            - imeas_value: The fixed IMEAS value used
            - OUT1_current: Measured OUT1 current
            - OUT2_current: Measured OUT2 current
        """
        # Get 5270B instrument (all terminals are on it)
        inst = self._get_instrument(InstrumentType.IV5270B)
        
        # Get terminal configs (for channel numbers and terminal names)
        x1_cfg = self.get_terminal_config("X1")
        imeas_cfg = self.get_terminal_config("IMEAS")
        out1_cfg = self.get_terminal_config("OUT1")
        out2_cfg = self.get_terminal_config("OUT2")
        
        # If IMEAS value not specified, use same as X1
        if imeas_value is None:
            imeas_value = x1_value
        
        self.logger.info(f"Executing spot measurement: X1 ({x1_cfg.terminal}) = {x1_value}A, IMEAS ({imeas_cfg.terminal}) = {imeas_value}A")
        
        # Set X1 to fixed value (use 0.1V compliance for positive currents)
        x1_compliance = 0.1 if x1_value > 0 else 2.0
        inst.set_current(x1_cfg.channel, x1_value, compliance=x1_compliance)
        self.logger.debug(f"X1 ({x1_cfg.terminal}, CH{x1_cfg.channel}): Set to {x1_value}A (Vcomp={x1_compliance}V)")
        
        # Set IMEAS to fixed value (use 0.1V compliance for positive currents)
        imeas_compliance = 0.1 if imeas_value > 0 else 2.0
        inst.set_current(imeas_cfg.channel, imeas_value, compliance=imeas_compliance)
        self.logger.debug(f"IMEAS ({imeas_cfg.terminal}, CH{imeas_cfg.channel}): Set to {imeas_value}A (Vcomp={imeas_compliance}V)")
        
        # Set measurement mode to spot measurement (mode 1)
        # Measure OUT1 and OUT2 currents
        inst.set_measurement_mode(1, [out1_cfg.channel, out2_cfg.channel])
        self.logger.debug(f"Measurement mode: Spot measurement on OUT1 ({out1_cfg.terminal}, CH{out1_cfg.channel}) and OUT2 ({out2_cfg.terminal}, CH{out2_cfg.channel})")
        
        # Execute spot measurement
        inst.execute_measurement()
        
        # Read measurement data
        data = inst.read_data()
        self.logger.debug(f"Raw instrument data: {data}")
        
        # Parse spot measurement data
        # Format: I1,I2 (OUT1 and OUT2 currents)
        results = {
            "x1_value": x1_value,
            "imeas_value": imeas_value,
            "OUT1_current": 0.0,
            "OUT2_current": 0.0,
        }
        
        try:
            # Parse comma-separated values
            parts = data.split(",")
            
            # Remove 3-letter prefixes (like TAI, TBI) from each value
            def remove_3letter_prefix(value: str) -> str:
                """Remove 3-letter alphabetic prefix from value if present."""
                value = value.strip()
                if len(value) >= 3 and value[:3].isalpha():
                    if len(value) == 3 or value[3] in '+-.0123456789':
                        return value[3:]
                return value
            
            # Clean all parts by removing 3-letter prefixes
            cleaned_parts = [remove_3letter_prefix(part) for part in parts]
            
            # Parse OUT1 and OUT2 currents
            if len(cleaned_parts) >= 2:
                try:
                    results["OUT1_current"] = float(cleaned_parts[0])
                    results["OUT2_current"] = float(cleaned_parts[1])
                except (ValueError, IndexError):
                    # Try alternative parsing
                    try:
                        out1_str = cleaned_parts[0].replace("I", "").replace("A", "")
                        out2_str = cleaned_parts[1].replace("I", "").replace("A", "")
                        results["OUT1_current"] = float(out1_str)
                        results["OUT2_current"] = float(out2_str)
                    except (ValueError, IndexError):
                        self.logger.warning(f"Error parsing spot measurement data: {data}")
            elif len(cleaned_parts) == 1:
                # Only one value - assume it's OUT1, set OUT2 to 0
                try:
                    results["OUT1_current"] = float(cleaned_parts[0])
                except ValueError:
                    self.logger.warning(f"Error parsing spot measurement data: {data}")
        except (IndexError, ValueError) as e:
            self.logger.warning(f"Error parsing spot measurement data: {e}, data={data}")
        
        self.logger.info(f"Spot measurement complete: OUT1={results['OUT1_current']}A, OUT2={results['OUT2_current']}A")
        
        return results
    
    # ========================================================================
    # Parameter Combination Iterator
    # ========================================================================
    
    def generate_experiment_combinations(self, experiment: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate all combinations for a single experiment based on its sweep variables.
        
        Args:
            experiment: Experiment dictionary with fixed_values, sweep_variables, and value lists
        
        Returns:
            List of dictionaries, each containing parameter values for one combination
        """
        sweep_vars = experiment.get("sweep_variables", [])
        fixed_values = experiment.get("fixed_values", {}).copy()
        
        if not sweep_vars:
            # No sweep variables, return single combination with all fixed values
            return [fixed_values]
        
        # Get value lists for each sweep variable
        param_names = []
        param_values = []
        
        for var_name in sweep_vars:
            # Construct the key for the values list (e.g., "X1_values", "KGAIN_values")
            values_key = f"{var_name}_values"
            if values_key in experiment:
                param_names.append(var_name)
                param_values.append(experiment[values_key])
            else:
                self.logger.warning(f"Experiment {experiment.get('name', 'Unknown')}: "
                                  f"No values found for sweep variable '{var_name}' (looking for '{values_key}')")
        
        if not param_values:
            # No valid sweep variables, return fixed values only
            return [fixed_values]
        
        # Generate all combinations using itertools.product
        combinations = []
        for combo in itertools.product(*param_values):
            combo_dict = fixed_values.copy()
            for var_name, value in zip(param_names, combo):
                combo_dict[var_name] = value
            combinations.append(combo_dict)
        
        self.logger.info(f"Experiment '{experiment.get('name', 'Unknown')}': "
                        f"Generated {len(combinations)} combinations from {len(sweep_vars)} sweep variable(s)")
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
        
        On first call: Full initialization with DC mode setup.
        On subsequent calls: Only change polarity (INV for ERASE, NORM for PROGRAM).
        
        Args:
            state_name: "ERASE" (VCC, INV polarity) or "PROGRAM" (0V, NORM polarity)
        """
        voltage = self.get_ppg_state_voltage(state_name)
        state_desc = COMPUTE_PPG_STATES[state_name]["description"]
        
        # Get PPG instrument
        cfg = self.get_terminal_config("ERASE_PROG")
        ppg = self._get_instrument(cfg.instrument)
        
        if self._current_ppg_state is None:
            # First call: Full initialization
            self.logger.info(f"Initializing PPG in {state_name} state at {voltage}V")
            self.set_ppg_dc_mode("ERASE_PROG", voltage)
            self._current_ppg_state = state_name
        elif self._current_ppg_state != state_name:
            # State change: Only change polarity
            if state_name == "ERASE":
                ppg.set_polarity(cfg.channel, "INV")
                self.logger.info(f"PPG polarity changed to INV ({state_name} mode)")
            else:  # PROGRAM
                ppg.set_polarity(cfg.channel, "NORM")
                self.logger.info(f"PPG polarity changed to NORM ({state_name} mode)")
            self._current_ppg_state = state_name
        else:
            # Same state: No change needed
            self.logger.debug(f"PPG already in {state_name} state, no change needed")
    
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
        # Metadata: Experiment_Name, PPG_state
        headers = [
            "Experiment_Name",
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
    
    def _write_measurement_row(self, experiment_name: str, ppg_state: str, ppg_voltage: float,
                               fixed_currents: Dict[str, float],
                               x1_value: float, imeas_value: float,
                               out1_current: float, out2_current: float) -> None:
        """
        Write a single measurement row to CSV.
        
        Args:
            experiment_name: Name of the experiment
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
            experiment_name,  # Experiment_Name
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
            3. For each enabled experiment:
               a. For each parameter combination in the experiment:
                  i. For each PPG state specified in the experiment:
                     - Set PPG voltage (only voltage value changes)
                     - Set fixed current values (only current values change)
                     - For each X1 value (if X1 is being swept):
                        - Set X1 and IMEAS values
                        - Execute spot measurement
                        - Record OUT1 and OUT2 currents
        
        Returns:
            Dictionary containing all measurement results
        """
        # Track start time for total elapsed time measurement
        start_time = time.time()
        
        self.logger.info("=" * 60)
        self.logger.info("Executing Compute experiment measurement sequence")
        self.logger.info("=" * 60)
        
        # Get enabled experiments from settings
        all_experiments = SETTINGS.EXPERIMENTS
        enabled_experiments = [exp for exp in all_experiments if exp.get("enabled", False)]
        
        if not enabled_experiments:
            self.logger.warning("No enabled experiments found! Check experiment enable flags in compute_settings.py")
            return {
                "experiment": "Compute",
                "parameters": {"VDD": self.vdd, "VCC": self.vcc},
                "experiments_run": [],
                "total_measurements": 0,
            }
        
        self.logger.info(f"Found {len(enabled_experiments)} enabled experiment(s):")
        for exp in enabled_experiments:
            self.logger.info(f"  - {exp.get('name', 'Unknown')}")
        self.logger.info("=" * 60)
        
        results = {
            "experiment": "Compute",
            "parameters": {
                "VDD": self.vdd,
                "VCC": self.vcc,
            },
            "experiments_run": [],
            "measurements": {},
            "total_measurements": 0,
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
        
        # NOTE: Current sources are NOT initialized to 0A here.
        # They will be set to the first experiment's first combination values.
        
        self.logger.info("=" * 60)
        self.logger.info("INITIALIZATION COMPLETE - Beginning measurements")
        self.logger.info("(Only current values will change from here)")
        self.logger.info("=" * 60)
        
        # =====================================================================
        # MEASUREMENT LOOPS (only current values change)
        # =====================================================================
        
        measurement_num = 0
        
        # For each enabled experiment
        for exp_idx, experiment in enumerate(enabled_experiments):
            exp_name = experiment.get("name", f"Experiment_{exp_idx+1}")
            
            self.logger.info("=" * 60)
            self.logger.info(f"EXPERIMENT {exp_idx+1}/{len(enabled_experiments)}: {exp_name}")
            self.logger.info("=" * 60)
            
            # Generate all parameter combinations for this experiment
            combinations = self.generate_experiment_combinations(experiment)
            
            # Get sweep variables
            sweep_vars = experiment.get("sweep_variables", [])
            
            # Get PPG states for this experiment
            # If ERASE_PROG is in sweep_variables, it will be in each combo
            # Otherwise, get it from fixed_values
            if "ERASE_PROG" in sweep_vars:
                # ERASE_PROG is being swept - will get from each combo
                # Need to determine PPG states from all combinations
                ppg_states_in_experiment = set()
                for combo in combinations:
                    erases_prog_value = combo.get("ERASE_PROG", ["ERASE", "PROGRAM"])
                    if isinstance(erases_prog_value, list):
                        ppg_states_in_experiment.update(erases_prog_value)
                    else:
                        ppg_states_in_experiment.add(erases_prog_value)
                # For swept ERASE_PROG, we'll iterate per combo, so just note it
                erases_prog_swept = True
            else:
                # ERASE_PROG is fixed - get from fixed_values
                erases_prog_list = experiment.get("fixed_values", {}).get("ERASE_PROG", ["ERASE", "PROGRAM"])
                if not isinstance(erases_prog_list, list):
                    erases_prog_list = [erases_prog_list]
                erases_prog_swept = False
            
            # Get X1 values for this experiment
            # If X1 is in sweep_variables, use the X1_values from experiment
            # Otherwise, use fixed X1 value from fixed_values
            if "X1" in sweep_vars:
                x1_list = experiment.get("X1_values", [])
                if not x1_list:
                    raise ValueError(f"Experiment '{exp_name}': X1 is in sweep_variables but X1_values is empty or missing")
            else:
                x1_value = experiment.get("fixed_values", {}).get("X1")
                if x1_value is None:
                    raise ValueError(f"Experiment '{exp_name}': X1 is not in sweep_variables but no fixed X1 value provided")
                x1_list = [x1_value]
            
            # Calculate total measurements for this experiment (rough estimate)
            if erases_prog_swept:
                # Will iterate per combo, so can't pre-calculate easily
                total_exp_measurements_estimate = len(combinations) * len(x1_list) * 2  # Estimate 2 PPG states
            else:
                total_exp_measurements_estimate = len(combinations) * len(erases_prog_list) * len(x1_list)
            
            self.logger.info(f"Experiment '{exp_name}': {len(combinations)} combinations x "
                           f"{len(x1_list)} X1 values = ~{total_exp_measurements_estimate} measurements")
            
            exp_results = {
                "name": exp_name,
                "combinations": len(combinations),
                "measurements": [],
            }
            
            # Track previous current values to only update changed sources
            prev_current_combo = None
            is_first_iteration_of_experiment = True
            
            # For each parameter combination
            for combo_idx, combo in enumerate(combinations):
                self.logger.info("-" * 60)
                self.logger.info(f"Experiment '{exp_name}' - Combination {combo_idx+1}/{len(combinations)}")
                self.logger.info(f"Normalized parameters: {combo}")
                
                # Convert normalized values to actual currents
                converted_combo = self.convert_combo_to_currents(combo)
                self.logger.info(f"Actual currents: {converted_combo}")
                
                # Get PPG states for this combination
                if erases_prog_swept:
                    # ERASE_PROG is in the combo (either a list or single value)
                    erases_prog_value = combo.get("ERASE_PROG", ["ERASE", "PROGRAM"])
                    if isinstance(erases_prog_value, list):
                        combo_ppg_states = erases_prog_value
                    else:
                        combo_ppg_states = [erases_prog_value]
                else:
                    # ERASE_PROG is fixed for the experiment
                    combo_ppg_states = erases_prog_list
                
                # Get X1 value for this combination (either from combo if swept, or from list)
                # Use converted values (actual currents)
                if "X1" in converted_combo:
                    combo_x1_list = [converted_combo["X1"]]  # Single value from combination
                else:
                    # X1 is from experiment's X1_values list - need to convert each
                    irefp = converted_combo.get("IREFP", 100e-9)
                    combo_x1_list = [self.convert_normalized_to_current("X1", x, irefp) for x in x1_list]
                
                # Set fixed current values (only current values change)
                # Filter out non-current parameters (ERASE_PROG, IMEAS if None)
                # Use converted values (actual currents)
                current_combo = {k: v for k, v in converted_combo.items() 
                               if k not in ["ERASE_PROG", "IMEAS"] or (k == "IMEAS" and v is not None)}
                
                if is_first_iteration_of_experiment:
                    # First iteration of experiment: set ALL sources and pause 1 second
                    self.logger.info("First iteration of experiment - setting all sources")
                    self.setup_fixed_currents(current_combo)
                    if not self.test_mode:
                        self.logger.info("Waiting 1 second for sources to settle...")
                        time.sleep(1.0)
                    is_first_iteration_of_experiment = False
                else:
                    # Subsequent iterations: only update sources that changed
                    changed_sources = {}
                    for param, value in current_combo.items():
                        if prev_current_combo is None or prev_current_combo.get(param) != value:
                            changed_sources[param] = value
                    
                    if changed_sources:
                        self.logger.info(f"Updating changed sources: {list(changed_sources.keys())}")
                        self.setup_fixed_currents(changed_sources)
                        if not self.test_mode:
                            self.logger.info("Waiting 100ms for sources to settle...")
                            time.sleep(0.1)
                    else:
                        self.logger.debug("No source changes needed")
                
                # Track current values for next iteration
                prev_current_combo = current_combo.copy()
                
                # For each PPG state in this combination
                for ppg_state in combo_ppg_states:
                    self.logger.info("-" * 40)
                    self.logger.info(f"PPG STATE: {ppg_state} ({COMPUTE_PPG_STATES.get(ppg_state, {}).get('description', 'Unknown')})")
                    
                    # Set PPG voltage (only voltage value changes, no reconfig)
                    self.set_ppg_state(ppg_state)
                    ppg_voltage = self.get_ppg_state_voltage(ppg_state)
                    
                    # For each X1 value
                    for x1_idx, x1_value in enumerate(combo_x1_list):
                        measurement_num += 1
                        self.logger.info("-" * 30)
                        self.logger.info(f"[{measurement_num}] Experiment '{exp_name}' - "
                                       f"PPG: {ppg_state}, X1: {x1_value}A ({x1_idx+1}/{len(combo_x1_list)})")
                        
                        # Determine IMEAS value (already converted to actual current)
                        imeas_value = converted_combo.get("IMEAS")
                        if imeas_value is None:
                            # If IMEAS is None in fixed_values, it means use same as X1
                            imeas_value = x1_value
                        elif "IMEAS" in sweep_vars:
                            # IMEAS is being swept, use converted value from combo
                            imeas_value = converted_combo.get("IMEAS", x1_value)
                        else:
                            # IMEAS is fixed, use converted value from fixed_values or combo
                            imeas_value = converted_combo.get("IMEAS", x1_value)
                        
                        # Execute spot measurement for this X1/IMEAS value
                        spot_results = self.execute_spot_measurement(x1_value, imeas_value=imeas_value)
                        
                        # Get measured currents from spot measurement
                        out1_current = spot_results["OUT1_current"]
                        out2_current = spot_results["OUT2_current"]
                        
                        # In test mode, use dummy measurement data but keep correct voltage/current settings
                        if self.test_mode:
                            # Use small dummy values for measurements, but keep actual voltage/current settings
                            out1_current = 1e-12  # Dummy measurement
                            out2_current = 1e-12  # Dummy measurement
                        
                        # Write row to CSV (include experiment name)
                        self._write_measurement_row(
                            experiment_name=exp_name,
                            ppg_state=ppg_state,
                            ppg_voltage=ppg_voltage,
                            fixed_currents=current_combo,
                            x1_value=spot_results["x1_value"],
                            imeas_value=spot_results["imeas_value"],
                            out1_current=out1_current,
                            out2_current=out2_current
                        )
                        
                        # Store results
                        measurement = {
                            "experiment_name": exp_name,
                            "combination_index": combo_idx,
                            "x1_index": x1_idx,
                            "x1_value": x1_value,
                            "imeas_value": spot_results["imeas_value"],
                            "ppg_state": ppg_state,
                            "ppg_voltage": ppg_voltage,
                            "parameters": current_combo.copy(),
                            "spot_results": spot_results,
                        }
                        exp_results["measurements"].append(measurement)
                        results["measurements"][exp_name] = results["measurements"].get(exp_name, [])
                        results["measurements"][exp_name].append(measurement)
                        
                        # Check for errors after first measurement
                        if measurement_num == 1:
                            self.logger.info("Checking for errors after first measurement...")
                            errors = self.check_all_instrument_errors()
                            self.report_and_exit_on_errors(errors)
            
            results["experiments_run"].append(exp_results)
            self.logger.info("=" * 60)
            self.logger.info(f"Experiment '{exp_name}' complete: {len(exp_results['measurements'])} measurements")
            self.logger.info("=" * 60)
        
        results["total_measurements"] = measurement_num
        
        self.logger.info("=" * 60)
        self.logger.info("All experiments complete")
        self.logger.info(f"Total experiments run: {len(enabled_experiments)}")
        self.logger.info(f"Total measurements: {measurement_num}")
        self.logger.info("Note: Using spot measurements (no sweeps)")
        self.logger.info("=" * 60)
        
        # Calculate and log total elapsed time
        end_time = time.time()
        total_elapsed_time = end_time - start_time
        
        # Format time in a readable way
        hours = int(total_elapsed_time // 3600)
        minutes = int((total_elapsed_time % 3600) // 60)
        seconds = total_elapsed_time % 60
        
        self.logger.info("=" * 60)
        self.logger.info("TOTAL EXPERIMENT TIME")
        self.logger.info("=" * 60)
        if hours > 0:
            self.logger.info(f"Total elapsed time: {hours}h {minutes}m {seconds:.2f}s ({total_elapsed_time:.2f} seconds)")
        elif minutes > 0:
            self.logger.info(f"Total elapsed time: {minutes}m {seconds:.2f}s ({total_elapsed_time:.2f} seconds)")
        else:
            self.logger.info(f"Total elapsed time: {seconds:.2f}s")
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
        
        # Experiments are now defined in configs/compute_settings.py
        # Each experiment has its own fixed values and sweep variables
        # No need to set sweep values here - they're loaded from EXPERIMENTS list
        
        # Run experiment
        results = experiment.run()
    
    # Print summary
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"Experiment: {results['experiment']}")
    print(f"Parameters: VDD={results['parameters']['VDD']}V, "
          f"VCC={results['parameters']['VCC']}V")
    print(f"Experiments run: {len(results.get('experiments_run', []))}")
    
    for exp_result in results.get('experiments_run', []):
        print(f"  - {exp_result.get('name', 'Unknown')}: {len(exp_result.get('measurements', []))} measurements")
    
    print(f"Total measurements: {results.get('total_measurements', 0)}")
    print("=" * 60)


if __name__ == '__main__':
    main()
