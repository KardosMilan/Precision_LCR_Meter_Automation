import tkinter as tk # Module for GUI
from tkinter import filedialog, messagebox, ttk
import pyvisa #VISA communication module
import csv    #Handle csv files
import os          #Handle files
import matplotlib.pyplot as plt
import sys              #Check runtime environment



# Dictionary that maps GUI mode names to SCPI command suffixes
mode_scpi = {
    "Cp-D": "CPD",
    "Cp-Q": "CPQ",
    "Cp-G": "CPG",
    "Cp-Rp": "CPRP",
    "Cs-D": "CSD",
    "Cs-Rs": "CSRS",
    "Cs-Q": "CSQ",
    "Lp-D": "LPD",
    "Lp-Q": "LPQ",
    "Lp-G": "LPG",
    "Lp-Rp": "LPRP",
    "Lp-Rdc": "LPRD",
    "Ls-D": "LSD",
    "Ls-Q": "LSQ",
    "Ls-Rs": "LSRS",
    "Ls-Rdc": "LSRD",
    "R-X": "RX",
    "Y-0d": "YTD",
    "Y-0r": "YTR",
    "Z-0d": "ZTD",
    "Z-0r": "ZTR",
}

mode_labels = {
    "Cp-D": ("Cp (F)", "D (-)"),
    "Cp-Q": ("Cp (F)", "Q (-)"),
    "Cp-G": ("Cp (F)", "G (S)"),
    "Cp-Rp": ("Cp (F)", "Rp (Ω)"),
    "Cs-D": ("Cs (F)", "D (-)"),
    "Cs-Rs": ("Cs (F)", "Rs (Ω)"),
    "Cs-Q": ("Cs (F)", "Q (-)"),
    "Lp-D": ("Lp (H)", "D (-)"),
    "Lp-Q": ("Lp (H)", "Q (-)"),
    "Lp-G": ("Lp (H)", "G (S)"),
    "Lp-Rp": ("Lp (H)", "Rp (Ω)"),
    "Lp-Rdc": ("Lp (H)", "Rdc (Ω)"),
    "Ls-D": ("Ls (H)", "D (-)"),
    "Ls-Q": ("Ls (H)", "Q (-)"),
    "Ls-Rs": ("Ls (H)", "Rs (Ω)"),
    "Ls-Rdc": ("Ls (H)", "Rdc (Ω)"),
    "R-X": ("R (Ω)", "X (Ω)"),
    "G-B": ("G (S)", "B (S)"),
    "Y-0d": ("Y (S)", "θ (°)"),
    "Y-0r": ("Y (S)", "θ (rad)"),
    "Z-0d": ("Z (Ω)", "θ (°)"),
    "Z-0r": ("Z (Ω)", "θ (rad)"),
}

class VisaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LCR Control Tool")

        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        # Create notebook tabs
        self.manual_tab = tk.Frame(self.notebook)
        self.notebook.add(self.manual_tab, text="Manual meas.")

        self.sweep_tab = tk.Frame(self.notebook)
        self.notebook.add(self.sweep_tab, text="Sweep meas.")

        self.plot_tab = tk.Frame(self.notebook)
        self.notebook.add(self.plot_tab, text="Generate Plot")

        # VISA Resource Manager
        self.rm = pyvisa.ResourceManager()

        # Disable resizing
        self.root.resizable(False, False)

        # Create submodules
        self.sweep_module = SweepModule(self.sweep_tab, self.rm)
        self.plot_module = PlotModule(self.plot_tab)
        self.manual_module = ManualModule(self.manual_tab, self.rm)

        tk.Label(root, text="Software: v4.0").pack(padx=10,anchor="ne")

