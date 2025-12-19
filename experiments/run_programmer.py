#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Programmer Experiment Execution Script

Top-level execution script for the Programmer experiment.
This script:
- Measures programming timing (WR_ENB low to PROG_OUT low)
- Uses 5270B for all SMU functions (4156B not used)
- Uses 53230A counter for time interval measurement
- Uses 81104A pulse generator for WR_ENB

Usage:
    python -m experiments.run_programmer [--test] [--vdd VDD] [--vcc VCC]
    
    --test: Run in TEST_MODE (log commands without hardware)
    --vdd: VDD voltage (default: 1.8V)
    --vcc: VCC voltage (default: 5.0V)

Configuration:
    Terminal mappings are defined in configs/programmer.py
    
Terminal Connections:
    PROG_OUT: SMU CH1 with VCC and series resistor → Counter CH2
    ICELLMEAS: SMU CH2 with VDD/2
    IREFP: SMU CH3 (current list)
    PROG_IN: SMU CH4 (10nA to 100nA in 10nA steps)
    VSS: GNDU
    WR_ENB: PPG CH1 → Counter CH1

Counter Setup:
    - CH1: Connected to PPG output (WR_ENB) - start event (falling edge)
    - CH2: Connected to PROG_OUT SMU - stop event (falling edge)
    - Threshold: VCC/2 on both channels

Experiment Sequence:
    1. Reset all instruments
    2. Turn on PPG (WR_ENB idle at VCC)
    3. Turn on voltage sources (PROG_OUT=VCC, ICELLMEAS=VDD/2)
    4. Turn on current sources (IREFP, PROG_IN)
    5. Spot measurement on ICELLMEAS
    6. Trigger PPG (WR_ENB goes to 0V for 1ms)
    7. Read counter for time delay
    8. Final spot measurement on ICELLMEAS
    9. Record: all currents, starting/final ICELLMEAS, pulse width
    10. Disable all instruments

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
import csv
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.base_experiment import ExperimentRunner
from configs.programmer import (
    PROGRAMMER_CONFIG,
    PROGRAMMER_TERMINALS,
    PROGRAMMER_BY_TYPE,
    PROGRAMMER_PULSE_CONFIG,
    PROGRAMMER_COUNTER_CONFIG,
    PROGRAMMER_PROG_IN_SWEEP,
    PROGRAMMER_DEFAULTS,
    PROGRAMMER_ENABLE_SEQUENCE,
)
from configs.resource_types import MeasurementType, InstrumentType

# Import experiment settings (edit these in configs/programmer_settings.py)
from configs import programmer_settings as SETTINGS


