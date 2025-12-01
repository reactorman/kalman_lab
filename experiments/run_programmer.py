#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Programmer Experiment Execution Script

Top-level execution script for the Programmer experiment.
This script:
- Imports instrument-level modules
- Loads the Programmer experiment configuration
- Executes the programming/erase measurement sequence
- Handles TEST_MODE for safe command logging

Usage:
    python -m experiments.run_programmer [--test] [--vdd VDD] [--cycles N]
    
    --test: Run in TEST_MODE (log commands without hardware)
    --vdd: VDD voltage (default: 1.8V)
    --vcc: VCC voltage (default: 5.0V)
    --cycles: Number of program/erase cycles (default: 1)

Configuration:
    Terminal mappings are defined in configs/programmer.py
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
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.base_experiment import ExperimentRunner
from configs.programmer import (
    PROGRAMMER_CONFIG,
    PROGRAMMER_TERMINALS,
    PROGRAMMER_BY_TYPE,
    PROGRAMMER_PULSE_CONFIG,
    PROGRAMMER_COUNTER_CONFIG,
    PROGRAMMER_DEFAULTS,
)
from configs.resource_types import MeasurementType, InstrumentType


class ProgrammerExperiment(ExperimentRunner):
    """
    Programmer experiment runner.
    
    Performs programming mode characterization with:
    - Voltage biasing on VDD, VCC, ICELLMEAS
    - Pulse generation on WR_ENB
    - Frequency measurement on PROG_OUT
    - Current measurements on IREFP, PROG_IN
    
    All currents are "pulled" (positive = into IV meter).
    """
    
    def __init__(self, test_mode: bool = False, vdd: float = None,
                 vcc: float = None, erase_prog_voltage: float = 5.0,
                 program_cycles: int = 1):
        """
        Initialize Programmer experiment.
        
        Args:
            test_mode: If True, log commands without hardware
            vdd: VDD voltage in volts (default: 1.8V)
            vcc: VCC voltage in volts (default: 5.0V)
            erase_prog_voltage: ERASE_PROG voltage for programming
            program_cycles: Number of program/erase cycles
        """
        super().__init__(PROGRAMMER_CONFIG, test_mode)
        self.vdd = vdd if vdd is not None else PROGRAMMER_DEFAULTS["VDD"]
        self.vcc = vcc if vcc is not None else PROGRAMMER_DEFAULTS["VCC"]
        self.erase_prog_voltage = erase_prog_voltage
        self.program_cycles = program_cycles
    
    def setup_bias(self) -> None:
        """Configure all bias conditions for the experiment."""
        self.logger.info("Setting up bias conditions...")
        
        # Enable GNDU (ground reference)
        self.enable_gndu("VSS")
        
        # Set V terminals (high-resolution voltage sources)
        self.set_terminal_voltage("VDD", self.vdd)
        self.set_terminal_voltage("VCC", self.vcc)
        self.set_terminal_voltage("ICELLMEAS", 0.0)  # Initial value
        
        # Set VSU terminal
        self.set_terminal_voltage("ERASE_PROG", 0.0)  # Start at 0V
        
        # Set I terminals to 0A initially
        # Current is "pulled" (positive = into meter)
        for terminal in PROGRAMMER_BY_TYPE[MeasurementType.I]:
            self.set_terminal_current(terminal, 0.0)
        
        # Configure counter
        self.configure_counter()
        
        self.logger.info("Bias setup complete")
    
    def configure_counter(self) -> None:
        """Configure the frequency counter for PROG_OUT measurement."""
        cfg = PROGRAMMER_COUNTER_CONFIG.get("PROG_OUT", {})
        counter = self._get_instrument(InstrumentType.CT53230A)
        
        # Configure for frequency measurement
        channel = PROGRAMMER_TERMINALS["PROG_OUT"].channel
        counter.configure_frequency(channel)
        counter.set_gate_time(cfg.get("default_gate_time", 0.1))
        counter.set_coupling(channel, cfg.get("coupling", "AC"))
        counter.set_impedance(channel, cfg.get("impedance", 1000000))
        
        self.logger.info("Counter configured for PROG_OUT")
    
    def send_write_pulse(self, count: int = 1) -> None:
        """
        Send write enable pulse(s).
        
        Args:
            count: Number of pulses to send
        """
        pulse_cfg = PROGRAMMER_PULSE_CONFIG.get("WR_ENB", {})
        
        self.set_pulse(
            terminal="WR_ENB",
            vhigh=pulse_cfg.get("default_vhigh", 3.3),
            vlow=pulse_cfg.get("default_vlow", 0.0),
            width=pulse_cfg.get("default_width", "100NS"),
            period=pulse_cfg.get("default_period", "1US"),
            count=count
        )
    
    def program_cell(self) -> dict:
        """
        Execute a single program operation.
        
        Returns:
            Dictionary with programming results
        """
        self.logger.info("Executing PROGRAM operation...")
        results = {}
        
        # Set ERASE_PROG to programming voltage
        self.set_terminal_voltage("ERASE_PROG", self.erase_prog_voltage)
        
        # Small delay for voltage settling
        time.sleep(0.01) if not self.test_mode else None
        
        # Send write pulse
        self.send_write_pulse(count=1)
        
        # Measure PROG_OUT frequency
        results["frequency"] = self.measure_frequency("PROG_OUT")
        
        # Measure reference current (pulled into meter)
        results["irefp"] = self.measure_terminal_current("IREFP")
        
        # Return ERASE_PROG to safe level
        self.set_terminal_voltage("ERASE_PROG", 0.0)
        
        self.logger.info(f"PROGRAM complete: freq={results['frequency']} Hz")
        return results
    
    def erase_cell(self) -> dict:
        """
        Execute a single erase operation.
        
        Returns:
            Dictionary with erase results
        """
        self.logger.info("Executing ERASE operation...")
        results = {}
        
        # Set ERASE_PROG to erase voltage (negative of program voltage)
        erase_voltage = -self.erase_prog_voltage
        self.set_terminal_voltage("ERASE_PROG", erase_voltage)
        
        # Small delay for voltage settling
        time.sleep(0.01) if not self.test_mode else None
        
        # Send write pulse
        self.send_write_pulse(count=1)
        
        # Measure PROG_OUT frequency
        results["frequency"] = self.measure_frequency("PROG_OUT")
        
        # Measure reference current (pulled into meter)
        results["irefp"] = self.measure_terminal_current("IREFP")
        
        # Return ERASE_PROG to safe level
        self.set_terminal_voltage("ERASE_PROG", 0.0)
        
        self.logger.info(f"ERASE complete: freq={results['frequency']} Hz")
        return results
    
    def measure_baseline(self) -> dict:
        """
        Measure baseline (unprogrammed) state.
        
        Returns:
            Dictionary with baseline measurements
        """
        self.logger.info("Measuring baseline state...")
        results = {}
        
        results["frequency"] = self.measure_frequency("PROG_OUT")
        results["irefp"] = self.measure_terminal_current("IREFP")
        results["prog_in"] = self.measure_terminal_current("PROG_IN")
        
        return results
    
    def run(self) -> dict:
        """
        Execute the Programmer experiment.
        
        Returns:
            Dictionary containing all measurement results
        """
        self.logger.info("=" * 60)
        self.logger.info("Executing Programmer experiment measurement sequence")
        self.logger.info("=" * 60)
        
        results = {
            "experiment": "Programmer",
            "parameters": {
                "VDD": self.vdd,
                "VCC": self.vcc,
                "ERASE_PROG_VOLTAGE": self.erase_prog_voltage,
                "PROGRAM_CYCLES": self.program_cycles,
            },
            "measurements": {
                "baseline": None,
                "cycles": []
            }
        }
        
        # Step 1: Setup bias
        self.setup_bias()
        
        # Step 2: Baseline measurement
        self.logger.info("-" * 40)
        self.logger.info("Step 2: Baseline measurement")
        results["measurements"]["baseline"] = self.measure_baseline()
        
        # Step 3: Program/Erase cycles
        for cycle in range(self.program_cycles):
            self.logger.info("-" * 40)
            self.logger.info(f"Step 3.{cycle+1}: Program/Erase cycle {cycle+1}")
            
            cycle_results = {
                "cycle": cycle + 1,
                "program": None,
                "erase": None,
            }
            
            # Program
            cycle_results["program"] = self.program_cell()
            
            # Erase
            cycle_results["erase"] = self.erase_cell()
            
            results["measurements"]["cycles"].append(cycle_results)
        
        # Step 4: Final measurement
        self.logger.info("-" * 40)
        self.logger.info("Step 4: Final measurement")
        results["measurements"]["final"] = self.measure_baseline()
        
        self.logger.info("=" * 60)
        self.logger.info("Programmer experiment complete")
        self.logger.info("=" * 60)
        
        return results


