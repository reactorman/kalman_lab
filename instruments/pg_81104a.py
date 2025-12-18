# -*- coding: utf-8 -*-
"""
Agilent 81104A Pulse Generator Driver

GPIB commands based on 81104_ref.pdf manual.
This instrument uses SCPI command syntax.

Features:
    - Dual channel output
    - Pulse width from 3.3ns to 999s
    - Variable rise/fall times
    - Pattern generation
    - External/internal triggering
"""

from .base import InstrumentBase, format_number
from typing import Optional


class PG81104A(InstrumentBase):
    """
    Driver for Agilent 81104A Pulse Pattern Generator.
    
    The 81104A is a dual-channel pulse generator capable of producing
    pulses with programmable width, period, and transition times.
    
    Reference: Agilent 81104A Reference Guide (81104_ref.pdf)
    """
    
    def __init__(self, resource_manager, address: str = "GPIB0::10::INSTR",
                 timeout: int = 5000):
        """
        Initialize the 81104A pulse generator.
        
        Args:
            resource_manager: PyVISA ResourceManager instance
            address: GPIB address (default: "GPIB0::10::INSTR")
            timeout: Communication timeout in ms (default: 5000)
        """
        super().__init__(resource_manager, address, "PG81104A", timeout)
    
    def reset(self) -> None:
        """
        Reset the pulse generator to default state.
        
        Configures:
        - Display off for faster command execution
        - Output impedance: 50 ohms into 1 Megohm load (both channels)
        
        Reference: *RST, :DISP, :OUTP:IMP commands
        """
        self.write("*RST")
        self.write(":DISP OFF")  # Speeds up command execution
        
        # Configure output impedance: 50 ohm source into 1 Megohm load
        self._configure_output_impedance()
        
        self.logger.info("PG81104A reset (50 ohm -> 1 MOhm, display off)")
    
    def _configure_output_impedance(self) -> None:
        """
        Configure output impedance for both channels.
        
        Fixed configuration: 50 ohm output impedance into 1 Megohm load.
        This is the standard setup for high-impedance DUT inputs.
        
        Reference: :OUTP:IMP:EXT command
        """
        # Set expected load impedance to 1 Megohm (high impedance)
        # This tells the generator not to double voltages for 50 ohm matching
        self.write(":OUTP1:IMP:EXT 1E6 OHM")  # Channel 1: expect 1 MOhm load
        self.write(":OUTP2:IMP:EXT 1E6 OHM")  # Channel 2: expect 1 MOhm load
        self.logger.debug("Output impedance: 50 ohm source -> 1 MOhm load")
    
    def error_query(self) -> str:
        """
        Query the error queue.
        
        Returns:
            Error code and message
        
        Reference: :SYST:ERR? command
        """
        self.write(":SYST:ERR?")
        return self.read()
    
    # =========================================================================
    # Output Control
    # =========================================================================
    
    def enable_output(self, channel: int) -> None:
        """
        Enable output on specified channel.
        
        Args:
            channel: Channel number (1 or 2)
        
        Reference: :OUTP command
        """
        self.write(f":OUTP{channel} ON")
        self.logger.info(f"Channel {channel} output enabled")
    
    def disable_output(self, channel: int) -> None:
        """
        Disable output on specified channel.
        
        Args:
            channel: Channel number (1 or 2)
        
        Reference: :OUTP command
        """
        self.write(f":OUTP{channel} OFF")
        self.logger.info(f"Channel {channel} output disabled")
    
    def idle(self) -> None:
        """Turn off all outputs."""
        self.write(":OUTP1 OFF")
        self.write(":OUTP2 OFF")
        self.logger.info("PG81104A outputs disabled")
    
    # =========================================================================
    # Trigger Configuration
    # =========================================================================
    
    def set_arm_source(self, source: str = "MAN") -> None:
        """
        Set the arm source.
        
        Args:
            source: "MAN" (manual/*TRG), "IMM" (immediate), "EXT" (external)
        
        Reference: :ARM:SOUR command
        """
        self.write(f":ARM:SOUR {source}")
        self.logger.debug(f"Arm source: {source}")
    
    def set_trigger_source(self, source: str = "IMM") -> None:
        """
        Set the trigger source.
        
        Args:
            source: "IMM" (immediate), "EXT" (external), "INT" (internal)
        
        Reference: :TRIG:SOUR command
        """
        self.write(f":TRIG:SOUR {source}")
        self.logger.debug(f"Trigger source: {source}")
    
    def set_trigger_count(self, count: int = 1) -> None:
        """
        Set the number of pulses per trigger.
        
        Args:
            count: Number of pulses (1 to 1000000, or INF)
        
        Reference: :TRIG:COUN command
        """
        self.write(f":TRIG:COUN {count}")
        self.logger.debug(f"Trigger count: {count}")
    
    def trigger(self) -> None:
        """
        Send a software trigger.
        
        Reference: *TRG command
        """
        self.write("*TRG")
        self.logger.info("Trigger sent")
    
    # =========================================================================
    # Pulse Configuration
    # =========================================================================
    
    def set_period(self, period: str) -> None:
        """
        Set the pulse period.
        
        Args:
            period: Period string (e.g., "1US", "10MS", "100NS")
        
        Reference: :PULS:PER command
        """
        self.write(f":PULS:PER {period}")
        self.logger.debug(f"Period: {period}")
    
    def set_pulse_width(self, channel: int, width: str) -> None:
        """
        Set the pulse width for a channel.
        
        Args:
            channel: Channel number (1 or 2)
            width: Width string (e.g., "100NS", "1US")
        
        Reference: :PULS:WIDT command
        """
        self.write(f":PULS:WIDT{channel} {width}")
        self.logger.debug(f"CH{channel} width: {width}")
    
    def set_transition(self, channel: int, transition: str) -> None:
        """
        Set the transition (rise/fall) time for a channel.
        
        Args:
            channel: Channel number (1 or 2)
            transition: Transition time (e.g., "1US", "10NS")
        
        Reference: :PULS:TRAN command
        """
        self.write(f":PULS:TRAN{channel} {transition}")
        self.logger.debug(f"CH{channel} transition: {transition}")
    
    def set_delay(self, channel: int, delay: str) -> None:
        """
        Set the delay for a channel.
        
        Args:
            channel: Channel number (1 or 2)
            delay: Delay time string
        
        Reference: :PULS:DEL command
        """
        self.write(f":PULS:DEL{channel} {delay}")
        self.logger.debug(f"CH{channel} delay: {delay}")
    
    # =========================================================================
    # Voltage Configuration
    # =========================================================================
    
    def set_voltage_high(self, channel: int, voltage: float) -> None:
        """
        Set the high voltage level for a channel.
        
        Args:
            channel: Channel number (1 or 2)
            voltage: High voltage in volts
        
        Reference: :VOLT:HIGH command
        """
        cmd = f":VOLT{channel}:HIGH {format_number(voltage)}"
        self.write(cmd)
        self.logger.debug(f"CH{channel} Vhigh: {format_number(voltage)}V")
    
    def set_voltage_low(self, channel: int, voltage: float) -> None:
        """
        Set the low voltage level for a channel.
        
        Args:
            channel: Channel number (1 or 2)
            voltage: Low voltage in volts
        
        Reference: :VOLT:LOW command
        """
        cmd = f":VOLT{channel}:LOW {format_number(voltage)}"
        self.write(cmd)
        self.logger.debug(f"CH{channel} Vlow: {format_number(voltage)}V")
    
    def set_polarity(self, channel: int, polarity: str = "NORM") -> None:
        """
        Set the output polarity.
        
        Args:
            channel: Channel number (1 or 2)
            polarity: "NORM" (normal) or "INV" (inverted)
        
        Reference: :OUTP:POL command
        """
        self.write(f":OUTP{channel}:POL {polarity}")
        self.logger.debug(f"CH{channel} polarity: {polarity}")
    
    # =========================================================================
    # Pattern Mode
    # =========================================================================
    
    def set_pattern_mode(self, enabled: bool) -> None:
        """
        Enable or disable digital pattern mode.
        
        Note: Disabling pattern mode may change trigger count.
        
        Args:
            enabled: True to enable, False to disable
        
        Reference: :DIG:PATT command
        """
        state = "ON" if enabled else "OFF"
        self.write(f":DIG:PATT {state}")
        self.logger.debug(f"Pattern mode: {state}")
    
    # =========================================================================
    # Common Pulse Functions
    # =========================================================================
    
    def pulse_single_channel(self, pulse_width: str, period: str = "1US",
                            rise_time: str = "1US", vhigh: float = None,
                            vlow: float = None, default: str = "low",
                            count: int = 1, channel: int = 1) -> None:
        """
        Configure and trigger a single-channel pulse.
        
        Args:
            pulse_width: Pulse width (e.g., "100NS")
            period: Pulse period (default: "1US")
            rise_time: Rise/fall time (default: "1US")
            vhigh: High voltage level in volts
            vlow: Low voltage level in volts
            default: "low" or "high" - default output state
            count: Number of pulses (default: 1)
            channel: Output channel (default: 1)
        
        Reference: Based on pulse1ch function in backup code
        """
        if vhigh is None or vlow is None:
            self.logger.error("Voltages must be specified")
            return
        
        # Configure triggering
        self.set_arm_source("MAN")
        self.set_pattern_mode(False)  # Must come before trigger count
        self.set_trigger_count(count)
        self.set_trigger_source("IMM")
        
        # Configure timing
        self.set_period(period)
        
        # Configure output
        if default == "low":
            self.set_polarity(channel, "NORM")
        else:
            self.set_polarity(channel, "INV")
        
        self.set_voltage_high(channel, vhigh)
        self.set_voltage_low(channel, vlow)
        self.set_pulse_width(channel, pulse_width)
        self.set_transition(channel, rise_time)
        
        # Enable output and trigger
        self.enable_output(channel)
        self.trigger()
        
        # Return to idle
        self.idle()
        
        self.logger.info(f"Pulse: CH{channel}, {pulse_width}, {vlow}V-{vhigh}V, x{count}")
    
    def pulse_dual_channel(self, pulse_width: str, period: str = "1US",
                          rise_time: str = "1US",
                          vhigh1: float = None, vlow1: float = None,
                          default1: str = "low",
                          vhigh2: float = None, vlow2: float = None,
                          default2: str = "low",
                          count: int = 1) -> None:
        """
        Configure and trigger a dual-channel pulse.
        
        Args:
            pulse_width: Pulse width for both channels
            period: Pulse period
            rise_time: Rise/fall time
            vhigh1, vlow1: Channel 1 voltage levels
            default1: Channel 1 default state
            vhigh2, vlow2: Channel 2 voltage levels
            default2: Channel 2 default state
            count: Number of pulses
        
        Reference: Based on pulse2ch function in backup code
        """
        # Configure triggering
        self.set_arm_source("MAN")
        self.set_pattern_mode(False)
        self.set_trigger_count(count)
        self.set_trigger_source("IMM")
        self.set_period(period)
        
        # Configure channel 1 if voltages provided
        if vhigh1 is not None and vlow1 is not None:
            if default1 == "low":
                self.set_polarity(1, "NORM")
            else:
                self.set_polarity(1, "INV")
            
            self.set_voltage_high(1, vhigh1)
            self.set_voltage_low(1, vlow1)
            self.set_pulse_width(1, pulse_width)
            self.set_transition(1, rise_time)
            self.enable_output(1)
        
        # Configure channel 2 if voltages provided
        if vhigh2 is not None and vlow2 is not None:
            if default2 == "low":
                self.set_polarity(2, "NORM")
            else:
                self.set_polarity(2, "INV")
            
            self.set_voltage_high(2, vhigh2)
            self.set_voltage_low(2, vlow2)
            self.set_pulse_width(2, pulse_width)
            self.set_transition(2, rise_time)
            self.enable_output(2)
        
        # Trigger and return to idle
        self.trigger()
        self.idle()
        
        self.logger.info(f"Dual pulse: {pulse_width}, x{count}")
    
    def pulse_stress(self, channel: int, vhigh: float, vlow: float,
                    pulse_width: str, period: str, count: int,
                    rise_time: str = "1US") -> None:
        """
        Apply stress pulses for reliability testing.
        
        Args:
            channel: Output channel
            vhigh: High voltage level
            vlow: Low voltage level
            pulse_width: Pulse width
            period: Pulse period
            count: Number of pulses
            rise_time: Rise/fall time
        """
        self.pulse_single_channel(
            pulse_width=pulse_width,
            period=period,
            rise_time=rise_time,
            vhigh=vhigh,
            vlow=vlow,
            count=count,
            channel=channel
        )
        self.logger.info(f"Stress: {count} pulses at {vhigh}V")
    
    # =========================================================================
    # Query Functions
    # =========================================================================
    
    def get_period(self) -> str:
        """Query current period setting."""
        return self.query(":PULS:PER?")
    
    def get_pulse_width(self, channel: int) -> str:
        """Query pulse width for a channel."""
        return self.query(f":PULS:WIDT{channel}?")
    
    def get_voltage_high(self, channel: int) -> float:
        """Query high voltage for a channel."""
        response = self.query(f":VOLT{channel}:HIGH?")
        try:
            return float(response.strip())
        except ValueError:
            return 0.0
    
    def get_voltage_low(self, channel: int) -> float:
        """Query low voltage for a channel."""
        response = self.query(f":VOLT{channel}:LOW?")
        try:
            return float(response.strip())
        except ValueError:
            return 0.0
    
    # =========================================================================
    # DC Mode Output
    # =========================================================================
    
    def set_dc_output(self, channel: int, voltage: float) -> None:
        """
        Set a channel to output a constant DC voltage.
        
        This configures the channel to output a steady DC level without
        any pulse generation or triggering. The channel is configured to
        output the desired voltage level by default (idle state).
        
        Args:
            channel: Channel number (1 or 2)
            voltage: DC voltage level in volts
        
        Note:
            - LOW voltage is always set to 0V (instrument requirement)
            - HIGH voltage is set to the desired voltage (or 0.001V if voltage is 0V)
            - For voltage > 0: Polarity is INV so idle state is HIGH
            - For voltage = 0: Polarity is NORM so idle state is LOW
            - Output is enabled but never triggered
            - To disable, call disable_output() or idle().
        """
        # Set LOW to 0V (always)
        self.set_voltage_low(channel, 0.0)
        
        # Set HIGH voltage
        # If voltage is 0V, set HIGH to a small value to avoid HIGH=LOW (not supported)
        if voltage == 0.0:
            high_voltage = 0.001  # Small positive value
            # Use NORM polarity so idle state is LOW (0V)
            self.set_polarity(channel, "NORM")
            self.set_voltage_high(channel, high_voltage)
            polarity_info = "NORM (idle=LOW=0V)"
        else:
            high_voltage = voltage
            # Use INV polarity so idle state is HIGH (desired voltage)
            self.set_polarity(channel, "INV")
            self.set_voltage_high(channel, voltage)
            polarity_info = f"INV (idle=HIGH={voltage}V)"
        
        # Configure for manual arm (never triggered)
        self.set_arm_source("MAN")
        self.set_trigger_count(1)
        self.set_trigger_source("IMM")
        
        # Enable output (idle state outputs desired voltage, never triggered)
        self.enable_output(channel)
        
        self.logger.info(f"CH{channel}: DC output at {voltage}V (LOW=0V, HIGH={high_voltage}V, {polarity_info}, enabled, no trigger)")

