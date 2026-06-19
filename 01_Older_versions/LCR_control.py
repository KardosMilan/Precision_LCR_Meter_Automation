import pyvisa
import numpy as np
import csv
import time
import matplotlib.pyplot as plt
import time

# === USER SETTINGS ===
visa_address = "USB0::0x2A8D::0x2F01::MY54412144::0::INSTR" # Replace with the actual VISA address
num_points = 100 # Number of frequency points to be measured
start_freq = 20 # Hz
stop_freq = 1_000_000 # Hz
output_csv = "test_AVER1.csv" 
measurement_delay = 1 # seconds between frequency points

# === CONNECT TO INSTRUMENT ===
rm = pyvisa.ResourceManager()
inst = rm.open_resource(visa_address)
inst.timeout = 5000 # ms

print("Instrument ID:", inst.query("*IDN?").strip()) # Printing the ID of the instrument which has been connected

# === SET MEASUREMENT MODE ===
inst.write(":FUNCtion:IMPedance:TYPE ZTR") # Sets the impedance parameter to Z, phase in radian (ZTD -> degrees)
inst.write(":APER LONG, 1") # Sets the measurement time and the averaging value. (1 is enough, it doesn't change much)

# === CREATE FREQUENCY ARRAY ===
frequencies = np.logspace(np.log10(start_freq), np.log10(stop_freq), num=num_points) # Logarithmic scale for num_points number of frequencies

# === MEASUREMENT LOOP ===
with open(output_csv, mode='w', newline='') as file: # Open csv file for writing in the file variable
    writer = csv.writer(file) # creating csv write object, so we can write in the csv file
    writer.writerow(["Frequency (Hz)", "Impedance (Ohm)", "Phase (rad)"]) # Writing the first row as the headers

    print("\nStarting frequency sweep...\n")
    for f in frequencies: # Iterating through the frequencies list which contains the frequencies to be measured
        inst.write(f"FREQ {f}") # SCPI command for the instrument to set the actual frequency to the value of f
        time.sleep(measurement_delay) # Waiting between measurements to stabilize the instrument (the variable is in seconds)
        response = inst.query("FETC?") # Query of the measured values into variable response
        parts = response.strip().split(',') # Cutting unnecessary characters such as commas, spaces
        z = float(parts[0]) # The impedance to variable z as a float number
        phase_rad = float(parts[1]) # The phase to variable phase_rad as a float number
        writer.writerow([f, z, phase_rad]) # Writing the measured values into CSV file
        print(f"f = {f:.4f} Hz → Z = {z:.4f} Ω, θ = {phase_rad:.4f} rad") # Printing the actual values to console

print(f"\n✅ Sweep complete. Data saved to: {output_csv}")
inst.close() # Closing the communication line with the instrument

# === PLOT RESULTS ===
frequencies = [] # Empty list to store the frequencies
impedances = [] # Empty list to store impedances
phases = [] # Empty list to store phases in radian

with open(output_csv, 'r') as file: # Opening the CSV file in read mode
    reader = csv.reader(file) # Creating a reader object for each line
    next(reader)  # Skip header
    for row in reader: 
        freq = float(row[0])
        z = float(row[1]) # Creating a float from each element
        phase = float(row[2])
        frequencies.append(freq)
        impedances.append(z) # Appending the new values to the previous list
        phases.append(phase)

plt.figure(figsize=(10, 5))

# |Z| plot
plt.subplot(1, 2, 1)
plt.loglog(frequencies, impedances, marker='o', linewidth=1)
plt.xlabel("Frequency (Hz)")
plt.ylabel("Impedance |Z| (Ohm)")
plt.title("Impedance Magnitude")
plt.grid(True, which="both")

# Phase plot
plt.subplot(1, 2, 2)
plt.semilogx(frequencies, phases, marker='o', linewidth=1)
plt.xlabel("Frequency (Hz)")
plt.ylabel("Phase (rad)")
plt.title("Phase Angle")
plt.grid(True, which="both")
plt.tight_layout()
plt.show()


