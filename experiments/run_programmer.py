#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Programmer Experiment Execution Script

Top-level execution script for the Programmer experiment.
This script:
- Measures programming timing (PROG_OUT pulse width: falling to rising)
- Uses 5270B for all SMU functions (4156B not used)
- Uses 53230A counter for time interval measurement
- Uses 81104A pulse generator for WR_ENB (not connected to counter)

Usage:
    python -m experiments.run_programmer [--test] [--vdd VDD] [--vcc VCC]
    
    --test: Run in TEST_MODE (log commands without hardware)
    --vdd: VDD voltage (default: 1.8V)
    --vcc: VCC voltage (default: 5.0V)

Configuration:
    Terminal mappings are defined in configs/programmer.py
    Counter threshold is configurable in configs/programmer_settings.py (default: 4V)
    
Terminal Connections:
    PROG_OUT: SMU CH1 with +20µA current source (1.8V compliance) → Counter CH1
    ICELLMEAS: SMU CH2 with VDD/2
    IREFP: SMU CH3 (current list)
    PROG_IN: SMU CH4 (10nA to 100nA in 10nA steps)
    VSS: GNDU
    WR_ENB: PPG CH1 (not connected to counter)

Counter Setup:
    - CH1: Connected to PROG_OUT SMU - measures pulse width (falling to rising edge)
    - CH2: Not connected
    - Threshold: Configurable in settings (default: 4V)
    - Note: PPG (WR_ENB) is not connected to the counter

Experiment Sequence:
    1. Reset all instruments
    2. Turn on PPG (WR_ENB idle at VCC)
    3. Turn on voltage sources and current sources (PROG_OUT=+20µA, ICELLMEAS=VDD/2)
    4. Turn on current sources (IREFP, PROG_IN)
    5. Spot measurement on ICELLMEAS
    6. Trigger PPG (WR_ENB goes to 0V for 500ms)
    7. Read counter for time delay
    8. Final spot measurement on ICELLMEAS
    9. Record: all currents, starting/final ICELLMEAS, pulse width
    10. Disable all instruments

Compliance Settings:
    - Voltage sources: 1mA compliance
    - Current sources: 0.1V compliance for positive currents, 2V for non-positive
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

