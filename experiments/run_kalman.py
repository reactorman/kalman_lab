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
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.run_compute import ComputeExperiment  # Reuse hardware setup helpers
from configs.compute import COMPUTE_CONFIG
from configs import kalman_settings as SETTINGS
from configs.resource_types import InstrumentType
from experiments.imeas_test_pattern import generate_imeas_pattern


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

        # IMEAS sequence will be generated in run()
        self.imeas_vector: List[float] = []

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
        # Generate IMEAS test vector using shared pattern generator
        # ------------------------------------------------------------------
        self.logger.info("Generating IMEAS test pattern from kalman_settings.")
        imeas_values, roc_values = generate_imeas_pattern()
        self.imeas_vector = imeas_values

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

        x1_trajectory: List[float] = []
        x2_trajectory: List[float] = []
        if self.test_mode:
            x1_trajectory.append(self.x1)
            x2_trajectory.append(self.x2)

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

            if self.test_mode:
                # In TEST_MODE, bypass hardware measurement so X1/X2 still
                # evolve according to the update equations using a simple
                # model where OUT currents track X currents.
                out1_erase = self.x1
                out2_erase = self.x2
            else:
                erase_currents = self._measure_out_currents_pair()
                out1_erase = erase_currents["OUT1"]
                out2_erase = erase_currents["OUT2"]

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

            if self.test_mode:
                out1_prog = self.x1
                out2_prog = self.x2
            else:
                prog_currents = self._measure_out_currents_pair()
                out1_prog = prog_currents["OUT1"]
                out2_prog = prog_currents["OUT2"]

            ierr1_prog = self._compute_ierr(self.trim1, out1_prog, label="PROGRAM/OUT1")
            ierr2_prog = self._compute_ierr(self.trim2, out2_prog, label="PROGRAM/OUT2")

            self.x1 = self._update_current(self.x1, ierr1_prog, mode="PROGRAM")
            self.x2 = self._update_current(self.x2, ierr2_prog, mode="PROGRAM")

            if self.test_mode:
                x1_trajectory.append(self.x1)
                x2_trajectory.append(self.x2)

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

        if self.test_mode:
            self._plot_test_mode_trajectories(x1_trajectory, x2_trajectory)
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
    # MEASUREMENT HELPERS
    # ======================================================================

    def _measure_out_currents_pair(self) -> Dict[str, float]:
        """
        Measure OUT1 and OUT2 currents in a single 5270B spot measurement.

        Uses multi-channel MM 1,CH_OUT1,CH_OUT2 and parses both currents
        from the returned data string. Falls back to per-terminal
        measurement if either terminal is not on the 5270B.
        """
        out1_cfg = self.get_terminal_config("OUT1")
        out2_cfg = self.get_terminal_config("OUT2")

        if out1_cfg.instrument != InstrumentType.IV5270B or out2_cfg.instrument != InstrumentType.IV5270B:
            return {
                "OUT1": self.measure_terminal_current("OUT1", record=False),
                "OUT2": self.measure_terminal_current("OUT2", record=False),
            }

        iv = self._get_instrument(InstrumentType.IV5270B)
        channels = [out1_cfg.channel, out2_cfg.channel]
        iv.set_measurement_mode(1, channels)
        iv.execute_measurement()
        raw = iv.read_data()

        self.logger.debug("5270B OUT1/OUT2 raw data: %s", raw)

        out1_current = 0.0
        out2_current = 0.0

        try:
            parts = raw.split(",")
            cleaned = [self._remove_3letter_prefix(p) for p in parts]

            # First value: OUT1 current
            if len(cleaned) >= 1:
                try:
                    out1_current = float(cleaned[0])
                except ValueError:
                    out1_str = cleaned[0].replace("I", "").replace("A", "")
                    out1_current = float(out1_str)

            # Second value: OUT2 current
            if len(cleaned) >= 2:
                try:
                    out2_current = float(cleaned[1])
                except ValueError:
                    out2_str = cleaned[1].replace("I", "").replace("A", "")
                    out2_current = float(out2_str)
        except Exception as exc:
            self.logger.warning("Error parsing OUT1/OUT2 currents from 5270B data %r: %s", raw, exc)

        self.logger.info("OUT1 current = %g A, OUT2 current = %g A", out1_current, out2_current)
        return {"OUT1": out1_current, "OUT2": out2_current}

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

    # ======================================================================
    # TEST-MODE PLOTTING
    # ======================================================================

    def _plot_test_mode_trajectories(
        self,
        x1_trajectory: List[float],
        x2_trajectory: List[float],
    ) -> None:
        """
        In TEST_MODE, plot X1, X2, and IMEAS versus step index.

        This is purely a visualization aid; it is not used in hardware runs.
        """
        try:
            import matplotlib.pyplot as plt  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            self.logger.warning("matplotlib not available; skipping test-mode plots: %s", exc)
            return

        steps_x = list(range(len(x1_trajectory)))
        steps_i = list(range(len(self.imeas_vector)))

        fig, ax1 = plt.subplots()
        ax1.set_xlabel("Step index")
        ax1.set_ylabel("X currents (A)", color="tab:blue")
        ax1.plot(steps_x, x1_trajectory, label="X1", color="tab:blue")
        ax1.plot(steps_x, x2_trajectory, label="X2", color="tab:cyan")
        ax1.tick_params(axis="y", labelcolor="tab:blue")
        ax1.legend(loc="upper left")

        ax2 = ax1.twinx()
        ax2.set_ylabel("IMEAS (A)", color="tab:orange")
        ax2.plot(steps_i, self.imeas_vector, label="IMEAS", color="tab:orange", linestyle="--")
        ax2.tick_params(axis="y", labelcolor="tab:orange")

        fig.tight_layout()
        plt.title("Test Mode Trajectories: X1, X2, IMEAS")
        plt.show()


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

