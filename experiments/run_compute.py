#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Compute Experiment Execution Script

Top-level execution script for the Compute experiment.
This script:
- Imports instrument-level modules
- Loads the Compute experiment configuration
- Executes the measurement sequence
- Handles TEST_MODE for safe command logging

Usage:
    python -m experiments.run_compute [--test] [--vdd VDD] [--vcc VCC]
    
    --test: Run in TEST_MODE (log commands without hardware)
    --vdd: VDD voltage (default: 1.8V)
    --vcc: VCC voltage (default: 3.3V)

Configuration:
    Terminal mappings are defined in configs/compute.py
    This script does NOT read the CSV file at runtime.
"""

import sys
import os
import argparse
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.base_experiment import ExperimentRunner
from configs.compute import (
    COMPUTE_CONFIG,
    COMPUTE_TERMINALS,
    COMPUTE_BY_TYPE,
    COMPUTE_SEQUENTIAL_PAIRS,
)
from configs.resource_types import MeasurementType


class ComputeExperiment(ExperimentRunner):
    """
    Compute experiment runner.
    
    Performs computation mode characterization with:
    - Voltage biasing on VDD, OUT1, OUT2
    - Current measurements on trim, gain, and reference terminals
    - VSU biasing on VCC and ERASE_PROG
    """
    
    def __init__(self, test_mode: bool = False, vdd: float = 1.8, 
                 vcc: float = 3.3, erase_prog: float = 0.0):
        """
        Initialize Compute experiment.
        
        Args:
            test_mode: If True, log commands without hardware
            vdd: VDD voltage in volts
            vcc: VCC voltage in volts
            erase_prog: ERASE_PROG voltage in volts
        """
        super().__init__(COMPUTE_CONFIG, test_mode)
        self.vdd = vdd
        self.vcc = vcc
        self.erase_prog = erase_prog
    
    def setup_bias(self) -> None:
        """Configure all bias conditions for the experiment."""
        self.logger.info("Setting up bias conditions...")
        
        # Enable GNDU (ground reference)
        self.enable_gndu("VSS")
        
        # Set V terminals (voltage sources)
        self.set_terminal_voltage("VDD", self.vdd)
        self.set_terminal_voltage("OUT1", 0.0)  # Initial value
        self.set_terminal_voltage("OUT2", 0.0)  # Initial value
        
        # Set VSU terminals
        self.set_terminal_voltage("VCC", self.vcc)
        self.set_terminal_voltage("ERASE_PROG", self.erase_prog)
        
        # Set I terminals to 0A initially (current force mode)
        for terminal in COMPUTE_BY_TYPE[MeasurementType.I]:
            if terminal not in ["IMEAS"]:  # Skip sequential pair
                self.set_terminal_current(terminal, 0.0)
        
        self.logger.info("Bias setup complete")
    
    def measure_all_currents(self) -> dict:
        """
        Measure currents on all I terminals.
        
        Returns:
            Dictionary mapping terminal names to current values
        """
        self.logger.info("Measuring all terminal currents...")
        results = {}
        
        # Measure primary I terminals
        for terminal in COMPUTE_BY_TYPE[MeasurementType.I]:
            # Handle sequential pairs - skip IMEAS for now
            skip_pair = any(terminal == pair[1] for pair in COMPUTE_SEQUENTIAL_PAIRS)
            if not skip_pair:
                current = self.measure_terminal_current(terminal)
                results[terminal] = current
        
        # Now measure sequential terminals
        for pair in COMPUTE_SEQUENTIAL_PAIRS:
            primary, secondary = pair
            self.logger.info(f"Sequential measurement: {secondary} (after {primary})")
            # Reconfigure the channel for the secondary terminal
            current = self.measure_terminal_current(secondary)
            results[secondary] = current
        
        return results
    
    def sweep_output_voltage(self, terminal: str, start: float, stop: float,
                            step: float) -> list:
        """
        Sweep voltage on an output terminal and measure response.
        
        Args:
            terminal: Output terminal (OUT1 or OUT2)
            start: Start voltage
            stop: Stop voltage
            step: Step voltage
            
        Returns:
            List of (voltage, currents_dict) tuples
        """
        self.logger.info(f"Sweeping {terminal}: {start}V to {stop}V, step {step}V")
        results = []
        
        voltage = start
        while voltage <= stop:
            self.set_terminal_voltage(terminal, voltage)
            currents = self.measure_all_currents()
            results.append((voltage, currents))
            voltage += step
        
        return results
    
    def run(self) -> dict:
        """
        Execute the Compute experiment.
        
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
                "ERASE_PROG": self.erase_prog,
            },
            "measurements": {}
        }
        
        # Step 1: Setup bias
        self.setup_bias()
        
        # Step 2: Initial current measurement
        self.logger.info("-" * 40)
        self.logger.info("Step 2: Initial current measurements")
        results["measurements"]["initial"] = self.measure_all_currents()
        
        # Step 3: Sweep OUT1
        self.logger.info("-" * 40)
        self.logger.info("Step 3: OUT1 voltage sweep")
        results["measurements"]["out1_sweep"] = self.sweep_output_voltage(
            "OUT1", 0.0, self.vdd, 0.1
        )
        
        # Step 4: Reset OUT1 and sweep OUT2
        self.set_terminal_voltage("OUT1", 0.0)
        self.logger.info("-" * 40)
        self.logger.info("Step 4: OUT2 voltage sweep")
        results["measurements"]["out2_sweep"] = self.sweep_output_voltage(
            "OUT2", 0.0, self.vdd, 0.1
        )
        
        self.logger.info("=" * 60)
        self.logger.info("Compute experiment complete")
        self.logger.info("=" * 60)
        
        return results


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
        default=1.8,
        help='VDD voltage in volts (default: 1.8)'
    )
    parser.add_argument(
        '--vcc',
        type=float,
        default=3.3,
        help='VCC voltage in volts (default: 3.3)'
    )
    parser.add_argument(
        '--erase-prog',
        type=float,
        default=0.0,
        help='ERASE_PROG voltage in volts (default: 0.0)'
    )
    args = parser.parse_args()
    
    # Run experiment
    with ComputeExperiment(
        test_mode=args.test,
        vdd=args.vdd,
        vcc=args.vcc,
        erase_prog=args.erase_prog
    ) as experiment:
        results = experiment.run()
    
    # Print summary
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"Experiment: {results['experiment']}")
    print(f"Parameters: VDD={results['parameters']['VDD']}V, "
          f"VCC={results['parameters']['VCC']}V")
    print(f"Initial currents measured: {len(results['measurements']['initial'])}")
    print(f"OUT1 sweep points: {len(results['measurements']['out1_sweep'])}")
    print(f"OUT2 sweep points: {len(results['measurements']['out2_sweep'])}")
    print("=" * 60)


if __name__ == '__main__':
    main()

