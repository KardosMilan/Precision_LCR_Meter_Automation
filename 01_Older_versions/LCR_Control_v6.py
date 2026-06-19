import tkinter as tk # Module for GUI
from tkinter import filedialog, messagebox, ttk
import pyvisa #VISA communication module
import csv    #Handle csv files
import os     #Handle files
import sys    #Check runtime environment
import threading
import winsound

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

# Dictionary that maps measurement mode names to their unit of measure
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

# ---------------------- Number formatting helper ----------------------

def format_entry_real_time(entry_widget, event=None):
    value = entry_widget.get()
    cursor_pos = entry_widget.index(tk.INSERT)

    clean_value = value.replace(".", "")

    if clean_value.isdigit():
        num = int(clean_value)
        formatted = f"{num:,}"
        formatted = formatted.replace(",", ".")

        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, formatted)

        new_pos = cursor_pos + (formatted.count(".") - value.count("."))
        entry_widget.icursor(new_pos)

        entry_widget.num_value = num
    else:
        entry_widget.num_value = 0

def attach_number_formatter(entry_widget):
    entry_widget.num_value = 0
    entry_widget.bind(
        "<KeyRelease>",
        lambda e: format_entry_real_time(entry_widget)
    )

def visa_connect(rm, device_address, timeout=5):
    result = {}

    def worker():
        try:
            inst = rm.open_resource(device_address)
            inst.timeout = 2000
            idn = inst.query("*IDN?")
            result["inst"] = inst
            result["idn"] = idn
        except Exception as e:
            result["error"] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout)   # vár maximum timeout másodpercet

    if t.is_alive():
        raise TimeoutError("Device did not respond")

    if "error" in result:
        raise result["error"]

    return result["inst"]

def convert_number(value, decimal_sep):
    if isinstance(value, float):
        s = f"{value:.6g}"
        if decimal_sep == ",":
            s = s.replace(".", ",")
        return s
    return str(value)

# -------------------------- Main application --------------------------
class VisaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LCR Control Tool")

        # Notebook view
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        # Create notebook tabs
        self.manual_tab = tk.Frame(self.notebook)
        self.notebook.add(self.manual_tab, text="Manual meas.")

        self.sweep_tab = tk.Frame(self.notebook)
        self.notebook.add(self.sweep_tab, text="Sweep meas.")

        self.plot_tab = tk.Frame(self.notebook)
        self.notebook.add(self.plot_tab, text="Generate Plot")

        # open VISA Resource Manager
        self.rm = pyvisa.ResourceManager()

        # Disable resizing
        self.root.resizable(False, False)

        # Link submodules
        self.sweep_module = SweepModule(self.sweep_tab, self.rm)
        self.plot_module = PlotModule(self.plot_tab)
        self.manual_module = ManualModule(self.manual_tab, self.rm)

        tk.Label(root, text="Software: v7.0").pack(padx=10,anchor="ne")

