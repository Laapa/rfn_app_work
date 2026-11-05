import tango

for res in ["1e1", "2e1", "3e1", "4e1", "1e2", "2e2", "3e2", "4e2"]:
    d = tango.DeviceProxy(f"tango://localhost:10000/rf2/{res}/mod#dbase=no")
    print(res, round(d.read_attribute("Ucav").value, 2))