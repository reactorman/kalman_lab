# -*- coding: utf-8 -*-
"""
Stanford Research Systems SR570 Low-Noise Current Preamplifier Driver

Commands based on SR570m.pdf manual.
This instrument uses serial commands via NI GPIB-Serial converter.

Features:
    - Current gains from 1 pA/V to 1 mA/V
    - Low-noise and high-bandwidth modes
    - Adjustable filters (highpass and lowpass)
    - Input offset current
    - Bias voltage output
"""

from .base import InstrumentBase


class SR570(InstrumentBase):
    """
    Driver for SRS SR570 Low-Noise Current Preamplifier.
    
    The SR570 is a low-noise current preamplifier with programmable
    sensitivity, filtering, and bias voltage output.
    
    Note: Controlled via NI GPIB-Serial converter. Commands are ASCII
    strings terminated with carriage return.
    
    Reference: SRS SR570 Operating Manual (SR570m.pdf)
    """
    
    # Sensitivity (gain) settings: index -> pA/V
    SENSITIVITY_MAP = {
        0: 1e-12,    # 1 pA/V
        1: 2e-12,    # 2 pA/V
        2: 5e-12,    # 5 pA/V
        3: 10e-12,   # 10 pA/V
        4: 20e-12,   # 20 pA/V
        5: 50e-12,   # 50 pA/V
        6: 100e-12,  # 100 pA/V
        7: 200e-12,  # 200 pA/V
        8: 500e-12,  # 500 pA/V
        9: 1e-9,     # 1 nA/V
        10: 2e-9,    # 2 nA/V
        11: 5e-9,    # 5 nA/V
        12: 10e-9,   # 10 nA/V
        13: 20e-9,   # 20 nA/V
        14: 50e-9,   # 50 nA/V
        15: 100e-9,  # 100 nA/V
        16: 200e-9,  # 200 nA/V
        17: 500e-9,  # 500 nA/V
        18: 1e-6,    # 1 µA/V
        19: 2e-6,    # 2 µA/V
        20: 5e-6,    # 5 µA/V
        21: 10e-6,   # 10 µA/V
        22: 20e-6,   # 20 µA/V
        23: 50e-6,   # 50 µA/V
        24: 100e-6,  # 100 µA/V
        25: 200e-6,  # 200 µA/V
        26: 500e-6,  # 500 µA/V
        27: 1e-3,    # 1 mA/V
    }
    
    # Filter frequency settings (Hz) for lowpass
    LOWPASS_FREQ_MAP = {
        0: 0.03, 1: 0.1, 2: 0.3, 3: 1, 4: 3,
        5: 10, 6: 30, 7: 100, 8: 300, 9: 1000,
        10: 3000, 11: 10000, 12: 30000, 13: 100000, 14: 300000, 15: 1000000
    }
    
    # Filter frequency settings for highpass
    HIGHPASS_FREQ_MAP = {
        0: 0.03, 1: 0.1, 2: 0.3, 3: 1, 4: 3,
        5: 10, 6: 30, 7: 100, 8: 300, 9: 1000,
        10: 3000, 11: 10000
    }
    
    def __init__(self, resource_manager, address: str = "GPIB0::8::INSTR",
                 timeout: int = 5000):
        """
        Initialize the SR570.
        
        Args:
            resource_manager: PyVISA ResourceManager instance
            address: GPIB address of the GPIB-Serial converter
            timeout: Communication timeout in ms
        """
        super().__init__(resource_manager, address, "SR570", timeout)
    
    def reset(self) -> None:
        """
        Reset the SR570 to default settings.
        
        Reference: *RST command
        """
        self.write("*RST")
        self.logger.info("SR570 reset to defaults")
    
    def idn_query(self) -> str:
        """
        Query instrument identification.
        
        Note: SR570 may not support standard *IDN? query.
        Returns a constructed identification string.
        """
        # SR570 may not support *IDN?, return known identity
        return "Stanford Research Systems,SR570,N/A,N/A"
    
    # =========================================================================
    # Sensitivity (Gain) Control
    # =========================================================================
    
    def set_sensitivity(self, index: int) -> None:
        """
        Set the current sensitivity (gain).
        
        Args:
            index: Sensitivity index (0-27)
                   0 = 1 pA/V, 27 = 1 mA/V
        
        Reference: SENS command
        """
        if not 0 <= index <= 27:
            raise ValueError("Sensitivity index must be 0-27")
        self.write(f"SENS {index}")
        sens = self.SENSITIVITY_MAP.get(index, "unknown")
        self.logger.info(f"Sensitivity set to index {index} ({sens} A/V)")
    
    def set_sensitivity_value(self, amps_per_volt: float) -> None:
        """
        Set sensitivity by value (finds closest setting).
        
        Args:
            amps_per_volt: Desired sensitivity in A/V
        """
        # Find closest match
        closest_idx = min(self.SENSITIVITY_MAP.keys(),
                         key=lambda k: abs(self.SENSITIVITY_MAP[k] - amps_per_volt))
        self.set_sensitivity(closest_idx)
    
    # =========================================================================
    # Filter Control
    # =========================================================================
    
    def set_filter_type(self, filter_type: int) -> None:
        """
        Set the filter type.
        
        Args:
            filter_type: 0=6dB highpass, 1=12dB highpass,
                        2=6dB bandpass, 3=6dB lowpass,
                        4=12dB lowpass, 5=none
        
        Reference: FLTT command
        """
        if not 0 <= filter_type <= 5:
            raise ValueError("Filter type must be 0-5")
        self.write(f"FLTT {filter_type}")
        types = ["6dB HP", "12dB HP", "6dB BP", "6dB LP", "12dB LP", "None"]
        self.logger.info(f"Filter type: {types[filter_type]}")
    
    def set_lowpass_frequency(self, index: int) -> None:
        """
        Set the lowpass filter cutoff frequency.
        
        Args:
            index: Frequency index (0-15)
                   0 = 0.03 Hz, 15 = 1 MHz
        
        Reference: LFRQ command
        """
        if not 0 <= index <= 15:
            raise ValueError("Lowpass frequency index must be 0-15")
        self.write(f"LFRQ {index}")
        freq = self.LOWPASS_FREQ_MAP.get(index, "unknown")
        self.logger.info(f"Lowpass frequency: {freq} Hz")
    
    def set_highpass_frequency(self, index: int) -> None:
        """
        Set the highpass filter cutoff frequency.
        
        Args:
            index: Frequency index (0-11)
                   0 = 0.03 Hz, 11 = 10 kHz
        
        Reference: HFRQ command
        """
        if not 0 <= index <= 11:
            raise ValueError("Highpass frequency index must be 0-11")
        self.write(f"HFRQ {index}")
        freq = self.HIGHPASS_FREQ_MAP.get(index, "unknown")
        self.logger.info(f"Highpass frequency: {freq} Hz")
    
    # =========================================================================
    # Gain Mode Control
    # =========================================================================
    
    def set_gain_mode(self, mode: int) -> None:
        """
        Set the gain mode.
        
        Args:
            mode: 0=Low Noise, 1=High Bandwidth, 2=Low Drift
        
        Reference: GNMD command
        """
        if not 0 <= mode <= 2:
            raise ValueError("Gain mode must be 0-2")
        self.write(f"GNMD {mode}")
        modes = ["Low Noise", "High Bandwidth", "Low Drift"]
        self.logger.info(f"Gain mode: {modes[mode]}")
    
    # =========================================================================
    # Input Offset Control
    # =========================================================================
    
    def set_input_offset_on(self, enabled: bool) -> None:
        """
        Enable or disable input offset current.
        
        Args:
            enabled: True to enable, False to disable
        
        Reference: IOON command
        """
        state = 1 if enabled else 0
        self.write(f"IOON {state}")
        self.logger.info(f"Input offset: {'ON' if enabled else 'OFF'}")
    
    def set_input_offset_sign(self, positive: bool) -> None:
        """
        Set input offset current sign.
        
        Args:
            positive: True for positive, False for negative
        
        Reference: IOSN command
        """
        sign = 1 if positive else 0
        self.write(f"IOSN {sign}")
    
    def set_input_offset_level(self, index: int) -> None:
        """
        Set input offset current level.
        
        Args:
            index: Offset level index (instrument-specific)
        
        Reference: IOLVL command
        """
        self.write(f"IOLVL {index}")
    
    # =========================================================================
    # Bias Voltage Control
    # =========================================================================
    
    def set_bias_voltage_on(self, enabled: bool) -> None:
        """
        Enable or disable bias voltage output.
        
        Args:
            enabled: True to enable, False to disable
        
        Reference: BSON command
        """
        state = 1 if enabled else 0
        self.write(f"BSON {state}")
        self.logger.info(f"Bias voltage: {'ON' if enabled else 'OFF'}")
    
    def set_bias_voltage(self, voltage: float) -> None:
        """
        Set the bias voltage level.
        
        Args:
            voltage: Bias voltage in volts (-5V to +5V)
        
        Reference: BSLV command
        """
        if not -5.0 <= voltage <= 5.0:
            raise ValueError("Bias voltage must be -5V to +5V")
        # Convert to millivolts for command
        mv = int(voltage * 1000)
        self.write(f"BSLV {mv}")
        self.logger.info(f"Bias voltage: {voltage} V")
    
    # =========================================================================
    # Blanking Control
    # =========================================================================
    
    def set_blank_on(self, enabled: bool) -> None:
        """
        Enable or disable output blanking.
        
        Args:
            enabled: True to blank output, False for normal
        
        Reference: BLNK command
        """
        state = 1 if enabled else 0
        self.write(f"BLNK {state}")
        self.logger.info(f"Output blank: {'ON' if enabled else 'OFF'}")
    
    # =========================================================================
    # Common Configurations
    # =========================================================================
    
    def configure_low_noise(self, sensitivity_index: int = 12,
                           lowpass_freq_index: int = 9) -> None:
        """
        Configure for low-noise current measurement.
        
        Args:
            sensitivity_index: Sensitivity setting (default: 10 nA/V)
            lowpass_freq_index: Lowpass filter frequency (default: 1 kHz)
        """
        self.reset()
        self.set_gain_mode(0)  # Low noise mode
        self.set_sensitivity(sensitivity_index)
        self.set_filter_type(4)  # 12 dB lowpass
        self.set_lowpass_frequency(lowpass_freq_index)
        self.set_input_offset_on(False)
        self.set_bias_voltage_on(False)
        self.logger.info("Configured for low-noise measurement")
    
    def configure_high_bandwidth(self, sensitivity_index: int = 18,
                                lowpass_freq_index: int = 13) -> None:
        """
        Configure for high-bandwidth measurement.
        
        Args:
            sensitivity_index: Sensitivity setting (default: 1 µA/V)
            lowpass_freq_index: Lowpass filter frequency (default: 100 kHz)
        """
        self.reset()
        self.set_gain_mode(1)  # High bandwidth mode
        self.set_sensitivity(sensitivity_index)
        self.set_filter_type(4)  # 12 dB lowpass
        self.set_lowpass_frequency(lowpass_freq_index)
        self.logger.info("Configured for high-bandwidth measurement")
    
    def idle(self) -> None:
        """Set the SR570 to a safe idle state."""
        self.set_blank_on(True)
        self.set_bias_voltage_on(False)
        self.logger.info("SR570 set to idle")

