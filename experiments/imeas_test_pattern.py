#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IMEAS Test Pattern Generator
============================

Shared IMEAS test pattern generator for:
- `experiments/run_kalman.py`
- `experiments/run_big_kalman.py`
- Standalone plotting / debugging.

The pattern is a bounded, optionally noisy triangle wave in IMEAS with
optional cycling of the rate-of-change (ROC).
"""

from __future__ import annotations

import argparse
import logging
import math
import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from configs import kalman_settings as SETTINGS


logger = logging.getLogger(__name__)


@dataclass
class IMEASTestConfig:
    """Configuration for IMEAS test pattern generation."""

    # Hard limits on IMEAS and ROC
    imeas_hard_min: float
    imeas_hard_max: float
    imeas_hard_roc_max: float

    # Soft limits on IMEAS and ROC
    imeas_soft_min: float
    imeas_soft_max: float
    imeas_soft_roc_min: float
    imeas_soft_roc_max: float

    # Noise
    imeas_sigma: float
    roc_sigma: float

    # Sequence length and initial conditions
    imeas_initial: float
    num_points: int
    roc_cycle_enabled: bool
    rng_seed: Optional[int] = None


def _make_default_config_from_settings() -> IMEASTestConfig:
    """Build a default IMEASTestConfig from kalman_settings."""
    return IMEASTestConfig(
        imeas_hard_min=SETTINGS.IMEAS_HARD_MIN,
        imeas_hard_max=SETTINGS.IMEAS_HARD_MAX,
        imeas_hard_roc_max=SETTINGS.IMEAS_HARD_ROC_MAX,
        imeas_soft_min=SETTINGS.IMEAS_SOFT_MIN,
        imeas_soft_max=SETTINGS.IMEAS_SOFT_MAX,
        imeas_soft_roc_min=SETTINGS.IMEAS_SOFT_ROC_MIN,
        imeas_soft_roc_max=SETTINGS.IMEAS_SOFT_ROC_MAX,
        imeas_sigma=SETTINGS.IMEAS_SIGMA,
        roc_sigma=SETTINGS.ROC_SIGMA,
        imeas_initial=SETTINGS.IMEAS_INITIAL,
        num_points=SETTINGS.IMEAS_NUM_POINTS,
        roc_cycle_enabled=SETTINGS.ROC_CYCLE_ENABLED,
        rng_seed=SETTINGS.RNG_SEED,
    )


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _clamp_roc(delta: float, max_abs_delta: float) -> float:
    if max_abs_delta <= 0.0:
        return delta
    if delta > max_abs_delta:
        return max_abs_delta
    if delta < -max_abs_delta:
        return -max_abs_delta
    return delta


def generate_imeas_pattern(
    config: Optional[IMEASTestConfig] = None,
) -> Tuple[List[float], List[float]]:
    """
    Generate an IMEAS test pattern and corresponding ROC sequence.

    The pattern:
    - Linearly ramps IMEAS between soft min and soft max (triangle wave).
    - Enforces hard limits on IMEAS and |ROC|.
    - Optionally cycles ROC magnitude between soft ROC min and max.
    - Adds Gaussian noise to IMEAS and ROC (with clamping to hard limits).

    Returns:
        (imeas_values, roc_values) where:
            imeas_values[k] is IMEAS at step k (after IMEAS noise + clamping)
            roc_values[k]   is the calculated ROC applied at step k, i.e.
                            the intended IMEAS step (after ROC noise and
                            ROC clamping but before IMEAS noise).
    """
    if config is None:
        config = _make_default_config_from_settings()

    if config.num_points <= 0:
        return [], []

    rng = random.Random(config.rng_seed)

    # Ensure soft limits are nested within hard limits
    soft_min = _clamp(config.imeas_soft_min, config.imeas_hard_min, config.imeas_hard_max)
    soft_max = _clamp(config.imeas_soft_max, config.imeas_hard_min, config.imeas_hard_max)
    if soft_max < soft_min:
        soft_min, soft_max = soft_max, soft_min

    imeas_values: List[float] = []
    roc_values: List[float] = []

    # Start at initial value clamped to hard limits; if it's outside soft
    # limits we'll move toward the soft range on the first few steps.
    current = _clamp(config.imeas_initial, config.imeas_hard_min, config.imeas_hard_max)

    # Determine initial direction based on where we start relative to soft
    # limits: if at or below soft_min, go up; if at or above soft_max, go down.
    if current <= soft_min:
        direction = 1.0
    elif current >= soft_max:
        direction = -1.0
    else:
        direction = 1.0

    # Initial ROC magnitude
    roc_mag = max(config.imeas_soft_roc_min, 0.0)
    roc_mag = min(roc_mag, config.imeas_soft_roc_max if config.imeas_soft_roc_max > 0 else roc_mag)

    imeas_values.append(current)
    roc_values.append(0.0)

    for _ in range(1, config.num_points):
        # Base ROC magnitude: either fixed or cycling between soft ROC min/max
        if config.roc_cycle_enabled and config.imeas_soft_roc_max > config.imeas_soft_roc_min:
            # Simple triangle-wave sweep between soft_roc_min and soft_roc_max
            step_roc = (config.imeas_soft_roc_max - config.imeas_soft_roc_min) / max(
                config.num_points - 1, 1
            )
            roc_mag += step_roc
            if roc_mag > config.imeas_soft_roc_max or roc_mag < config.imeas_soft_roc_min:
                # Reflect at the boundaries
                roc_mag = _clamp(roc_mag, config.imeas_soft_roc_min, config.imeas_soft_roc_max)
                step_roc = -step_roc
        else:
            # Fixed ROC magnitude equal to soft ROC max (or min if max is not set)
            base = config.imeas_soft_roc_max if config.imeas_soft_roc_max > 0 else config.imeas_soft_roc_min
            roc_mag = max(base, 0.0)

        # Signed ROC (direction encoded in sign)
        roc = direction * roc_mag

        # Add noise to ROC, then enforce hard ROC limit
        if config.roc_sigma > 0.0:
            roc += rng.gauss(0.0, config.roc_sigma)
        roc = _clamp_roc(roc, config.imeas_hard_roc_max)

        proposed = current + roc

        # Enforce soft limits with reflection behavior: when we hit soft max
        # or min, we flip direction and keep walking within [soft_min, soft_max].
        if proposed > soft_max:
            overflow = proposed - soft_max
            proposed = soft_max - overflow
            direction = -1.0
        elif proposed < soft_min:
            underflow = soft_min - proposed
            proposed = soft_min + underflow
            direction = 1.0

        # Add IMEAS noise and then clamp to hard limits.
        if config.imeas_sigma > 0.0:
            proposed += rng.gauss(0.0, config.imeas_sigma)
        proposed = _clamp(proposed, config.imeas_hard_min, config.imeas_hard_max)

        imeas_values.append(proposed)
        # Store the calculated ROC (after ROC noise and clamping, before IMEAS noise).
        roc_values.append(roc)
        current = proposed

    logger.info(
        "Generated IMEAS pattern: %d points, IMEAS in [%g, %g] A, |ROC|_max=%g A/step",
        len(imeas_values),
        min(imeas_values),
        max(imeas_values),
        max((abs(r) for r in roc_values[1:]), default=0.0),
    )

    return imeas_values, roc_values


def _plot_pattern(imeas: Sequence[float], roc: Sequence[float]) -> None:
    """Plot IMEAS and ROC versus step index."""
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise SystemExit(f"matplotlib is required for plotting: {exc}") from exc

    x = list(range(len(imeas)))

    fig, ax1 = plt.subplots()
    ax1.set_xlabel("Step index")
    ax1.set_ylabel("IMEAS (A)", color="tab:blue")
    ax1.plot(x, imeas, color="tab:blue", label="IMEAS")
    ax1.tick_params(axis="y", labelcolor="tab:blue")

    ax2 = ax1.twinx()
    ax2.set_ylabel("ROC (A/step)", color="tab:orange")
    ax2.plot(x, roc, color="tab:orange", linestyle="--", label="ROC")
    ax2.tick_params(axis="y", labelcolor="tab:orange")

    fig.tight_layout()
    plt.title("IMEAS Test Pattern and ROC")
    plt.show()


def main() -> None:
    """Standalone entry point for generating and plotting IMEAS test patterns."""
    parser = argparse.ArgumentParser(description="Generate and plot IMEAS test pattern")
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Generate the pattern but do not display plots",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = _make_default_config_from_settings()
    imeas, roc = generate_imeas_pattern(config)

    print(f"Generated {len(imeas)} IMEAS points using kalman_settings:")
    print(f"  IMEAS range: [{min(imeas):.4e}, {max(imeas):.4e}] A")
    if len(roc) > 1:
        roc_abs = [abs(r) for r in roc[1:]]
        print(f"  ROC max: {max(roc_abs):.4e} A/step")

    if not args.no_plot:
        _plot_pattern(imeas, roc)


if __name__ == "__main__":
    main()

