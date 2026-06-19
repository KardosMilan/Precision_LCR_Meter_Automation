import tkinter as tk
from tkinter import filedialog, messagebox
import pyvisa
import csv
import time
import numpy as np
import os
from tkinter import ttk
import matplotlib
matplotlib.use("TkAgg") 
import matplotlib.pyplot as plt
import sys

class VisaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LCR Control Tool")
        self.rm = pyvisa.ResourceManager()
        
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(__file__)
        
        self.plots_dir = os.path.join(self.base_dir, "plots")
        self.logs_dir = os.path.join(self.base_dir, "logs")
        os.makedirs(self.plots_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        

        icon_dir = os.path.join(os.path.dirname(__file__), "icons")

        self.help_icon = tk.PhotoImage(file=os.path.join(icon_dir, "help.png"))
        options = ["Ls-Rdc","Ls-Rs","Ls-Q","Ls-D","Lp-Rdc","Lp-Rp","Lp-G","Lp-Q","Lp-D","Cs-Q","Cs-Rs","Cs-D","Cp-Rp","Cp-G","Cp-Q","Cp-D", "R-X","Y-0d","Y-0r","Z-0d","Z-0r"]
        
        # Paraméterek bevitele
        # Külső konténer a top1 és top2 frame számára
        self.top12_container = tk.Frame(root)
        tk.Label(root, text="Szoftver: v3.0").pack(padx=10,anchor="ne")
        self.top12_container.pack(anchor="nw", padx=5, pady=10, fill="x")

        # Paraméterek bevitele - top1_frame
        self.top1_frame = tk.Frame(self.top12_container, bd=1, relief="solid")
        self.top1_frame.grid(row=0, column=0, padx=5, pady=5, sticky="n")

        # --- itt jön minden a korábbi top1_frame-ből ---
        self.start_freq_label = tk.Label(self.top1_frame, text="Kezdő frekvencia [Hz]:")
        self.start_freq_label.grid(row=0, column=0, padx=5, pady=10)

        self.start_freq = tk.IntVar()
        self.start_freq_entry = tk.Entry(self.top1_frame, textvariable=self.start_freq, width=30)
        self.start_freq_entry.grid(row=0, column=1, padx=40, pady=10)

        self.stop_freq_label = tk.Label(self.top1_frame, text="Végfrekvencia [Hz]:")
        self.stop_freq_label.grid(row=1, column=0, padx=5, pady=10)

        self.end_freq = tk.IntVar()
        self.stop_freq_entry = tk.Entry(self.top1_frame, textvariable=self.end_freq, width=30)
        self.stop_freq_entry.grid(row=1, column=1, padx=5, pady=10)

        self.points_label = tk.Label(self.top1_frame, text="Mérési pontok száma:")
        self.points_label.grid(row=2, column=0, padx=5, pady=10)

        self.points = tk.IntVar()
        self.points_entry = tk.Entry(self.top1_frame, textvariable=self.points, width=30)
        self.points_entry.grid(row=2, column=1, padx=5, pady=10)

        self.delay_label = tk.Label(self.top1_frame, text="Késleltetés (s):")
        self.delay_label.grid(row=3, column=0, padx=5, pady=10)
        self.delay = tk.IntVar()
        self.delay_entry = tk.Entry(self.top1_frame, textvariable=self.delay, width=30)
        self.delay_entry.grid(row=3, column=1, padx=5, pady=10)

        self.mode_label = tk.Label(self.top1_frame, text="Mérési mód:")
        self.mode_label.grid(row=4, column=0, padx=40, pady=25)
        self.mode = tk.StringVar()
        self.combo = ttk.Combobox(self.top1_frame, textvariable=self.mode, values=options, width=27)
        self.combo.grid(row=4, column=1, padx=5, pady=10)

        self.help_save_button = tk.Button(self.top1_frame, image=self.help_icon, command=self.help,relief="flat")
        self.help_save_button.grid(row=0, column=3,padx=10, pady=10, sticky='e')

        # VISA eszközök listázása
        # Mentési útvonal - top2_frame
        self.top2_frame = tk.Frame(self.top12_container, bd=1, relief="solid")
        self.top2_frame.grid(row=0, column=1, padx=5, pady=5, sticky="n")

        self.visa_frame = tk.Frame(self.top2_frame, bd=0, relief="solid")
        self.visa_frame.grid(row=0, column=0, padx=5, pady=5, sticky="wn")

        self.visa_label = tk.Label(self.visa_frame, text="Elérhető VISA eszközök:")
        self.visa_label.grid(row=0, column=0, padx=10, pady=10,sticky='w')

        self.refresh_button = tk.Button(self.visa_frame, text="Frissítés", command=self.refresh_visa_devices)
        self.refresh_button.grid(row=0, column=1, padx=10, pady=10)
        

        self.visa_listbox = tk.Listbox(self.top2_frame, height=5, width=40)
        self.visa_listbox.grid(row=1, column=0, padx=10, pady=10)
        self.refresh_visa_devices()

        

        # státusz kiírása
        self.device_status = tk.StringVar(value="Nincs kiválasztva eszköz")
        self.device_status_label = tk.Label(self.top2_frame, textvariable=self.device_status, fg="blue")
        self.device_status_label.grid(row=2, column=0, padx=10, pady=2,sticky='w')

        # esemény a listbox kiválasztásához
        self.visa_listbox.bind("<<ListboxSelect>>", self.update_device_status)


        # Mentési útvonal
        self.filepath = tk.StringVar()
        self.filepath.set(self.logs_dir)
        self.save_label = tk.Label(self.top2_frame, text="Fájlnév:")
        self.save_label.grid(row=0, column=1, padx=5, sticky='e')
        self.filename = tk.StringVar()
        self.file_label = tk.Entry(self.top2_frame, textvariable=self.filename, width=30)
        self.file_label.grid(row=0, column=2, padx=5)

        self.file_format = tk.Label(self.top2_frame, text=".csv")
        self.file_format.grid(row=0, column=3, padx=5, sticky="w")

        # Plotolás csak úgy
        self.start_button = tk.Button(self.top2_frame, text="Plot CSV-ből", command=self.plot_from_csv)
        self.start_button.grid(row=0, column=4, padx=40, pady=10)


        # Start gomb


        self.start_button = tk.Button(self.top2_frame, text="Start", command=self.start_measurement, font=("Arial", 20, "bold"),fg="white",bg="red",width=10,height=1)
        self.start_button.grid(row=1, column=2, padx=5, pady=10)

        # státusz kiírása
        self.meas_status = tk.StringVar()
        self.meas_status_label = tk.Label(self.top2_frame, textvariable=self.meas_status, anchor='w')
        self.meas_status_label.grid(row=2, column=2, padx=5, pady=10, columnspan=3, sticky="nw")



    def plot_from_csv(self):
        self.output_csv = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not self.output_csv:
            return
        base = os.path.splitext(os.path.basename(self.output_csv))[0]
        self.output_plot = os.path.join(self.plots_dir, base + ".png")

        self.plot_results()

    def help(self):
        messagebox.showinfo("Help", "Kezdő frekvencia [Hz]: min 0\n\nVégfrekvencia [Hz]: max 1000000\n\nMérési pontok száma: pl. 100\n\nKésleltetés: pl. 1")

    def refresh_visa_devices(self):
        self.visa_listbox.delete(0, tk.END)
        try:
            devices = self.rm.list_resources()
            for dev in devices:
                self.visa_listbox.insert(tk.END, dev)
            if devices:
                self.visa_listbox.select_set(0)  # első elem kijelölése
                self.update_device_status()
            else:
                self.device_status.set("Nincs elérhető eszköz")
        except:
            print()

    def update_device_status(self, event=None):
        try:
            selected_index = self.visa_listbox.curselection()[0]
            device = self.visa_listbox.get(selected_index)
            self.device_status.set(f"Kiválasztott eszköz: {device}")
        except IndexError:
            self.device_status.set("Nincs kiválasztva eszköz")
    
    def run_measurement_step(self):
        mode=self.mode.get()
        if self.current_index < len(self.frequencies):
            f = self.frequencies[self.current_index]

            # SCPI parancs küldése
            self.inst.write(f"FREQ {f}")
            

            # Lekérdezés
            response = self.inst.query("FETC?")
            parts = response.strip().split(',')
            z = float(parts[0])
            phase_rad = float(parts[1])
            if (mode=="G-B"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nG = {z:.4f}\nB = {phase_rad:.4f}")
            elif (mode=="R-X"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nR = {z:.4f}\nX = {phase_rad:.4f}")
            elif (mode=="Ls-Rdc"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nLs = {z:.4f}\nRdc = {phase_rad:.4f}")
            elif (mode=="Ls-Q"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nLs = {z:.4f}\nQ = {phase_rad:.4f}")
            elif (mode=="Ls-D"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nLs = {z:.4f}\nD = {phase_rad:.4f}")
            elif (mode=="Lp-Rp"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nLp = {z:.4f}\nRp = {phase_rad:.4f}")
            elif (mode=="Lp-G"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nLp = {z:.4f}\nG = {phase_rad:.4f}")
            elif (mode=="Lp-Q"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nLp = {z:.4f}\nQ = {phase_rad:.4f}")
            elif (mode=="Lp-D"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nLp = {z:.4f}\nD = {phase_rad:.4f}")
            elif (mode=="Cs-Q"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nCs = {z:.4f}\nQ = {phase_rad:.4f}")
            elif (mode=="Cs-Rs"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nCs = {z:.4f}\nRs = {phase_rad:.4f}")
            elif (mode=="Cs-D"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nCs = {z:.4f}\nD = {phase_rad:.4f}")
            elif (mode=="Cp-Rp"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nCp = {z:.4f}\nRp = {phase_rad:.4f}")
            elif (mode=="Cp-G"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nCp = {z:.4f}\nG = {phase_rad:.4f}")
            elif (mode=="Cp-Q"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nCp = {z:.4f}\nQ = {phase_rad:.4f}")
            elif (mode=="Cp-D"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nCp = {z:.4f}\nD = {phase_rad:.4f}")
            elif (mode=="Y-0d"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nY = {z:.4f} Ω\nθ = {phase_rad:.4f} °")
            elif (mode=="Y-0r"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nY = {z:.4f} Ω\nθ = {phase_rad:.4f} rad")
            elif (mode=="Z-0d"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nZ = {z:.4f} Ω\nθ = {phase_rad:.4f} °")
            elif (mode=="Z-0r"):
                self.meas_status.set(f"Mérés folyamatban:\n\nFrequency: {f:.2f} Hz\nZ = {z:.4f} Ω\nθ = {phase_rad:.4f} rad")
            
            self.meas_status_label.grid(row=1,column=4)
            self.root.update_idletasks()

            # Írás CSV-be
            self.writer.writerow([f, z, phase_rad])

            # Következő frekvencia előkészítése
            self.current_index += 1

            # Következő lépés időzítve (ms)
            self.root.after(int(self.measurement_delay * 1000), self.run_measurement_step)
        else:
            self.meas_status.set("Mérés kész ✅")
            self.csv_file.close()
            self.inst.close()

            answer2 = messagebox.askokcancel("Info", "Készítsek plotot?")
            if answer2:
                self.plot_results()

    def plot_results(self):
        # === PLOT RESULTS ===
                frequencies = [] # Empty list to store the frequencies
                impedances = [] # Empty list to store impedances
                phases = [] # Empty list to store phases in radian

                with open(self.output_csv , 'r') as file: # Opening the CSV file in read mode
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
                plt.savefig(self.output_plot, dpi=300)
                plt.show()

    def start_measurement(self):

        # Ha előző mérésből maradt nyitott eszköz vagy fájl, zárjuk le
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

        if not self.filepath.get():
            messagebox.showwarning("Figyelem", "Először válaszd ki a mentési helyet!")
            return
        
        if not self.filename.get():
            messagebox.showwarning("Figyelem", "Nevezd el a fájlt!")
            return

        try:
            start_freq = float(self.start_freq_entry.get())
            stop_freq = float(self.stop_freq_entry.get())
            points = int(self.points_entry.get())
            delay = float(self.delay_entry.get())
        except ValueError:
            messagebox.showerror("Hiba", "Érvénytelen bemenet!")
            return

        try:
            selected_index = self.visa_listbox.curselection()[0]
            device_address = self.visa_listbox.get(selected_index)
        except IndexError:
            messagebox.showerror("Hiba", "Válassz ki egy VISA eszközt!")
            return

        num_points = int(self.points.get())
        start_freq = max(int(self.start_freq.get()), 20)
        stop_freq = min(int(self.end_freq.get()), 1000000)

        self.output_csv = os.path.join(self.filepath.get(), self.filename.get() + ".csv")
        self.output_plot = os.path.join(self.plots_dir, self.filename.get() + ".png")
        self.measurement_delay = int(self.delay.get())

        try:
            self.inst = self.rm.open_resource(device_address)
        except Exception as e:
            messagebox.showerror("Hiba", f"Nem sikerült csatlakozni az eszközhöz: {e}")
            return

        self.inst.timeout = 5000
        self.meas_status.set(f"Instrument ID: {self.inst.query('*IDN?').strip()}")

        # === MEASUREMENT MODE ===
        mode = self.mode.get()

        if (mode=="Cp-D"):
            self.inst.write(":FUNCtion:IMPedance:TYPE CPD") 
        elif (mode=="Cp-Q"):
            self.inst.write(":FUNCtion:IMPedance:TYPE CPQ") 
        elif (mode=="Cp-G"):
            self.inst.write(":FUNCtion:IMPedance:TYPE CPG")
        elif (mode=="Cp-Rp"):
            self.inst.write(":FUNCtion:IMPedance:TYPE CPRP") 
        elif (mode=="Cs-D"):
            self.inst.write(":FUNCtion:IMPedance:TYPE CSD")
        elif (mode=="Cs-Rs"):
            self.inst.write(":FUNCtion:IMPedance:TYPE CSRS")
        elif (mode=="Cs-Q"):
            self.inst.write(":FUNCtion:IMPedance:TYPE CSQ")
        elif (mode=="Lp-D"):
            self.inst.write(":FUNCtion:IMPedance:TYPE LPD")
        elif (mode=="Lp-Q"):
            self.inst.write(":FUNCtion:IMPedance:TYPE LPQ")
        elif (mode=="Lp-G"):
            self.inst.write(":FUNCtion:IMPedance:TYPE LPG")
        elif (mode=="Lp-Rp"):
            self.inst.write(":FUNCtion:IMPedance:TYPE LPRP")
        elif (mode=="Lp-Rdc"):
            self.inst.write(":FUNCtion:IMPedance:TYPE LPRD")
        elif (mode=="Ls-D"):
            self.inst.write(":FUNCtion:IMPedance:TYPE LSD")
        elif (mode=="Ls-Q"):
            self.inst.write(":FUNCtion:IMPedance:TYPE LSQ")
        elif (mode=="Ls-Rs"):
            self.inst.write(":FUNCtion:IMPedance:TYPE LSRS")
        elif (mode=="Ls-Rdc"):
            self.inst.write(":FUNCtion:IMPedance:TYPE LSRD")
        elif (mode=="R-X"):
            self.inst.write(":FUNCtion:IMPedance:TYPE RX")
        elif (mode=="Y-0d"):
            self.inst.write(":FUNCtion:IMPedance:TYPE YTD") 
        elif (mode=="Y-0r"):
            self.inst.write(":FUNCtion:IMPedance:TYPE YTR") 
        elif (mode=="Z-0d"):
            self.inst.write(":FUNCtion:IMPedance:TYPE ZTD") 
        elif (mode=="Z-0r"):
            self.inst.write(":FUNCtion:IMPedance:TYPE ZTR") 
        else:
            messagebox.showerror("Hiba", "Nincs kiválasztott mérési mód!")
            return

        self.inst.write(":APER LONG, 1")

        self.frequencies = np.logspace(np.log10(start_freq),
                                        np.log10(stop_freq),
                                        num=num_points)

        answer = messagebox.askokcancel("Info", "A mérés elkezdődik!")
        if not answer:
            return

        # === CSV megnyitása HELYESEN ===
        self.csv_file = open(self.output_csv, mode='w', newline='')
        self.writer = csv.writer(self.csv_file)
        self.writer.writerow(["Frequency (Hz)", "Impedance (Ohm)", "Phase (rad)"])

        # === Állapot reset ===
        self.current_index = 0
        self.meas_status_label.grid(row=1,column=4)
        self.meas_status.set("Mérés elindult...")
        self.root.update_idletasks()

        self.run_measurement_step()



import skrf as rf

import csv

class SKRFCSVPlotModule:
    def __init__(self, root):
        self.root = root
        self.files = []  # Lista a fájlokhoz (S-param vagy CSV)
        self.file_types = {}  # Dict: file -> type ('S' vagy 'CSV')
        self.show_markers = tk.BooleanVar(value=False)  # Új: adatpontok megjelenítésének kapcsolója

        # Frame az új modul gombjaihoz
        self.frame = tk.Frame(root, bd=1, relief="solid")
        self.frame.pack(anchor="nw", padx=5, pady=5, fill="x")

        tk.Label(self.frame, text="SKRF Plot modul").grid(row=0, column=0, columnspan=6)

        # Hozzáadás gomb
        tk.Button(self.frame, text="Fájl hozzáadása", command=self.add_file).grid(row=1, column=0, padx=5, pady=5)

        # Eltávolítás gomb
        tk.Button(self.frame, text="Fájl eltávolítása", command=self.remove_file).grid(row=2, column=0, padx=5, pady=5)

        # Adatpontok megjelenítése kapcsoló
        tk.Checkbutton(self.frame, text="Mutassa az adatpontokat", variable=self.show_markers).grid(row=4, column=0,  pady=5)

        # Tengely beállítások
        tk.Label(self.frame, text="X tengely felirat").grid(row=1, column=1)
        self.xl = tk.StringVar(value="X label")
        tk.Entry(self.frame, textvariable=self.xl, width=12).grid(row=1, column=2)

        tk.Label(self.frame, text="Y tengely felirat").grid(row=1, column=3)
        self.yl = tk.StringVar(value="Y label")
        tk.Entry(self.frame, textvariable=self.yl, width=12).grid(row=1, column=4)

        tk.Label(self.frame, text="X tengely típus").grid(row=2, column=1, padx=50, sticky="e")
        self.xscale = tk.StringVar(value="log")
        ttk.Combobox(self.frame, textvariable=self.xscale, values=["linear", "log"], width=10).grid(row=2, column=2)

        tk.Label(self.frame, text="Y tengely típus").grid(row=2, column=3, padx=50, sticky="e")
        self.yscale = tk.StringVar(value="linear")
        ttk.Combobox(self.frame, textvariable=self.yscale, values=["linear", "log"], width=10).grid(row=2, column=4)

        tk.Label(self.frame, text="X min").grid(row=3, column=1)
        self.xmin = tk.DoubleVar(value=1e4)
        tk.Entry(self.frame, textvariable=self.xmin, width=12).grid(row=3, column=2)

        tk.Label(self.frame, text="X max").grid(row=3, column=3)
        self.xmax = tk.DoubleVar(value=1e8)
        tk.Entry(self.frame, textvariable=self.xmax, width=12).grid(row=3, column=4)

        tk.Label(self.frame, text="Y min").grid(row=4, column=1)
        self.ymin = tk.DoubleVar(value=1)
        tk.Entry(self.frame, textvariable=self.ymin, width=12).grid(row=4, column=2)

        tk.Label(self.frame, text="Y max").grid(row=4, column=3)
        self.ymax = tk.DoubleVar(value=60000)
        tk.Entry(self.frame, textvariable=self.ymax, width=12).grid(row=4, column=4)

        # Plot gomb
        tk.Label(self.frame, text="Plotolt adatok").grid(row=1, column=5)
        tk.Button(self.frame, text="Plot készítése", command=self.plot_files).grid(row=3, column=0, pady=5)

        # Lista a hozzáadott fájlokhoz
        self.listbox = tk.Listbox(self.frame, height=5)
        self.listbox.grid(row=2, column=5, rowspan=3,padx=100, pady=10, sticky="we")

        

    # -----------------------------
    # Fájl hozzáadás
    # -----------------------------
    def add_file(self):
        file = filedialog.askopenfilename(filetypes=[("S-parameter or CSV files", "*.s1p *.s2p *.s4p *.csv")])
        if file and file not in self.files:
            self.files.append(file)
            ext = os.path.splitext(file)[1].lower()
            if ext == ".csv":
                self.file_types[file] = "CSV"
            else:
                self.file_types[file] = "S"
            self.listbox.insert(tk.END, os.path.basename(file))

    # -----------------------------
    # Fájl eltávolítás
    # -----------------------------
    def remove_file(self):
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            fpath = self.files.pop(index)
            self.file_types.pop(fpath, None)
            self.listbox.delete(index)

    # -----------------------------
    # Plot elkészítése
    # -----------------------------
    def plot_files(self):
        if not self.files:
            messagebox.showwarning("Figyelem", "Nincs fájl hozzáadva!")
            return

        plt.figure(dpi=140, figsize=(6,4))
        markers = ['o', 'x', '*', '+', 's', 'd', '^']  # Marker lista több fájlhoz

        for i, fpath in enumerate(self.files):
            marker = markers[i % len(markers)] if self.show_markers.get() else ''  # Ha be van kapcsolva, használ markert
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
                messagebox.showerror("Hiba", f"Hiba a fájl olvasásakor: {fpath}\n{e}")

        plt.xscale(self.xscale.get())
        plt.yscale(self.yscale.get())
        plt.xlim(self.xmin.get(), self.xmax.get())
        plt.ylim(self.ymin.get(), self.ymax.get())
        plt.xlabel(self.xl.get())
        plt.ylabel(self.yl.get())
        plt.grid(which="both")
        plt.legend(fontsize="x-small")
        #plt.tight_layout()
        plt.title("SKRF Plot")
        plt.show()



if __name__ == "__main__":
    root = tk.Tk()
    app = VisaApp(root)
    skrf_module = SKRFCSVPlotModule(root)
    root.mainloop()