# --------------------- Manual measurement module ----------------------
class ManualModule:
    def __init__(self, root, rm):
        self.root = root
        self.rm = rm # Get VISA Resource Manager
        self.last_measure_extra_line = 0

        # Base directory
        self.base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
        self.logs_dir = os.path.join(self.base_dir, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)

        # Main frame
        self.frame = tk.Frame(root)
        self.frame.pack(anchor="nw", padx=10, pady=5, fill="x")
        self.frame.pack_propagate(False)
        self.frame.config(width=1000, height=320)
        
        
        # ___________________ VISA devices frame ________________________
        self.top1_frame = tk.Frame(self.frame, bd=1, relief="solid")
        self.top1_frame.grid(row=0, column=0, padx=5, pady=5, sticky="n")
        self.top1_frame.grid_propagate(False)
        self.top1_frame.config(width=610, height=320)
        
        tk.Label(self.top1_frame, text="Accessible VISA devices:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        self.visa_listbox = tk.Listbox(self.top1_frame, height=5, width=32,  exportselection=False)
        self.visa_listbox.grid(row=1, column=0, padx=10, pady=0)
        
        self.refresh_button = tk.Button(self.top1_frame, text="Update", command=self.refresh_visa_devices)
        self.refresh_button.grid(row=0, column=1, padx=10, pady=10)

        self.device_status = tk.StringVar(value="No device selected!")
        tk.Label(self.top1_frame, textvariable=self.device_status, fg="blue").grid(row=2, column=0, padx=15, pady=33)
        self.visa_listbox.bind("<space>", self.manual_measure_entry_safe)
        self.visa_listbox.bind("<Delete>", self.delete_last_entry)
        self.visa_listbox.bind("<<ListboxSelect>>", self.update_device_status)
        self.refresh_visa_devices()

        # File controls
        self.sub_frame = tk.Frame(self.top1_frame, relief="solid")
        self.sub_frame.grid(row=4, column=0, padx=5, pady=5, sticky="n")
        tk.Label(self.sub_frame, text="Output fomat:").grid(row=0, column=0, sticky="e", pady=10)
        self.output_format = tk.StringVar(value="CSV [HU]")        
        self.output_entry=ttk.Combobox(self.sub_frame, textvariable=self.output_format, values=["TXT", "CSV [HU]", "CSV [EN]"], width=9, justify="center")
        self.output_entry.grid(row=0, column=1,sticky="w")
        self.output_entry.bind("<space>", lambda e: "break")
        self.output_entry.bind("<space>", self.manual_measure_entry_safe)
        self.output_entry.bind("<Delete>", lambda e: "break")
        self.output_entry.bind("<Delete>", self.delete_last_entry)

        

        
        self.current_file_loaded = ""
        tk.Label(self.top1_frame, text="Filename:").grid(row=0, column=2, padx=5, sticky='e')
        self.filename = tk.StringVar()
        self.filename_entry = tk.Entry(self.top1_frame, textvariable=self.filename, width=30)
        self.filename_entry.grid(row=0, column=3, padx=5)
        self.filename.trace_add("write", lambda *args: self.load_console_from_file())
        self.filename_entry.bind("<space>", lambda e: "break")
        self.filename_entry.bind("<space>", self.manual_measure_entry_safe)
        self.filename_entry.bind("<Delete>", lambda e: "break")
        self.filename_entry.bind("<Delete>", self.delete_last_entry)

        # Save folder selection
        tk.Label(self.top1_frame, text="Save folder:").grid(row=4, column=2, padx=5, sticky='e')
        self.save_dir = tk.StringVar(value=self.logs_dir)
        folder_selected=self.save_dir.get()
        parts = folder_selected.replace("\\", "/").split("/")
        display_path = ".../"+"/".join(parts[-1:])
        self.save_display = tk.StringVar(value=display_path)
        self.save_dir_entry = tk.Entry(self.top1_frame, textvariable=self.save_display, width=31, state="readonly")
        self.save_dir_entry.grid(row=4, column=3, padx=5, sticky='w', columnspan=4)

        icon_dir = os.path.join(os.path.dirname(__file__), "icons")
        self.folder_icon = tk.PhotoImage(file=os.path.join(icon_dir, "open.png"))
        self.delete_icon = tk.PhotoImage(file=os.path.join(icon_dir, "nok.png"))
        self.check_icon = tk.PhotoImage(file=os.path.join(icon_dir, "ok.png"))
        #Set icons
        self.help2_icon = tk.PhotoImage(file=os.path.join(icon_dir, "help2.png"))
        self.browse_button = tk.Button(self.top1_frame, image=self.folder_icon, command=self.select_save_folder)
        self.browse_button.grid(row=4, column=4, padx=2, sticky='w')

        # Help button
        self.help2_save_button = tk.Button(self.top1_frame, image=self.help2_icon, command=self.help2,relief="flat")
        self.help2_save_button.grid(row=4, column=1,padx=5, pady=5, sticky='w')

        tk.Label(self.top1_frame, text="Limit table:").grid(row=5, column=2, padx=5, sticky='e')
        self.limit_display = tk.StringVar(value="")
        self.limit_entry = tk.Entry(self.top1_frame, textvariable=self.limit_display, width=31, state="readonly")
        self.limit_entry.grid(row=5, column=3, padx=5, sticky='w', columnspan=4)
        self.browse_button = tk.Button(self.top1_frame, image=self.folder_icon, command=self.select_limit_file)
        self.browse_button.grid(row=5, column=4, padx=2, sticky='w')
        self.check_button = tk.Button(self.top1_frame, image=self.check_icon, command=self.check_limits)
        self.check_button.grid(row=5, column=5, padx=2, sticky='w')

        self.show_limit = tk.BooleanVar(value=False)  # Enable showing limits
        # Show limit deviation
        tk.Checkbutton(self.top1_frame, text="Show limit deviation", variable=self.show_limit, width=15).grid(row=6, column=3, padx=2, sticky='w')

        # Start button
        self.start_button = tk.Button(
            self.top1_frame, text="Start\n(Space)",
            command=self.manual_measure,
            font=("Arial", 16, "bold"), fg="white", bg="red", width=14, height=2
        )
        self.start_button.grid(row=1, column=3, padx=5, pady=10)
        self.top1_frame.bind("<space>", self.manual_measure_entry_safe)
        self.top1_frame.bind("<Delete>", self.delete_last_entry)

        # Measurement status view
        self.meas_status = tk.StringVar()
        tk.Label(self.top1_frame, textvariable=self.meas_status).grid(row=2, column=3, padx=5, pady=10, rowspan=2)

        # SCPI → GUI mapping
        self.scpi_to_gui = {v: k for k, v in mode_scpi.items()}

        # ___________________ LOG console vindow ________________________
        # LOG PANEL
        self.top2_frame = tk.Frame(self.frame, bd=1, relief="solid", width=450, height=320)
        self.top2_frame.grid(row=0, column=1, padx=5, pady=5)
        self.top2_frame.grid_propagate(False)
        self.top2_frame.grid_rowconfigure(1, weight=1)
        self.top2_frame.grid_columnconfigure(0, weight=1)

        # Maseurement log
        tk.Label(self.top2_frame, text="Measurement log")\
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        
        self.delete_last_button = tk.Button(self.top2_frame, image=self.delete_icon, command=self.delete_last_entry).grid(row=0, column=1, padx=5, pady=5, sticky="e")

        # Text widget
        self.console_text = tk.Text(self.top2_frame, wrap="none")
        self.console_text.grid(row=1, column=0, sticky="nsew", padx=(5,0), pady=5)

        # Scrollbar
        scrollbar = tk.Scrollbar(self.top2_frame, command=self.console_text.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0,5), pady=5)
        self.console_text.config(yscrollcommand=scrollbar.set)
        self.console_text.config(state="disabled") # Only read mode
        self.console_text.bind("<space>", self.manual_measure_entry_safe)
        self.console_text.bind("<Delete>", self.delete_last_entry)

    
    def help2(self):
        # Show a help window for measurement initialization
        messagebox.showinfo("Help", "CSV [HU]: separator: ';' decimal point: ',' \n\n" \
        "CSV [EN]: separator: ',' decimal point: '.' \n\n"\
        "TXT: separator: '/t' decimal point: '.' \n\n")

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
            inst = visa_connect(self.rm, device_address,2000)
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
        save_folder = self.save_dir.get() if self.save_dir.get() else self.logs_dir
        
        fmt = self.output_format.get()
        if fmt == "CSV [HU]":
            output = os.path.join(save_folder, self.filename.get() + ".csv")
            delimiter = ";"
            decimal_sep = ","
        elif fmt == "CSV [EN]":
            output = os.path.join(save_folder, self.filename.get() + ".csv")
            delimiter = ","
            decimal_sep = "."
        else:  # TXT
            output = os.path.join(save_folder, self.filename.get() + ".txt")
            delimiter = "\t"
            decimal_sep = "." 

        # Kiinduló index
        last_index = 0
        if os.path.isfile(output):
            with open(output, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=delimiter)
                lines = list(reader)
                if len(lines) > 1:  # ha van már adat
                    try:
                        last_index = int(lines[-1][0])
                    except:
                        last_index = 0
        else:
            lines = []

        # Query frequency and measurement
        freq = float(inst.query(":FREQuency?").strip())
        resp = inst.query("FETC?").strip().split(',')
        z, p = float(resp[0]), float(resp[1])

        # New index
        current_index = last_index + 1

        # Write to file
        new_file=False
        try:
            with open(output, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=delimiter)
                if not lines:  # if new file write header
                    writer.writerow(["Index", "Frequency (Hz)", label1, label2])
                    new_file=True
                writer.writerow([convert_number(current_index, decimal_sep),
                 convert_number(freq, decimal_sep),
                 convert_number(z, decimal_sep),
                 convert_number(p, decimal_sep)])
        except Exception as e:
            messagebox.showerror("Error", str(e))
            inst.close()
            return

        # Update GUI
        self.meas_status.set(
            f"Pin No.: {current_index:.3g}\nFrequency: {freq:.10g} Hz\n{label1} = {z:.15g}\n{label2} = {p:.15g}"
        )

        # Update console
        self.current_file_loaded = "" 
        self.insert_measurement_line(current_index, freq,z,p, new_file, label1, label2) 

        inst.close()

    def insert_measurement_line(self, index, freq, z, p, new_file, label1, label2):
        self.console_text.config(state="normal")
        self.console_text.tag_config("out_of_limit", foreground="red")
        self.console_text.tag_config("no_limit", foreground="blue")

        if self.col_widths_console is None or new_file:
            header_labels = ["Index", "Frequency (Hz)", label1, label2]
            self.col_widths_console = [len(lbl)+2 for lbl in header_labels]
            header_line = "\t".join(f"{lbl:^{self.col_widths_console[i]}}" for i, lbl in enumerate(header_labels)) + "\n"
            self.console_text.insert(tk.END, header_line.rstrip())
            

        # Sor formázása
        line = "\t".join([
            f"{index:^{self.col_widths_console[0]}}",
            f"{freq:^{self.col_widths_console[1]}.6g}",
            f"{z:^{self.col_widths_console[2]}.6g}",
            f"{p:^{self.col_widths_console[3]}.6g}"
        ]) + "\n"

        # Limit ellenőrzés
        if self.show_limit.get() and self.limit_entry.get()=="":
            messagebox.showwarning("Warning", "Load a limit CSV file first!")

        tag_to_use = None
        feedback_line = ""
        if self.show_limit.get() and hasattr(self, "limits"):
            if index-1 < len(self.limits) and self.limits[index-1] is not None:
                ID, target, plus, minus = self.limits[index-1]
                if z > target + plus or z < target - minus:
                    tag_to_use = "out_of_limit"
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                    

            else:
                feedback_line = f"⚠ No limit for index {index}\n"
                tag_to_use = "no_limit"
                self.last_measure_extra_line +=1
                winsound.MessageBeep(winsound.MB_ICONHAND)

        if tag_to_use:
            self.console_text.insert(tk.END, line, tag_to_use)
            if feedback_line:
                self.console_text.insert(tk.END, feedback_line, tag_to_use)
        else:
            self.console_text.insert(tk.END, line)

        self.console_text.see(tk.END)
        self.console_text.config(state="disabled")

    def manual_measure_entry_safe(self, event):
        # Trigger measurement running with SPACE button
        self.manual_measure()  
        return "break"  

    def load_console_from_file(self):
        filename = self.filename.get()
        if not filename:
            return

        if filename == self.current_file_loaded:
            return

        self.current_file_loaded = filename
        save_folder = self.save_dir.get() if self.save_dir.get() else self.logs_dir

        fmt = self.output_format.get()
        if fmt == "CSV [EN]":
            path = os.path.join(save_folder, filename + ".csv")
            delimiter = ","
            decimal_sep = "."
        elif fmt == "CSV [HU]":
            path = os.path.join(save_folder, filename + ".csv")
            delimiter = ";"
            decimal_sep = ","
        else:  # TXT
            path = os.path.join(save_folder, filename + ".txt")
            delimiter = "\t"
            decimal_sep = "."

        self.console_text.config(state="normal")
        self.console_text.delete("1.0", tk.END)
        self.console_text.config(font=("Courier New", 10))
        self.col_widths_console = None  # reset

        if os.path.isfile(path):
            rows = []
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    formatted_row = []
                    for cell in row:
                        try:
                            # Ha CSV HU, pontot használunk float olvasásnál
                            if fmt == "CSV [HU]":
                                cell = cell.replace(",", ".")
                            num = float(cell)
                            formatted_cell = f"{num:.6g}"
                            # Konzolban mindig tabulátor, tehát HU pont/cella itt már ok
                            # Nem kell visszacserélni ','-ra
                        except ValueError:
                            formatted_cell = cell
                        formatted_row.append(formatted_cell)
                    rows.append(formatted_row)

            if rows:
                num_cols = len(rows[0])
                self.col_widths_console = [max(len(r[col]) for r in rows) for col in range(num_cols)]

                for row in rows:
                    line = "\t".join(f"{cell:^{self.col_widths_console[i]}}" for i, cell in enumerate(row))
                    self.console_text.insert(tk.END, line + "\n")

        self.console_text.see(tk.END)
        self.console_text.config(state="disabled")

    def select_save_folder(self):
        # Modify the default save folder
        folder_selected = filedialog.askdirectory(initialdir=self.save_dir.get(), title="Select folder to save measurements")
        if folder_selected:
            self.save_dir.set(folder_selected)
            parts = folder_selected.replace("\\", "/").split("/")
            display_path = ".../"+"/".join(parts[-1:])
            self.save_display.set(display_path)

    def select_limit_file(self):
        # Limit fájl kiválasztása
        file_selected = filedialog.askopenfilename(
            initialdir=self.save_dir.get(),
            title="Select limit CSV file",
            filetypes=[("CSV files", "*.csv")]
        )
        if file_selected:
            self.limit_file = file_selected
            # Csak a fájlnevet jelenítjük meg
            filename_only = os.path.basename(file_selected)
            self.limit_display.set(filename_only)

            # Limit fájl beolvasása
            self.limits = []
            try:
                with open(self.limit_file, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header = next(reader)  # skip header
                    for row in reader:
                        if len(row) < 3:
                            continue
                        try:
                            ID = float(row[0])
                            target = float(row[1])
                            plus = float(row[2])
                            minus = float(row[3])
                            self.limits.append((ID, target, plus, minus))
                        except ValueError:
                            continue
            except Exception as e:
                messagebox.showerror("Error", f"Failed to read limit file:\n{e}")
                return
      
    def check_limits(self):
        if not hasattr(self, "limit_file") or not self.limit_file:
            messagebox.showinfo("Info", "No limit file selected!")
            return
         
        # Read Console
        filename = self.filename.get()
        if not filename:
            messagebox.showwarning("Warning", "Set a filename first!")
            return

        save_folder = self.save_dir.get() if self.save_dir.get() else self.logs_dir
        if self.output_format.get()=="CSV [HU]":
            path = os.path.join(save_folder, self.filename.get() + ".csv")
            delimiter = ";"

        if self.output_format.get()=="CSV [EN]":
            path = os.path.join(save_folder, self.filename.get() + ".csv")
            delimiter = ","
        else:
            path = os.path.join(save_folder, self.filename.get() + ".txt")    
            delimiter = "\t"  

        if not os.path.isfile(path):
            messagebox.showwarning("Warning", "Measurement file not found!")
            return

        rows = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)

        if len(rows)-1 != len(self.limits):
            messagebox.showwarning("Warning", "Limit file and measurement file have different number of data rows!")
            return

        self.console_text.config(state="normal")
        self.console_text.delete("1.0", tk.END)
        self.console_text.tag_config("out_of_limit", foreground="red")
        self.console_text.config(font=("Courier New", 10))

        if not rows:
            self.console_text.config(state="disabled")
            return
        num_cols = len(rows[0])
        col_widths = [max(len(str(r[col])) for r in rows) for col in range(num_cols)]

        for idx, row in enumerate(rows):
            line = ""
            for i, cell in enumerate(row):
                line += f"{cell:^{col_widths[i]}} "
            line = line.rstrip() + "\n"

            if idx == 0:
                self.console_text.insert(tk.END, line)
            else:
                try:
                    z_val = float(row[2])
                    ID, target, plus, minus = self.limits[idx-1] if idx-1 < len(self.limits) else (0,0,0)
                    if z_val > target + plus or z_val < target - minus:
                        self.console_text.insert(tk.END, line, "out_of_limit")
                    else:
                        self.console_text.insert(tk.END, line)
                except ValueError:
                    self.console_text.insert(tk.END, line)

        self.console_text.config(state="disabled")

    def refresh_visa_devices(self):
        # Refresh VISA devices if GPIB device was not connected on application launch
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
        # Update the status of the VISA devices
        try:
            device = self.visa_listbox.get(self.visa_listbox.curselection()[0])
            self.device_status.set(f"Selected device: {device}")
        except IndexError:
            self.device_status.set("No device selected!")
    
    def delete_last_entry(self, event=None):

        filename = self.filename.get()
        if not filename:
            messagebox.showwarning("Warning", "Set a filename!")
            return

        save_folder = self.save_dir.get() if self.save_dir.get() else self.logs_dir

        if self.output_format.get()=="CSV [HU]":
            path = os.path.join(save_folder, self.filename.get() + ".csv")
            delimiter = ";"

        if self.output_format.get()=="CSV [EN]":
            path = os.path.join(save_folder, self.filename.get() + ".csv")
            delimiter = ","
        else:
            path = os.path.join(save_folder, self.filename.get() + ".txt")    
            delimiter = "\t"  

        if not os.path.isfile(path):
            messagebox.showwarning("Warning", "File does not exist!")
            return

        # Beolvassuk a teljes fájlt
        with open(path, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f, delimiter=delimiter))

        # Ha csak fejléc van vagy üres
        if len(rows) <= 1:
            messagebox.showinfo("Info", "No measurement to delete!")
            return

        # Utolsó adat sor törlése
        rows.pop()

        # Fájl újraírása
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=delimiter)
            writer.writerows(rows)
           

        self.console_text.config(state="normal")

        if self.last_measure_extra_line > 0:
            self.console_text.delete("end-3l", "end-1l")   # 2 sor törlése
            self.last_measure_extra_line-=1
            print(self.last_measure_extra_line)
        else:
            self.console_text.delete("end-2l", "end-1l")   # 1 sor törlése

        self.console_text.config(state="disabled")