class ManualModule: #Manual measurement module
    
    def __init__(self, root, rm):
        self.root = root

        # Get VISA Resource Manager
        self.rm = rm

        #Konzol inicializálása
        self.console_window = None
        self.console_text = None
        self.current_console_file = None

        # Base directory
        self.base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
        self.logs_dir = os.path.join(self.base_dir, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)

        # Main frame
        self.frame = tk.Frame(root)
        self.frame.pack(anchor="nw", padx=10, pady=5, fill="x")
        self.frame.config(width=1000, height=250)

        # VISA devices frame
        self.top1_frame = tk.Frame(self.frame, bd=1, relief="solid")
        self.top1_frame.grid(row=0, column=0, padx=5, pady=5, sticky="n")
        self.top1_frame.config(width=550, height=240)

        tk.Label(self.top1_frame, text="Accessible VISA devices:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        self.visa_listbox = tk.Listbox(self.top1_frame, height=5, width=32,  exportselection=False)
        self.visa_listbox.grid(row=1, column=0, padx=10, pady=0)
        

        self.refresh_button = tk.Button(self.top1_frame, text="Update", command=self.refresh_visa_devices)
        self.refresh_button.grid(row=0, column=1, padx=10, pady=10)

        self.device_status = tk.StringVar(value="No device selected!")
        tk.Label(self.top1_frame, textvariable=self.device_status, fg="blue").grid(row=2, column=0, padx=15, pady=10)
        self.visa_listbox.bind("<<ListboxSelect>>", self.update_device_status)
        self.refresh_visa_devices()

        self.sub_frame = tk.Frame(self.top1_frame, relief="solid")
        self.sub_frame.grid(row=4, column=0, padx=5, pady=5, sticky="n")
        tk.Label(self.sub_frame, text="Output fomat:").grid(row=0, column=0, sticky="e", pady=10)
        self.output_format = tk.StringVar(value="csv")        
        self.output_entry=ttk.Combobox(self.sub_frame, textvariable=self.output_format, values=["txt", "csv"], width=9, justify="center")
        self.output_entry.grid(row=0, column=1,sticky="w")
        self.output_entry.bind("<space>", lambda e: "break")
        self.output_entry.bind("<space>", self.manual_measure_entry_safe)

        # File controls
        tk.Label(self.top1_frame, text="Filename:").grid(row=0, column=2, padx=5, sticky='e')
        self.filename = tk.StringVar()
        self.filename_entry = tk.Entry(self.top1_frame, textvariable=self.filename, width=30)
        self.filename_entry.grid(row=0, column=3, padx=5)
        self.filename_entry.bind("<space>", lambda e: "break")
        self.filename_entry.bind("<space>", self.manual_measure_entry_safe)

        # Start button
        self.start_button = tk.Button(
            self.top1_frame, text="Start\n(Space)",
            command=self.manual_measure,
            font=("Arial", 16, "bold"), fg="white", bg="red", width=14, height=2
        )
        
        self.start_button.grid(row=1, column=3, padx=5, pady=10)
        self.top1_frame.bind("<space>", self.manual_measure_entry_safe)

        # Measurement status
        self.meas_status = tk.StringVar()
        tk.Label(self.top1_frame, textvariable=self.meas_status).grid(row=2, column=3, padx=5, pady=10)

        # SCPI → GUI mapping
        self.scpi_to_gui = {v: k for k, v in mode_scpi.items()}

    def manual_measure(self, event=None):
        # Check filename
        if not self.filename.get():
            messagebox.showwarning("Warning", "Set a filename!")
            return

        # Check selected VISA device
        try:
            device_address = self.visa_listbox.get(self.visa_listbox.curselection()[0])
        except IndexError:
            messagebox.showerror("Error", "Select a VISA device!")
            return

        # Connect to instrument
        
        try:
            inst = self.rm.open_resource(device_address)
            inst.timeout = 5000
            idn = inst.query('*IDN?').strip()
            self.meas_status.set(f"Instrument: {idn}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to VISA device: {e}")
            return

        # Get measurement mode
        mode_scpi_code = inst.query(":FUNCtion:IMPedance:TYPE?").strip()
        gui_mode = self.scpi_to_gui.get(mode_scpi_code, None)
        if gui_mode is None:
            messagebox.showerror("Error", f"Unknown measurement mode: {mode_scpi_code}")
            inst.close()
            return
        label1, label2 = mode_labels[gui_mode]

        # Get CSV path
        if self.output_format.get()=="csv":
            output = os.path.join(self.logs_dir, self.filename.get() + ".csv")
        else:
            output = os.path.join(self.logs_dir, self.filename.get() + ".txt")      

        file_exists = os.path.isfile(output)

        try:
            # Open CSV in append mode
            with open(output, "a", newline="", encoding="utf-8") as f:
                if self.output_format.get()=="csv":
                    writer = csv.writer(f)
                else:
                    writer = csv.writer(f, delimiter='\t')

                # Write header if file is new
                if not file_exists:
                    writer.writerow(["Frequency (Hz)", label1, label2])

                # Query frequency and measurement
                freq = float(inst.query(":FREQuency?").strip())
                resp = inst.query("FETC?").strip().split(',')
                z, p = float(resp[0]), float(resp[1])

                # Update GUI
                self.meas_status.set(
                    f"Frequency: {freq:.10g} Hz\n"
                    f"{label1} = {z:.15g}\n"
                    f"{label2} = {p:.15g}"
                )
                #self.root.update_idletasks()

                # Write data
                writer.writerow([freq, z, p])

                # Konzol megnyitása ha kell
                if self.current_console_file != output:
                    self.open_console_window(output)

                # Új sor hozzáadása a konzolhoz
                new_line = f"{freq}\t{z}\t{p}\n"
                self.console_text.insert(tk.END, new_line)
                self.console_text.see(tk.END)

        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            inst.close()

    def open_console_window(self, filepath):
        if self.console_window is None or not self.console_window.winfo_exists():
            self.console_window = tk.Toplevel(self.root)
            self.console_window.title(f"Measurement log: {os.path.basename(filepath)}")
            self.console_window.geometry("600x400")

            self.console_text = tk.Text(self.console_window, wrap="none")
            self.console_text.pack(fill="both", expand=True)

            scrollbar = tk.Scrollbar(self.console_text, command=self.console_text.yview)
            scrollbar.pack(side="right", fill="y")
            self.console_text.config(yscrollcommand=scrollbar.set)

        self.current_console_file = filepath

    def manual_measure_entry_safe(self, event):
        self.manual_measure()  # run measurement
        return "break"          
    
    def refresh_visa_devices(self):
        self.visa_listbox.delete(0, tk.END)
        try:
            devices = self.rm.list_resources()
            for dev in devices:
                self.visa_listbox.insert(tk.END, dev)
            if devices:
                self.visa_listbox.select_set(tk.END)
                self.update_device_status()
            else:
                self.device_status.set("No accessible device!")
        except:
            self.device_status.set("Error scanning VISA devices")

    def update_device_status(self, event=None):
        try:
            device = self.visa_listbox.get(self.visa_listbox.curselection()[0])
            self.device_status.set(f"Selected device: {device}")
        except IndexError:
            self.device_status.set("No device selected!")

class SweepModule: # Main application (Sweep module)
    def __init__(self, root, rm):
        self.root = root

        # Get VISA Resource Manager
        self.rm = rm
        
        # Check runtime environment
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(__file__)
        
        # Create output folders
        self.plots_dir = os.path.join(self.base_dir, "plots")
        self.logs_dir = os.path.join(self.base_dir, "logs")
        os.makedirs(self.plots_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        
        #Set icons
        icon_dir = os.path.join(os.path.dirname(__file__), "icons")
        self.help_icon = tk.PhotoImage(file=os.path.join(icon_dir, "help.png"))
        
        # __________________________________ Create GUI __________________________________________________
        
        self.top12_container = tk.Frame(self.root)
        self.top12_container.pack(anchor="nw", padx=5, pady=0, fill="x")

        self.top1_frame = tk.Frame(self.top12_container, bd=1, relief="solid")
        self.top1_frame.grid(row=0, column=0, padx=5, pady=5, sticky="n")
        self.top1_frame.grid_propagate(False)
        self.top1_frame.config(width=450, height=250)  # adjust as needed

        # Start frequency entry
        self.start_freq_label = tk.Label(self.top1_frame, text="Start frequency [Hz]:")
        self.start_freq_label.grid(row=0, column=0, padx=5, pady=10, sticky="e")

        self.start_freq = tk.IntVar()
        self.start_freq_entry = tk.Entry(self.top1_frame, textvariable=self.start_freq, width=30)
        self.start_freq_entry.grid(row=0, column=1, padx=5, pady=10, sticky="w")

        # End frequency entry
        self.stop_freq_label = tk.Label(self.top1_frame, text="End frequency [Hz]:")
        self.stop_freq_label.grid(row=1, column=0, padx=5, pady=10, sticky="e")

        self.end_freq = tk.IntVar()
        self.stop_freq_entry = tk.Entry(self.top1_frame, textvariable=self.end_freq, width=30)
        self.stop_freq_entry.grid(row=1, column=1, padx=5, pady=10, sticky="w")

        # Measurement points entry
        self.points_label = tk.Label(self.top1_frame, text="Number of measurement points:")
        self.points_label.grid(row=2, column=0, padx=5, pady=10, sticky="e")

        self.points = tk.IntVar()
        self.points_entry = tk.Entry(self.top1_frame, textvariable=self.points, width=30)
        self.points_entry.grid(row=2, column=1, padx=5, pady=10, sticky="w")

        # Delay entry
        self.delay_label = tk.Label(self.top1_frame, text="Delay (s):")
        self.delay_label.grid(row=3, column=0, padx=5, pady=10, sticky="e")
        self.delay = tk.IntVar()
        self.delay_entry = tk.Entry(self.top1_frame, textvariable=self.delay, width=30)
        self.delay_entry.grid(row=3, column=1, padx=5, pady=10, sticky="w")

        # Measurement mode entry
        self.mode_label = tk.Label(self.top1_frame, text="Measurement mode:")
        self.mode_label.grid(row=4, column=0, padx=5, pady=10, sticky="e")
        self.mode = tk.StringVar()
        self.combo = ttk.Combobox(self.top1_frame, textvariable=self.mode, values=sorted(mode_labels.keys()), width=27)
        self.combo.grid(row=4, column=1, padx=5, pady=10, sticky="w")

        # Help button
        self.help_save_button = tk.Button(self.top1_frame, image=self.help_icon, command=self.help,relief="flat")
        self.help_save_button.grid(row=0, column=3,padx=10, pady=10, sticky='e')

        # -------------------------- Handle VISA devices -------------------------------------
        # List VISA devices
        self.top2_frame = tk.Frame(self.top12_container, bd=1, relief="solid")
        self.top2_frame.grid(row=0, column=1, padx=5, pady=5, sticky="n")
        self.top2_frame.grid_propagate(False)
        self.top2_frame.config(width=600, height=250)

        self.visa_frame = tk.Frame(self.top2_frame, bd=0, relief="solid")
        self.visa_frame.grid(row=0, column=0, padx=5, pady=5, sticky="wn")

        self.visa_label = tk.Label(self.visa_frame, text="Accesible VISA devices:")
        self.visa_label.grid(row=0, column=0, padx=10, pady=10,sticky='w')

        # Update VISA devices list
        self.refresh_button = tk.Button(self.visa_frame, text="Update", command=self.refresh_visa_devices)
        self.refresh_button.grid(row=0, column=1, padx=10, pady=10)
        
        self.visa_listbox = tk.Listbox(self.top2_frame, height=5, width=32,exportselection=False)
        self.visa_listbox.grid(row=1, column=0, padx=10, pady=0)
        self.refresh_visa_devices()
    
        # Display device status
        self.device_status = tk.StringVar(value="No device selected!")
        self.device_status_label = tk.Label(self.top2_frame, textvariable=self.device_status, fg="blue")
        self.device_status_label.grid(row=2, column=0, padx=15, pady=50,sticky='w')

        # Listbox for choosing device
        self.visa_listbox.bind("<<ListboxSelect>>", self.update_device_status)

        # -------------------------- Save file  -------------------------------------
        self.filepath = tk.StringVar()
        self.filepath.set(self.logs_dir)
        self.save_label = tk.Label(self.top2_frame, text="Filename:")
        self.save_label.grid(row=0, column=1, padx=5, sticky='e')
        self.filename = tk.StringVar()
        self.file_label = tk.Entry(self.top2_frame, textvariable=self.filename, width=30)
        self.file_label.grid(row=0, column=2, padx=5)

        self.file_format = tk.Label(self.top2_frame, text=".csv")
        self.file_format.grid(row=0, column=3, padx=5, sticky="w")

        # Start button
        self.start_button = tk.Button(self.top2_frame, text="Start", command=self.start_measurement, font=("Arial", 20, "bold"),fg="white",bg="red",width=10,height=1)
        self.start_button.grid(row=1, column=2, padx=5, pady=10)

        # Display measurement status
        self.meas_status = tk.StringVar()
        self.meas_status_label = tk.Label(self.top2_frame, textvariable=self.meas_status)
        self.meas_status_label.grid(row=2, column=2, padx=5, pady=10)
    
    # __________________________________ Help window __________________________________________________
    def help(self):
        # Show a help window for measurement initialization
        messagebox.showinfo("Help", "Start frequency [Hz]: min 0\n\nEnd frequency [Hz]: max 1000000\n\nNumber od measurement points: e.g. 100\n\nDelay: e.g. 1")

    # __________________________________ Device handling _______________________________________________
    def refresh_visa_devices(self):
        # Scan and list available VISA resources
        self.visa_listbox.delete(0, tk.END)
        try:
            devices = self.rm.list_resources()
            for dev in devices:
                self.visa_listbox.insert(tk.END, dev)
            if devices:
                self.visa_listbox.select_set(tk.END)  # set the first device automatically
                self.update_device_status()
            else:
                self.device_status.set("No accessible device!")
        except:
            print()

    def update_device_status(self, event=None):
        # Update GUI with selected device address
        try:
            selected_index = self.visa_listbox.curselection()[0]
            device = self.visa_listbox.get(selected_index)
            self.device_status.set(f"Selected device: {device}")
        except IndexError:
            self.device_status.set("No device selected!")
    
    # __________________________________ Measurement Sequence _________________________________________
    def start_measurement(self):
        #Import math module
        import math

        # Initialize instrument and start frequency sweep
        if hasattr(self, "inst"):
            try:
                self.inst.close()
            except:
                pass

        if hasattr(self, "csv_file"):
            try:
                self.csv_file.close()
            except:
                pass
      
        if not self.filename.get():
            messagebox.showwarning("Warning", "Set a filename!")
            return

        # Check input data validity
        try:
            start_freq = float(self.start_freq_entry.get())
            stop_freq = float(self.stop_freq_entry.get())
            points = int(self.points_entry.get())
            delay = float(self.delay_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid input!")
            return

        # Check selected VISA device
        try:
            selected_index = self.visa_listbox.curselection()[0]
            device_address = self.visa_listbox.get(selected_index)
        except IndexError:
            messagebox.showerror("Error", "Select a VISA device!")
            return

        # Initialize the measurement
        num_points = int(self.points.get())
        start_freq = max(int(self.start_freq.get()), 20)
        stop_freq = min(int(self.end_freq.get()), 1000000)
        self.output_csv = os.path.join(self.filepath.get(), self.filename.get() + ".csv")
        self.output_plot = os.path.join(self.plots_dir, self.filename.get() + ".png")
        self.measurement_delay = int(self.delay.get())

        # Connect to VISA device
        try:
            self.inst = self.rm.open_resource(device_address)
            self.inst.timeout = 5000
            d1,d2,d3,d4=self.inst.query('*IDN?').strip().split(",")
            self.meas_status.set(f"Instrument: \n{d1},\n{d2},\n{d3},\n{d4}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to VISA device: {e}")
            return
        
        # Set measurement mode
        mode = self.mode.get()
        try:
            scpi_code = mode_scpi[mode]
            self.inst.write(f":FUNCtion:IMPedance:TYPE {scpi_code}")
        except KeyError:
            messagebox.showerror("Error", "No measurement mode selected!")
            return

        #Set LONG integration time, 1 measurement per point (no averaging)
        self.inst.write(":APER LONG, 1") 

        # Create logarithmically distributed frequency list through the defined frequency range
        
        log_start = math.log10(start_freq)
        log_stop = math.log10(stop_freq)
        step = (log_stop - log_start) / (num_points - 1)

        self.frequencies = [
            10 ** (log_start + i * step)
            for i in range(num_points)
            ]

        answer = messagebox.askokcancel("Info", "Measurement starts!")
        if not answer:
            return

        # Open CSV for writing measurement data
        self.csv_file = open(self.output_csv, mode='w', newline='', encoding='utf-8', buffering=1 )
        self.writer = csv.writer(self.csv_file)
        label1, label2 = mode_labels[mode]
        self.writer.writerow(["Frequency (Hz)", label1, label2])

        # Reset state
        self.current_index = 0
        self.meas_status.set("")
        
        #self.root.update_idletasks()

        # Run measurement
        self.run_measurement_step()
    
    def run_measurement_step(self):
        # Run the frequency sweep
        
        if self.current_index < len(self.frequencies):
            f = self.frequencies[self.current_index]

            # Set frequency
            self.inst.write(f"FREQ {f}")
            
            # Get measurement data
            response = self.inst.query("FETC?")
            parts = response.strip().split(',')
            z = float(parts[0])
            p = float(parts[1])

            # Display current measurement state
            mode=self.mode.get()
            label1, label2 = mode_labels[mode]
            self.meas_status.set(
                f"Measurement in progress:\n\n"
                f"Frequency: {f:.10g} Hz\n"
                f"{label1} = {z:.15g}\n"
                f"{label2} = {p:.15g}"
            )

            #self.root.update_idletasks()

            # Write to CSV
            self.writer.writerow([f, z, p])

            # Move to next frequency
            self.current_index += 1
            self.root.after(int(self.measurement_delay * 1000), self.run_measurement_step)

        else:
            self.meas_status.set("Measurement done ✅")
            self.csv_file.close()
            self.inst.close()

            answer2 = messagebox.askokcancel("Info", "Make a plot?")
            if answer2:
                self.plot_results()

    def plot_results(self):
        import matplotlib.pyplot as plt # for plot generation

        # Plot results
        frequencies = [] # Empty list to store the frequencies
        impedances = [] # Empty list to store impedances
        phases = [] # Empty list to store phases in radian

        with open(self.output_csv , 'r') as file: # Opening the CSV file in read mode
            reader = csv.reader(file) # Creating a reader object for each line
            next(reader)  # Skip header
            for row in reader: 
                freq = float(row[0])
                z = float(row[1]) # Creating a float from each element
                p = float(row[2])
                frequencies.append(freq)
                impedances.append(z) # Appending the new values to the previous list
                phases.append(p)

        mode=self.mode.get()
        label1, label2 = mode_labels[mode]
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10,5))

        ax1.loglog(frequencies, impedances, marker='o', linewidth=1)
        ax1.set_xlabel("Frequency (Hz)")
        ax1.set_ylabel(label1)
        ax1.grid(True, which="both")

        ax2.semilogx(frequencies, phases, marker='o', linewidth=1)
        ax2.set_xlabel("Frequency (Hz)")
        ax2.set_ylabel(label2)
        ax2.grid(True, which="both")

        fig.tight_layout()
        fig.savefig(self.output_plot, dpi=300)
        plt.show()

class PlotModule: # Plot module
    def __init__(self, root):
        self.root = root
        self.files = []  # List files (S-param or CSV)
        self.file_types = {}  # Dict: file -> type ('S' or 'CSV')
        self.show_markers = tk.BooleanVar(value=False)  # Enable showing markers

        # Frame for the plot module
        self.frame = tk.Frame(root, bd=1, relief="solid")
        self.frame.pack(anchor="nw", padx=10, pady=5, fill="x")
        self.frame.grid_propagate(False)
        self.frame.config(width=1000, height=250)


        # Add plot button
        tk.Button(self.frame, text="Add file", command=self.add_file).grid(row=2, column=6, padx=5)

        # Remove plot button
        tk.Button(self.frame, text="Remove file", command=self.remove_file).grid(row=3, column=6, padx=5)

        #Create plot button
        tk.Button(self.frame, text="Create plot", command=self.plot_files).grid(row=4, column=6)

        # Show data points button
        tk.Checkbutton(self.frame, text="Show data points", variable=self.show_markers, width=24).grid(row=5, column=6)

        # ------------------------------- Axis settings ------------------------------------------------
        tk.Label(self.frame, text="Plot settings", font=("Arial", 10, "bold")).grid(row=1, column=1, pady=2, columnspan=4)

        tk.Label(self.frame, text="X label:").grid(row=2, column=1, sticky="e", pady=10)
        self.xl = tk.StringVar(value="")
        tk.Entry(self.frame, textvariable=self.xl, width=12).grid(row=2, column=2, sticky="w")

        tk.Label(self.frame, text="Y label:").grid(row=2, column=3, sticky="e", pady=10)
        self.yl = tk.StringVar(value="")
        tk.Entry(self.frame, textvariable=self.yl, width=12).grid(row=2, column=4,sticky="w")

        tk.Label(self.frame, text="      X axis type:").grid(row=3, column=1, sticky="e", pady=10)
        self.xscale = tk.StringVar(value="log")
        ttk.Combobox(self.frame, textvariable=self.xscale, values=["linear", "log"], width=9, justify="center").grid(row=3, column=2,sticky="w")

        tk.Label(self.frame, text="      Y axis type:").grid(row=3, column=3, sticky="e", pady=10)
        self.yscale = tk.StringVar(value="linear")
        ttk.Combobox(self.frame, textvariable=self.yscale, values=["linear", "log"], width=9, justify="center").grid(row=3, column=4,sticky="w")

        tk.Label(self.frame, text="X min:").grid(row=4, column=1,sticky="e", pady=10)
        self.xmin = tk.DoubleVar(value=0)
        tk.Entry(self.frame, textvariable=self.xmin, width=12).grid(row=4, column=2,sticky="w")

        tk.Label(self.frame, text="X max:").grid(row=4, column=3,sticky="e", pady=10)
        self.xmax = tk.DoubleVar(value=0)
        tk.Entry(self.frame, textvariable=self.xmax, width=12).grid(row=4, column=4,sticky="w")

        tk.Label(self.frame, text="Y min:").grid(row=5, column=1,sticky="e", pady=10)
        self.ymin = tk.DoubleVar(value=0)
        tk.Entry(self.frame, textvariable=self.ymin, width=12).grid(row=5, column=2,sticky="w")

        tk.Label(self.frame, text="Y max:").grid(row=5, column=3,sticky="e", pady=10)
        self.ymax = tk.DoubleVar(value=0)
        tk.Entry(self.frame, textvariable=self.ymax, width=12).grid(row=5, column=4,sticky="w")

        tk.Label(self.frame, text="", width=40).grid(row=1, column=5)
        tk.Label(self.frame, text="Plotted data", width=12,font=("Arial", 10, "bold")).grid(row=1, column=7)


        # List of the added measurement files
        self.listbox = tk.Listbox(self.frame, height=10, width=30, justify="center")
        self.listbox.grid(row=2, column=7, rowspan=3,padx=10)

    def add_file(self):
        # Add a measurement file
        file = filedialog.askopenfilename(filetypes=[("S-parameter or CSV files", "*.s1p *.s2p *.s4p *.csv")])
        if file and file not in self.files:
            self.files.append(file)
            ext = os.path.splitext(file)[1].lower()
            if ext == ".csv":
                self.file_types[file] = "CSV"
            else:
                self.file_types[file] = "S"
            self.listbox.insert(tk.END, os.path.basename(file))

    def remove_file(self):
        # Remove a measurement file
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            fpath = self.files.pop(index)
            self.file_types.pop(fpath, None)
            self.listbox.delete(index)

    def plot_files(self):
        # Import libaries
        import matplotlib.pyplot as plt
        import skrf as rf

        # Create a plot
        if not self.files:
            messagebox.showwarning("Warning", "No file selected!")
            return

        plt.figure(dpi=140, figsize=(6,4))
        markers = ['o', 'x', '*', '+', 's', 'd', '^']  # Marker list

        for i, fpath in enumerate(self.files):
            marker = markers[i % len(markers)] if self.show_markers.get() else ''  # If enabled, use markers
            try:
                if self.file_types[fpath] == "CSV":
                    x, y = [], []
                    with open(fpath, 'r', newline='') as csvfile:
                        reader = csv.reader(csvfile)
                        for row in reader:
                            try:
                                x.append(float(row[0]))
                                y.append(float(row[1]))
                            except ValueError:
                                continue
                    plt.plot(x, y, label=os.path.basename(fpath), marker=marker)
                else:
                    ntwk = rf.Network(fpath)
                    frek = ntwk.frequency.f
                    Z = abs(50*(1+ntwk.s[:,0,0])/(1-ntwk.s[:,0,0]))
                    plt.plot(frek, Z, label=os.path.basename(fpath), marker=marker)
            except Exception as e:
                messagebox.showerror("Error", f"Error while reading file: {fpath}\n{e}")

        plt.xscale(self.xscale.get())
        plt.yscale(self.yscale.get())
        plt.xlim(self.xmin.get(), self.xmax.get())
        plt.ylim(self.ymin.get(), self.ymax.get())
        plt.xlabel(self.xl.get())
        plt.ylabel(self.yl.get())
        plt.grid(which="both")
        plt.legend(fontsize="x-small")
        plt.title("Evaluation Plot")
        plt.show()

if __name__ == "__main__":
    root = tk.Tk()
    app = VisaApp(root)
    root.mainloop()
