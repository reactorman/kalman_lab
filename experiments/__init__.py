# -*- coding: utf-8 -*-
"""
Experiments Package

Contains top-level execution scripts for each experiment.
Each experiment script:
- Imports instrument-level modules
- Loads its experiment configuration
- Executes the appropriate measurement sequence
- Handles TEST_MODE for safe command logging

Experiments are independent and executed at different times.

Available Experiments:
    - compute: Computation mode characterization
    - programmer: Programming mode with pulse/counter measurements
"""

from .base_experiment import ExperimentRunner

__all__ = ['ExperimentRunner']

