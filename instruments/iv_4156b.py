# -*- coding: utf-8 -*-
"""
Agilent 4156B/C Semiconductor Parameter Analyzer Driver

GPIB commands based on gpib_4156.pdf manual.
This instrument uses FLEX command mode for most operations.

Features:
    - 4 SMU (Source/Monitor Unit) channels
    - 2 VSU (Voltage Source Unit) channels
    - Spot measurements (single point I/V)
    - Sweep measurements (I-V curves)
    - Constant current Vt extraction
    - FLEX command syntax
"""

from .base import InstrumentBase, format_number
from typing import List, Tuple, Optional


class IV4156B(InstrumentBase):
    """
    Driver for Agilent 4156B/C Semiconductor Parameter Analyzer.
    
    The 4156B is a precision semiconductor parameter analyzer with
    4 SMUs for DC characterization of transistors and other devices.
    
    Note: This instrument uses FLEX command mode. After reset,
    the 'US' command must be sent to enable FLEX mode.
    
    Reference: Agilent 4156B/C GPIB Command Reference (gpib_4156.pdf)
    """
    
    def __init__(self, resource_manager, address: str = "GPIB0::15::INSTR",
                 timeout: int = 90000):
        """
        Initialize the 4156B.
        
        Args:
            resource_manager: PyVISA ResourceManager instance
            address: GPIB address (default: "GPIB0::15::INSTR")
            timeout: Communication timeout in ms (default: 90000 for long sweeps)
        """
        super().__init__(resource_manager, address, "IV4156B", timeout)
    
    def reset(self) -> None:
        """
        Reset the instrument and enable FLEX command mode.
        
        Reference: *RST and US commands
        """
        self.write("*RST")
        self.write("US")  # Enable FLEX command mode
        self.logger.info("IV4156B reset and FLEX mode enabled")
    
    def error_query(self) -> str:
        """
        Query the error status.
        
        Returns:
            Error message string
        
        Reference: ERR? command
        """
        return self.query("ERR?")
    
    # =========================================================================
    # Channel Control
    # =========================================================================
    
    def enable_channels(self, channels: List[int]) -> None:
        """
        Enable specified SMU/VSU channels.
        
        Args:
            channels: List of channel numbers (1-4 for SMU, 21-22 for VSU)
        
        Reference: CN command
        """
        ch_str = ",".join(str(ch) for ch in channels)
        self.write(f"CN {ch_str}")
        self.logger.info(f"Enabled channels: {channels}")
    
    def disable_channels(self, channels: List[int] = None) -> None:
        """
        Disable specified channels or all channels.
        
        Args:
            channels: List of channel numbers, or None to disable all
        
        Reference: CL command
        """
        if channels is None:
            self.write("CL")  # Disable all
            self.logger.info("All channels disabled")
        else:
            ch_str = ",".join(str(ch) for ch in channels)
            self.write(f"CL {ch_str}")
            self.logger.info(f"Disabled channels: {channels}")
    
    def idle(self) -> None:
        """Set all channels to idle (disabled) state."""
        self.write("CL")
        self.logger.info("IV4156B set to idle")
    
    # =========================================================================
    # Voltage/Current Source Commands
    # =========================================================================
    
    def set_voltage(self, channel: int, voltage: float, 
                   compliance: float = 0.1, v_range: int = 0) -> None:
        """
        Set a DC voltage on a channel (force voltage mode).
        
        Args:
            channel: SMU channel number (1-4)
            voltage: Voltage to force in volts
            compliance: Current compliance in amps (default: 100mA)
            v_range: Voltage range (0=auto, 11-20 for fixed ranges)
        
        Reference: DV command - DV channel, range, voltage, compliance
        """
        cmd = f"DV {channel},{v_range},{format_number(voltage)},{format_number(compliance)}"
        self.write(cmd)
        self.logger.debug(f"CH{channel}: DV={format_number(voltage)}V, Icomp={format_number(compliance)}A")
    
    def set_current(self, channel: int, current: float,
                   compliance: float = 100.0, i_range: int = 0) -> None:
        """
        Set a DC current on a channel (force current mode).
        
        Note: The current value is negated before sending to the instrument (DI command).
        Positive current in code means current flowing into the instrument, but the
        instrument expects negative values for current sources.
        
        Args:
            channel: SMU channel number (1-4)
            current: Current to force in amps (positive = into instrument)
            compliance: Voltage compliance in volts (default: 100V)
            i_range: Current range (0=auto, 11-20 for fixed ranges)
        
        Reference: DI command - DI channel, range, current, compliance
        """
        # Negate current for instrument (positive in code = negative to instrument)
        negated_current = -current
        cmd = f"DI {channel},{i_range},{format_number(negated_current)},{format_number(compliance)}"
        self.write(cmd)
        self.logger.debug(f"CH{channel}: DI={format_number(current)}A (sent as {format_number(negated_current)}A), Vcomp={format_number(compliance)}V")
    
    def set_vsu_voltage(self, vsu_channel: int, voltage: float) -> None:
        """
        Set voltage on a VSU (Voltage Source Unit) channel.
        
        Note: Channel must already be enabled via enable_channels() before calling this.
        This method does NOT call CN to avoid duplication when channels are pre-enabled.
        
        Args:
            vsu_channel: VSU channel (21 or 22)
            voltage: Voltage to set in volts
        
        Reference: DV command for VSU
        """
        cmd = f"DV {vsu_channel},0,{format_number(voltage)}"
        self.write(cmd)
        self.logger.debug(f"VSU{vsu_channel}: {format_number(voltage)}V")
    
    # =========================================================================
    # Measurement Mode Configuration
    # =========================================================================
    
    def set_measurement_mode(self, mode: int, channels: List[int]) -> None:
        """
        Set the measurement mode.
        
        Args:
            mode: Measurement mode
                  1 = Spot measurement
                  2 = Sweep measurement
                  14 = Linear search (constant current Vt)
                  15 = Binary search
                  16 = Multi-channel sweep
            channels: List of channels to measure
        
        Reference: MM command - MM mode, channel1, channel2, ...
        """
        ch_str = ",".join(str(ch) for ch in channels)
        self.write(f"MM {mode},{ch_str}")
        self.logger.info(f"Measurement mode {mode} on channels {channels}")
    
    def set_current_range(self, channel: int, i_range: int) -> None:
        """
        Set the current measurement range.
        
        Args:
            channel: SMU channel (1-4)
            i_range: Range setting
                     11 = 1nA, 12 = 10nA, 13 = 100nA
                     14 = 1µA, 15 = 10µA, 16 = 100µA
                     17 = 1mA, 18 = 10mA, 19 = 100mA, 20 = 1A
        
        Reference: RI command
        """
        self.write(f"RI {channel},{i_range}")
    
    # =========================================================================
    # Sweep Configuration
    # =========================================================================
    
    def configure_voltage_sweep(self, channel: int, start: float, stop: float,
                                step: float, compliance: float = 0.1,
                                v_range: int = 11) -> None:
        """
        Configure a voltage sweep on a channel.
        
        Args:
            channel: SMU channel (1-4)
            start: Start voltage in volts
            stop: Stop voltage in volts
            step: Step voltage in volts
            compliance: Current compliance in amps
            v_range: Voltage range (11=auto)
        
        Reference: WV command - WV channel, mode, range, start, stop, step, Icomp
        """
        # mode=1 for linear sweep
        cmd = f"WV {channel},1,{v_range},{format_number(start)},{format_number(stop)},{format_number(step)},{format_number(compliance)}"
        self.write(cmd)
        self.logger.info(f"CH{channel}: Sweep {start}V to {stop}V, step={step}V")
    
    def configure_current_sweep(self, channel: int, start: float, stop: float,
                                step: float, compliance: float = 100.0,
                                i_range: int = 11) -> None:
        """
        Configure a current sweep on a channel.
        
        Note: Current values are negated before sending to the instrument (WI command).
        Positive current in code means current flowing into the instrument, but the
        instrument expects negative values for current sources.
        
        Args:
            channel: SMU channel (1-4)
            start: Start current in amps (positive = into instrument)
            stop: Stop current in amps (positive = into instrument)
            step: Step current in amps
            compliance: Voltage compliance in volts
            i_range: Current range
        
        Reference: WI command
        """
        # Negate start and stop for instrument (positive in code = negative to instrument)
        negated_start = -start
        negated_stop = -stop
        cmd = f"WI {channel},1,{i_range},{format_number(negated_start)},{format_number(negated_stop)},{format_number(step)},{format_number(compliance)}"
        self.write(cmd)
        self.logger.info(f"CH{channel}: Current sweep {start}A to {stop}A (sent as {format_number(negated_start)}A to {format_number(negated_stop)}A)")
    
    # =========================================================================
    # Linear Search (Constant Current Vt Measurement)
    # =========================================================================
    
    def configure_linear_search(self, measure_channel: int, polarity: int,
                                i_range: int, target_current: float) -> None:
        """
        Configure linear search for constant current Vt measurement.
        
        Args:
            measure_channel: Channel to measure current on
            polarity: 0=negative, 1=positive target current
            i_range: Current measurement range (11-20)
            target_current: Target current value in amps
        
        Reference: LGI command
        """
        cmd = f"LGI {measure_channel},{polarity},{i_range},{format_number(target_current)}"
        self.write(cmd)
        self.logger.info(f"Linear search: CH{measure_channel}, Itarget={format_number(target_current)}A")
    
    def configure_linear_search_voltage(self, sweep_channel: int, v_range: int,
                                        start: float, stop: float, step: float,
                                        compliance: float = 0.1) -> None:
        """
        Configure the voltage sweep for linear search.
        
        Args:
            sweep_channel: Channel for voltage sweep
            v_range: Voltage range
            start: Start voltage in volts
            stop: Stop voltage in volts
            step: Step voltage in volts
            compliance: Current compliance in amps
        
        Reference: LSV command
        """
        cmd = f"LSV {sweep_channel},{v_range},{format_number(start)},{format_number(stop)},{format_number(step)},{format_number(compliance)}"
        self.write(cmd)
    
    def set_linear_search_output(self, format_mode: int) -> None:
        """
        Set linear search output format.
        
        Args:
            format_mode: Output format (0=data only, 1=with status)
        
        Reference: LSVM command
        """
        self.write(f"LSVM {format_mode}")
    
    def set_linear_search_timing(self, hold: float = 0, delay: float = 0) -> None:
        """
        Set linear search hold and delay times.
        
        Args:
            hold: Hold time in seconds
            delay: Delay time in seconds
        
        Reference: LSTM command
        """
        self.write(f"LSTM {hold},{delay}")
    
    # =========================================================================
    # Measurement Execution
    # =========================================================================
    
    def execute_measurement(self) -> None:
        """
        Execute the configured measurement.
        
        Reference: XE command
        """
        self.write("XE")
        self.logger.info("Measurement executed")
    
    def read_measurement_data(self) -> str:
        """
        Read the measurement data buffer.
        
        Returns:
            Raw measurement data string
        
        Reference: RMD? command
        """
        self.write("RMD?")
        return self.read()
    
    # =========================================================================
    # Common Measurement Functions
    # =========================================================================
    
    def spot_4terminal(self, vd: float, vg: float, vb: float = 0,
                       measure_channel: int = 4, record: bool = True) -> float:
        """
        Perform a 4-terminal spot drain current measurement (for MOSFETs).
        
        Typical connection:
            CH1 = Bulk, CH2 = Gate, CH3 = Source, CH4 = Drain
        
        Args:
            vd: Drain voltage in volts
            vg: Gate voltage in volts
            vb: Bulk voltage in volts (default: 0)
            measure_channel: Channel to measure current (default: 4 for drain)
            record: If True, record to CSV file
            
        Returns:
            Measured drain current in amps
        
        Reference: Based on backup code spot_4t function
        """
        # Enable all 4 SMU channels
        self.enable_channels([1, 2, 3, 4])
        
        # Set measurement mode: spot measurement on specified channel
        self.set_measurement_mode(1, [measure_channel])
        
        # Apply voltages
        self.set_voltage(1, vb, compliance=0.1)      # Bulk
        self.set_voltage(2, vg, compliance=0.1)      # Gate
        self.set_voltage(3, 0, compliance=0.1)       # Source (ground)
        self.set_voltage(4, vd, compliance=0.1)      # Drain
        
        # Execute measurement
        self.execute_measurement()
        
        # Read result
        data = self.read_measurement_data()
        
        # Parse current value from response (format: ...I<value>)
        try:
            current = float(data.split("I")[1].strip())
        except (IndexError, ValueError):
            current = 0.0
            self.logger.warning(f"Could not parse current from: {data}")
        
        # Disable channels
        self.idle()
        
        if record:
            self.record_measurement("SpotCurrent_4T", current, "A")
        
        return current
    
    def spot_2terminal(self, voltage: float, measure_channel: int = 4,
                       record: bool = True) -> float:
        """
        Perform a 2-terminal spot current measurement.
        
        Args:
            voltage: Voltage to apply in volts
            measure_channel: Channel to measure current (default: 4)
            record: If True, record to CSV file
            
        Returns:
            Measured current in amps
        """
        # Enable channels 3 and 4
        self.enable_channels([3, 4])
        
        # Set measurement mode
        self.set_measurement_mode(1, [measure_channel])
        
        # Apply voltages
        self.set_voltage(3, 0, compliance=0.1)
        self.set_voltage(4, voltage, compliance=0.1)
        
        # Execute measurement
        self.execute_measurement()
        
        # Read result
        data = self.read_measurement_data()
        
        try:
            current = float(data.split("I")[1].strip())
        except (IndexError, ValueError):
            current = 0.0
            self.logger.warning(f"Could not parse current from: {data}")
        
        self.idle()
        
        if record:
            self.record_measurement("SpotCurrent_2T", current, "A")
        
        return current
    
    def measure_vt_constant_current(self, vd: float, target_current: float,
                                    vg_start: float, vg_stop: float, 
                                    vg_step: float, polarity: int = 1,
                                    record: bool = True) -> float:
        """
        Measure threshold voltage using constant current method.
        
        Args:
            vd: Drain voltage in volts
            target_current: Target drain current for Vt definition (amps)
            vg_start: Gate voltage sweep start (volts)
            vg_stop: Gate voltage sweep stop (volts)
            vg_step: Gate voltage step (volts)
            polarity: 0=negative current, 1=positive current
            record: If True, record to CSV file
            
        Returns:
            Threshold voltage in volts
        
        Reference: Based on meas_ccvt function in backup code
        """
        # Enable channels
        self.enable_channels([1, 2, 3, 4])
        
        # Set linear search mode
        self.set_measurement_mode(14, [])
        self.set_linear_search_output(0)
        self.set_linear_search_timing(0, 0)
        
        # Configure search parameters
        i_range = 11  # Auto range
        self.configure_linear_search(4, polarity, i_range, target_current)
        self.configure_linear_search_voltage(2, 11, vg_start, vg_stop, vg_step, 0.1)
        
        # Set fixed biases
        self.set_voltage(4, vd, compliance=0.1)  # Drain
        self.set_voltage(3, 0, compliance=0.1)   # Source
        self.set_voltage(1, 0, compliance=0.1)   # Bulk
        
        # Wait mode
        self.write("WM 2,2")
        
        # Execute
        self.execute_measurement()
        
        # Read result
        data = self.read_measurement_data()
        
        # Parse Vt from response
        try:
            parts = data.split(",")
            if len(parts) >= 2:
                vt_part = parts[1].split("v")
                if len(vt_part) >= 2:
                    vt = float(vt_part[1].strip())
                else:
                    vt = float("nan")
            else:
                vt = float("nan")
        except (IndexError, ValueError):
            vt = float("nan")
            self.logger.warning(f"Could not parse Vt from: {data}")
        
        self.idle()
        
        if record:
            self.record_measurement("Vt_ConstCurrent", vt, "V")
        
        return vt
    
    def sweep_iv(self, vd: float, vg_start: float, vg_stop: float, vg_step: float,
                 vb: float = 0) -> str:
        """
        Perform an Id-Vg sweep measurement.
        
        Args:
            vd: Drain voltage (constant)
            vg_start: Gate voltage start
            vg_stop: Gate voltage stop
            vg_step: Gate voltage step
            vb: Bulk voltage (default: 0)
            
        Returns:
            Raw measurement data string
        
        Reference: Based on sweep4t function in backup code
        """
        self.enable_channels([1, 2, 3, 4])
        
        # Set sweep measurement mode
        self.set_measurement_mode(2, [4])  # Measure channel 4 (drain)
        
        # Configure sweep on gate
        self.configure_voltage_sweep(2, vg_start, vg_stop, vg_step)
        
        # Fixed voltages
        self.set_voltage(1, vb, compliance=0.1)     # Bulk
        self.set_voltage(3, 0, compliance=0.1)      # Source
        self.set_voltage(4, vd, compliance=0.1)     # Drain
        
        # Set measurement range
        self.set_current_range(4, 12)  # 10nA range
        
        # Execute
        self.execute_measurement()
        
        # Read data
        data = self.read_measurement_data()
        
        self.idle()
        
        return data

