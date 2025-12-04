#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Compute Experiment Execution Script

Top-level execution script for the Compute experiment.
This script:
- Imports instrument-level modules
- Loads the Compute experiment configuration
- Executes the measurement sequence with synchronous sweeps
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
       - Execute synchronous sweep (X1 and IMEAS)
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
    - Synchronous sweep of X1 and IMEAS
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
        
        # Synchronous sweep configuration
        self.sync_sweep_config = {
            "X1": {"start": 0.0, "stop": 0.0, "step": 0.0},
            "IMEAS": {"start": 0.0, "stop": 0.0, "step": 0.0},
        }
        
        # Flag to track if initial setup has been done
        self._channels_initialized = False
    
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
    
    def set_sync_sweep_config(self, terminal: str, start: float, stop: float, 
                              step: float) -> None:
        """
        Configure the synchronous sweep for X1 or IMEAS.
        
        Args:
            terminal: "X1" or "IMEAS"
            start: Start current in Amps
            stop: Stop current in Amps
            step: Step current in Amps
        """
        if terminal in self.sync_sweep_config:
            self.sync_sweep_config[terminal] = {
                "start": start,
                "stop": stop,
                "step": step,
            }
            self.logger.info(f"{terminal} sweep: {start}A to {stop}A, step={step}A")
        else:
            raise ValueError(f"Unknown sync sweep terminal: {terminal}")
    
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
        # Channels: 1 (OUT1), 2 (OUT2), 3 (X1), 4 (IMEAS), 5 (TRIM1), 6 (TRIM2), 7 (F11), 8 (F12)
        # Plus GNDU (channel 0)
        iv5270b.enable_channels([0, 1, 2, 3, 4, 5, 6, 7, 8])
        self.logger.info("5270B: Enabled channels 0-8 (GNDU + 8 SMUs)")
        
        # Enable all 4156B channels used in this experiment
        # Channels: 1 (X2), 2 (KGAIN1), 3 (KGAIN2), 4 (IREFP), 21 (VDD VSU), 22 (VCC VSU)
        iv4156b.enable_channels([1, 2, 3, 4, 21, 22])
        self.logger.info("4156B: Enabled channels 1-4 (SMUs) + 21-22 (VSUs)")
        
        # Set measurement mode for spot measurements on 5270B
        # Mode 1 = spot measurement, we'll measure OUT1 and OUT2
        iv5270b.set_measurement_mode(1, [1, 2])
        
        self._channels_initialized = True
        self.logger.info("All channels initialized")
    
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
                    self.set_terminal_current(terminal, value)
                self.logger.debug(f"{param_name} (linked): {value}A -> {terminals}")
            else:
                # Single terminal
                self.set_terminal_current(param_name, value)
                self.logger.debug(f"{param_name}: {value}A")
    
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
    
    def execute_sync_sweep(self) -> Dict[str, Any]:
        """
        Execute synchronous sweep of X1 with IMEAS offset.
        
        X1 is swept as the primary channel. IMEAS is set as an offset from X1.
        Multiple sweeps are performed, one for each offset value.
        
        Offset values: -20e-9, -10e-9, 0, 10e-9, 20e-9 (5 sweeps total)
        For each offset, IMEAS = X1 + offset at each sweep point.
        
        Note: This method only changes current values on SMU channels.
        Channel initialization and measurement mode are set once at experiment start.
        
        Returns:
            Dictionary with sweep results including:
            - offset_sweeps: List of dictionaries, one per offset, each containing:
              - offset: The IMEAS offset value used
              - sweep_points: List of (X1_current, IMEAS_current) tuples
              - OUT1_currents: List of measured currents
              - OUT2_currents: List of measured currents
        """
        self.logger.info("Executing synchronous sweep with IMEAS offsets...")
        
        # Define IMEAS offset values: -20e-9 to 20e-9 in steps of 10e-9
        imeas_offsets = [-20e-9, -10e-9, 0.0, 10e-9, 20e-9]
        
        # Get 5270B instrument (all sync sweep terminals are on it)
        inst = self._get_instrument(InstrumentType.IV5270B)
        
        # Get channel numbers (no reinitialization - just reference)
        x1_cfg = self.get_terminal_config("X1")
        imeas_cfg = self.get_terminal_config("IMEAS")
        out1_cfg = self.get_terminal_config("OUT1")
        out2_cfg = self.get_terminal_config("OUT2")
        
        # Calculate X1 sweep points (IMEAS is now offset-based, not independent)
        x1_config = self.sync_sweep_config["X1"]
        
        # Generate X1 sweep points
        x1_points = []
        current = x1_config["start"]
        step = x1_config["step"] if x1_config["step"] != 0 else 1
        while current <= x1_config["stop"]:
            x1_points.append(current)
            current += step
        
        if len(x1_points) == 0:
            x1_points = [x1_config["start"]]
        
        num_points = len(x1_points)
        
        results = {
            "offset_sweeps": [],
        }
        
        self.logger.info(f"X1 sweep: {num_points} points")
        self.logger.info(f"IMEAS offsets: {len(imeas_offsets)} values ({imeas_offsets})")
        
        # Execute sweep for each offset value
        for offset_idx, imeas_offset in enumerate(imeas_offsets):
            self.logger.info(f"Offset sweep {offset_idx + 1}/{len(imeas_offsets)}: IMEAS offset = {imeas_offset}A")
            
            offset_results = {
                "offset": imeas_offset,
                "sweep_points": [],
                "OUT1_currents": [],
                "OUT2_currents": [],
            }
            
            # Execute sweep - ONLY changing current values
            for i in range(num_points):
                x1_val = x1_points[i]
                imeas_val = x1_val + imeas_offset  # IMEAS = X1 + offset
                
                # Set sweep source currents (this is the ONLY thing that changes)
                inst.set_current(x1_cfg.channel, x1_val, compliance=2.0)
                inst.set_current(imeas_cfg.channel, imeas_val, compliance=2.0)
                
                # Execute measurement and read data
                # Channels are already configured for measurement
                inst.execute_measurement()
                data = inst.read_data()
                
                # Parse OUT1 and OUT2 currents from measurement data
                # The format depends on how the instrument was configured
                try:
                    # Try to parse two current values from the response
                    parts = data.replace(",", " ").split()
                    out1_current = 0.0
                    out2_current = 0.0
                    current_values = []
                    for part in parts:
                        if "I" in part or "E" in part.upper():
                            try:
                                val = float(part.replace("I", "").strip())
                                current_values.append(val)
                            except ValueError:
                                try:
                                    val = float(part.strip())
                                    current_values.append(val)
                                except ValueError:
                                    pass
                    if len(current_values) >= 2:
                        out1_current = current_values[0]
                        out2_current = current_values[1]
                    elif len(current_values) == 1:
                        out1_current = current_values[0]
                except (IndexError, ValueError):
                    out1_current = 0.0
                    out2_current = 0.0
                
                offset_results["sweep_points"].append((x1_val, imeas_val))
                offset_results["OUT1_currents"].append(out1_current)
                offset_results["OUT2_currents"].append(out2_current)
            
            results["offset_sweeps"].append(offset_results)
            self.logger.debug(f"Offset {imeas_offset}A: {num_points} points complete")
        
        total_points = num_points * len(imeas_offsets)
        self.logger.info(f"Sweep complete: {len(imeas_offsets)} offset sweeps, {total_points} total points")
        
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
                "X1": self.sync_sweep_config["X1"],
                "IMEAS": self.sync_sweep_config["IMEAS"],
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
        total_measurements = len(COMPUTE_PPG_STATE_ORDER) * len(combinations)
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
                measurement_num += 1
                self.logger.info("-" * 60)
                self.logger.info(f"[{measurement_num}/{total_measurements}] "
                               f"{ppg_state} - Combination {i+1}/{len(combinations)}")
                self.logger.info(f"Fixed currents: {combo}")
                
                # Set fixed current values (only current values change)
                self.setup_fixed_currents(combo)
                
                # Execute synchronous sweep (only X1/IMEAS currents change)
                sweep_results = self.execute_sync_sweep()
                
                # Store results
                measurement = {
                    "combination_index": i,
                    "ppg_state": ppg_state,
                    "ppg_voltage": self.get_ppg_state_voltage(ppg_state),
                    "fixed_currents": combo,
                    "sweep_results": sweep_results,
                }
                results["measurements"][ppg_state].append(measurement)
        
        self.logger.info("=" * 60)
        self.logger.info("Compute experiment complete")
        self.logger.info(f"Total measurements: {measurement_num} "
                        f"({len(combinations)} combinations x {len(COMPUTE_PPG_STATE_ORDER)} PPG states)")
        self.logger.info("=" * 60)
        
        return results
    
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
        
        # Configure synchronous sweep from settings
        experiment.set_sync_sweep_config(
            "X1",
            start=SETTINGS.X1_SWEEP["start"],
            stop=SETTINGS.X1_SWEEP["stop"],
            step=SETTINGS.X1_SWEEP["step"]
        )
        experiment.set_sync_sweep_config(
            "IMEAS",
            start=SETTINGS.IMEAS_SWEEP["start"],
            stop=SETTINGS.IMEAS_SWEEP["stop"],
            step=SETTINGS.IMEAS_SWEEP["step"]
        )
        
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
        if 'offset_sweeps' in first['sweep_results']:
            # New structure with offset sweeps
            num_offsets = len(first['sweep_results']['offset_sweeps'])
            if num_offsets > 0:
                points_per_offset = len(first['sweep_results']['offset_sweeps'][0]['sweep_points'])
                print(f"Sweep structure: {num_offsets} offset sweeps, {points_per_offset} points per offset")
                print(f"Total sweep points per measurement: {num_offsets * points_per_offset}")
        elif 'sweep_points' in first['sweep_results']:
            # Old structure (backward compatibility)
            print(f"Sweep points per measurement: {len(first['sweep_results']['sweep_points'])}")
    print("=" * 60)


if __name__ == '__main__':
    main()
