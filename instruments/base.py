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
from datetime import datetime
from typing import Optional, Any, Union

# Global TEST_MODE flag - when True, commands are logged instead of sent
TEST_MODE = False

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
            # Log command to test file
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

