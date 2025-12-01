# -*- coding: utf-8 -*-
"""
Stanford Research Systems SR560 Low-Noise Voltage Preamplifier Driver

Commands based on SR560m.pdf manual.
This instrument uses serial commands via NI GPIB-Serial converter.

Features:
    - Voltage gains from 1 to 50000
    - AC or DC coupling
    - Adjustable highpass and lowpass filters
    - Differential or single-ended input
    - Low-noise FET or low-drift bipolar input
"""

from .base import InstrumentBase


class SR560(InstrumentBase):
    """
    Driver for SRS SR560 Low-Noise Voltage Preamplifier.
    
    The SR560 is a low-noise voltage preamplifier with programmable
    gain, filtering, and input configuration.
    
    Note: Controlled via NI GPIB-Serial converter. Commands are ASCII
    strings terminated with carriage return.
    
    Reference: SRS SR560 Operating Manual (SR560m.pdf)
    """
    
    # Gain settings: index -> gain value
    GAIN_MAP = {
        0: 1, 1: 2, 2: 5, 3: 10, 4: 20, 5: 50,
        6: 100, 7: 200, 8: 500, 9: 1000, 10: 2000,
        11: 5000, 12: 10000, 13: 20000, 14: 50000
    }
    
    # Filter frequency settings (Hz)
    FILTER_FREQ_MAP = {
        0: 0.03, 1: 0.1, 2: 0.3, 3: 1, 4: 3,
        5: 10, 6: 30, 7: 100, 8: 300, 9: 1000,
        10: 3000, 11: 10000, 12: 30000, 13: 100000, 14: 300000, 15: 1000000
    }
    
    def __init__(self, resource_manager, address: str = "GPIB0::9::INSTR",
                 timeout: int = 5000):
        """
        Initialize the SR560.
        
        Args:
            resource_manager: PyVISA ResourceManager instance
            address: GPIB address of the GPIB-Serial converter
            timeout: Communication timeout in ms
        """
        super().__init__(resource_manager, address, "SR560", timeout)
    
    def reset(self) -> None:
        """
        Reset the SR560 to default settings.
        
        Reference: *RST command
        """
        self.write("*RST")
        self.logger.info("SR560 reset to defaults")
    
    def idn_query(self) -> str:
        """
        Query instrument identification.
        
        Note: SR560 may not support standard *IDN? query.
        Returns a constructed identification string.
        """
        # SR560 may not support *IDN?, return known identity
        return "Stanford Research Systems,SR560,N/A,N/A"
    
    # =========================================================================
    # Gain Control
    # =========================================================================
    
    def set_gain(self, index: int) -> None:
        """
        Set the voltage gain.
        
        Args:
            index: Gain index (0-14)
                   0 = 1, 14 = 50000
        
        Reference: GAIN command
        """
        if not 0 <= index <= 14:
            raise ValueError("Gain index must be 0-14")
        self.write(f"GAIN {index}")
        gain = self.GAIN_MAP.get(index, "unknown")
        self.logger.info(f"Gain set to {gain}")
    
    def set_gain_value(self, gain: int) -> None:
        """
        Set gain by value (finds closest setting).
        
        Args:
            gain: Desired gain value
        """
        closest_idx = min(self.GAIN_MAP.keys(),
                         key=lambda k: abs(self.GAIN_MAP[k] - gain))
        self.set_gain(closest_idx)
    
    # =========================================================================
    # Input Configuration
    # =========================================================================
    
    def set_input_coupling(self, coupling: str) -> None:
        """
        Set the input coupling mode.
        
        Args:
            coupling: "AC", "DC", or "GND"
        
        Reference: CPLG command
        """
        coupling_map = {"GND": 0, "DC": 1, "AC": 2}
        coupling = coupling.upper()
        if coupling not in coupling_map:
            raise ValueError("Coupling must be 'AC', 'DC', or 'GND'")
        self.write(f"CPLG {coupling_map[coupling]}")
        self.logger.info(f"Input coupling: {coupling}")
    
    def set_input_mode(self, mode: str) -> None:
        """
        Set the input mode.
        
        Args:
            mode: "A" (single-ended A), "B" (single-ended B),
                  "A-B" (differential)
        
        Reference: SRCE command
        """
        mode_map = {"A": 0, "A-B": 1, "B": 2}
        if mode not in mode_map:
            raise ValueError("Mode must be 'A', 'B', or 'A-B'")
        self.write(f"SRCE {mode_map[mode]}")
        self.logger.info(f"Input mode: {mode}")
    
    def set_dynamic_reserve(self, reserve: str) -> None:
        """
        Set the dynamic reserve mode.
        
        Args:
            reserve: "LOW", "MED", or "HIGH"
        
        Reference: DYNR command
        """
        reserve_map = {"LOW": 0, "MED": 1, "HIGH": 2}
        reserve = reserve.upper()
        if reserve not in reserve_map:
            raise ValueError("Reserve must be 'LOW', 'MED', or 'HIGH'")
        self.write(f"DYNR {reserve_map[reserve]}")
        self.logger.info(f"Dynamic reserve: {reserve}")
    
    # =========================================================================
    # Filter Control
    # =========================================================================
    
    def set_filter_mode(self, mode: int) -> None:
        """
        Set the filter mode.
        
        Args:
            mode: 0=bypass, 1=6dB lowpass, 2=12dB lowpass,
                  3=6dB highpass, 4=12dB highpass, 5=bandpass
        
        Reference: FLTM command
        """
        if not 0 <= mode <= 5:
            raise ValueError("Filter mode must be 0-5")
        self.write(f"FLTM {mode}")
        modes = ["Bypass", "6dB LP", "12dB LP", "6dB HP", "12dB HP", "Bandpass"]
        self.logger.info(f"Filter mode: {modes[mode]}")
    
    def set_lowpass_frequency(self, index: int) -> None:
        """
        Set the lowpass filter frequency.
        
        Args:
            index: Frequency index (0-15)
                   0 = 0.03 Hz, 15 = 1 MHz
        
        Reference: LFRQ command
        """
        if not 0 <= index <= 15:
            raise ValueError("Lowpass frequency index must be 0-15")
        self.write(f"LFRQ {index}")
        freq = self.FILTER_FREQ_MAP.get(index, "unknown")
        self.logger.info(f"Lowpass frequency: {freq} Hz")
    
    def set_highpass_frequency(self, index: int) -> None:
        """
        Set the highpass filter frequency.
        
        Args:
            index: Frequency index (0-11)
                   0 = 0.03 Hz, 11 = 10 kHz
        
        Reference: HFRQ command
        """
        if not 0 <= index <= 11:
            raise ValueError("Highpass frequency index must be 0-11")
        self.write(f"HFRQ {index}")
        freq = self.FILTER_FREQ_MAP.get(index, "unknown")
        self.logger.info(f"Highpass frequency: {freq} Hz")
    
    # =========================================================================
    # Signal Inversion
    # =========================================================================
    
    def set_invert(self, inverted: bool) -> None:
        """
        Enable or disable signal inversion.
        
        Args:
            inverted: True to invert output, False for non-inverted
        
        Reference: INVT command
        """
        state = 1 if inverted else 0
        self.write(f"INVT {state}")
        self.logger.info(f"Output invert: {'ON' if inverted else 'OFF'}")
    
    # =========================================================================
    # Blanking Control
    # =========================================================================
    
    def set_blank(self, blanked: bool) -> None:
        """
        Enable or disable output blanking.
        
        Args:
            blanked: True to blank (zero) output, False for normal
        
        Reference: BLNK command
        """
        state = 1 if blanked else 0
        self.write(f"BLNK {state}")
        self.logger.info(f"Output blank: {'ON' if blanked else 'OFF'}")
    
    # =========================================================================
    # Vernier Gain Control
    # =========================================================================
    
    def set_vernier_gain(self, enabled: bool) -> None:
        """
        Enable or disable vernier gain (fine gain adjustment).
        
        Args:
            enabled: True to enable vernier, False to disable
        
        Reference: VERN command
        """
        state = 1 if enabled else 0
        self.write(f"VERN {state}")
        self.logger.info(f"Vernier gain: {'ON' if enabled else 'OFF'}")
    
    # =========================================================================
    # Common Configurations
    # =========================================================================
    
    def configure_dc_measurement(self, gain_index: int = 6,
                                lowpass_freq_index: int = 9) -> None:
        """
        Configure for DC voltage measurement.
        
        Args:
            gain_index: Gain setting (default: 100)
            lowpass_freq_index: Lowpass filter frequency (default: 1 kHz)
        """
        self.reset()
        self.set_input_coupling("DC")
        self.set_input_mode("A-B")  # Differential
        self.set_gain(gain_index)
        self.set_filter_mode(2)  # 12 dB lowpass
        self.set_lowpass_frequency(lowpass_freq_index)
        self.set_invert(False)
        self.logger.info("Configured for DC measurement")
    
    def configure_ac_measurement(self, gain_index: int = 6,
                                highpass_freq_index: int = 4,
                                lowpass_freq_index: int = 11) -> None:
        """
        Configure for AC voltage measurement.
        
        Args:
            gain_index: Gain setting (default: 100)
            highpass_freq_index: Highpass filter frequency (default: 3 Hz)
            lowpass_freq_index: Lowpass filter frequency (default: 10 kHz)
        """
        self.reset()
        self.set_input_coupling("AC")
        self.set_input_mode("A-B")  # Differential
        self.set_gain(gain_index)
        self.set_filter_mode(5)  # Bandpass
        self.set_highpass_frequency(highpass_freq_index)
        self.set_lowpass_frequency(lowpass_freq_index)
        self.set_invert(False)
        self.logger.info("Configured for AC measurement")
    
    def configure_low_noise(self, gain_index: int = 9) -> None:
        """
        Configure for low-noise measurement.
        
        Args:
            gain_index: Gain setting (default: 1000)
        """
        self.reset()
        self.set_input_coupling("DC")
        self.set_input_mode("A-B")
        self.set_gain(gain_index)
        self.set_dynamic_reserve("LOW")
        self.set_filter_mode(2)  # 12 dB lowpass
        self.set_lowpass_frequency(7)  # 100 Hz
        self.logger.info("Configured for low-noise measurement")
    
    def idle(self) -> None:
        """Set the SR560 to a safe idle state."""
        self.set_blank(True)
        self.set_input_coupling("GND")
        self.logger.info("SR560 set to idle")

