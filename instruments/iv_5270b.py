# -*- coding: utf-8 -*-
"""
Keysight E5270B Precision IV Analyzer Driver

GPIB commands based on E5270_programming.pdf manual.
This instrument uses a combination of FLEX-like commands and SCPI.

Features:
    - 8 SMU slots (expandable)
    - High-resolution current measurement
    - Linear and binary search for Vt measurement
    - Multi-channel sweep capability
    - High-speed sampling mode
"""

from .base import InstrumentBase, format_number
from typing import List, Optional, Tuple


class IV5270B(InstrumentBase):
    """
    Driver for Keysight E5270B Precision IV Analyzer.
    
    The E5270B is a modular mainframe supporting multiple SMU modules
    for precise semiconductor parameter measurements.
    
    Reference: Keysight E5270B Programming Guide (E5270_programming.pdf)
    """
    
    def __init__(self, resource_manager, address: str = "GPIB0::17::INSTR",
                 timeout: int = 20000):
        """
        Initialize the E5270B.
        
        Args:
            resource_manager: PyVISA ResourceManager instance
            address: GPIB address (default: "GPIB0::17::INSTR")
            timeout: Communication timeout in ms (default: 20000)
        """
        super().__init__(resource_manager, address, "IV5270B", timeout)
    
    def reset(self) -> None:
        """Reset the instrument to default state."""
        self.write("*RST")
        self.write("*CLS")
        self.logger.info("IV5270B reset to default state")
    
    def error_query(self) -> str:
        """
        Query the error queue.
        
        Returns detailed error message if an error exists.
        
        Returns:
            Error message string
        
        Reference: ERR? and EMG? commands
        """
        response = self.query("ERR?")
        error_code = response.split(",")[0].strip()
        
        if error_code != "0":
            message = self.query(f"EMG? {error_code}")
            return f"{error_code}: {message}"
        else:
            return "0: No error"
    
    # =========================================================================
    # Channel Control
    # =========================================================================
    
    def enable_channels(self, channels: List[int]) -> None:
        """
        Enable specified SMU channels.
        
        Args:
            channels: List of channel numbers (1-8 depending on configuration)
        
        Reference: CN command
        """
        ch_str = ",".join(str(ch) for ch in channels)
        self.write(f"CN {ch_str}")
        self.logger.info(f"Enabled channels: {channels}")
    
    def disable_channels(self, channels: List[int] = None) -> None:
        """
        Disable specified channels or all channels.
        
        Args:
            channels: List of channel numbers, or None for all
        
        Reference: CL command
        """
        if channels is None:
            self.write("CL")
            self.logger.info("All channels disabled")
        else:
            ch_str = ",".join(str(ch) for ch in channels)
            self.write(f"CL {ch_str}")
            self.logger.info(f"Disabled channels: {channels}")
    
    def idle(self) -> None:
        """Set all channels to idle (disabled) state."""
        self.write("CL")
        self.logger.info("IV5270B set to idle")
    
    # =========================================================================
    # Voltage/Current Source Commands
    # =========================================================================
    
    def set_voltage(self, channel: int, voltage: float,
                   compliance: float = 0.1, v_range: int = 0) -> None:
        """
        Set a DC voltage on a channel.
        
        Args:
            channel: SMU channel number
            voltage: Voltage to force in volts
            compliance: Current compliance in amps
            v_range: Voltage range (0=auto, 11-20 for fixed)
        
        Reference: DV command - DV channel, range, voltage, compliance
        """
        cmd = f"DV {channel},{v_range},{format_number(voltage)},{format_number(compliance)}"
        self.write(cmd)
        self.logger.debug(f"CH{channel}: DV={format_number(voltage)}V, Icomp={format_number(compliance)}A")
    
    def set_current(self, channel: int, current: float,
                   compliance: float = 1.0, i_range: int = 0) -> None:
        """
        Set a DC current on a channel.
        
        Note: The current value is negated before sending to the instrument (DI command).
        Positive current in code means current flowing into the instrument, but the
        instrument expects negative values for current sources.
        
        Args:
            channel: SMU channel number
            current: Current to force in amps (positive = into instrument)
            compliance: Voltage compliance in volts
            i_range: Current range (0=auto)
        
        Reference: DI command - DI channel, range, current, compliance
        """
        # Negate current for instrument (positive in code = negative to instrument)
        negated_current = -current
        cmd = f"DI {channel},{i_range},{format_number(negated_current)},{format_number(compliance)}"
        self.write(cmd)
        self.logger.debug(f"CH{channel}: DI={format_number(current)}A (sent as {format_number(negated_current)}A), Vcomp={format_number(compliance)}V")
    
    def set_series_resistor(self, channel: int, enabled: bool) -> None:
        """
        Enable or disable series resistor on a channel.
        
        The series resistor (1 MOhm) can be inserted in series with
        the SMU output for high-impedance applications.
        
        Args:
            channel: SMU channel number
            enabled: True to enable series resistor, False to disable
        
        Reference: SSR command - SSR channel, mode (0=off, 1=on)
        """
        mode = 1 if enabled else 0
        self.write(f"SSR {channel},{mode}")
        state_str = "enabled" if enabled else "disabled"
        self.logger.info(f"CH{channel}: Series resistor {state_str}")
    
    # =========================================================================
    # Measurement Mode Configuration
    # =========================================================================
    
    def set_measurement_mode(self, mode: int, channels: List[int] = None) -> None:
        """
        Set the measurement mode.
        
        Args:
            mode: Measurement mode
                  1 = Spot measurement
                  2 = Sweep measurement
                  14 = Linear search
                  15 = Binary search
                  16 = Multi-channel sweep
            channels: List of measurement channels
        
        Reference: MM command
        """
        if channels:
            ch_str = ",".join(str(ch) for ch in channels)
            self.write(f"MM {mode},{ch_str}")
        else:
            self.write(f"MM {mode}")
        self.logger.info(f"Measurement mode set to {mode}")
    
    def set_current_range(self, channel: int, i_range: int) -> None:
        """
        Set the current measurement range.
        
        Args:
            channel: SMU channel
            i_range: Range (11=1nA to 20=1A, or -11 to -20 for limited auto)
        
        Reference: RI command
        """
        self.write(f"RI {channel},{i_range}")
    
    def set_voltage_range(self, channel: int, v_range: int) -> None:
        """
        Set the voltage measurement range.
        
        Args:
            channel: SMU channel
            v_range: Range (11=2V, 12=20V, 13=40V, etc.)
        
        Reference: RV command
        """
        self.write(f"RV {channel},{v_range}")
    
    # =========================================================================
    # Sweep Configuration
    # =========================================================================
    
    def configure_voltage_sweep(self, channel: int, start: float, stop: float,
                                steps: int, compliance: float = 0.1,
                                mode: int = 1, v_range: int = 0) -> None:
        """
        Configure a voltage sweep.
        
        Args:
            channel: SMU channel
            start: Start voltage
            stop: Stop voltage
            steps: Number of steps
            compliance: Current compliance
            mode: Sweep mode (1=linear, 2=log, 3=linear 2-way, 4=log 2-way)
            v_range: Voltage range
        
        Reference: WV command - WV channel, mode, range, start, stop, steps, Icomp
        """
        cmd = f"WV {channel},{mode},{v_range},{format_number(start)},{format_number(stop)},{steps},{format_number(compliance)}"
        self.write(cmd)
        self.logger.info(f"CH{channel}: Sweep {format_number(start)}V to {format_number(stop)}V in {steps} steps")
    
    def configure_current_sweep(self, channel: int, start: float, stop: float,
                                steps: int, compliance: float = 2.0,
                                mode: int = 1, i_range: int = 0) -> None:
        """
        Configure a current sweep.
        
        Note: Current values are negated before sending to the instrument (WI command).
        Positive current in code means current flowing into the instrument, but the
        instrument expects negative values for current sources.
        
        Args:
            channel: SMU channel
            start: Start current (positive = into instrument)
            stop: Stop current (positive = into instrument)
            steps: Number of steps
            compliance: Voltage compliance
            mode: Sweep mode (1=linear, 2=log, 3=linear 2-way, 4=log 2-way)
            i_range: Current range (0=auto)
        
        Reference: WI command - WI channel, mode, range, start, stop, steps, Vcomp
        """
        # Negate start and stop for instrument (positive in code = negative to instrument)
        negated_start = -start
        negated_stop = -stop
        cmd = f"WI {channel},{mode},{i_range},{format_number(negated_start)},{format_number(negated_stop)},{steps},{format_number(compliance)}"
        self.write(cmd)
        self.logger.info(f"CH{channel}: Current sweep {format_number(start)}A to {format_number(stop)}A (sent as {format_number(negated_start)}A to {format_number(negated_stop)}A) in {steps} steps")
    
    # =========================================================================
    # Linear Search (Constant Current Vt)
    # =========================================================================
    
    def configure_linear_search(self, measure_channel: int, polarity: int,
                                i_range: int, target_current: float) -> None:
        """
        Configure linear search for constant current measurement.
        
        Args:
            measure_channel: Channel to measure current
            polarity: 0=negative, 1=positive
            i_range: Current range
            target_current: Target current in amps
        
        Reference: LGI command
        """
        cmd = f"LGI {measure_channel},{polarity},{i_range},{format_number(target_current)}"
        self.write(cmd)
    
    def configure_linear_search_voltage(self, sweep_channel: int, v_range: int,
                                        start: float, stop: float, step: float,
                                        compliance: float) -> None:
        """
        Configure voltage sweep for linear search.
        
        Reference: LSV command
        """
        cmd = f"LSV {sweep_channel},{v_range},{format_number(start)},{format_number(stop)},{format_number(step)},{format_number(compliance)}"
        self.write(cmd)
    
    def set_linear_search_output(self, format_mode: int) -> None:
        """
        Set linear search output format.
        
        Args:
            format_mode: 0=data only, 1=with status
        
        Reference: LSVM command
        """
        self.write(f"LSVM {format_mode}")
    
    def set_linear_search_timing(self, hold: float, delay: float) -> None:
        """
        Set linear search timing.
        
        Reference: LSTM command
        """
        cmd = f"LSTM {format_number(hold)},{format_number(delay)}"
        self.write(cmd)
    
    def set_linear_search_abort(self, mode: int, post_condition: int) -> None:
        """
        Set linear search abort and post-output conditions.
        
        Args:
            mode: Abort mode (0=never, 1=on compliance, 2=on target, 3=both)
            post_condition: Output after abort (0=start, 1=stop, 2=hold, 3=zero)
        
        Reference: LSM command
        """
        self.write(f"LSM {mode},{post_condition}")
    
    # =========================================================================
    # Binary Search
    # =========================================================================
    
    def configure_binary_search(self, measure_channel: int, polarity: int,
                                i_range: int, target_current: float) -> None:
        """
        Configure binary search for constant current measurement.
        
        Reference: BGI command
        """
        cmd = f"BGI {measure_channel},{polarity},{i_range},{format_number(target_current)}"
        self.write(cmd)
    
    def configure_binary_search_voltage(self, sweep_channel: int, v_range: int,
                                        start: float, stop: float, step: float,
                                        compliance: float) -> None:
        """
        Configure voltage for binary search.
        
        Reference: BSV command
        """
        cmd = f"BSV {sweep_channel},{v_range},{format_number(start)},{format_number(stop)},{format_number(step)},{format_number(compliance)}"
        self.write(cmd)
    
    def set_binary_search_output(self, format_mode: int) -> None:
        """Set binary search output format. Reference: BSVM command"""
        self.write(f"BSVM {format_mode}")
    
    def set_binary_search_timing(self, hold: float, delay: float) -> None:
        """Set binary search timing. Reference: BST command"""
        cmd = f"BST {format_number(hold)},{format_number(delay)}"
        self.write(cmd)
    
    def set_binary_search_abort(self, mode: int, abort_cond: int, 
                                post_condition: int) -> None:
        """
        Set binary search abort conditions.
        
        Reference: BSM command
        """
        self.write(f"BSM {mode},{abort_cond},{post_condition}")
    
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
    
    def read_data(self) -> str:
        """
        Read measurement data from the instrument.
        
        Returns:
            Raw data string
        """
        return self.read()
    
    # =========================================================================
    # Common Measurement Functions
    # =========================================================================
    
    def spot_4terminal(self, vd: float, vg: float, vb: float = 0,
                       record: bool = True) -> float:
        """
        Perform a 4-terminal spot drain current measurement.
        
        Args:
            vd: Drain voltage
            vg: Gate voltage
            vb: Bulk voltage (default: 0)
            record: If True, record to CSV
            
        Returns:
            Drain current in amps
        """
        self.enable_channels([1, 2, 3, 4])
        self.set_measurement_mode(1, [4])
        
        self.set_voltage(1, vb, compliance=0.1)
        self.set_voltage(2, vg, compliance=0.1)
        self.set_voltage(3, 0, compliance=0.1)
        self.set_voltage(4, vd, compliance=0.1)
        
        self.execute_measurement()
        data = self.read_data()
        
        try:
            current = float(data.split("I")[1].strip())
        except (IndexError, ValueError):
            current = 0.0
            self.logger.warning(f"Could not parse current: {data}")
        
        self.idle()
        
        if record:
            self.record_measurement("SpotCurrent_4T", current, "A")
        
        return current
    
    def spot_2terminal(self, voltage: float, record: bool = True) -> float:
        """
        Perform a 2-terminal spot current measurement.
        
        Args:
            voltage: Voltage to apply
            record: If True, record to CSV
            
        Returns:
            Current in amps
        """
        self.enable_channels([3, 4])
        self.set_measurement_mode(1, [3])
        
        self.set_voltage(4, 0, compliance=0.1)
        self.set_voltage(3, voltage, compliance=0.1)
        
        self.execute_measurement()
        data = self.read_data()
        
        try:
            current = float(data.split("I")[1].strip())
        except (IndexError, ValueError):
            current = 0.0
        
        self.idle()
        
        if record:
            self.record_measurement("SpotCurrent_2T", current, "A")
        
        return current
    
    def measure_vt_constant_current(self, vd: float, target_current: float,
                                    vg_start: float, vg_stop: float,
                                    vg_step: float, mode: str = "linear",
                                    record: bool = True) -> float:
        """
        Measure Vt using constant current method.
        
        Args:
            vd: Drain voltage
            target_current: Target current for Vt
            vg_start: Gate sweep start
            vg_stop: Gate sweep stop
            vg_step: Gate sweep step
            mode: "linear" or "binary" search
            record: If True, record to CSV
            
        Returns:
            Threshold voltage in volts
        """
        polarity = 1 if vg_start < vg_stop else 0
        
        if mode == "linear":
            self.set_measurement_mode(14, [])
            self.set_linear_search_output(1)
            self.set_linear_search_timing(0, 0)
            self.configure_linear_search(4, polarity, 11, target_current)
            self.configure_linear_search_voltage(2, 11, vg_start, vg_stop, 
                                                 vg_step, 0.1)
            self.set_linear_search_abort(2, 3)
        elif mode == "binary":
            self.set_measurement_mode(15, [])
            self.set_binary_search_output(1)
            self.set_binary_search_timing(0, 0)
            self.configure_binary_search(4, polarity, 11, target_current)
            self.configure_binary_search_voltage(2, 11, vg_start, vg_stop,
                                                 vg_step, 0.1)
            self.set_binary_search_abort(0, 2, 3)
        
        # Set fixed biases (skip CN since channels are already enabled)
        self.set_bias([0, None, 0, vd], [None, None, None, None], [2], skip_cn=True)
        
        self.execute_measurement()
        data = self.read_data()
        
        try:
            vt = float(data.split(",")[0].split("V")[1].strip())
        except (IndexError, ValueError):
            vt = float("nan")
            self.logger.warning(f"Could not parse Vt: {data}")
        
        self.idle()
        
        if record:
            self.record_measurement("Vt_ConstCurrent", vt, "V")
        
        return vt
    
    def set_bias(self, voltages: List[Optional[float]], 
                 currents: List[Optional[float]],
                 others: List[int], skip_cn: bool = False) -> None:
        """
        Set bias conditions on multiple channels.
        
        Args:
            voltages: List of voltages (None to skip)
            currents: List of currents (None to skip)
            others: List of channels in sweep/search mode
            skip_cn: If True, skip CN command (channels already enabled)
        """
        all_ch = list(others)
        all_force = []
        
        for ch, volt in enumerate(voltages, start=1):
            if volt is not None:
                all_ch.append(ch)
                all_force.append(f"DV {ch},0,{format_number(volt)},{format_number(100E-3)}")
        
        for ch, current in enumerate(currents, start=1):
            if current is not None:
                all_ch.append(ch)
                # Negate current for instrument (positive in code = negative to instrument)
                negated_current = -current
                all_force.append(f"DI {ch},0,{format_number(negated_current)},{format_number(1.0)}")
        
        if not skip_cn:
            channels = ",".join(str(i) for i in all_ch)
            self.write(f"CN {channels}")
        
        for cmd in all_force:
            self.write(cmd)
    
    # =========================================================================
    # High-Speed Sampling
    # =========================================================================
    
    def configure_high_speed_sampling(self, voltage: float, samples: int) -> None:
        """
        Configure high-speed sampling mode.
        
        Args:
            voltage: Bias voltage
            samples: Number of samples
        
        Reference: Based on high_speed_sample_setup in backup code
        """
        self.enable_channels([1, 2, 3, 4, 6])
        
        # Set compliance measurement mode
        for ch in [1, 2, 3]:
            self.write(f"CMM {ch},2")
            self.write(f"AAD {ch},0")
            self.write(f"RV {ch},-11")
        
        # Set integration time
        self.write("AIT 0,1,1")
        
        # Multi-channel sweep mode
        self.set_measurement_mode(16, [1, 2, 3])
        
        # Set bias
        self.set_voltage(4, voltage, compliance=0.1)  # voltage is already a float parameter
        
        # Configure sweep trigger
        self.write(f"WV 6,1,0,0,1,{samples}")
        
        self.logger.info(f"High-speed sampling configured: {samples} samples at {voltage}V")
    
    def sample(self) -> str:
        """
        Execute measurement and return data.
        
        Returns:
            Measurement data string
        """
        self.execute_measurement()
        return self.read_data()

