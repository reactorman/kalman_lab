#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Debug Script for Manual Instrument Control

This script creates PyVISA connections to all test equipment for manual
debugging and command testing from the Python debugger.

Usage:
    Run from Python interpreter with -i flag to keep interactive session:
        python -i scripts/debug_instruments.py
    
    This will connect to all instruments and leave you in an interactive
    Python session where you can manually send commands.

Available instrument objects:
    - iv5270b: Keysight E5270B Precision IV Analyzer (GPIB0::17)
    - iv4156b: Agilent 4156B Precision Semiconductor Analyzer (GPIB0::3)
    - pg81104a: Keysight 81104A Pulse Pattern Generator (GPIB0::10)
    - ct53230a: Keysight 53230A Universal Counter (GPIB0::5)
    - sr560: Stanford Research SR560 Preamp (GPIB0::9 via GPIB-Serial)
    - sr570: Stanford Research SR570 Current Preamp (GPIB0::8 via GPIB-Serial)

Example usage in debugger:
    # Query instrument identity
    print(iv5270b.query("*IDN?"))
    
    # Send a command
    iv5270b.write("*RST")
    
    # Read response
    response = iv5270b.read()
    
    # Check for errors
    errors = iv5270b.query("ERR?")
    print(f"Errors: {errors}")
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyvisa

# Initialize PyVISA resource manager
print("Initializing PyVISA...")
rm = pyvisa.ResourceManager()

# List all available resources
print("\nAvailable VISA resources:")
resources = rm.list_resources()
for res in resources:
    print(f"  {res}")

# Create instrument objects with GPIB addresses
print("\nCreating instrument connections...")

# Keysight E5270B Precision IV Analyzer
print("  Connecting to E5270B (GPIB0::17)...")
iv5270b = rm.open_resource("GPIB0::17::INSTR")
iv5270b.timeout = 10000  # 10 second timeout
iv5270b.read_termination = '\n'
iv5270b.write_termination = '\n'
print(f"    ID: {iv5270b.query('*IDN?').strip()}")

# Agilent 4156B Precision Semiconductor Analyzer
print("  Connecting to 4156B (GPIB0::3)...")
iv4156b = rm.open_resource("GPIB0::3::INSTR")
iv4156b.timeout = 10000
iv4156b.read_termination = '\n'
iv4156b.write_termination = '\n'
print(f"    ID: {iv4156b.query('*IDN?').strip()}")

# Keysight 81104A Pulse Pattern Generator
print("  Connecting to 81104A (GPIB0::10)...")
pg81104a = rm.open_resource("GPIB0::10::INSTR")
pg81104a.timeout = 10000
pg81104a.read_termination = '\n'
pg81104a.write_termination = '\n'
print(f"    ID: {pg81104a.query('*IDN?').strip()}")

# Keysight 53230A Universal Counter
print("  Connecting to 53230A (GPIB0::5)...")
ct53230a = rm.open_resource("GPIB0::5::INSTR")
ct53230a.timeout = 10000
ct53230a.read_termination = '\n'
ct53230a.write_termination = '\n'
print(f"    ID: {ct53230a.query('*IDN?').strip()}")

# Stanford Research SR560 Preamp (via GPIB-Serial)
print("  Connecting to SR560 (GPIB0::9 via GPIB-Serial)...")
sr560 = rm.open_resource("GPIB0::9::INSTR")
sr560.timeout = 5000
sr560.read_termination = '\n'
sr560.write_termination = '\n'
print("    Connected (Serial device via GPIB-Serial converter)")

# Stanford Research SR570 Current Preamp (via GPIB-Serial)
print("  Connecting to SR570 (GPIB0::8 via GPIB-Serial)...")
sr570 = rm.open_resource("GPIB0::8::INSTR")
sr570.timeout = 5000
sr570.read_termination = '\n'
sr570.write_termination = '\n'
print("    Connected (Serial device via GPIB-Serial converter)")

print("\n" + "="*60)
print("All instruments connected successfully!")
print("="*60)
print("\nYou can now send commands manually. Examples:")
print("  iv5270b.query('*IDN?')           # Query identity")
print("  iv5270b.write('*RST')             # Reset instrument")
print("  iv5270b.query('ERR?')             # Check for errors")
print("  ct53230a.query(':SYST:ERR?')      # Check counter errors")
print("  pg81104a.write(':OUTP ON')        # Turn on pulse output")
print("\nTo close connections when done:")
print("  for inst in [iv5270b,iv4156b,pg81104a,ct53230a,sr560,sr570]: inst.close()")
print("  rm.close()")
print("="*60)
print("\nInteractive session ready. Type commands above to control instruments.")
print("Press Ctrl+D (Linux/Mac) or Ctrl+Z then Enter (Windows) to exit.")
