#!/usr/bin/env python

import sys
import os


import pyvisa

rm = pyvisa.ResourceManager()


iv5270b = rm.open_resource("GPIB0::17::INSTR")
iv5270b.timeout = 10000  # 10 second timeout
#iv5270b.read_termination = '\n'
#iv5270b.write_termination = '\n'
print(f"    ID: {iv5270b.query('*IDN?').strip()}")

# Keysight 81104A Pulse Pattern Generator
# Used for: WR_ENB pulse generation
print("  Connecting to 81104A (GPIB0::10)...")
pg81104a = rm.open_resource("GPIB0::10::INSTR")
pg81104a.timeout = 10000
pg81104a.read_termination = '\n'
pg81104a.write_termination = '\n'
print(f"    ID: {pg81104a.query('*IDN?').strip()}")

# Keysight 53230A Universal Counter
# Used for: Time interval measurement (WR_ENB to PROG_OUT)
print("  Connecting to 53230A (GPIB0::5)...")
ct53230a = rm.open_resource("GPIB0::5::INSTR")
ct53230a.timeout = 10000
ct53230a.read_termination = '\n'
ct53230a.write_termination = '\n'
print(f"    ID: {ct53230a.query('*IDN?').strip()}")

print("\n" + "="*60)
print("All Programmer instruments connected successfully!")
print("="*60)
print("\nInstrument Channels (E5270B):")
print("  CH1: PROG_OUT (voltage mode: VCC+series resistor, current mode: +100nA)")
print("  CH2: ICELLMEAS (VDD/2)")
print("  CH3: IREFP (current source)")
print("  CH4: PROG_IN (current source, 10nA to 100nA)")
print("  CH5: VDD (1.8V)")
print("  CH6: VCC (5.0V)")
print("  CH7: ERASE_PROG (VCC or 0V)")
print("\nCounter Channels (53230A):")
print("  CH1: Start trigger (WR_ENB from PPG)")
print("  CH2: Stop trigger (PROG_OUT from SMU)")
print("\nPulse Generator (81104A):")
print("  CH1: WR_ENB pulse output")
print("\nYou can now send commands manually. Examples:")
print("  iv5270b.query('*IDN?')              # Query identity")
print("  iv5270b.write('*RST')               # Reset instrument")
print("  iv5270b.write('DV 1,0,5.0,0.001')   # Set CH1 to 5V, 1mA compliance")
print("  iv5270b.write('DI 3,0,-100e-9,2.0') # Set CH3 to 100nA, 2V compliance")
print("  iv5270b.write('CN 1,2,3,4,5,6,7')   # Enable all channels")
print("  iv5270b.query('ERR?')               # Check for errors")
print("  pg81104a.write('*TRG')              # Trigger pulse")
print("  ct53230a.query(':SYST:ERR?')        # Check counter errors")
print("\nTo close connections when done:")
print("  iv5270b.close(); pg81104a.close(); ct53230a.close(); rm.close()")
print("="*60)
print("\nInteractive session ready. Type commands above to control instruments.")
print("Press Ctrl+D (Linux/Mac) or Ctrl+Z then Enter (Windows) to exit.")
