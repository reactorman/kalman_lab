#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Kalman-Style Closed-Loop Experiment
===================================

This experiment is a sibling of `run_compute.py` that:
- Uses the same terminal configuration (`COMPUTE_CONFIG`) and instruments.
- Separates TRIM into TRIM1 and TRIM2, and KGAIN into KGAIN1 and KGAIN2.
- Measures both OUT1 and OUT2 currents at each step.
- Generates an IMEAS test vector starting from an initial IMEAS value.
- Runs a closed-loop update of X1 and X2 using ERASE/PROGRAM PPG states.

Update equations:
    IERR1 = TRIM1 / OUT1
    IERR2 = TRIM2 / OUT2

    ERASE step:
        X1_new = X1_old * (1 + IERR1)
        X2_new = X2_old * (1 + IERR2)

    PROGRAM step:
        X1_new = X1_old * (1 - IERR1)
        X2_new = X2_old * (1 - IERR2)

Bounds:
    X1, X2, IMEAS are bounded to [0.1 nA, 100 nA].
    The IMEAS test vector is generated on startup and validated; the program
    terminates immediately if any IMEAS value is outside this bound.

Usage:
    python -m experiments.run_kalman [--test] [--vdd VDD] [--vcc VCC]
"""

import sys
import os
import argparse
import logging
import math
import random
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.run_compute import ComputeExperiment  # Reuse hardware setup helpers
from configs.compute import COMPUTE_CONFIG
from configs import kalman_settings as SETTINGS
from configs.resource_types import InstrumentType


class KalmanExperiment(ComputeExperiment):
    """
    Kalman-style experiment that reuses the Compute hardware configuration
    but implements a custom IMEAS-driven ERASE/PROGRAM loop.
    """

    def __init__(self, test_mode: bool = False,
                 vdd: Optional[float] = None,
                 vcc: Optional[float] = None) -> None:
        # Initialize as a Compute experiment (uses COMPUTE_CONFIG, logging, etc.)
        super().__init__(test_mode=test_mode, vdd=vdd, vcc=vcc)

        # Override config name for logging clarity
        self.config = COMPUTE_CONFIG._replace(name="Kalman")  # type: ignore[attr-defined]
        self.logger = logging.getLogger("Experiment.Kalman")

        # Current bounds (A)
        self.min_current = SETTINGS.MIN_CURRENT
        self.max_current = SETTINGS.MAX_CURRENT

        # Fixed reference / bias currents (A)
        self.irefp = SETTINGS.IREFP_DEFAULT
        self.trim1 = SETTINGS.TRIM1_INITIAL
        self.trim2 = SETTINGS.TRIM2_INITIAL
        self.kgain1 = SETTINGS.KGAIN1_INITIAL
        self.kgain2 = SETTINGS.KGAIN2_INITIAL
        self.f11 = SETTINGS.F11_INITIAL
        self.f12 = SETTINGS.F12_INITIAL

        # X currents (A) – updated during loop
        self.x1 = SETTINGS.X1_INITIAL
        self.x2 = SETTINGS.X2_INITIAL

        # IMEAS sequence settings
        self.imeas_initial = SETTINGS.IMEAS_INITIAL
        self.imeas_num_points = SETTINGS.IMEAS_NUM_POINTS
        self.imeas_max_rel_step = SETTINGS.IMEAS_MAX_REL_STEP
        self.imeas_noise_std = SETTINGS.IMEAS_NOISE_STD
        self.rng_seed = SETTINGS.RNG_SEED

        # Time step between IMEAS points (seconds)
        self.time_step = SETTINGS.TIME_STEP

        # IMEAS sequence will be generated in run()
        self.imeas_vector: List[float] = []

    # ======================================================================
    # IMEAS TEST VECTOR GENERATION
    # ======================================================================

    def _make_rng(self) -> random.Random:
        """Create a random number generator, optionally seeded."""
        if self.rng_seed is None:
            return random.Random()
        return random.Random(self.rng_seed)

    def _random_relative_step(self, rng: random.Random) -> float:
        """
        Draw a random relative step in [-imeas_max_rel_step, +imeas_max_rel_step].
        """
        return rng.uniform(-self.imeas_max_rel_step, self.imeas_max_rel_step)

    def _additive_noise(self, rng: random.Random) -> float:
        """
        Optional additive Gaussian noise (A). Returns 0 if noise std is 0.
        """
        if self.imeas_noise_std <= 0.0:
            return 0.0
        return rng.gauss(0.0, self.imeas_noise_std)

    def generate_imeas_vector(self, start: float, time_step: float) -> List[float]:
        """
        Generate an IMEAS test vector starting from `start`.

        Uses a bounded-length random walk:
            IMEAS_{k+1} = IMEAS_k * (1 + delta_k) + noise_k
        where delta_k ~ U[-IMEAS_MAX_REL_STEP, IMEAS_MAX_REL_STEP].

        The resulting vector is later validated against [MIN_CURRENT, MAX_CURRENT].
        """
        self.logger.debug("Generating IMEAS vector with time_step=%g s", time_step)
        rng = self._make_rng()
        values = [start]

        for _ in range(self.imeas_num_points - 1):
            prev = values[-1]
            rel_step = self._random_relative_step(rng)
            noise = self._additive_noise(rng)
            next_val = prev * (1.0 + rel_step) + noise
            values.append(next_val)

        return values

    def _validate_imeas_vector(self, values: List[float]) -> None:
        """
        Ensure all IMEAS values are within [MIN_CURRENT, MAX_CURRENT].

        If any value is out of bounds, log an error and terminate the program.
        """
        for idx, val in enumerate(values):
            if not (self.min_current <= val <= self.max_current):
                self.logger.error("=" * 60)
                self.logger.error("IMEAS test vector validation FAILED.")
                self.logger.error(
                    "Index %d has value %g A which is outside [%g, %g] A",
                    idx, val, self.min_current, self.max_current,
                )
                self.logger.error("Terminate program due to invalid IMEAS test vector.")
                self.logger.error("=" * 60)
                raise SystemExit(
                    f"IMEAS[{idx}] = {val} A is outside [{self.min_current}, {self.max_current}] A"
                )

        self.logger.info(
            "IMEAS test vector validated: %d points within [%g, %g] A",
            len(values), self.min_current, self.max_current,
        )

    # ======================================================================
    # HELPER: CLAMP CURRENTS
    # ======================================================================

    def _clamp_current(self, value: float) -> float:
        """Clamp a current value into [MIN_CURRENT, MAX_CURRENT]."""
        return max(self.min_current, min(self.max_current, value))

    # ======================================================================
    # MAIN CLOSED-LOOP RUN
    # ======================================================================

    def run(self) -> Dict[str, Any]:
        """
        Execute the Kalman-style closed-loop experiment.

        Flow:
            1. One-time initialization (channels, VDD/VCC, OUT1/OUT2 bias).
            2. Apply fixed currents TRIM1/2, KGAIN1/2, F11, F12, IREFP.
            3. Generate and validate IMEAS test vector.
            4. For each IMEAS value:
                   ERASE step  -> update X1/X2 with (1 + IERR)
                   PROGRAM step -> update X1/X2 with (1 - IERR)
               X1/X2 are clamped to [0.1 nA, 100 nA] after each update.
        """
        self.logger.info("=" * 60)
        self.logger.info("Executing Kalman-style closed-loop experiment")
        self.logger.info("=" * 60)

        # ------------------------------------------------------------------
        # One-time initialization (reuse ComputeExperiment helpers)
        # ------------------------------------------------------------------
        # Initialize CSV/logging via base class (already done in __init__)
        # Enable all channels on all instruments
        self.initialize_all_channels()

        # Setup voltage supplies - VDD, VCC, VSS (one-time)
        self.setup_voltage_supplies()

        # Setup OUT1 and OUT2 at VDD voltage (one-time)
        self.setup_sync_sweep_outputs()

        # Note: fixed bias currents and initial X1/X2 are applied after
        # IMEAS test-vector generation so that generation is independent
        # of instrument state and can be validated before changing outputs.

        # ------------------------------------------------------------------
        # Generate and validate IMEAS test vector
        # ------------------------------------------------------------------
        if not (self.min_current <= self.imeas_initial <= self.max_current):
            raise SystemExit(
                f"Initial IMEAS ({self.imeas_initial} A) is outside "
                f"[{self.min_current}, {self.max_current}] A"
            )

        self.logger.info(
            "Generating IMEAS test vector: start=%g A, points=%d, max_rel_step=%g",
            self.imeas_initial, self.imeas_num_points, self.imeas_max_rel_step,
        )
        self.imeas_vector = self.generate_imeas_vector(self.imeas_initial, self.time_step)
        self._validate_imeas_vector(self.imeas_vector)

        # ------------------------------------------------------------------
        # Apply fixed currents that do NOT change during the loop
        # (moved here so IMEAS generation/validation happens first)
        # ------------------------------------------------------------------
        self.logger.info("Applying fixed bias currents (TRIM1/2, KGAIN1/2, F11, F12, IREFP)")

        # IREFP
        self.set_terminal_current("IREFP", self.irefp)

        # TRIM1 / TRIM2 (independent)
        self.set_terminal_current("TRIM1", self.trim1)
        self.set_terminal_current("TRIM2", self.trim2)

        # KGAIN1 / KGAIN2 (independent)
        self.set_terminal_current("KGAIN1", self.kgain1)
        self.set_terminal_current("KGAIN2", self.kgain2)

        # F11 / F12
        self.set_terminal_current("F11", self.f11)
        self.set_terminal_current("F12", self.f12)

        # Initial X1 / X2 (clamped to bounds)
        self.x1 = self._clamp_current(self.x1)
        self.x2 = self._clamp_current(self.x2)
        self.set_terminal_current("X1", self.x1)
        self.set_terminal_current("X2", self.x2)

        # ------------------------------------------------------------------
        # Closed-loop ERASE / PROGRAM cycle for each IMEAS value
        # ------------------------------------------------------------------
        history: List[Dict[str, Any]] = []

        for idx, imeas in enumerate(self.imeas_vector):
            self.logger.info("-" * 60)
            self.logger.info("IMEAS step %d/%d: IMEAS = %g A", idx + 1, len(self.imeas_vector), imeas)

            # Set IMEAS for this step
            self.set_terminal_current("IMEAS", imeas)

            # -------------------- ERASE STEP -------------------------------
            self.set_ppg_state("ERASE")

            # Ensure X1/X2 terminals use current values before measurement
            self.set_terminal_current("X1", self.x1)
            self.set_terminal_current("X2", self.x2)

            out1_erase = self.measure_terminal_current("OUT1", record=False)
            out2_erase = self.measure_terminal_current("OUT2", record=False)

            ierr1_erase = self._compute_ierr(self.trim1, out1_erase, label="ERASE/OUT1")
            ierr2_erase = self._compute_ierr(self.trim2, out2_erase, label="ERASE/OUT2")

            x1_after_erase = self._update_current(self.x1, ierr1_erase, mode="ERASE")
            x2_after_erase = self._update_current(self.x2, ierr2_erase, mode="ERASE")

            # -------------------- PROGRAM STEP -----------------------------
            self.set_ppg_state("PROGRAM")

            # Use updated X1/X2 from ERASE as starting point for PROGRAM step
            self.x1 = x1_after_erase
            self.x2 = x2_after_erase

            self.set_terminal_current("X1", self.x1)
            self.set_terminal_current("X2", self.x2)

            out1_prog = self.measure_terminal_current("OUT1", record=False)
            out2_prog = self.measure_terminal_current("OUT2", record=False)

            ierr1_prog = self._compute_ierr(self.trim1, out1_prog, label="PROGRAM/OUT1")
            ierr2_prog = self._compute_ierr(self.trim2, out2_prog, label="PROGRAM/OUT2")

            self.x1 = self._update_current(self.x1, ierr1_prog, mode="PROGRAM")
            self.x2 = self._update_current(self.x2, ierr2_prog, mode="PROGRAM")

            # Store step history
            history.append(
                {
                    "step_index": idx,
                    "imeas": imeas,
                    "erase": {
                        "out1": out1_erase,
                        "out2": out2_erase,
                        "ierr1": ierr1_erase,
                        "ierr2": ierr2_erase,
                        "x1_after": x1_after_erase,
                        "x2_after": x2_after_erase,
                    },
                    "program": {
                        "out1": out1_prog,
                        "out2": out2_prog,
                        "ierr1": ierr1_prog,
                        "ierr2": ierr2_prog,
                        "x1_final": self.x1,
                        "x2_final": self.x2,
                    },
                }
            )

        self.logger.info("=" * 60)
        self.logger.info("Kalman-style experiment complete.")
        self.logger.info(
            "Final X1 = %g A, Final X2 = %g A (bounded to [%g, %g] A)",
            self.x1,
            self.x2,
            self.min_current,
            self.max_current,
        )
        self.logger.info("=" * 60)

        return {
            "experiment": "Kalman",
            "parameters": {
                "VDD": self.vdd,
                "VCC": self.vcc,
                "MIN_CURRENT": self.min_current,
                "MAX_CURRENT": self.max_current,
            },
            "imeas_vector": self.imeas_vector,
            "final_x1": self.x1,
            "final_x2": self.x2,
            "history": history,
        }

    # ======================================================================
    # ERROR COMPUTATION AND CURRENT UPDATE HELPERS
    # ======================================================================

    def _compute_ierr(self, trim_current: float, out_current: float, label: str) -> float:
        """
        Compute IERR = TRIM / OUT for a given measurement, with guards.

        If OUT current is too small, returns 0.0 and logs a warning.
        """
        eps = 1e-15
        if abs(out_current) < eps:
            self.logger.warning(
                "OUT current near zero for %s (OUT=%g A); IERR set to 0",
                label,
                out_current,
            )
            return 0.0
        ierr = trim_current / out_current
        self.logger.debug("IERR (%s): trim=%g A, out=%g A, IERR=%g", label, trim_current, out_current, ierr)
        return ierr

    def _update_current(self, current: float, ierr: float, mode: str) -> float:
        """
        Update X current according to mode and clamp to [MIN_CURRENT, MAX_CURRENT].

        mode:
            "ERASE"   -> X_new = X_old * (1 + IERR)
            "PROGRAM" -> X_new = X_old * (1 - IERR)
        """
        if mode.upper() == "ERASE":
            updated = current * (1.0 + ierr)
        elif mode.upper() == "PROGRAM":
            updated = current * (1.0 - ierr)
        else:
            raise ValueError(f"Unknown update mode: {mode}")

        clamped = self._clamp_current(updated)
        self.logger.debug(
            "Update current (%s): X_old=%g A, IERR=%g, X_new_raw=%g A, X_new_clamped=%g A",
            mode,
            current,
            ierr,
            updated,
            clamped,
        )
        return clamped


def main() -> None:
    """Main entry point for Kalman-style experiment."""
    parser = argparse.ArgumentParser(description="Run Kalman-style closed-loop experiment")
    parser.add_argument(
        "--test",
        "-t",
        action="store_true",
        help="Run in TEST_MODE (log commands without hardware)",
    )
    parser.add_argument(
        "--vdd",
        type=float,
        default=SETTINGS.VDD_DEFAULT,
        help=f"VDD voltage in volts (default: {SETTINGS.VDD_DEFAULT})",
    )
    parser.add_argument(
        "--vcc",
        type=float,
        default=SETTINGS.VCC_DEFAULT,
        help=f"VCC voltage in volts (default: {SETTINGS.VCC_DEFAULT})",
    )
    args = parser.parse_args()

    with KalmanExperiment(
        test_mode=args.test,
        vdd=args.vdd,
        vcc=args.vcc,
    ) as experiment:
        results = experiment.run()

    # Simple summary to stdout
    print("\n" + "=" * 60)
    print("KALMAN EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"Experiment: {results['experiment']}")
    print(
        f"Parameters: VDD={results['parameters']['VDD']} V, "
        f"VCC={results['parameters']['VCC']} V",
    )
    print(f"IMEAS points: {len(results.get('imeas_vector', []))}")
    print(f"Final X1: {results.get('final_x1', 0.0)} A")
    print(f"Final X2: {results.get('final_x2', 0.0)} A")
    print("=" * 60)


if __name__ == "__main__":
    main()