class ProgrammerExperiment(ExperimentRunner):
    """
    Programmer experiment runner.
    
    Measures programming timing by:
    - Applying VCC to PROG_OUT with series resistor enabled
    - Applying VDD/2 to ICELLMEAS
    - Sweeping PROG_IN from 10nA to 100nA
    - Sweeping IREFP through a list of values
    - Triggering WR_ENB pulse (VCC → 0V for 1ms, 10ns edges)
    - Measuring time interval from WR_ENB low to PROG_OUT low
    - Recording ICELLMEAS before and after programming
    
    All currents are "pulled" (positive = into IV meter).
    """
    
    def __init__(self, test_mode: bool = False, vdd: float = None, vcc: float = None):
        """
        Initialize Programmer experiment.
        
        Args:
            test_mode: If True, log commands without hardware
            vdd: VDD voltage in volts (default: 1.8V)
            vcc: VCC voltage in volts (default: 5.0V)
        """
        super().__init__(PROGRAMMER_CONFIG, test_mode)
        self.vdd = vdd if vdd is not None else PROGRAMMER_DEFAULTS["VDD"]
        self.vcc = vcc if vcc is not None else PROGRAMMER_DEFAULTS["VCC"]
        
        # IREFP values (user configurable)
        self.irefp_values: List[float] = []
        
        # PROG_IN values from config (10nA to 100nA)
        self.prog_in_values: List[float] = PROGRAMMER_PROG_IN_SWEEP["values"].copy()
        
        # CSV output file
        self._csv_file = None
        self._csv_writer = None
        self._csv_initialized = False
    
    def set_irefp_values(self, values: List[float]) -> None:
        """
        Set the IREFP current values to sweep.
        
        Args:
            values: List of current values in Amps
        """
        self.irefp_values = values.copy()
        self.logger.info(f"Set IREFP values: {len(values)} points")
    
    # ========================================================================
    # Initialization (called once at start of experiment)
    # ========================================================================
    
    def initialize_all(self) -> None:
        """
        Initialize all instruments once at the beginning of the experiment.
        
        This method is called once before any measurements. It:
        1. Configures PPG for WR_ENB (idle at VCC)
        2. Enables SMU channels and sets voltage sources
        3. Configures counter for time interval measurement
        
        After this, only current levels on IREFP and PROG_IN will change.
        """
        self.logger.info("=" * 60)
        self.logger.info("INITIALIZING ALL INSTRUMENTS (once)")
        self.logger.info("=" * 60)
        
        # Get instrument references
        iv = self._get_instrument(InstrumentType.IV5270B)
        
        # Enable all SMU channels at once
        prog_out_ch = self.get_terminal_config("PROG_OUT").channel
        icellmeas_ch = self.get_terminal_config("ICELLMEAS").channel
        irefp_ch = self.get_terminal_config("IREFP").channel
        prog_in_ch = self.get_terminal_config("PROG_IN").channel
        gndu_ch = self.get_terminal_config("VSS").channel
        
        iv.enable_channels([gndu_ch, prog_out_ch, icellmeas_ch, irefp_ch, prog_in_ch])
        self.logger.info(f"Enabled SMU channels: GNDU={gndu_ch}, PROG_OUT={prog_out_ch}, "
                        f"ICELLMEAS={icellmeas_ch}, IREFP={irefp_ch}, PROG_IN={prog_in_ch}")
        
        # Configure PPG (once)
        self._configure_ppg()
        
        # Configure voltage sources (once)
        self._configure_voltage_sources()
        
        # Configure counter (once)
        self._configure_counter()
        
        # Set initial current values to 0
        self._set_currents(0.0, 0.0)
        
        self.logger.info("=" * 60)
        self.logger.info("INITIALIZATION COMPLETE - Ready for measurements")
        self.logger.info("=" * 60)
        
        # Check for errors after initialization
        errors = self.check_all_instrument_errors()
        self.report_and_exit_on_errors(errors)
    
    def _configure_ppg(self) -> None:
        """
        Configure PPG for WR_ENB (called once during initialization).
        
        WR_ENB starts at VCC (idle high). When triggered, it will:
        - Fall to 0V with 10ns fall time
        - Remain at 0V for 1ms
        - Return to VCC with 10ns rise time
        """
        self.logger.info("-" * 40)
        self.logger.info("Configuring PPG (WR_ENB at VCC)")
        
        ppg = self._get_instrument(InstrumentType.PG81104A)
        cfg = PROGRAMMER_PULSE_CONFIG["WR_ENB"]
        channel = PROGRAMMER_TERMINALS["WR_ENB"].channel
        
        # Configure for triggered operation (arm=manual, trigger=immediate)
        ppg.set_arm_source("MAN")
        ppg.set_pattern_mode(False)
        ppg.set_trigger_count(1)
        ppg.set_trigger_source("IMM")
        
        # Set period (must accommodate 1ms pulse width)
        ppg.set_period(cfg["default_period"])
        
        # Configure inverted polarity so idle state is HIGH (VCC)
        # When triggered, output goes LOW (0V)
        ppg.set_polarity(channel, "INV")
        
        # Set voltage levels
        ppg.set_voltage_high(channel, self.vcc)  # VCC when idle (inverted)
        ppg.set_voltage_low(channel, cfg["default_vlow"])  # 0V when pulsing
        
        # Set pulse width (1ms at 0V)
        ppg.set_pulse_width(channel, cfg["default_width"])
        
        # Set rise/fall time (10ns)
        ppg.set_transition(channel, cfg["default_rise"])
        
        # Enable output (but don't trigger yet)
        ppg.enable_output(channel)
        
        self.logger.info(f"WR_ENB: Idle at {self.vcc}V, pulse to 0V for 1ms, 10ns edges")
    
    def _configure_voltage_sources(self) -> None:
        """
        Configure voltage sources (called once during initialization).
        
        - PROG_OUT: VCC with series resistor enabled
        - ICELLMEAS: VDD/2
        """
        self.logger.info("-" * 40)
        self.logger.info("Configuring voltage sources")
        
        # Get 5270B instrument
        iv = self._get_instrument(InstrumentType.IV5270B)
        
        # PROG_OUT: VCC with series resistor enabled
        prog_out_cfg = self.get_terminal_config("PROG_OUT")
        iv.set_series_resistor(prog_out_cfg.channel, True)
        self.set_terminal_voltage("PROG_OUT", self.vcc)
        self.logger.info(f"PROG_OUT: {self.vcc}V with series resistor enabled")
        
        # ICELLMEAS: VDD/2
        icellmeas_voltage = self.vdd / 2.0
        self.set_terminal_voltage("ICELLMEAS", icellmeas_voltage)
        self.logger.info(f"ICELLMEAS: {icellmeas_voltage}V (VDD/2)")
    
    def _configure_counter(self) -> None:
        """
        Configure the counter for time interval measurement (called once during initialization).
        
        Measures time from WR_ENB going low (CH1) to PROG_OUT going low (CH2).
        Both channels use VCC/2 as threshold and falling edge (NEG slope).
        """
        self.logger.info("-" * 40)
        self.logger.info("Configuring counter for time interval measurement")
        
        counter = self._get_instrument(InstrumentType.CT53230A)
        cfg = PROGRAMMER_COUNTER_CONFIG["time_interval"]
        
        # Threshold is VCC/2
        threshold = self.vcc / 2.0
        
        # Configure for time interval measurement
        counter.configure_time_interval(
            start_channel=cfg["start_channel"],
            stop_channel=cfg["stop_channel"]
        )
        
        # Set input coupling (DC for logic signals)
        counter.set_coupling(cfg["start_channel"], cfg["coupling"])
        counter.set_coupling(cfg["stop_channel"], cfg["coupling"])
        
        # Set input impedance (1 MOhm)
        counter.set_impedance(cfg["start_channel"], cfg["impedance"])
        counter.set_impedance(cfg["stop_channel"], cfg["impedance"])
        
        # Set trigger levels to VCC/2
        counter.set_trigger_level(cfg["start_channel"], threshold)
        counter.set_trigger_level(cfg["stop_channel"], threshold)
        
        # Set trigger slopes to falling edge (NEG) for both channels
        # WR_ENB goes low (start event), PROG_OUT goes low (stop event)
        counter.set_slope(cfg["start_channel"], "NEG")
        counter.set_slope(cfg["stop_channel"], "NEG")
        
        self.logger.info(f"Counter: Time interval CH{cfg['start_channel']} -> CH{cfg['stop_channel']}")
        self.logger.info(f"Threshold: {threshold}V (VCC/2), falling edge trigger")
    
    # ========================================================================
    # Current Setting (only thing that changes between measurements)
    # ========================================================================
    
    def _set_currents(self, irefp: float, prog_in: float) -> None:
        """
        Set current levels on IREFP and PROG_IN.
        
        This is the ONLY thing that changes between measurements.
        All other instrument settings remain constant.
        
        Args:
            irefp: IREFP current in Amps
            prog_in: PROG_IN current in Amps
        """
        self.set_terminal_current("IREFP", irefp)
        self.set_terminal_current("PROG_IN", prog_in)
    
    # ========================================================================
    # Measurement Functions
    # ========================================================================
    
    def measure_icellmeas_current(self, label: str = "") -> float:
        """
        Perform spot current measurement on ICELLMEAS.
        
        Args:
            label: Label for logging (e.g., "START" or "FINAL")
            
        Returns:
            Measured current in Amps
        """
        iv = self._get_instrument(InstrumentType.IV5270B)
        cfg = self.get_terminal_config("ICELLMEAS")
        
        # Set measurement mode to spot measurement
        iv.set_measurement_mode(1, [cfg.channel])
        iv.execute_measurement()
        data = iv.read_data()
        
        try:
            # Parse current from response
            current = float(data.split("I")[1].strip())
        except (IndexError, ValueError):
            current = 0.0
            self.logger.warning(f"Could not parse ICELLMEAS current: {data}")
        
        self.logger.info(f"ICELLMEAS {label}: {current} A")
        return current
    
    def trigger_wr_enb(self) -> None:
        """
        Trigger WR_ENB pulse.
        
        WR_ENB goes from VCC to 0V for 1ms, then returns to VCC.
        """
        self.logger.info("Triggering WR_ENB pulse...")
        ppg = self._get_instrument(InstrumentType.PG81104A)
        ppg.trigger()
        
        # Wait for pulse to complete (1ms pulse + margin)
        if not self.test_mode:
            time.sleep(0.002)  # 2ms to ensure pulse completes
    
    def measure_time_interval(self) -> float:
        """
        Read time interval from counter.
        
        Returns:
            Time interval in seconds (WR_ENB low to PROG_OUT low)
        """
        counter = self._get_instrument(InstrumentType.CT53230A)
        cfg = PROGRAMMER_COUNTER_CONFIG["time_interval"]
        
        interval = counter.measure_time_interval(
            start_channel=cfg["start_channel"],
            stop_channel=cfg["stop_channel"],
            record=True
        )
        
        self.logger.info(f"Time interval (pulse width): {interval*1e6:.3f} µs")
        return interval
    
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
            f"programmer_measurements_{timestamp}.csv"
        )
        
        # Open CSV file for writing
        self._csv_file = open(csv_filename, 'w', newline='', encoding='utf-8')
        self._csv_writer = csv.writer(self._csv_file)
        
        # Define CSV headers
        # Current sources: IREFP, PROG_IN
        # Voltage sources: VDD, VCC, PROG_OUT, V_ICELLMEAS
        # Measurements: ICELLMEAS_START, ICELLMEAS_FINAL, PULSE_WIDTH
        headers = [
            "IREFP", "PROG_IN",  # Current sources
            "VDD", "VCC", "PROG_OUT", "V_ICELLMEAS",  # Voltage sources
            "ICELLMEAS_START", "ICELLMEAS_FINAL", "PULSE_WIDTH"  # Measurements
        ]
        
        # Write header row
        self._csv_writer.writerow(headers)
        self._csv_file.flush()
        
        self._csv_initialized = True
        self.logger.info(f"CSV output initialized: {csv_filename}")
    
    def _write_measurement_row(self, irefp: float, prog_in: float,
                               icellmeas_start: float, icellmeas_final: float,
                               pulse_width: float) -> None:
        """
        Write a single measurement row to CSV.
        
        Args:
            irefp: IREFP current value in Amps
            prog_in: PROG_IN current value in Amps
            icellmeas_start: ICELLMEAS current before pulse in Amps
            icellmeas_final: ICELLMEAS current after pulse in Amps
            pulse_width: Pulse width measured by counter in seconds
        """
        if not self._csv_initialized:
            self._initialize_csv_output()
        
        # Calculate voltage values
        prog_out_voltage = self.vcc
        icellmeas_voltage = self.vdd / 2.0
        
        # Build row data
        row = [
            irefp,  # IREFP
            prog_in,  # PROG_IN
            self.vdd,  # VDD
            self.vcc,  # VCC
            prog_out_voltage,  # PROG_OUT
            icellmeas_voltage,  # V_ICELLMEAS
            icellmeas_start,  # ICELLMEAS_START
            icellmeas_final,  # ICELLMEAS_FINAL
            pulse_width,  # PULSE_WIDTH
        ]
        
        self._csv_writer.writerow(row)
        self._csv_file.flush()
    
    def _close_csv_output(self) -> None:
        """Close CSV output file."""
        if self._csv_file:
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None
            self.logger.info("CSV output file closed")
    
    # ========================================================================
    # Main Experiment Execution
    # ========================================================================
    
    def run(self) -> dict:
        """
        Execute the Programmer experiment.
        
        Initialization (once at start):
            1. Reset all instruments (done in startup via context manager)
            2. Configure PPG (WR_ENB at VCC)
            3. Configure voltage sources (PROG_OUT=VCC, ICELLMEAS=VDD/2)
            4. Configure counter for time interval
            5. Enable all SMU channels
        
        Measurement loop (for each IREFP, PROG_IN combination):
            - Set current levels (ONLY thing that changes)
            - Spot measurement on ICELLMEAS (starting)
            - Trigger PPG
            - Read counter for time delay
            - Final spot measurement on ICELLMEAS
            - Record all data
        
        Shutdown (once at end):
            - Disable all instruments (done in shutdown via context manager)
        
        Returns:
            Dictionary containing all measurement results
        """
        self.logger.info("=" * 60)
        self.logger.info("Executing Programmer experiment")
        self.logger.info("=" * 60)
        self.logger.info(f"VDD: {self.vdd}V, VCC: {self.vcc}V")
        self.logger.info(f"IREFP values: {len(self.irefp_values)} points")
        self.logger.info(f"PROG_IN values: {len(self.prog_in_values)} points")
        
        results = {
            "experiment": "Programmer",
            "parameters": {
                "VDD": self.vdd,
                "VCC": self.vcc,
                "ICELLMEAS_VOLTAGE": self.vdd / 2.0,
                "PROG_OUT_VOLTAGE": self.vcc,
            },
            "irefp_values": self.irefp_values.copy(),
            "prog_in_values": self.prog_in_values.copy(),
            "measurements": []
        }
        
        # If no IREFP values set, use single value of 0
        if not self.irefp_values:
            self.irefp_values = [0.0]
            self.logger.warning("No IREFP values set, using [0.0]")
        
        total_measurements = len(self.irefp_values) * len(self.prog_in_values)
        measurement_num = 0
        
        # ====================================================================
        # INITIALIZATION (once at start)
        # ====================================================================
        # Initialize CSV output
        self._initialize_csv_output()
        
        self.initialize_all()
        
        # ====================================================================
        # MEASUREMENT LOOP
        # Only current levels change between measurements
        # ====================================================================
        self.logger.info("=" * 60)
        self.logger.info("BEGINNING MEASUREMENT LOOP")
        self.logger.info("=" * 60)
        
        for irefp in self.irefp_values:
            for prog_in in self.prog_in_values:
                measurement_num += 1
                self.logger.info("-" * 40)
                self.logger.info(f"[{measurement_num}/{total_measurements}] "
                               f"IREFP={irefp*1e9:.1f}nA, PROG_IN={prog_in*1e9:.1f}nA")
                
                # Set current levels (ONLY thing that changes)
                self._set_currents(irefp, prog_in)
                
                # Allow settling time
                if not self.test_mode:
                    time.sleep(0.01)
                
                # Starting ICELLMEAS measurement
                icellmeas_start = self.measure_icellmeas_current("START")
                
                # Trigger PPG
                self.trigger_wr_enb()
                
                # Read counter for time interval
                pulse_width = self.measure_time_interval()
                
                # Final ICELLMEAS measurement
                icellmeas_final = self.measure_icellmeas_current("FINAL")
                
                # Prepare values for CSV (use dummy data in test mode)
                csv_icellmeas_start = icellmeas_start
                csv_icellmeas_final = icellmeas_final
                csv_pulse_width = pulse_width
                
                if self.test_mode:
                    # Use dummy values for CSV measurements, but keep correct current settings
                    csv_icellmeas_start = 1e-12  # Dummy measurement
                    csv_icellmeas_final = 1e-12  # Dummy measurement
                    csv_pulse_width = 1e-6  # Dummy pulse width (1 µs)
                
                # Write to CSV
                self._write_measurement_row(
                    irefp=irefp,
                    prog_in=prog_in,
                    icellmeas_start=csv_icellmeas_start,
                    icellmeas_final=csv_icellmeas_final,
                    pulse_width=csv_pulse_width
                )
                
                # Check for errors after first measurement (first set of conditions)
                if measurement_num == 1:
                    self.logger.info("Checking for errors after first measurement...")
                    errors = self.check_all_instrument_errors()
                    self.report_and_exit_on_errors(errors)
                
                # Record measurement
                measurement = {
                    "IREFP": irefp,
                    "PROG_IN": prog_in,
                    "ICELLMEAS_START": icellmeas_start,
                    "ICELLMEAS_FINAL": icellmeas_final,
                    "PULSE_WIDTH": pulse_width,
                }
                results["measurements"].append(measurement)
                
                self.logger.info(f"Results: Start={icellmeas_start}A, "
                               f"Final={icellmeas_final}A, Width={pulse_width*1e6:.3f}µs")
        
        self.logger.info("=" * 60)
        self.logger.info("MEASUREMENT LOOP COMPLETE")
        self.logger.info(f"Total measurements: {measurement_num}")
        self.logger.info("=" * 60)
        
        # Close CSV output
        self._close_csv_output()
        
        return results
    
    def shutdown(self) -> None:
        """
        Override shutdown to ensure PPG is disabled first and CSV is closed.
        """
        self.logger.info("=" * 60)
        self.logger.info("Shutting down Programmer experiment")
        self.logger.info("=" * 60)
        
        # Close CSV output
        self._close_csv_output()
        
        # Disable PPG output explicitly
        try:
            ppg = self._get_instrument(InstrumentType.PG81104A)
            ppg.idle()
        except Exception as e:
            self.logger.error(f"Failed to idle PPG: {e}")
        
        # Disable series resistor on PROG_OUT
        try:
            iv = self._get_instrument(InstrumentType.IV5270B)
            prog_out_cfg = self.get_terminal_config("PROG_OUT")
            iv.set_series_resistor(prog_out_cfg.channel, False)
        except Exception as e:
            self.logger.error(f"Failed to disable series resistor: {e}")
        
        # Call parent shutdown
        super().shutdown()


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
    
    # Run experiment
    # Settings are loaded from configs/programmer_settings.py
    # Edit that file to change current lists, PPG settings, and timing
    with ProgrammerExperiment(
        test_mode=args.test,
        vdd=args.vdd,
        vcc=args.vcc,
    ) as experiment:
        
        # Load IREFP values from settings file
        experiment.set_irefp_values(SETTINGS.IREFP_VALUES)
        
        # Override PROG_IN values from settings if desired
        experiment.prog_in_values = SETTINGS.PROG_IN_VALUES.copy()
        
        results = experiment.run()
    
    # Print summary
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"Experiment: {results['experiment']}")
    print(f"Parameters: VDD={results['parameters']['VDD']}V, "
          f"VCC={results['parameters']['VCC']}V")
    print(f"ICELLMEAS voltage: {results['parameters']['ICELLMEAS_VOLTAGE']}V")
    print(f"PROG_OUT voltage: {results['parameters']['PROG_OUT_VOLTAGE']}V")
    print(f"Total measurements: {len(results['measurements'])}")
    
    if results['measurements']:
        # Show first and last measurement
        first = results['measurements'][0]
        last = results['measurements'][-1]
        print(f"\nFirst measurement:")
        print(f"  IREFP={first['IREFP']*1e9:.1f}nA, PROG_IN={first['PROG_IN']*1e9:.1f}nA")
        print(f"  Start={first['ICELLMEAS_START']}A, Final={first['ICELLMEAS_FINAL']}A")
        print(f"  Pulse width={first['PULSE_WIDTH']*1e6:.3f}µs")
        
        print(f"\nLast measurement:")
        print(f"  IREFP={last['IREFP']*1e9:.1f}nA, PROG_IN={last['PROG_IN']*1e9:.1f}nA")
        print(f"  Start={last['ICELLMEAS_START']}A, Final={last['ICELLMEAS_FINAL']}A")
        print(f"  Pulse width={last['PULSE_WIDTH']*1e6:.3f}µs")
    
    print("=" * 60)


if __name__ == '__main__':
    main()
