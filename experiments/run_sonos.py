#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sonos Experiment Execution Script

No counter; only ICELLMEAS before/after. cell_init sets ICELLMEAS to a target
current (prog_in=0, WR_ENB pulse width from mapping, max 100ms). Two test types:
PROG_IDEAL (list of WR_ENB times) and PROG_ACTUAL (constant WR_ENB, list of PROG_IN).
Erase mode increases ICELLMEAS, program mode decreases it.
All ICELLMEAS measurements are taken in program mode; circuit is then restored
to erase or program mode as appropriate.

Usage:
    python -m experiments.run_sonos [--test] [--vdd VDD] [--vcc VCC] [--ideal | --actual]

Configuration:
    configs/sonos.py, configs/sonos_settings.py
"""

import sys
import os
import argparse
import logging
import time
import csv
from datetime import datetime
from typing import Dict, List, Any, Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.base_experiment import ExperimentRunner, CURRENT_SOURCE_COMPLIANCE
from configs.sonos import (
    SONOS_CONFIG,
    SONOS_TERMINALS,
    SONOS_PULSE_CONFIG,
    SONOS_DEFAULTS,
)
from configs.resource_types import InstrumentType
from configs import sonos_settings as SETTINGS


def seconds_to_ppg_width(seconds: float) -> str:
    """
    Convert pulse time in seconds to PPG width string (e.g. "100MS", "50MS").
    Capped at 100 ms in caller; supports MS and US.
    """
    if seconds <= 0:
        return "1US"
    if seconds >= 1:
        return "1S"
    if seconds >= 0.001:  # >= 1 ms
        ms = round(seconds * 1000)
        return f"{max(1, ms)}MS"
    us = round(seconds * 1e6)
    return f"{max(1, us)}US"


class SonosExperiment(ExperimentRunner):
    """
    Sonos experiment: cell_init, PROG_IDEAL, PROG_ACTUAL.
    No counter; only ICELLMEAS. Erase increases ICELLMEAS, program decreases it.
    """

    def __init__(
        self,
        test_mode: bool = False,
        vdd: float = None,
        vcc: float = None,
        mapping: Optional[Callable[[float, float], float]] = None,
    ):
        super().__init__(SONOS_CONFIG, test_mode)
        self.vdd = vdd if vdd is not None else SONOS_DEFAULTS["VDD"]
        self.vcc = vcc if vcc is not None else SONOS_DEFAULTS["VCC"]
        self._mapping = mapping or SETTINGS.cell_init_pulse_time
        self._max_pulse_sec = SETTINGS.WR_ENB_MAX_PULSE_SEC
        self._target_error = SETTINGS.TARGET_ERROR
        self._imax = SETTINGS.IMAX
        self._imin = SETTINGS.IMIN
        self._current_mode: str = "ERASE"  # "ERASE" or "PROGRAM"
        self._csv_file = None
        self._csv_writer = None
        self._csv_file_latest = None
        self._csv_writer_latest = None
        self._csv_initialized = False

    def set_terminal_current(self, terminal: str, current: float,
                            compliance: float = None) -> None:
        if compliance is None:
            compliance = 0.1 if current > 0 else CURRENT_SOURCE_COMPLIANCE
        super().set_terminal_current(terminal, current, compliance)

    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------

    def initialize_all(self) -> None:
        """Configure PPG and voltage/current sources once. No counter."""
        self.logger.info("=" * 60)
        self.logger.info("INITIALIZING SONOS (no counter)")
        self.logger.info("=" * 60)

        iv = self._get_instrument(InstrumentType.IV5270B)
        used_channels = {cfg.channel for name, cfg in SONOS_TERMINALS.items()
                        if cfg.instrument == InstrumentType.IV5270B and cfg.channel > 0}
        all_channels = list(range(1, 9))
        iv.enable_channels(all_channels)
        unused = [ch for ch in all_channels if ch not in used_channels]
        for ch in unused:
            iv.set_voltage(ch, 0.0, compliance=0.001)
        self._configure_ppg()
        self._configure_voltage_sources("PROGRAM")  # Start in program for cell_init if needed
        self.set_terminal_current("PROG_IN", 0.0)
        self.set_terminal_current("IREFP", 0.0)
        self.logger.info("=" * 60)
        self.logger.info("INITIALIZATION COMPLETE")
        self.logger.info("=" * 60)

    def _configure_ppg(self) -> None:
        """PPG for WR_ENB: idle at VCC; pulse width set dynamically per trigger."""
        self.logger.info("-" * 40)
        self.logger.info("Configuring PPG (WR_ENB at VCC)")
        ppg = self._get_instrument(InstrumentType.PG81104A)
        cfg = SONOS_PULSE_CONFIG["WR_ENB"]
        ch = SONOS_TERMINALS["WR_ENB"].channel
        ppg.set_arm_source("MAN")
        ppg.set_pattern_mode(False)
        ppg.set_trigger_count(1)
        ppg.set_trigger_source("IMM")
        ppg.set_period(cfg["default_period"])
        ppg.set_polarity(ch, "INV")
        ppg.set_voltage_high(ch, self.vcc)
        ppg.set_voltage_low(ch, cfg["default_vlow"])
        ppg.set_pulse_width(ch, cfg["default_width"])
        ppg.set_transition(ch, cfg["default_rise"])
        ppg.enable_output(ch)
        self.logger.info(f"WR_ENB: Idle {self.vcc}V, pulse to 0V (width set per trigger)")

    def _configure_voltage_sources(self, mode: str = "ERASE") -> None:
        """Set ICELLMEAS=VDD/2, VDD, VCC, ERASE_PROG; PROG_OUT as current source."""
        self.logger.info("-" * 40)
        self.logger.info(f"Configuring voltage sources (mode={mode})")
        icellmeas_v = self.vdd / 2.0
        self.set_terminal_voltage("ICELLMEAS", icellmeas_v)
        self.set_terminal_voltage("VDD", self.vdd)
        self.set_terminal_voltage("VCC", self.vcc)
        erase_prog_v = self.vcc if mode == "ERASE" else 0.0
        self.set_terminal_voltage("ERASE_PROG", erase_prog_v)
        self.logger.info(f"ERASE_PROG: {erase_prog_v}V ({mode})")
        prog_out_i = getattr(SETTINGS, "PROG_OUT_CURRENT", 10e-6)
        prog_out_comp = getattr(SETTINGS, "PROG_OUT_COMPLIANCE", self.vcc)
        self.set_terminal_current("PROG_OUT", -prog_out_i, compliance=prog_out_comp)
        self._current_mode = mode

    def set_mode_erase(self) -> None:
        """Set ERASE_PROG to VCC (erase mode). Erase increases ICELLMEAS."""
        self.set_terminal_voltage("ERASE_PROG", self.vcc)
        self._current_mode = "ERASE"
        self.logger.info("Mode set to ERASE")

    def set_mode_program(self) -> None:
        """Set ERASE_PROG to 0V (program mode). Program decreases ICELLMEAS."""
        self.set_terminal_voltage("ERASE_PROG", 0.0)
        self._current_mode = "PROGRAM"
        self.logger.info("Mode set to PROGRAM")

    # -------------------------------------------------------------------------
    # ICELLMEAS measurement (always in program mode; restore mode after)
    # -------------------------------------------------------------------------

    def measure_icellmeas_in_program_mode(self, label: str = "") -> float:
        """
        Measure ICELLMEAS in program mode, then restore previous mode.
        Returns current in Amps.
        """
        prev = self._current_mode
        self.set_mode_program()
        if not self.test_mode:
            time.sleep(SETTINGS.SETTLING_TIME)
        ic = self._measure_icellmeas_current(label)
        if prev == "ERASE":
            self.set_mode_erase()
        return ic

    def _measure_icellmeas_current(self, label: str = "") -> float:
        """Raw spot current measurement on ICELLMEAS (assumes mode already set)."""
        iv = self._get_instrument(InstrumentType.IV5270B)
        cfg = self.get_terminal_config("ICELLMEAS")
        iv.set_measurement_mode(1, [cfg.channel])
        iv.execute_measurement()
        data = iv.read_data()
        try:
            current = float(data.split("I")[1].strip())
        except (IndexError, ValueError):
            current = 0.0
            self.logger.warning(f"Could not parse ICELLMEAS: {data}")
        self.logger.info(f"ICELLMEAS {label}: {current} A")
        return current

    # -------------------------------------------------------------------------
    # WR_ENB pulse (variable width)
    # -------------------------------------------------------------------------

    def trigger_wr_enb(self, pulse_width_seconds: float) -> None:
        """
        Set WR_ENB pulse width (capped at 100 ms) and trigger.
        pulse_width_seconds is capped at WR_ENB_MAX_PULSE_SEC.
        """
        width_sec = min(max(0.0, pulse_width_seconds), self._max_pulse_sec)
        width_str = seconds_to_ppg_width(width_sec)
        ppg = self._get_instrument(InstrumentType.PG81104A)
        ch = SONOS_TERMINALS["WR_ENB"].channel
        ppg.set_pulse_width(ch, width_str)
        ppg.trigger()
        if not self.test_mode:
            time.sleep(width_sec + SETTINGS.POST_PULSE_DELAY)

    # -------------------------------------------------------------------------
    # cell_init: set ICELLMEAS to target within TARGET_ERROR (prog_in=0, WR_ENB)
    # -------------------------------------------------------------------------

    def cell_init(self, target_current: float, target_error: float = None) -> None:
        """
        Set PROG_IN=0, use program mode, and pulse WR_ENB (width from mapping)
        until |ICELLMEAS - target_current| <= target_error.
        Pulse width from mapping(icellmeas_measured, target_current), capped at 100 ms.
        """
        if target_error is None:
            target_error = self._target_error
        self.set_terminal_current("PROG_IN", 0.0)
        self.set_mode_program()
        if not self.test_mode:
            time.sleep(SETTINGS.SETTLING_TIME)
        max_iter = getattr(SETTINGS, "CELL_INIT_MAX_ITERATIONS", 200)
        for iteration in range(max_iter):
            ic = self._measure_icellmeas_current(f"cell_init iter {iteration+1}")
            err = abs(ic - target_current)
            if err <= target_error:
                self.logger.info(f"cell_init converged to {target_current} A (error {err})")
                return
            pulse_sec = self._mapping(ic, target_current)
            pulse_sec = min(pulse_sec, self._max_pulse_sec)
            if pulse_sec <= 0:
                self.logger.warning("cell_init mapping returned 0; stopping")
                return
            self.trigger_wr_enb(pulse_sec)
        self.logger.warning(f"cell_init did not converge within {max_iter} iterations")

    # -------------------------------------------------------------------------
    # CSV
    # -------------------------------------------------------------------------

    def _initialize_csv_output(self, test_type: str) -> None:
        if self._csv_initialized:
            return
        measurements_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "measurements"
        )
        os.makedirs(measurements_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = os.path.join(measurements_dir, f"sonos_{test_type}_{timestamp}.csv")
        csv_latest = os.path.join(measurements_dir, "sonos.csv")
        self._csv_file = open(csv_filename, "w", newline="", encoding="utf-8")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_file_latest = open(csv_latest, "w", newline="", encoding="utf-8")
        self._csv_writer_latest = csv.writer(self._csv_file_latest)
        headers = [
            "TEST_TYPE", "PHASE", "STEP", "PARAM", "ICELLMEAS_BEFORE", "ICELLMEAS_AFTER"
        ]
        self._csv_writer.writerow(headers)
        self._csv_file.flush()
        self._csv_writer_latest.writerow(headers)
        self._csv_file_latest.flush()
        self._csv_initialized = True
        self.logger.info(f"CSV: {csv_filename}")

    def _write_row(self, test_type: str, phase: str, step: int, param: str,
                   ic_before: float, ic_after: float) -> None:
        if not self._csv_initialized:
            self._initialize_csv_output(test_type)
        # In test mode use dummy values so CSV structure is valid (same as run_programmer)
        if self.test_mode:
            ic_before, ic_after = 1e-12, 1e-12
        row = [test_type, phase, step, param, ic_before, ic_after]
        self._csv_writer.writerow(row)
        self._csv_file.flush()
        self._csv_writer_latest.writerow(row)
        self._csv_file_latest.flush()

    def _close_csv_output(self) -> None:
        if self._csv_file:
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None
        if self._csv_file_latest:
            self._csv_file_latest.close()
            self._csv_file_latest = None
            self._csv_writer_latest = None
        self._csv_initialized = False

    # -------------------------------------------------------------------------
    # Test execution: PROG_IDEAL and PROG_ACTUAL
    # -------------------------------------------------------------------------

    def run_prog_ideal(self) -> dict:
        """
        PROG_IDEAL: PROG_IN=0. cell_init(IMAX), program mode, steps with list of
        WR_ENB times until ICELLMEAS <= IMIN. Then cell_init(IMIN), erase mode,
        steps with same list until ICELLMEAS >= IMAX or stopped.
        """
        self._initialize_csv_output("PROG_IDEAL")
        times_sec = list(SETTINGS.PROG_IDEAL_WR_ENB_TIMES_SEC)
        results = {"test_type": "PROG_IDEAL", "phases": [], "measurements": []}

        # Phase 1: program from IMAX down to IMIN
        self.logger.info("=" * 60)
        self.logger.info("PROG_IDEAL Phase 1: cell_init(IMAX) -> program steps -> IMIN")
        self.cell_init(self._imax, self._target_error)
        self.set_mode_program()
        step = 0
        for t_sec in times_sec:
            t_sec = min(t_sec, self._max_pulse_sec)
            ic_before = self.measure_icellmeas_in_program_mode("before")
            self.set_mode_program()
            if not self.test_mode:
                time.sleep(SETTINGS.SETTLING_TIME)
            self.trigger_wr_enb(t_sec)
            ic_after = self.measure_icellmeas_in_program_mode("after")
            self.set_mode_program()
            step += 1
            self._write_row("PROG_IDEAL", "PROGRAM", step, f"WR_ENB={t_sec}s", ic_before, ic_after)
            results["measurements"].append({
                "phase": "PROGRAM", "step": step, "param": t_sec,
                "ICELLMEAS_BEFORE": ic_before, "ICELLMEAS_AFTER": ic_after,
            })
            if ic_after <= self._imin:
                self.logger.info(f"Reached IMIN at step {step}")
                break
        results["phases"].append("PROGRAM")

        # Phase 2: erase from IMIN up to IMAX
        self.logger.info("=" * 60)
        self.logger.info("PROG_IDEAL Phase 2: cell_init(IMIN) -> erase steps -> IMAX")
        self.cell_init(self._imin, self._target_error)
        self.set_mode_erase()
        for t_sec in times_sec:
            t_sec = min(t_sec, self._max_pulse_sec)
            ic_before = self.measure_icellmeas_in_program_mode("before")
            self.set_mode_erase()
            if not self.test_mode:
                time.sleep(SETTINGS.SETTLING_TIME)
            self.trigger_wr_enb(t_sec)
            ic_after = self.measure_icellmeas_in_program_mode("after")
            self.set_mode_erase()
            step += 1
            self._write_row("PROG_IDEAL", "ERASE", step, f"WR_ENB={t_sec}s", ic_before, ic_after)
            results["measurements"].append({
                "phase": "ERASE", "step": step, "param": t_sec,
                "ICELLMEAS_BEFORE": ic_before, "ICELLMEAS_AFTER": ic_after,
            })
            if ic_after >= self._imax:
                self.logger.info(f"Reached IMAX at step {step}")
                break
        results["phases"].append("ERASE")
        return results

    def run_prog_actual(self) -> dict:
        """
        PROG_ACTUAL: WR_ENB constant (e.g. 100 ms). cell_init(IMAX), program mode,
        steps with list of PROG_IN until ICELLMEAS <= IMIN. Then cell_init(IMIN),
        erase mode, steps until IMAX or stopped (same constant WR_ENB).
        """
        self._initialize_csv_output("PROG_ACTUAL")
        prog_in_list = list(SETTINGS.PROG_ACTUAL_PROG_IN_LIST)
        wr_enb_sec = SETTINGS.PROG_ACTUAL_WR_ENB_MS / 1000.0
        wr_enb_sec = min(wr_enb_sec, self._max_pulse_sec)
        results = {"test_type": "PROG_ACTUAL", "phases": [], "measurements": []}

        # Phase 1: program
        self.logger.info("=" * 60)
        self.logger.info("PROG_ACTUAL Phase 1: cell_init(IMAX) -> program steps -> IMIN")
        self.cell_init(self._imax, self._target_error)
        self.set_mode_program()
        step = 0
        for prog_in in prog_in_list:
            self.set_terminal_current("PROG_IN", prog_in)
            if not self.test_mode:
                time.sleep(SETTINGS.SETTLING_TIME)
            ic_before = self.measure_icellmeas_in_program_mode("before")
            self.set_mode_program()
            if not self.test_mode:
                time.sleep(SETTINGS.SETTLING_TIME)
            self.trigger_wr_enb(wr_enb_sec)
            ic_after = self.measure_icellmeas_in_program_mode("after")
            self.set_mode_program()
            step += 1
            self._write_row("PROG_ACTUAL", "PROGRAM", step, f"PROG_IN={prog_in}A", ic_before, ic_after)
            results["measurements"].append({
                "phase": "PROGRAM", "step": step, "param": prog_in,
                "ICELLMEAS_BEFORE": ic_before, "ICELLMEAS_AFTER": ic_after,
            })
            if ic_after <= self._imin:
                self.logger.info(f"Reached IMIN at step {step}")
                break
        results["phases"].append("PROGRAM")

        # Phase 2: erase (constant WR_ENB, PROG_IN=0 for erase steps)
        self.logger.info("=" * 60)
        self.logger.info("PROG_ACTUAL Phase 2: cell_init(IMIN) -> erase steps -> IMAX")
        self.cell_init(self._imin, self._target_error)
        self.set_terminal_current("PROG_IN", 0.0)
        self.set_mode_erase()
        step = 0
        while True:
            ic_before = self.measure_icellmeas_in_program_mode("before")
            self.set_mode_erase()
            if not self.test_mode:
                time.sleep(SETTINGS.SETTLING_TIME)
            self.trigger_wr_enb(wr_enb_sec)
            ic_after = self.measure_icellmeas_in_program_mode("after")
            self.set_mode_erase()
            step += 1
            self._write_row("PROG_ACTUAL", "ERASE", step, "WR_ENB_const", ic_before, ic_after)
            results["measurements"].append({
                "phase": "ERASE", "step": step, "param": wr_enb_sec,
                "ICELLMEAS_BEFORE": ic_before, "ICELLMEAS_AFTER": ic_after,
            })
            if ic_after >= self._imax:
                self.logger.info(f"Reached IMAX at step {step}")
                break
            if step >= 500:  # Safety
                self.logger.warning("Erase phase step limit reached")
                break
        results["phases"].append("ERASE")
        return results

    def run(self, test_type: str = "PROG_IDEAL") -> dict:
        """Run either PROG_IDEAL or PROG_ACTUAL."""
        self.logger.info("=" * 60)
        self.logger.info(f"Sonos experiment: {test_type}")
        self.logger.info("=" * 60)
        self.initialize_all()
        if test_type.upper() == "PROG_ACTUAL":
            return self.run_prog_actual()
        return self.run_prog_ideal()

    def shutdown(self) -> None:
        self._close_csv_output()
        try:
            ppg = self._get_instrument(InstrumentType.PG81104A)
            ppg.idle()
        except Exception as e:
            self.logger.error(f"PPG idle: {e}")
        super().shutdown()


def main():
    parser = argparse.ArgumentParser(description="Run Sonos Experiment")
    parser.add_argument("--test", "-t", action="store_true", help="Test mode (no hardware)")
    parser.add_argument("--vdd", type=float, default=SETTINGS.VDD, help="VDD (V)")
    parser.add_argument("--vcc", type=float, default=SETTINGS.VCC, help="VCC (V)")
    parser.add_argument("--ideal", action="store_true", help="Run PROG_IDEAL (default)")
    parser.add_argument("--actual", action="store_true", help="Run PROG_ACTUAL")
    args = parser.parse_args()
    test_type = "PROG_ACTUAL" if args.actual else "PROG_IDEAL"

    with SonosExperiment(test_mode=args.test, vdd=args.vdd, vcc=args.vcc) as expt:
        results = expt.run(test_type=test_type)

    print("\n" + "=" * 60)
    print("SONOS SUMMARY")
    print("=" * 60)
    print(f"Test: {results.get('test_type', test_type)}")
    print(f"Measurements: {len(results.get('measurements', []))}")
    print("=" * 60)


if __name__ == "__main__":
    main()
