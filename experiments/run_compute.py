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
    --vcc: VCC voltage (default: 5.0V)

Configuration:
    Terminal mappings are defined in configs/compute.py
    This script does NOT read the CSV file at runtime.

Compliance Settings:
    - Voltage sources: 1mA compliance
    - Current sources: 2V compliance
    - Current direction: "pulled" (positive = into IV meter)
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
    COMPUTE_PULSE_CONFIG,
    COMPUTE_DEFAULTS,
)
from configs.resource_types import MeasurementType


class ComputeExperiment(ExperimentRunner):
    """
    Compute experiment runner.
    
    Performs computation mode characterization with:
    - Voltage biasing on OUT1, OUT2 (V terminals)
    - VSU biasing on VDD, VCC
    - Pulse generation on ERASE_PROG
    - Current measurements on trim, gain, and reference terminals
    
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
        """
        super().__init__(COMPUTE_CONFIG, test_mode)
        self.vdd = vdd if vdd is not None else COMPUTE_DEFAULTS["VDD"]
        self.vcc = vcc if vcc is not None else COMPUTE_DEFAULTS["VCC"]
    
    def setup_bias(self) -> None:
        """Configure all bias conditions for the experiment."""
        self.logger.info("Setting up bias conditions...")
        
        # Enable GNDU (ground reference)
        self.enable_gndu("VSS")
        
        # Set VSU terminals (VDD and VCC are VSU type)
        self.set_terminal_voltage("VDD", self.vdd)
        self.set_terminal_voltage("VCC", self.vcc)
        
        # Set V terminals (output voltages)
        self.set_terminal_voltage("OUT1", 0.0)  # Initial value
        self.set_terminal_voltage("OUT2", 0.0)  # Initial value
        
        # Set I terminals to 0A initially (current force mode)
        # Current is "pulled" (positive = into meter)
        for terminal in COMPUTE_BY_TYPE[MeasurementType.I]:
            self.set_terminal_current(terminal, 0.0)
        
        self.logger.info("Bias setup complete")
    
    def send_erase_prog_pulse(self, vhigh: float = None, vlow: float = None,
                              width: str = None, count: int = 1) -> None:
        """
        Send erase/program pulse on ERASE_PROG terminal.
        
        Args:
            vhigh: High voltage (default from config)
            vlow: Low voltage (default from config)
            width: Pulse width (default from config)
            count: Number of pulses
        """
        pulse_cfg = COMPUTE_PULSE_CONFIG.get("ERASE_PROG", {})
        
        self.set_pulse(
            terminal="ERASE_PROG",
            vhigh=vhigh or pulse_cfg.get("default_vhigh", 5.0),
            vlow=vlow or pulse_cfg.get("default_vlow", 0.0),
            width=width or pulse_cfg.get("default_width", "100NS"),
            period=pulse_cfg.get("default_period", "1US"),
            count=count
        )
    
    def measure_all_currents(self) -> dict:
        """
        Measure currents on all I terminals.
        
        All currents are "pulled" (positive = into IV meter).
        
        Returns:
            Dictionary mapping terminal names to current values
        """
        self.logger.info("Measuring all terminal currents...")
        results = {}
        
        # Measure all I terminals
        for terminal in COMPUTE_BY_TYPE[MeasurementType.I]:
            current = self.measure_terminal_current(terminal)
            results[terminal] = current
        
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
            },
            "measurements": {}
        }
        
        # Step 1: Setup bias
        self.setup_bias()
        
        # Step 2: Initial current measurement
        self.logger.info("-" * 40)
        self.logger.info("Step 2: Initial current measurements")
        results["measurements"]["initial"] = self.measure_all_currents()
        
        # Step 3: Send erase/program pulse and measure
        self.logger.info("-" * 40)
        self.logger.info("Step 3: Erase/Program pulse test")
        self.send_erase_prog_pulse(count=1)
        results["measurements"]["after_pulse"] = self.measure_all_currents()
        
        # Step 4: Sweep OUT1
        self.logger.info("-" * 40)
        self.logger.info("Step 4: OUT1 voltage sweep")
        results["measurements"]["out1_sweep"] = self.sweep_output_voltage(
            "OUT1", 0.0, self.vdd, 0.1
        )
        
        # Step 5: Reset OUT1 and sweep OUT2
        self.set_terminal_voltage("OUT1", 0.0)
        self.logger.info("-" * 40)
        self.logger.info("Step 5: OUT2 voltage sweep")
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
        default=5.0,
        help='VCC voltage in volts (default: 5.0)'
    )
    args = parser.parse_args()
    
    # Run experiment
    with ComputeExperiment(
        test_mode=args.test,
        vdd=args.vdd,
        vcc=args.vcc,
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