# ---------------------- Sweep measurement module ----------------------
class SweepModule: 
    def __init__(self, root, rm):
        self.root = root
        self.rm = rm # Get VISA Resource Manager
        
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
        self.top1_frame.config(width=460, height=320)

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
        self.points_label = tk.Label(self.top1_frame, text="Number of measurement points [pc]:")
        self.points_label.grid(row=2, column=0, padx=5, pady=10, sticky="e")

        self.points = tk.IntVar()
        self.points_entry = tk.Entry(self.top1_frame, textvariable=self.points, width=30)
        self.points_entry.grid(row=2, column=1, padx=5, pady=10, sticky="w")

        # Delay entry
        self.delay_label = tk.Label(self.top1_frame, text="Delay [s]:")
        self.delay_label.grid(row=3, column=0, padx=5, pady=10, sticky="e")
        self.delay = tk.IntVar()
        self.delay_entry = tk.Entry(self.top1_frame, textvariable=self.delay, width=30)
        self.delay_entry.grid(row=3, column=1, padx=5, pady=10, sticky="w")

        # Number formatter
        attach_number_formatter(self.start_freq_entry)
        attach_number_formatter(self.stop_freq_entry)
        attach_number_formatter(self.points_entry)
        attach_number_formatter(self.delay_entry)

        # Measurement mode entry
        self.mode_label = tk.Label(self.top1_frame, text="Measurement mode:")
        self.mode_label.grid(row=4, column=0, padx=5, pady=10, sticky="e")
        self.mode = tk.StringVar()
        self.combo = ttk.Combobox(self.top1_frame, textvariable=self.mode, values=sorted(mode_labels.keys()), width=27)
        self.combo.grid(row=4, column=1, padx=5, pady=10, sticky="w")

        # Help button
        self.help_save_button = tk.Button(self.top1_frame, image=self.help_icon, command=self.help,relief="flat")
        self.help_save_button.grid(row=0, column=3,padx=10, pady=10, sticky='e')

        # __________________________________ Handle VISA devices __________________________________________________
        # List VISA devices
        self.top2_frame = tk.Frame(self.top12_container, bd=1, relief="solid")
        self.top2_frame.grid(row=0, column=1, padx=5, pady=5, sticky="n")
        self.top2_frame.grid_propagate(False)
        self.top2_frame.config(width=600, height=320)

        self.visa_frame = tk.Frame(self.top2_frame, bd=0, relief="solid")
        self.visa_frame.grid(row=0, column=0, padx=5, pady=5, sticky="wn")

        self.visa_label = tk.Label(self.visa_frame, text="Accesible VISA devices:")
        self.visa_label.grid(row=0, column=0, padx=10, pady=10,sticky='w')

        # Display device status
        self.device_status = tk.StringVar(value="No device selected!")
        self.device_status_label = tk.Label(self.top2_frame, textvariable=self.device_status, fg="blue")
        self.device_status_label.grid(row=2, column=0, padx=15, pady=50,sticky='w')

        # Update VISA devices list
        self.refresh_button = tk.Button(self.visa_frame, text="Update", command=self.refresh_visa_devices)
        self.refresh_button.grid(row=0, column=1, padx=10, pady=10)
        
        # Listbox for choosing device
        self.visa_listbox = tk.Listbox(self.top2_frame, height=5, width=32,exportselection=False)
        self.visa_listbox.grid(row=1, column=0, padx=10, pady=0)
        self.refresh_visa_devices()
        self.visa_listbox.bind("<<ListboxSelect>>", self.update_device_status)

        # ___________________________________ Save file  ____________________________________________________________
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
    
    def help(self):
        # Show a help window for measurement initialization
        messagebox.showinfo("Help", "Start frequency [Hz]: integer, if smaller than device range -> device range min \n\n" \
        "End frequency [Hz]: integer, if greater than device range -> device range max  \n\n" \
        "Number of measurement points [pc]: min 1, evenly distributed \n\n" \
        "Delay [s]: integer, min 1")

    def refresh_visa_devices(self):
        # Refresh VISA devices if GPIB device was not connected on application launch
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
        # Update the status of the VISA devices
        try:
            selected_index = self.visa_listbox.curselection()[0]
            device = self.visa_listbox.get(selected_index)
            self.device_status.set(f"Selected device: {device}")
        except IndexError:
            self.device_status.set("No device selected!")
    
    # ___________ Measurement Sequence ___________
    def start_measurement(self):
        #Import math module
        import math

        # Close files and VISA device connections if they are open
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
      
        # Check filename
        if not self.filename.get():
            messagebox.showwarning("Warning", "Set a filename!")
            return

        # Get input data
        try:
            start_freq = self.start_freq_entry.num_value
            stop_freq = self.stop_freq_entry.num_value
            num_points = self.points_entry.num_value
            self.measurement_delay = self.delay_entry.num_value
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
        self.output_csv = os.path.join(self.filepath.get(), self.filename.get() + ".csv")
        self.output_plot = os.path.join(self.plots_dir, self.filename.get() + ".png")

        
        try:
            self.inst = self.rm.open_resource(device_address)
            self.inst.timeout = 5000
            d1,d2,d3,d4=self.inst.query('*IDN?').strip().split(",")
            self.meas_status.set(f"Instrument: \n{d1},\n{d2},\n{d3},\n{d4}")

            # Decide maximum frequency
            opt = self.inst.query("*OPT?")
            min_freq=20
            if "032" in opt:
                max_freq = 300000
            elif "052" in opt:
                max_freq = 500000
            elif "102" in opt:
                max_freq = 1000000
            else:
                max_freq = 5000000

        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to VISA device: {e}")
            return
        
        # Set measurement mode
        mode = self.mode.get()
        try:
            scpi_code = mode_scpi[mode]
            self.inst.write(f":FUNCtion:IMPedance:TYPE {scpi_code}")
        except Exception:
            messagebox.showerror("Error", "No measurement mode selected!")
            return

        #Set LONG integration time, 1 measurement per point (no averaging)
        self.inst.write(":APER LONG, 1") 

        # Check input data validity
        if start_freq <= 0 or stop_freq <= 0:
            messagebox.showerror("Error", "Frequencies must be > 0")
            return
        if min_freq>start_freq:
            messagebox.showerror("Error", f"Set start frequency above or equal {min_freq} [Hz]!")
            return
        if max_freq<stop_freq:
            messagebox.showerror(f"Error", f"Set stop frequency below or equal {max_freq} [Hz]!")
            return
        if self.measurement_delay<1:
            messagebox.showerror(f"Error", f"Set delay time above or equal 1 [s]!")
            return
        if num_points<=1:
            messagebox.showerror(f"Error", f"Set number of points above 1 [pc]!")
            return

        # Create logarithmically distributed frequency list through the defined frequency range
        log_start = math.log10(start_freq)
        log_stop = math.log10(stop_freq)

        try:
            step = (log_stop - log_start) / (num_points - 1)
        except KeyError:
            messagebox.showerror("Error", "Number of ponts not valid!")
            return

        self.frequencies = [
            10 ** (log_start + i * step)
            for i in range(num_points)
            ]

        # Notification on start of the measurement
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

            # Write to CSV
            self.writer.writerow([f, z, p])

            # Move to next frequency
            self.current_index += 1
            self.root.after(int(self.measurement_delay * 1000), self.run_measurement_step)

        else:
            self.meas_status.set("Measurement done ✅")
            self.csv_file.close()
            self.inst.close()

            # Creat a plot for data visualization after test
            answer2 = messagebox.askokcancel("Info", "Make a plot?")
            if answer2:
                self.plot_results()

    def plot_results(self):
        import matplotlib
        matplotlib.use("TkAgg")
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

