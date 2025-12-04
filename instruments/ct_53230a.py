# -*- coding: utf-8 -*-
"""
Keysight 53230A Universal Counter Driver

GPIB commands based on 53230a_programming.pdf manual.
This instrument uses standard SCPI command syntax.

Features:
    - Frequency measurement (up to 350 MHz)
    - Period measurement
    - Time interval measurement
    - Totalize (event counting)
    - Ratio measurement
"""

from .base import InstrumentBase, format_number


class CT53230A(InstrumentBase):
    """
    Driver for Keysight 53230A Universal Counter/Timer.
    
    The 53230A is a high-performance frequency counter supporting
    frequency, period, time interval, and totalize measurements.
    
    Reference: Keysight 53230A Programming Guide (53230a_programming.pdf)
    """
    
    def __init__(self, resource_manager, address: str = "GPIB0::5::INSTR", 
                 timeout: int = 10000):
        """
        Initialize the 53230A counter.
        
        Args:
            resource_manager: PyVISA ResourceManager instance
            address: GPIB address (default: "GPIB0::5::INSTR")
            timeout: Communication timeout in ms (default: 10000)
        """
        super().__init__(resource_manager, address, "CT53230A", timeout)
    
    def reset(self) -> None:
        """Reset the counter to default settings."""
        self.write("*RST")
        self.write("*CLS")
        self.logger.info("CT53230A reset to default state")
    
    def error_query(self) -> str:
        """
        Query the error queue.
        
        Returns:
            Error code and message (e.g., '0,"No error"')
        """
        return self.query("SYST:ERR?")
    
    # =========================================================================
    # Configuration Methods
    # =========================================================================
    
    def configure_frequency(self, channel: int = 1, expected_freq: float = None,
                           resolution: float = None) -> None:
        """
        Configure the counter for frequency measurement.
        
        Args:
            channel: Input channel (1, 2, or 3)
            expected_freq: Expected frequency in Hz (for optimization)
            resolution: Measurement resolution in Hz
        
        Reference: CONFigure:FREQuency command (53230a_programming.pdf)
        """
        cmd = f"CONF:FREQ (@{channel})"
        self.write(cmd)
        
        if expected_freq is not None:
            self.write(f"SENS:FREQ:EXP1 {expected_freq}")
        
        if resolution is not None:
            self.write(f"SENS:FREQ:RES {resolution}")
        
        self.logger.info(f"Configured for frequency measurement on channel {channel}")
    
    def configure_period(self, channel: int = 1) -> None:
        """
        Configure the counter for period measurement.
        
        Args:
            channel: Input channel (1, 2, or 3)
        
        Reference: CONFigure:PERiod command
        """
        self.write(f"CONF:PER (@{channel})")
        self.logger.info(f"Configured for period measurement on channel {channel}")
    
    def configure_time_interval(self, start_channel: int = 1, 
                                stop_channel: int = 2) -> None:
        """
        Configure for time interval measurement between two channels.
        
        Args:
            start_channel: Start event channel
            stop_channel: Stop event channel
        
        Reference: CONFigure:TINTerval command
        """
        self.write(f"CONF:TINT (@{start_channel}),(@{stop_channel})")
        self.logger.info(f"Configured for time interval: CH{start_channel} to CH{stop_channel}")
    
    def configure_totalize(self, channel: int = 1) -> None:
        """
        Configure the counter for totalize (event counting) mode.
        
        Args:
            channel: Input channel (1, 2, or 3)
        
        Reference: CONFigure:TOTalize command
        """
        self.write(f"CONF:TOT:TIM (@{channel})")
        self.logger.info(f"Configured for totalize on channel {channel}")
    
    def set_gate_time(self, gate_time: float) -> None:
        """
        Set the measurement gate time.
        
        Args:
            gate_time: Gate time in seconds
        
        Reference: SENSe:FREQuency:GATE:TIME command
        """
        cmd = f"SENS:FREQ:GATE:TIME {format_number(gate_time)}"
        self.write(cmd)
        self.logger.info(f"Gate time set to {format_number(gate_time)} s")
    
    def set_trigger_level(self, channel: int, level: float) -> None:
        """
        Set the trigger level for a channel.
        
        Args:
            channel: Input channel (1, 2, or 3)
            level: Trigger level in volts
        
        Reference: INPut:LEVel command
        """
        cmd = f"INP{channel}:LEV {format_number(level)}"
        self.write(cmd)
        self.logger.info(f"Channel {channel} trigger level set to {format_number(level)} V")
    
    def set_coupling(self, channel: int, coupling: str = "AC") -> None:
        """
        Set the input coupling for a channel.
        
        Args:
            channel: Input channel (1, 2, or 3)
            coupling: "AC" or "DC"
        
        Reference: INPut:COUPling command
        """
        coupling = coupling.upper()
        if coupling not in ["AC", "DC"]:
            raise ValueError("Coupling must be 'AC' or 'DC'")
        self.write(f"INP{channel}:COUP {coupling}")
        self.logger.info(f"Channel {channel} coupling set to {coupling}")
    
    def set_impedance(self, channel: int, impedance: int = 1000000) -> None:
        """
        Set the input impedance for a channel.
        
        Args:
            channel: Input channel (1, 2, or 3)
            impedance: 50 or 1000000 (1 MOhm)
        
        Reference: INPut:IMPedance command
        """
        if impedance not in [50, 1000000]:
            raise ValueError("Impedance must be 50 or 1000000")
        self.write(f"INP{channel}:IMP {impedance}")
        self.logger.info(f"Channel {channel} impedance set to {impedance} Ohm")
    
    def set_slope(self, channel: int, slope: str = "POS") -> None:
        """
        Set the trigger slope (edge direction) for a channel.
        
        Args:
            channel: Input channel (1, 2, or 3)
            slope: "POS" (rising edge) or "NEG" (falling edge)
        
        Reference: INPut:SLOPe command
        """
        slope = slope.upper()
        if slope not in ["POS", "NEG"]:
            raise ValueError("Slope must be 'POS' or 'NEG'")
        self.write(f"INP{channel}:SLOP {slope}")
        edge_str = "rising" if slope == "POS" else "falling"
        self.logger.info(f"Channel {channel} trigger slope: {edge_str} edge")
    
    # =========================================================================
    # Measurement Methods
    # =========================================================================
    
    def measure_frequency(self, channel: int = 1, record: bool = True) -> float:
        """
        Perform a frequency measurement.
        
        Args:
            channel: Input channel (1, 2, or 3)
            record: If True, record to CSV file
            
        Returns:
            Measured frequency in Hz
        
        Reference: MEASure:FREQuency? command
        """
        response = self.query(f"MEAS:FREQ? (@{channel})")
        
        try:
            frequency = float(response.strip())
        except ValueError:
            frequency = 0.0
            self.logger.warning(f"Could not parse frequency response: {response}")
        
        if record:
            self.record_measurement("Frequency", frequency, "Hz")
        
        return frequency
    
    def measure_period(self, channel: int = 1, record: bool = True) -> float:
        """
        Perform a period measurement.
        
        Args:
            channel: Input channel (1, 2, or 3)
            record: If True, record to CSV file
            
        Returns:
            Measured period in seconds
        
        Reference: MEASure:PERiod? command
        """
        response = self.query(f"MEAS:PER? (@{channel})")
        
        try:
            period = float(response.strip())
        except ValueError:
            period = 0.0
            self.logger.warning(f"Could not parse period response: {response}")
        
        if record:
            self.record_measurement("Period", period, "s")
        
        return period
    
    def measure_time_interval(self, start_channel: int = 1, 
                             stop_channel: int = 2, record: bool = True) -> float:
        """
        Measure time interval between two channels.
        
        Args:
            start_channel: Start event channel
            stop_channel: Stop event channel
            record: If True, record to CSV file
            
        Returns:
            Time interval in seconds
        
        Reference: MEASure:TINTerval? command
        """
        response = self.query(f"MEAS:TINT? (@{start_channel}),(@{stop_channel})")
        
        try:
            interval = float(response.strip())
        except ValueError:
            interval = 0.0
            self.logger.warning(f"Could not parse time interval response: {response}")
        
        if record:
            self.record_measurement("TimeInterval", interval, "s")
        
        return interval
    
    def read_measurement(self) -> float:
        """
        Read the current measurement value.
        
        Use after configuring measurement mode.
        
        Returns:
            Measurement value
        
        Reference: READ? command
        """
        response = self.query("READ?")
        try:
            return float(response.strip())
        except ValueError:
            self.logger.warning(f"Could not parse READ response: {response}")
            return 0.0
    
    def initiate(self) -> None:
        """
        Initiate a measurement.
        
        Reference: INITiate command
        """
        self.write("INIT")
    
    def fetch(self) -> float:
        """
        Fetch the last measurement result.
        
        Returns:
            Last measurement value
        
        Reference: FETCh? command
        """
        response = self.query("FETC?")
        try:
            return float(response.strip())
        except ValueError:
            self.logger.warning(f"Could not parse FETCH response: {response}")
            return 0.0
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def abort(self) -> None:
        """
        Abort current measurement.
        
        Reference: ABORt command
        """
        self.write("ABOR")
    
    def get_sample_count(self) -> int:
        """
        Get the number of samples per measurement.
        
        Returns:
            Sample count
        
        Reference: SENSe:FREQuency:GATE:SOURce command
        """
        response = self.query("SAMP:COUN?")
        try:
            return int(float(response.strip()))
        except ValueError:
            return 1
    
    def set_sample_count(self, count: int) -> None:
        """
        Set the number of samples per measurement.
        
        Args:
            count: Number of samples (1 to 1000000)
        
        Reference: SAMPle:COUNt command
        """
        self.write(f"SAMP:COUN {count}")
        self.logger.info(f"Sample count set to {count}")
    
    def idle(self) -> None:
        """Put the counter in idle state."""
        self.abort()
        self.logger.info("CT53230A set to idle")

