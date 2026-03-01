#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Big Kalman Experiment

Uses only the 5270B and the E5250A switch matrix. Switch matrix has 36 outputs
(3 blades × 12 channels); each output can be connected to VCC (input 1) or VSS (input 2).

SMU mapping:
    SMU1 (ch 1): CELLMEAS — apply VDD; measure ICELLMEAS when requested
    SMU2 (ch 2): VCC — apply VCC; measure IVCC when requested
    SMU3 (ch 3): VDD — apply VDD
    SMU4 (ch 4): IMEAS — force IMEAS (current, sinks); VCOMP 1.8V; measure VIMEAS when requested
    SMU5 (ch 5): IREFP — force IREFP (current, sinks); measure VREFP when requested
    SMU6 (ch 6): MODE — apply VCC/2; measure current for 3-bit code when MODE requested
    SMU7 (ch 7): VCC — apply VCC whenever SMU2 has VCC; current never measured

VSS (pin 7) is hardwired to GNDU; no code.

Test modes will be defined later. This module provides initialization, bias application,
switch matrix control, and measurement helpers (IVCC, VIMEAS, VREFP, MODE 3-bit, ICELLMEAS).
"""

import sys
import os
import re
import argparse
import logging
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.base_experiment import ExperimentRunner
from configs.big_kalman import (
    BIG_KALMAN_CONFIG,
    BIG_KALMAN_SMU7_VCC_CHANNEL,
)
from configs import big_kalman_settings as SETTINGS
from configs.resource_types import InstrumentType

# E5250A output count
NUM_SWITCH_OUTPUTS = 36


def _parse_spot_value(data: str) -> float:
    """Try to extract a single float from 5270B spot measurement response."""
    # Common formats: " 5.0, 1e-6", "V2,I2", "I4: 1.23e-6", or just "1.23e-6"
    data = data.strip()
    # Try splitting by comma and take last number-like token
    for part in re.split(r"[\s,]+", data):
        part = part.strip()
        if not part:
            continue
        # Remove leading non-numeric (e.g. "I4:" or "V2")
        m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", part)
        if m:
            try:
                return float(m.group())
            except ValueError:
                continue
    raise ValueError(f"Cannot parse float from spot data: {data!r}")


class BigKalmanExperiment(ExperimentRunner):
    """
    Big Kalman experiment: 5270B + E5250A switch matrix.

    - Applies VCC (SMU2 + SMU7), VDD (SMU3, SMU1 for CELLMEAS), IMEAS (SMU4),
      IREFP (SMU5), MODE at VCC/2 (SMU6).
    - Switch matrix: connect any output 1–36 to VCC or VSS; open all when done.
    - Measurement helpers: IVCC, VIMEAS, VREFP, MODE 3-bit, ICELLMEAS.
    """

    def __init__(self, test_mode: bool = False,
                 vcc: Optional[float] = None,
                 vdd: Optional[float] = None,
                 imeas: Optional[float] = None,
                 irefp: Optional[float] = None,
                 iadc_ref: Optional[float] = None):
        super().__init__(BIG_KALMAN_CONFIG, test_mode)
        self.vcc = vcc if vcc is not None else SETTINGS.VCC_DEFAULT
        self.vdd = vdd if vdd is not None else SETTINGS.VDD_DEFAULT
        self.imeas = imeas if imeas is not None else SETTINGS.IMEAS_DEFAULT
        self.irefp = irefp if irefp is not None else SETTINGS.IREFP_DEFAULT
        self.iadc_ref = iadc_ref if iadc_ref is not None else SETTINGS.IADC_REF_DEFAULT

    # ========================================================================
    # Initialization
    # ========================================================================

    def initialize_all(self) -> None:
        """
        Initialize 5270B (enable channels 1–7, set biases) and E5250A (open all).
        """
        self.logger.info("=" * 60)
        self.logger.info("BIG KALMAN: INITIALIZING INSTRUMENTS")
        self.logger.info("=" * 60)

        iv = self._get_instrument(InstrumentType.IV5270B)
        sw = self._get_instrument(InstrumentType.SW_E5250A)

        # E5250A: start with all switches open
        sw.open_all()

        # 5270B: enable channels 1–7 (GNDU 0 is always enabled)
        channels = list(range(1, 8))
        iv.enable_channels(channels)

        # Apply default biases (voltages and currents)
        self._apply_biases()

        self.logger.info("=" * 60)
        self.logger.info("BIG KALMAN: INITIALIZATION COMPLETE")
        self.logger.info("=" * 60)

    def _apply_biases(self) -> None:
        """
        Set all SMU biases from config: VCC (ch2+ch7), VDD (ch3, ch1), IMEAS (ch4),
        IREFP (ch5), MODE VCC/2 (ch6).
        """
        iv = self._get_instrument(InstrumentType.IV5270B)
        comp_v = SETTINGS.VOLTAGE_COMPLIANCE_DEFAULT
        comp_i = SETTINGS.CURRENT_COMPLIANCE_DEFAULT

        # VCC on SMU2 and SMU7
        iv.set_voltage(2, self.vcc, compliance=comp_v)
        iv.set_voltage(BIG_KALMAN_SMU7_VCC_CHANNEL, self.vcc, compliance=comp_v)

        # VDD on SMU3
        iv.set_voltage(3, self.vdd, compliance=comp_v)

        # VDD on SMU1 (CELLMEAS)
        iv.set_voltage(1, self.vdd, compliance=comp_v)

        # IMEAS on SMU4 (current sink; current flows into SMU)
        iv.set_current(4, self.imeas, compliance=comp_i)

        # IREFP on SMU5 (current sink)
        iv.set_current(5, self.irefp, compliance=comp_i)

        # MODE on SMU6: VCC/2
        mode_voltage = self.vcc / 2.0
        iv.set_voltage(6, mode_voltage, compliance=comp_v)

        self.logger.info(f"Biases: VCC={self.vcc}V (ch2,ch7), VDD={self.vdd}V (ch1,ch3), "
                        f"IMEAS={self.imeas}A, IREFP={self.irefp}A, MODE={mode_voltage}V")

    # ========================================================================
    # Switch matrix (E5250A)
    # ========================================================================

    def all_switches_off(self) -> None:
        """Open all E5250A relays (disconnect all outputs from VCC and VSS)."""
        sw = self._get_instrument(InstrumentType.SW_E5250A)
        sw.open_all()
        self.logger.info("E5250A: all switches open")

    def set_switch_output(self, output_one_based: int, to_vcc: bool) -> None:
        """
        Connect one switch matrix output to VCC (input 1) or VSS (input 2).

        Args:
            output_one_based: Output index 1–36 (pin 1 = blade1 out1, …, pin 36 = blade3 out12).
            to_vcc: True = VCC, False = VSS.
        """
        if not 1 <= output_one_based <= NUM_SWITCH_OUTPUTS:
            raise ValueError(f"output_one_based must be 1..{NUM_SWITCH_OUTPUTS}, got {output_one_based}")
        sw = self._get_instrument(InstrumentType.SW_E5250A)
        sw.set_output(output_one_based, to_vcc)

    def set_switch_outputs_from_pattern(self, pattern: list) -> None:
        """
        Set all 36 outputs from a list of bool (True = VCC, False = VSS).
        """
        if len(pattern) != NUM_SWITCH_OUTPUTS:
            raise ValueError(f"pattern length must be {NUM_SWITCH_OUTPUTS}, got {len(pattern)}")
        sw = self._get_instrument(InstrumentType.SW_E5250A)
        sw.set_outputs_from_pattern(pattern)

    # ========================================================================
    # Measurements (spot on 5270B)
    # ========================================================================

    def _spot_measure_channel(self, channel: int) -> str:
        """Run spot measurement on one channel and return raw response."""
        iv = self._get_instrument(InstrumentType.IV5270B)
        iv.set_measurement_mode(1, [channel])
        iv.execute_measurement()
        return iv.read_data()

    def measure_ivcc(self) -> float:
        """Measure current on VCC (SMU2). Returns current in A."""
        data = self._spot_measure_channel(2)
        return _parse_spot_value(data)

    def measure_vimeas(self) -> float:
        """Measure voltage on IMEAS (SMU4). Returns voltage in V."""
        data = self._spot_measure_channel(4)
        return _parse_spot_value(data)

    def measure_vrefp(self) -> float:
        """Measure voltage on IREFP (SMU5). Returns voltage in V."""
        data = self._spot_measure_channel(5)
        return _parse_spot_value(data)

    def measure_icellmeas(self) -> float:
        """Measure current on CELLMEAS (SMU1). Returns current in A."""
        data = self._spot_measure_channel(1)
        return _parse_spot_value(data)

    def measure_mode_3bit(self) -> int:
        """
        Measure current on MODE (SMU6) and return 3-bit code (0–7).

        Uses IADC_REF from config: 000 = 0A, full scale = IADC_REF.
        """
        data = self._spot_measure_channel(6)
        i = _parse_spot_value(data)
        # Map current to 0..7; clamp to [0, 1] then scale to 7
        if self.iadc_ref <= 0:
            return 0
        ratio = i / self.iadc_ref
        ratio = max(0.0, min(1.0, ratio))
        code = int(round(ratio * 7))
        return min(7, max(0, code))

    # ========================================================================
    # Shutdown
    # ========================================================================

    def finish(self) -> None:
        """Open all switches and set 5270B to idle."""
        self.all_switches_off()
        self.idle_all()


def main() -> None:
    parser = argparse.ArgumentParser(description="Big Kalman experiment (5270B + E5250A)")
    parser.add_argument("--test", action="store_true", help="Run in TEST_MODE (no hardware)")
    parser.add_argument("--vcc", type=float, default=None, help=f"VCC voltage (default {SETTINGS.VCC_DEFAULT})")
    parser.add_argument("--vdd", type=float, default=None, help=f"VDD voltage (default {SETTINGS.VDD_DEFAULT})")
    parser.add_argument("--imeas", type=float, default=None, help="IMEAS current (A)")
    parser.add_argument("--irefp", type=float, default=None, help="IREFP current (A)")
    parser.add_argument("--iadc-ref", type=float, default=None, help="MODE ADC full-scale current (A)")
    args = parser.parse_args()

    exp = BigKalmanExperiment(
        test_mode=args.test,
        vcc=args.vcc,
        vdd=args.vdd,
        imeas=args.imeas,
        irefp=args.irefp,
        iadc_ref=args.iadc_ref,
    )
    exp.initialize_instruments()
    exp.initialize_all()

    # Test modes will be defined later; for now just init and exit cleanly
    exp.logger.info("Test modes TBD; run complete (init + finish).")
    exp.finish()
    exp.close_all()


if __name__ == "__main__":
    main()