from experiments.base_experiment import ExperimentRunner, CURRENT_SOURCE_COMPLIANCE
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
    - Applying +20µA current source to PROG_OUT (1.8V compliance)
    - Applying VDD/2 to ICELLMEAS
    - Sweeping PROG_IN from 10nA to 100nA
    - Sweeping IREFP through a list of values
    - Triggering WR_ENB pulse (VCC → 0V for 500ms, 10ns edges)
    - Measuring pulse width on PROG_OUT (falling to rising edge on CH1)
    - Recording ICELLMEAS before and after programming
    
    All currents are "pulled" (positive = into IV meter).
    Positive currents use 0.1V compliance (they get negated when sent to instrument).
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
        
        # CSV output files
        self._csv_file = None
        self._csv_writer = None
        self._csv_file_latest = None
        self._csv_writer_latest = None
        self._csv_initialized = False
    
    def set_irefp_values(self, values: List[float]) -> None:
        """
        Set the IREFP current values to sweep.
        
        Args:
            values: List of current values in Amps
        """
        self.irefp_values = values.copy()
        self.logger.info(f"Set IREFP values: {len(values)} points")
    
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
        
        # Get all used channels from terminal configs
        used_channels = set()
        for terminal_name, terminal_cfg in PROGRAMMER_TERMINALS.items():
            if terminal_cfg.instrument == InstrumentType.IV5270B:
                used_channels.add(terminal_cfg.channel)
        
        # Enable all 5270B channels (1-8) - Channel 0 (GNDU) is automatically enabled
        all_channels = list(range(1, 9))  # Channels 1-8
        iv.enable_channels(all_channels)
        
        # Set unused channels to 0V (connected to GNDU)
        unused_channels = [ch for ch in all_channels if ch not in used_channels]
        for ch in unused_channels:
            iv.set_voltage(ch, 0.0, compliance=0.001)  # 0V with 1mA compliance
            self.logger.debug(f"5270B CH{ch}: Set to 0V (connected to GNDU)")
        
        # Log enabled channels
        channel_info = []
        for ch in sorted(used_channels):
            if ch == 0:
                channel_info.append(f"CH0 (VSS/GNDU)")
            else:
                term_name = next((name for name, cfg in PROGRAMMER_TERMINALS.items() 
                                if cfg.instrument == InstrumentType.IV5270B and cfg.channel == ch), f"CH{ch}")
                channel_info.append(f"CH{ch} ({term_name})")
        for ch in unused_channels:
            channel_info.append(f"CH{ch} (GNDU)")
        self.logger.info(f"5270B: Enabled channels: {', '.join(channel_info)}")
        
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
        
        # Check for errors after initialization (ignore counter errors)
        errors = self.check_all_instrument_errors()
        self.report_and_exit_on_errors_filtered(errors)
    
    def _configure_ppg(self) -> None:
        """
        Configure PPG for WR_ENB (called once during initialization).
        
        WR_ENB starts at VCC (idle high). When triggered, it will:
        - Fall to 0V with 10ns fall time
        - Remain at 0V for 500ms
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
        
        # Set period (must accommodate 500ms pulse width)
        ppg.set_period(cfg["default_period"])
        
        # Configure inverted polarity so idle state is HIGH (VCC)
        # When triggered, output goes LOW (0V)
        ppg.set_polarity(channel, "INV")
        
        # Set voltage levels
        ppg.set_voltage_high(channel, self.vcc)  # VCC when idle (inverted)
        ppg.set_voltage_low(channel, cfg["default_vlow"])  # 0V when pulsing
        
        # Set pulse width (500ms at 0V)
        ppg.set_pulse_width(channel, cfg["default_width"])
        
        # Set rise/fall time (10ns)
        ppg.set_transition(channel, cfg["default_rise"])
        
        # Enable output (but don't trigger yet)
        ppg.enable_output(channel)
        
        self.logger.info(f"WR_ENB: Idle at {self.vcc}V, pulse to 0V for 500ms, 10ns edges")
    
    def _configure_voltage_sources(self, mode: str = "ERASE") -> None:
        """
        Configure voltage sources and current sources (called during initialization and when switching modes).
        
        - PROG_OUT: +20µA current source with 1.8V compliance
        - ICELLMEAS: VDD/2
        - VDD: self.vdd (power supply voltage)
        - VCC: self.vcc (VCC voltage)
        - ERASE_PROG: VCC for ERASE mode, 0V for PROGRAM mode
        
        Args:
            mode: "ERASE" or "PROGRAM" - sets ERASE_PROG voltage accordingly
        """
        self.logger.info("-" * 40)
        self.logger.info(f"Configuring voltage sources (mode={mode})")
        
        # Get 5270B instrument
        iv = self._get_instrument(InstrumentType.IV5270B)
        
        # Configure all other channels first, then PROG_OUT last
        
        # ICELLMEAS: VDD/2
        icellmeas_voltage = self.vdd / 2.0
        self.set_terminal_voltage("ICELLMEAS", icellmeas_voltage)
        self.logger.info(f"ICELLMEAS: {icellmeas_voltage}V (VDD/2)")
        
        # VDD: Power supply voltage
        self.set_terminal_voltage("VDD", self.vdd)
        self.logger.info(f"VDD: {self.vdd}V")
        
        # VCC: VCC voltage
        self.set_terminal_voltage("VCC", self.vcc)
        self.logger.info(f"VCC: {self.vcc}V")
        
        # ERASE_PROG: VCC for ERASE, 0V for PROGRAM
        erase_prog_voltage = self.vcc if mode == "ERASE" else 0.0
        self.set_terminal_voltage("ERASE_PROG", erase_prog_voltage)
        self.logger.info(f"ERASE_PROG: {erase_prog_voltage}V ({mode} mode)")
        
        # PROG_OUT: Configure as current source (set last after all other channels)
        prog_out_cfg = self.get_terminal_config("PROG_OUT")
        # Current source value from settings
        # Note: set_terminal_current() uses set_current() which negates the value,
        # so we pass negative value and it gets negated to positive for the instrument,
        # giving us positive current flowing into the instrument
        prog_out_current = SETTINGS.PROG_OUT_CURRENT
        prog_out_compliance = SETTINGS.PROG_OUT_COMPLIANCE
        # Pass negative value to get positive current (instrument driver negates it)
        self.set_terminal_current("PROG_OUT", -prog_out_current, compliance=prog_out_compliance)
        self.logger.info(f"PROG_OUT: +{prog_out_current*1e6:.1f}µA current source with {prog_out_compliance}V compliance")
    
    def _configure_counter(self) -> None:
        """
        Configure the counter for pulse width measurement (called once during initialization).
        
        Measures pulse width on CH1: PROG_OUT falling edge to rising edge.
        CH2 is not connected.
        """
        self.logger.info("-" * 40)
        self.logger.info("Configuring counter for pulse width measurement")
        
        counter = self._get_instrument(InstrumentType.CT53230A)
        cfg = PROGRAMMER_COUNTER_CONFIG["pulse_width"]
        
        # Get threshold from settings (default: 4V)
        threshold = SETTINGS.COUNTER_CONFIG["threshold"]
        if isinstance(threshold, str) and threshold == "VCC/2":
            threshold = self.vcc / 2.0
        elif not isinstance(threshold, (int, float)):
            threshold = 4.0  # Default fallback
        
        # Configure for pulse width measurement on single channel
        # Use CH1 for both start and stop (pulse width = time from falling to rising)
        channel = cfg["channel"]
        counter.configure_time_interval(
            start_channel=channel,
            stop_channel=channel  # Same channel for pulse width measurement
        )

        # Explicitly set input range based on VCC
        input_range = 50 if self.vcc > 5.01 else 5
        counter.set_input_range(channel, input_range)
        self.logger.info(f"Counter input range set to {input_range}V (VCC={self.vcc}V)")

        # Set input coupling (DC for logic signals) - only CH1
        counter.set_coupling(channel, cfg["coupling"])

        # Set input impedance (1 MOhm) - only CH1
        counter.set_impedance(channel, cfg["impedance"])

        # Set trigger levels for CH1 (start/stop)
        counter.set_trigger_levels(channel, threshold, threshold)

        # For pulse width measurement on a single channel, the 53230A uses:
        # - Start event: falling edge (NEG slope)
        # - Stop event: rising edge (POS slope)
        # When both start and stop are the same channel, the counter automatically
        # measures pulse width. The slope setting may need to be configured separately
        # for start and stop, but for now we set it for the channel.
        # Note: The 53230A requires separate slope commands for start/stop in time interval mode
        counter.set_slopes(channel, cfg["start_slope"], cfg["stop_slope"])
        
        self.logger.info(f"Counter: Pulse width measurement on CH{channel} (PROG_OUT)")
        self.logger.info(f"Trigger level: {threshold}V")
        self.logger.info(f"Measurement: Falling edge to rising edge on CH{channel}")
        self.logger.info(f"CH2: Not connected")
    
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
    
    def report_and_exit_on_errors_filtered(self, errors: Dict[str, List[str]]) -> None:
        """
        Report all errors/warnings and exit if any are found, but ignore counter errors.
        
        Counter errors are logged as warnings but do not cause the experiment to exit.
        This allows the experiment to continue even if the counter reports errors.
        
        Args:
            errors: Dictionary mapping instrument names to lists of error messages
        """
        if not errors:
            return
        
        # Filter out counter errors (create a copy to avoid modifying original)
        counter_errors = errors.get("CT53230A", None)
        filtered_errors = {k: v for k, v in errors.items() if k != "CT53230A" and v}
        
        # Log counter errors as warnings (but don't exit)
        if counter_errors:
            self.logger.warning("=" * 60)
            self.logger.warning("Counter (CT53230A) reported errors/warnings (non-fatal):")
            for i, error_msg in enumerate(counter_errors, 1):
                self.logger.warning(f"  - Warning {i}: {error_msg}")
            self.logger.warning("Continuing experiment despite counter errors...")
            self.logger.warning("=" * 60)
        
        # Report and exit on non-counter errors (if any)
        if filtered_errors:
            super().report_and_exit_on_errors(filtered_errors)
    
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
    
    def measure_irefp_voltage(self) -> float:
        """
        Perform spot voltage measurement on IREFP.
        
        Returns:
            Measured voltage in Volts
        """
        iv = self._get_instrument(InstrumentType.IV5270B)
        cfg = self.get_terminal_config("IREFP")
        
        # Set measurement mode to spot measurement
        iv.set_measurement_mode(1, [cfg.channel])
        iv.execute_measurement()
        data = iv.read_data()
        
        try:
            # Parse voltage from response
            voltage = float(data.split("V")[1].split(",")[0].strip())
        except (IndexError, ValueError):
            voltage = 0.0
            self.logger.warning(f"Could not parse IREFP voltage: {data}")
        
        self.logger.info(f"VREFP: {voltage} V")
        return voltage
    
    def trigger_wr_enb(self) -> None:
        """
        Trigger WR_ENB pulse.
        
        WR_ENB goes from VCC to 0V for 10ms, then returns to VCC.
        """
        self.logger.info("Triggering WR_ENB pulse...")
        ppg = self._get_instrument(InstrumentType.PG81104A)
        ppg.trigger()
        
        # Wait for pulse to complete (10ms pulse + margin)
        if not self.test_mode:
            time.sleep(0.012)  # 12ms to ensure 10ms pulse completes
    
    def initiate_time_interval(self) -> None:
        """
        Initiate pulse width measurement on the counter.
        
        This should be called BEFORE triggering WR_ENB.
        Counter will wait for PROG_OUT falling edge (start of pulse width measurement).
        """
        counter = self._get_instrument(InstrumentType.CT53230A)
        counter.initiate()
        self.logger.info("Counter measurement initiated (waiting for PROG_OUT falling edge on CH1)")
    
    def fetch_time_interval(self) -> float:
        """
        Fetch pulse width measurement from counter.
        
        This should be called AFTER triggering WR_ENB.
        Returns the measured pulse width: PROG_OUT falling to rising edge on CH1.
        
        Returns:
            Pulse width in seconds (PROG_OUT falling to rising edge)
        """
        counter = self._get_instrument(InstrumentType.CT53230A)
        pulse_width = counter.fetch()
        
        self.logger.info(f"PROG_OUT pulse width (CH1): {pulse_width*1e6:.3f} µs")
        return pulse_width
    
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
            f"prog_{timestamp}.csv"
        )
        
        # Generate CSV filename without timestamp (overwrites each run)
        csv_filename_latest = os.path.join(
            measurements_dir,
            "prog.csv"
        )
        
        # Open CSV files for writing
        self._csv_file = open(csv_filename, 'w', newline='', encoding='utf-8')
        self._csv_writer = csv.writer(self._csv_file)
        
        self._csv_file_latest = open(csv_filename_latest, 'w', newline='', encoding='utf-8')
        self._csv_writer_latest = csv.writer(self._csv_file_latest)
        
        # Define CSV headers
        # Mode: ERASE or PROGRAM
        # Current sources: IREFP, PROG_IN
        # Current sources: IREFP, PROG_IN, PROG_OUT
        # Voltage sources: VDD, VCC, V_ICELLMEAS, ERASE_PROG
        # Measurements: VREFP, ICELLMEAS_START, ICELLMEAS_FINAL, PULSE_WIDTH
        headers = [
            "MODE",  # ERASE or PROGRAM
            "IREFP", "PROG_IN", "PROG_OUT",  # Current sources
            "VDD", "VCC", "V_ICELLMEAS", "ERASE_PROG",  # Voltage sources
            "VREFP", "ICELLMEAS_START", "ICELLMEAS_FINAL", "PULSE_WIDTH"  # Measurements
        ]
        
        # Write header row
        self._csv_writer.writerow(headers)
        self._csv_file.flush()
        
        self._csv_initialized = True
        self.logger.info(f"CSV output initialized: {csv_filename}")
    
    def _write_measurement_row(self, mode: str, irefp: float, prog_in: float,
                               vrefp: float, icellmeas_start: float, icellmeas_final: float,
                               pulse_width: float) -> None:
        """
        Write a single measurement row to CSV.
        
        Args:
            mode: "ERASE" or "PROGRAM"
            irefp: IREFP current value in Amps
            prog_in: PROG_IN current value in Amps
            vrefp: IREFP voltage measurement in Volts
            icellmeas_start: ICELLMEAS current before pulse in Amps
            icellmeas_final: ICELLMEAS current after pulse in Amps
            pulse_width: Pulse width measured by counter in seconds
        """
        if not self._csv_initialized:
            self._initialize_csv_output()
        
        # Calculate voltage values
        prog_out_current = SETTINGS.PROG_OUT_CURRENT  # Current source value from settings
        icellmeas_voltage = self.vdd / 2.0
        erase_prog_voltage = self.vcc if mode == "ERASE" else 0.0
        
        # Build row data
        row = [
            mode,  # MODE
            irefp,  # IREFP
            prog_in,  # PROG_IN
            prog_out_current,  # PROG_OUT (current in Amps)
            self.vdd,  # VDD
            self.vcc,  # VCC
            icellmeas_voltage,  # V_ICELLMEAS
            erase_prog_voltage,  # ERASE_PROG
            vrefp,  # VREFP
            icellmeas_start,  # ICELLMEAS_START
            icellmeas_final,  # ICELLMEAS_FINAL
            pulse_width,  # PULSE_WIDTH
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
        Execute the Programmer experiment.
        
        Initialization (once at start):
            1. Reset all instruments (done in startup via context manager)
            2. Configure PPG (WR_ENB at VCC)
            3. Configure voltage sources and current sources (PROG_OUT=+20µA, ICELLMEAS=VDD/2)
            4. Configure counter for time interval
            5. Enable all SMU channels
        
        Measurement loop (for each IREFP, PROG_IN combination):
            - Set current levels (ONLY thing that changes)
            - Spot measurement on ICELLMEAS (starting)
            - Trigger PPG
            - Read counter for PROG_OUT pulse width
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
                "PROG_OUT_CURRENT": SETTINGS.PROG_OUT_CURRENT,
                "PROG_OUT_COMPLIANCE": SETTINGS.PROG_OUT_COMPLIANCE,
            },
            "irefp_values": self.irefp_values.copy(),
            "prog_in_values": self.prog_in_values.copy(),
            "measurements": []
        }
        
        # If no IREFP values set, use single value of 0
        if not self.irefp_values:
            self.irefp_values = [0.0]
            self.logger.warning("No IREFP values set, using [0.0]")
        
        # Total measurements = 2 modes * IREFP values * PROG_IN values
        total_measurements = 2 * len(self.irefp_values) * len(self.prog_in_values)
        measurement_num = 0
        
        # ====================================================================
        # INITIALIZATION (once at start)
        # ====================================================================
        # Initialize CSV output
        self._initialize_csv_output()
        
        self.initialize_all()
        
        # ====================================================================
        # MEASUREMENT LOOP
        # Run for both ERASE and PROGRAM modes
        # Only current levels and ERASE_PROG voltage change between measurements
        # ====================================================================
        self.logger.info("=" * 60)
        self.logger.info("BEGINNING MEASUREMENT LOOP")
        self.logger.info("=" * 60)
        
        for mode in ["ERASE", "PROGRAM"]:
            self.logger.info("=" * 60)
            self.logger.info(f"MODE: {mode}")
            self.logger.info("=" * 60)
            
            # Set ERASE_PROG voltage for current mode
            erase_prog_voltage = self.vcc if mode == "ERASE" else 0.0
            self.set_terminal_voltage("ERASE_PROG", erase_prog_voltage)
            self.logger.info(f"ERASE_PROG set to {erase_prog_voltage}V ({mode} mode)")
            
            for irefp in self.irefp_values:
                # Set IREFP current level
                self.set_terminal_current("IREFP", irefp)
                
                # Allow settling time for IREFP
                if not self.test_mode:
                    time.sleep(0.01)
                
                # Measure VREFP (only when IREFP changes)
                vrefp = self.measure_irefp_voltage()
                
                # Check VREFP is within safe range (0.5V to 1.5V)
                if not self.test_mode:
                    if vrefp < 0.5 or vrefp > 1.5:
                        self.logger.warning(f"WARNING: VREFP out of safe range: {vrefp}V (expected 0.5V to 1.5V)")
                        self.logger.warning(f"IREFP setting: {irefp*1e9:.1f}nA")
                
                for prog_in in self.prog_in_values:
                    measurement_num += 1
                    self.logger.info("-" * 40)
                    self.logger.info(f"[{measurement_num}/{total_measurements}] {mode}: "
                                   f"IREFP={irefp*1e9:.1f}nA, PROG_IN={prog_in*1e9:.1f}nA")
                    
                    # Set PROG_IN current level
                    self.set_terminal_current("PROG_IN", prog_in)
                    
                    # Allow settling time for PROG_IN
                    if not self.test_mode:
                        time.sleep(0.01)
                    
                    # Ensure ERASE_PROG is LOW before ICELLMEAS measurement in ERASE mode
                    if mode == "ERASE":
                        self.set_terminal_voltage("ERASE_PROG", 0.0)
                        self.logger.info("ERASE_PROG set to 0V before ICELLMEAS START measurement (ERASE mode)")
                    # Starting ICELLMEAS measurement
                    icellmeas_start = self.measure_icellmeas_current("START")
                    # Restore ERASE_PROG to VCC after ICELLMEAS measurement in ERASE mode
                    if mode == "ERASE":
                        self.set_terminal_voltage("ERASE_PROG", self.vcc)
                        self.logger.info(f"ERASE_PROG restored to {self.vcc}V after ICELLMEAS START measurement (ERASE mode)")

                    # Initiate counter measurement (arms counter to wait for trigger)
                    self.initiate_time_interval()
                    
                    # Trigger PPG
                    self.trigger_wr_enb()
                    
                    # Fetch counter measurement result
                    pulse_width = self.fetch_time_interval()

                    # Ensure ERASE_PROG is LOW before ICELLMEAS measurement in ERASE mode
                    if mode == "ERASE":
                        self.set_terminal_voltage("ERASE_PROG", 0.0)
                        self.logger.info("ERASE_PROG set to 0V before ICELLMEAS FINAL measurement (ERASE mode)")
                    # Final ICELLMEAS measurement
                    icellmeas_final = self.measure_icellmeas_current("FINAL")
                    # Restore ERASE_PROG to VCC after ICELLMEAS measurement in ERASE mode
                    if mode == "ERASE":
                        self.set_terminal_voltage("ERASE_PROG", self.vcc)
                        self.logger.info(f"ERASE_PROG restored to {self.vcc}V after ICELLMEAS FINAL measurement (ERASE mode)")
                    
                    # Prepare values for CSV (use dummy data in test mode)
                    csv_vrefp = vrefp
                    csv_icellmeas_start = icellmeas_start
                    csv_icellmeas_final = icellmeas_final
                    csv_pulse_width = pulse_width
                    
                    if self.test_mode:
                        # Use dummy values for CSV measurements, but keep correct current settings
                        csv_vrefp = 1.0  # Dummy voltage
                        csv_icellmeas_start = 1e-12  # Dummy measurement
                        csv_icellmeas_final = 1e-12  # Dummy measurement
                        csv_pulse_width = 1e-6  # Dummy pulse width (1 µs)
                    
                    # Write to CSV
                    self._write_measurement_row(
                        mode=mode,
                        irefp=irefp,
                        prog_in=prog_in,
                        vrefp=csv_vrefp,
                        icellmeas_start=csv_icellmeas_start,
                        icellmeas_final=csv_icellmeas_final,
                        pulse_width=csv_pulse_width
                    )
                    
                    # Check for errors after first measurement (first set of conditions)
                    # Ignore counter errors (they don't cause exit)
                    if measurement_num == 1:
                        self.logger.info("Checking for errors after first measurement...")
                        errors = self.check_all_instrument_errors()
                        self.report_and_exit_on_errors_filtered(errors)
                    
                    # Record measurement
                    measurement = {
                        "MODE": mode,
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
    print(f"PROG_OUT current: {results['parameters']['PROG_OUT_CURRENT']*1e6:.1f}µA")
    print(f"Total measurements: {len(results['measurements'])}")
    
    if results['measurements']:
        # Show first and last measurement
        first = results['measurements'][0]
        last = results['measurements'][-1]
        print(f"\nFirst measurement ({first['MODE']} mode):")
        print(f"  IREFP={first['IREFP']*1e9:.1f}nA, PROG_IN={first['PROG_IN']*1e9:.1f}nA")
        print(f"  Start={first['ICELLMEAS_START']}A, Final={first['ICELLMEAS_FINAL']}A")
        print(f"  Pulse width={first['PULSE_WIDTH']*1e6:.3f}µs")
        
        print(f"\nLast measurement ({last['MODE']} mode):")
        print(f"  IREFP={last['IREFP']*1e9:.1f}nA, PROG_IN={last['PROG_IN']*1e9:.1f}nA")
        print(f"  Start={last['ICELLMEAS_START']}A, Final={last['ICELLMEAS_FINAL']}A")
        print(f"  Pulse width={last['PULSE_WIDTH']*1e6:.3f}µs")
    
    print("=" * 60)


if __name__ == '__main__':
    main()
