# -*- coding: utf-8 -*-
"""
Agilent E5250A Low Leakage Switch Mainframe Driver

Controls the E5250A switch matrix via GPIB/SCPI. Supports E5252A 10×12 Matrix
cards in Auto Configuration: 3 blades of 12 channels = 36 outputs, with two
inputs (VCC = input 1, VSS = input 2).

Channel list format (Auto Config): 5 digits = Card (0) + Input (01-10) + Output (01-36).
  - Connect output N to VCC (input 1): channel 0 + 01 + NN → e.g. 101 for output 1, 136 for output 36.
  - Connect output N to VSS (input 2): channel 0 + 02 + NN → e.g. 201 for output 1, 236 for output 36.

Reference: Agilent E5250A User's Guide (E5250_user.pdf), :ROUTe subsystem.
"""

from .base import InstrumentBase
from typing import List


# Input port numbers for this setup (E5252A)
INPUT_VCC = 1   # Input 1 = VCC
INPUT_VSS = 2   # Input 2 = VSS

# Output count: 3 blades × 12 channels
NUM_OUTPUTS = 36


class SW_E5250A(InstrumentBase):
    """
    Driver for Agilent E5250A Low Leakage Switch Mainframe.

    Assumes 3× E5252A cards in slots 1–3 (Auto Configuration), giving
    10 inputs and 36 outputs. Input 1 = VCC, Input 2 = VSS.
    """

    def __init__(self, resource_manager, address: str = "GPIB0::18::INSTR",
                 timeout: int = 5000):
        """
        Initialize the E5250A.

        Args:
            resource_manager: PyVISA ResourceManager instance
            address: GPIB address (default: "GPIB0::18::INSTR")
            timeout: Communication timeout in ms (default: 5000)
        """
        super().__init__(resource_manager, address, "SW_E5250A", timeout)

    def reset(self) -> None:
        """Reset the instrument to default state."""
        self.write("*RST")
        self.logger.info("E5250A reset")

    def clear_status(self) -> None:
        """Clear status registers."""
        self.write("*CLS")

    def idn_query(self) -> str:
        """Return instrument identification."""
        return self.query("*IDN?")

    def open_all(self) -> None:
        """
        Open (disconnect) all switch matrix relays.

        Disconnects all outputs from both VCC (input 1) and VSS (input 2).
        Call this when done with measurements to leave the matrix in a safe state.
        """
        # Open all possible connections: input 01 outputs 01-36, input 02 outputs 01-36
        # Channel list: (@101:136,@201:236) for 5-digit; short form 101:136, 201:236
        self.write(":ROUT:OPEN (@101:136,@201:236)")
        self.logger.info("E5250A: all switches open")

    def connect_output_to_vcc(self, output_one_based: int) -> None:
        """
        Connect a single output to VCC (input 1).

        Args:
            output_one_based: Output index 1–36 (pin 1 = blade 1 out 1, ..., pin 36 = blade 3 out 12).
        """
        if not 1 <= output_one_based <= NUM_OUTPUTS:
            raise ValueError(f"output_one_based must be 1..{NUM_OUTPUTS}, got {output_one_based}")
        ch = self._channel_number(INPUT_VCC, output_one_based)
        self.write(f":ROUT:CLOS (@{ch})")
        self.logger.debug(f"E5250A: output {output_one_based} → VCC (input 1)")

    def connect_output_to_vss(self, output_one_based: int) -> None:
        """
        Connect a single output to VSS (input 2).

        Args:
            output_one_based: Output index 1–36.
        """
        if not 1 <= output_one_based <= NUM_OUTPUTS:
            raise ValueError(f"output_one_based must be 1..{NUM_OUTPUTS}, got {output_one_based}")
        ch = self._channel_number(INPUT_VSS, output_one_based)
        self.write(f":ROUT:CLOS (@{ch})")
        self.logger.debug(f"E5250A: output {output_one_based} → VSS (input 2)")

    def set_output(self, output_one_based: int, to_vcc: bool) -> None:
        """
        Connect one output to either VCC or VSS.

        Any previous connection of this output is replaced (Single Route behavior).

        Args:
            output_one_based: Output index 1–36.
            to_vcc: True = connect to VCC (input 1), False = connect to VSS (input 2).
        """
        if to_vcc:
            self.connect_output_to_vcc(output_one_based)
        else:
            self.connect_output_to_vss(output_one_based)

    def set_outputs_from_pattern(self, pattern: List[bool]) -> None:
        """
        Set each output from a list of booleans (True = VCC, False = VSS).

        Length must be NUM_OUTPUTS (36). Order is output 1, 2, ..., 36.
        """
        if len(pattern) != NUM_OUTPUTS:
            raise ValueError(f"pattern length must be {NUM_OUTPUTS}, got {len(pattern)}")
        for i, to_vcc in enumerate(pattern, start=1):
            self.set_output(i, to_vcc)

    def _channel_number(self, input_port: int, output_port: int) -> str:
        """Format 5-digit channel for Auto Config: card 0, input 01-10, output 01-36."""
        return f"0{input_port:02d}{output_port:02d}"

    def idle(self) -> None:
        """Set switch matrix to safe state: all relays open."""
        self.open_all()

    def close(self) -> None:
        """Open all switches and close the GPIB connection."""
        try:
            self.open_all()
        except Exception:
            pass
        super().close()
