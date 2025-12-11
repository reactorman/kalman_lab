# -*- coding: utf-8 -*-
"""
Base Instrument Class

Provides common functionality for all instrument classes including:
- TEST_MODE support for logging commands without hardware
- Error handling with try/except
- Response logging
- CSV measurement recording
"""

import os
import csv
import logging
import time
from datetime import datetime
from typing import Optional, Any, Union, List

# Global TEST_MODE flag - when True, commands are logged instead of sent
TEST_MODE = False

# Global timing tracker for test mode
class TimingTracker:
    """Tracks command execution timing for test mode runtime estimation."""
    def __init__(self):
        self.start_time: Optional[float] = None
        self.command_count: int = 0
        self.sweep_count: int = 0
        self.sweep_commands = {'WV', 'WI', 'LSV', 'BSV'}  # Sweep commands for 4156B/5270B
        self.sweep_instruments = {'IV4156B', 'IV5270B'}  # Instruments with sweep commands
    
    def start(self) -> None:
        """Start timing."""
        self.start_time = time.time()
        self.command_count = 0
        self.sweep_count = 0
    
    def record_command(self, instrument_name: str, command: str) -> None:
        """Record a command for timing estimation."""
        if not TEST_MODE:
            return
        
        self.command_count += 1
        
        # Check if this is a sweep command for 4156B or 5270B
        if instrument_name in self.sweep_instruments:
            # Check if command starts with a sweep command
            command_upper = command.strip().upper()
            for sweep_cmd in self.sweep_commands:
                if command_upper.startswith(sweep_cmd + ' ') or command_upper == sweep_cmd:
                    self.sweep_count += 1
                    break
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time
    
    def get_estimated_runtimes(self) -> tuple:
        """
        Calculate estimated runtimes.
        
        Returns:
            (python_runtime, command_runtime, sweep_runtime, total_runtime)
            All times in seconds.
        """
        python_runtime = self.get_elapsed_time()
        command_runtime = (self.command_count - self.sweep_count) * 0.001  # 1ms per non-sweep command
        sweep_runtime = self.sweep_count * 1.0  # 1s per sweep command
        total_runtime = python_runtime + command_runtime + sweep_runtime
        
        return python_runtime, command_runtime, sweep_runtime, total_runtime

# Global timing tracker instance
_timing_tracker = TimingTracker()

# Paths for logs and measurements
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
MEASUREMENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'measurements')
TEST_COMMANDS_FILE = os.path.join(LOG_DIR, 'test_commands.txt')
RESULTS_FILE = os.path.join(MEASUREMENTS_DIR, 'results.csv')


def set_test_mode(enabled: bool) -> None:
    """
    Enable or disable TEST_MODE globally.
    
    Args:
        enabled: True to enable test mode, False to disable
    """
    global TEST_MODE
    TEST_MODE = enabled
    if enabled:
        _timing_tracker.start()


def get_timing_tracker() -> TimingTracker:
    """Get the global timing tracker instance."""
    return _timing_tracker


def get_test_mode() -> bool:
    """Return current TEST_MODE state."""
    return TEST_MODE


def ensure_directories() -> None:
    """Create logs/ and measurements/ directories if they don't exist."""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(MEASUREMENTS_DIR, exist_ok=True)


def initialize_csv() -> None:
    """
    Initialize the CSV results file with headers if it doesn't exist.
    Headers: Instrument, Function, Value, Units, Timestamp
    """
    ensure_directories()
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Instrument', 'Function', 'Value', 'Units', 'Timestamp'])


def format_number(value: Union[int, float], 
                  max_sig_digits: int = 12,
                  use_scientific_threshold: float = 1e-3) -> str:
    """
    Format a number for instrument commands to avoid floating-point precision issues.
    
    This function ensures that numbers are formatted consistently and avoid
    issues like "4.9999999999999996e-06" instead of "5E-6".
    
    Args:
        value: Number to format (int or float)
        max_sig_digits: Maximum significant digits to use (default: 12)
        use_scientific_threshold: Use scientific notation below this value (default: 1e-3)
    
    Returns:
        Formatted number string suitable for instrument commands
    
    Examples:
        format_number(5e-6) -> "5E-6"
        format_number(1.5) -> "1.5"
        format_number(0.0001) -> "1E-4"
        format_number(100.0) -> "100"
    """
    if isinstance(value, int):
        return str(value)
    
    # Handle zero
    if value == 0.0:
        return "0"
    
    # Handle negative numbers
    sign = "-" if value < 0 else ""
    abs_value = abs(value)
    
    # Use scientific notation for very small numbers
    if abs_value < use_scientific_threshold:
        # Format in scientific notation with proper precision
        # Use 'E' format (uppercase) as many instruments prefer it
        formatted = f"{abs_value:.{max_sig_digits-1}E}"
        # Remove unnecessary zeros and normalize format
        # e.g., "5.000000E-06" -> "5E-6"
        if 'E' in formatted:
            mantissa, exponent = formatted.split('E')
            mantissa = mantissa.rstrip('0').rstrip('.')
            exp_num = int(exponent)
            # Format exponent - Python's E format already includes the sign
            # Simplify: "1E-6" instead of "1.0E-06"
            if mantissa == "1":
                return f"{sign}1E{exp_num}"
            else:
                return f"{sign}{mantissa}E{exp_num}"
        return f"{sign}{formatted}"
    
    # For larger numbers, use decimal notation
    # Round to avoid floating-point precision issues
    # Use enough decimal places to preserve precision but avoid unnecessary digits
    # First, round to reasonable precision to avoid floating-point artifacts
    import math
    if abs_value >= 1:
        # For numbers >= 1, round to 12 significant digits
        if abs_value != 0:
            magnitude = math.floor(math.log10(abs_value))
            rounded = round(abs_value, max_sig_digits - 1 - magnitude)
        else:
            rounded = abs_value
        formatted = f"{rounded:.12f}".rstrip('0').rstrip('.')
    else:
        # For numbers between threshold and 1, use more precision
        rounded = round(abs_value, max_sig_digits)
        formatted = f"{rounded:.12f}".rstrip('0').rstrip('.')
    
    return f"{sign}{formatted}"


