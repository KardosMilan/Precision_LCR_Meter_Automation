import pyvisa

rm = pyvisa.ResourceManager()
inst = rm.open_resource("GPIB0::17::INSTR")

print("IDN:", inst.query("*IDN?"))

try:
    print("OPT:", inst.query("*OPT?"))
except Exception as e:
    print("*OPT? nem működik:", e)

try:
    print("SYST:OPT:", inst.query(":SYST:OPT?"))
except Exception as e:
    print(":SYST:OPT? nem működik:", e)

inst.close()