def main():
    """Main entry point for Programmer experiment."""
    parser = argparse.ArgumentParser(
        description='Run Programmer Experiment'
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
    parser.add_argument(
        '--erase-prog-voltage',
        type=float,
        default=5.0,
        help='ERASE_PROG voltage in volts (default: 5.0)'
    )
    parser.add_argument(
        '--cycles',
        type=int,
        default=1,
        help='Number of program/erase cycles (default: 1)'
    )
    args = parser.parse_args()
    
    # Run experiment
    with ProgrammerExperiment(
        test_mode=args.test,
        vdd=args.vdd,
        vcc=args.vcc,
        erase_prog_voltage=args.erase_prog_voltage,
        program_cycles=args.cycles
    ) as experiment:
        results = experiment.run()
    
    # Print summary
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"Experiment: {results['experiment']}")
    print(f"Parameters: VDD={results['parameters']['VDD']}V, "
          f"VCC={results['parameters']['VCC']}V, "
          f"Cycles={results['parameters']['PROGRAM_CYCLES']}")
    print(f"Baseline frequency: {results['measurements']['baseline']['frequency']} Hz")
    if results['measurements']['cycles']:
        last_cycle = results['measurements']['cycles'][-1]
        print(f"Last program frequency: {last_cycle['program']['frequency']} Hz")
        print(f"Last erase frequency: {last_cycle['erase']['frequency']} Hz")
    print(f"Final frequency: {results['measurements']['final']['frequency']} Hz")
    print("=" * 60)


if __name__ == '__main__':
    main()