# ---------------------------- Plot module -----------------------------
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
        self.frame.config(width=1000, height=320)

        # Add plot button
        tk.Button(self.frame, text="Add file", command=self.add_file).grid(row=2, column=6, padx=5)

        # Remove plot button
        tk.Button(self.frame, text="Remove file", command=self.remove_file).grid(row=3, column=6, padx=5)

        #Create plot button
        tk.Button(self.frame, text="Create plot", command=self.plot_files).grid(row=4, column=6)

        # Show data points button
        tk.Checkbutton(self.frame, text="Show data points", variable=self.show_markers, width=24).grid(row=5, column=6)

        # ____________ Axis settings __________________________
        tk.Label(self.frame, text="Plot settings", font=("Arial", 10, "bold")).grid(row=1, column=1, pady=2, columnspan=4)

        tk.Label(self.frame, text="X label:").grid(row=2, column=1, sticky="e", pady=10)
        self.xl = tk.StringVar(value="")
        tk.Entry(self.frame, textvariable=self.xl, width=25).grid(row=2, column=2, sticky="w")

        tk.Label(self.frame, text="Y label:").grid(row=2, column=3, sticky="e", pady=10)
        self.yl = tk.StringVar(value="")
        tk.Entry(self.frame, textvariable=self.yl, width=25).grid(row=2, column=4,sticky="w")

        tk.Label(self.frame, text="      X axis type:").grid(row=3, column=1, sticky="e", pady=10)
        self.xscale = tk.StringVar(value="log")
        ttk.Combobox(self.frame, textvariable=self.xscale, values=["linear", "log"], width=9, justify="center").grid(row=3, column=2,sticky="w")

        tk.Label(self.frame, text="      Y axis type:").grid(row=3, column=3, sticky="e", pady=10)
        self.yscale = tk.StringVar(value="linear")
        ttk.Combobox(self.frame, textvariable=self.yscale, values=["linear", "log"], width=9, justify="center").grid(row=3, column=4,sticky="w")

        tk.Label(self.frame, text="X min:").grid(row=4, column=1,sticky="e", pady=10)
        self.xmin = tk.Entry(self.frame, width=12)
        self.xmin.grid(row=4, column=2,sticky="w")

        tk.Label(self.frame, text="X max:").grid(row=4, column=3,sticky="e", pady=10)
        self.xmax = tk.Entry(self.frame, width=12)
        self.xmax.grid(row=4, column=4,sticky="w")

        tk.Label(self.frame, text="Y min:").grid(row=5, column=1,sticky="e", pady=10)
        self.ymin = tk.Entry(self.frame, width=12)
        self.ymin.grid(row=5, column=2,sticky="w")

        tk.Label(self.frame, text="Y max:").grid(row=5, column=3,sticky="e", pady=10)
        self.ymax = tk.Entry(self.frame, width=12)
        self.ymax.grid(row=5, column=4,sticky="w")

         # Format numbers
        attach_number_formatter(self.xmin)
        attach_number_formatter(self.xmax)
        attach_number_formatter(self.ymin)
        attach_number_formatter(self.ymax)

        # List of the added measurement files
        tk.Label(self.frame, text="", width=25).grid(row=1, column=5)
        tk.Label(self.frame, text="Plotted data", width=12,font=("Arial", 10, "bold")).grid(row=1, column=7)
        self.listbox = tk.Listbox(self.frame, height=10, width=30, justify="center")
        self.listbox.grid(row=2, column=7, rowspan=3,padx=10)

    def add_file(self):
        # Add a new measurement file
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
        import matplotlib
        matplotlib.use("TkAgg")
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
                    
                    with open(fpath, 'r', newline='') as csvfile:
                        x, y = [], []
                        reader = csv.reader(csvfile, delimiter=',')
                        next(reader, None)
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

            # ------- Axis limit handle --------
            def get_limit(entry):
                value = entry.get().strip()
                if value == "":
                    return None
                return entry.num_value

            xmin = get_limit(self.xmin)
            xmax = get_limit(self.xmax)
            ymin = get_limit(self.ymin)
            ymax = get_limit(self.ymax)

            # X scale
            if xmin is not None or xmax is not None:
                current_xlim = plt.xlim()
                plt.xlim(
                    xmin if xmin is not None else current_xlim[0],
                    xmax if xmax is not None else current_xlim[1]
                )

            # Y scale
            if ymin is not None or ymax is not None:
                current_ylim = plt.ylim()
                plt.ylim(
                    ymin if ymin is not None else current_ylim[0],
                    ymax if ymax is not None else current_ylim[1]
                )

        plt.xscale(self.xscale.get())
        plt.yscale(self.yscale.get())
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