class InstrumentBase:
    """
    Base class for all instrument drivers.
    
    Provides common GPIB communication methods with TEST_MODE support,
    error handling, and measurement logging.
    
    Attributes:
        name: Human-readable instrument name
        resource: PyVISA resource object (None in TEST_MODE)
        address: GPIB address string (e.g., "GPIB0::17::INSTR")
        timeout: Communication timeout in milliseconds
        logger: Python logger instance for this instrument
    """
    
    def __init__(self, resource_manager, address: str, name: str, timeout: int = 10000):
        """
        Initialize the instrument.
        
        Args:
            resource_manager: PyVISA ResourceManager instance
            address: GPIB address string (e.g., "GPIB0::17::INSTR")
            name: Human-readable instrument name for logging
            timeout: Communication timeout in milliseconds (default: 10000)
        """
        self.name = name
        self.address = address
        self.timeout = timeout
        self.resource = None
        self._rm = resource_manager
        
        # Set up logging
        self.logger = logging.getLogger(f'instruments.{name}')
        self.logger.setLevel(logging.DEBUG)
        
        # Ensure directories exist
        ensure_directories()
        
        # Connect to instrument if not in TEST_MODE
        if not TEST_MODE:
            try:
                self.resource = self._rm.open_resource(address)
                self.resource.timeout = timeout
                self.logger.info(f"Connected to {name} at {address}")
            except Exception as e:
                self.logger.error(f"Failed to connect to {name} at {address}: {e}")
                raise
        else:
            self.logger.info(f"TEST_MODE: {name} initialized (no hardware connection)")
    
    def write(self, command: str) -> None:
        """
        Send a command to the instrument.
        
        In TEST_MODE, logs the command to test_commands.txt instead.
        
        Args:
            command: GPIB/SCPI command string to send
        """
        timestamp = datetime.now().isoformat()
        
        if TEST_MODE:
            # Track command for timing estimation
            _timing_tracker.record_command(self.name, command)
            
            # Log command to test file with improved formatting
            with open(TEST_COMMANDS_FILE, 'a') as f:
                f.write(f"{timestamp} | {self.name} | WRITE | {command}\n")
            self.logger.debug(f"TEST_MODE WRITE: {command}")
        else:
            try:
                self.resource.write(command)
                self.logger.debug(f"WRITE: {command}")
            except Exception as e:
                self.logger.error(f"Write error for '{command}': {e}")
                raise
    
    def read(self) -> str:
        """
        Read response from the instrument.
        
        In TEST_MODE, returns a placeholder string.
        
        Returns:
            Response string from instrument
        """
        timestamp = datetime.now().isoformat()
        
        if TEST_MODE:
            # Track read as a command (1ms overhead)
            _timing_tracker.record_command(self.name, "READ")
            
            response = "TEST_MODE_RESPONSE"
            with open(TEST_COMMANDS_FILE, 'a') as f:
                f.write(f"{timestamp} | {self.name} | READ | {response}\n")
            self.logger.debug(f"TEST_MODE READ: {response}")
            return response
        else:
            try:
                response = self.resource.read()
                self.logger.debug(f"READ: {response}")
                return response
            except Exception as e:
                self.logger.error(f"Read error: {e}")
                raise
    
    def query(self, command: str) -> str:
        """
        Send a query command and read the response.
        
        In TEST_MODE, logs the command and returns a placeholder.
        
        Args:
            command: GPIB/SCPI query command string
            
        Returns:
            Response string from instrument
        """
        timestamp = datetime.now().isoformat()
        
        if TEST_MODE:
            # Track query as a command (1ms overhead for the write part)
            # Note: query is write + read, but we count it as one command
            _timing_tracker.record_command(self.name, command)
            
            response = "TEST_MODE_RESPONSE"
            with open(TEST_COMMANDS_FILE, 'a') as f:
                f.write(f"{timestamp} | {self.name} | QUERY | {command} -> {response}\n")
            self.logger.debug(f"TEST_MODE QUERY: {command} -> {response}")
            return response
        else:
            try:
                response = self.resource.query(command)
                self.logger.debug(f"QUERY: {command} -> {response}")
                return response
            except Exception as e:
                self.logger.error(f"Query error for '{command}': {e}")
                raise
    
    def reset(self) -> None:
        """
        Reset the instrument to default state.
        
        Sends the IEEE 488.2 *RST command.
        """
        self.write("*RST")
        self.logger.info(f"{self.name} reset")
    
    def idn_query(self) -> str:
        """
        Query instrument identification.
        
        Sends the IEEE 488.2 *IDN? command.
        
        Returns:
            Instrument identification string
        """
        response = self.query("*IDN?")
        self.logger.info(f"{self.name} IDN: {response}")
        return response
    
    def clear_status(self) -> None:
        """
        Clear the instrument status registers.
        
        Sends the IEEE 488.2 *CLS command.
        """
        self.write("*CLS")
    
    def operation_complete(self) -> str:
        """
        Query operation complete status.
        
        Sends the IEEE 488.2 *OPC? command.
        
        Returns:
            "1" when all pending operations are complete
        """
        return self.query("*OPC?")
    
    def error_query(self) -> str:
        """
        Query the instrument error queue.
        
        Override in subclasses for instrument-specific error commands.
        
        Returns:
            Error message string
        """
        # Default implementation uses SCPI standard
        # Subclasses may override with instrument-specific commands
        return self.query("SYST:ERR?")
    
    def _is_no_error(self, response: str) -> bool:
        """
        Check if an error response indicates "no error".
        
        Handles different instrument error formats:
        - IV5270B: "0: No error"
        - IV4156B: "0" or "0,No error" (comma-separated)
        - SCPI instruments: '0,"No error"' format
        
        Args:
            response: Error query response string
            
        Returns:
            True if response indicates no error, False otherwise
        """
        response = response.strip()
        
        # Check for IV5270B format: "0: No error"
        if response.startswith("0:"):
            return True
        
        # Check for SCPI format: '0,"No error"' or '0,"No error"'
        if response.startswith("0,"):
            # Extract the error code (first part before comma)
            parts = response.split(",", 1)
            if len(parts) > 0:
                try:
                    error_code = int(parts[0].strip())
                    return error_code == 0
                except ValueError:
                    pass
        
        # Check for IV4156B format: "0" or just "0" at start
        try:
            error_code = int(response.split(",")[0].strip())
            return error_code == 0
        except (ValueError, IndexError):
            pass
        
        # If we can't parse it, assume it's an error
        return False
    
    def check_all_errors(self, max_tries: int = 10) -> List[str]:
        """
        Check all errors in the instrument error queue.
        
        Queries the error queue repeatedly until "no error" is returned,
        collecting all errors/warnings found. Instruments typically return
        one error per query, so multiple queries are needed to clear the queue.
        
        Args:
            max_tries: Maximum number of error queries (default: 10)
            
        Returns:
            List of all error/warning messages found. Empty list if no errors.
            In TEST_MODE, always returns empty list.
        """
        if TEST_MODE:
            # In test mode, no real errors exist
            return []
        
        errors = []
        
        for i in range(max_tries):
            try:
                response = self.error_query()
                
                # Check if this is a "no error" response
                if self._is_no_error(response):
                    # No more errors, we're done
                    break
                else:
                    # This is an error or warning
                    errors.append(response)
                    self.logger.debug(f"{self.name} error query {i+1}: {response}")
            except Exception as e:
                # If error query itself fails, log it and continue
                error_msg = f"Error query failed: {e}"
                errors.append(error_msg)
                self.logger.warning(f"{self.name} {error_msg}")
                # Don't break on query failure - try to get more errors
                # But limit iterations to avoid infinite loops
                if i >= max_tries - 1:
                    break
        
        if errors:
            self.logger.warning(f"{self.name} found {len(errors)} error(s)/warning(s)")
        else:
            self.logger.debug(f"{self.name} error queue is clean")
        
        return errors
    
    def record_measurement(self, function: str, value: Any, units: str) -> None:
        """
        Record a measurement to the CSV results file.
        
        Args:
            function: Name of the measurement function (e.g., "Frequency")
            value: Measured value
            units: Units of measurement (e.g., "Hz", "V", "A")
        """
        initialize_csv()
        timestamp = datetime.now().isoformat()
        
        with open(RESULTS_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([self.name, function, value, units, timestamp])
        
        self.logger.info(f"Recorded: {function} = {value} {units}")
    
    def close(self) -> None:
        """Close the instrument connection."""
        if self.resource is not None:
            try:
                self.resource.close()
                self.logger.info(f"{self.name} connection closed")
            except Exception as e:
                self.logger.error(f"Error closing {self.name}: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""
        self.close()
        return False

