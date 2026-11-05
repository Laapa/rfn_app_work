import json

with open("RfnMonViewer-config.json", "r") as f:
    cfg = json.load(f)

for cav, paths in cfg["devices"].items():
    cfg["devices"][cav] = [f"tango://localhost:10000/{p}#dbase=no" for p in paths]

with open("test-config.json", "w") as f:
    json.dump(cfg, f, indent=4)