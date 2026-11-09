"""
Make test-config.json from rfn_app/oapp/mon/RfnMonViewer-config.json for the fake server.

Examples:
    python make_test_config.py                        all resonators on localhost:10000
    python make_test_config.py --port 10001           all resonators on localhost:10001
    python make_test_config.py --split 10001          resonators 1-4 on 10000, 5-8 on 10001
    python make_test_config.py --out other-config.json
"""
import argparse
import json
import os

parser = argparse.ArgumentParser(description="Тестовый конфиг для фейкового сервера")
parser.add_argument("--port", type=int, default=10000,
                    help="порт для всех резонаторов (или для 1-4 при --split)")
parser.add_argument("--split", type=int, default=None, metavar="PORT2",
                    help="порт для второй половины резонаторов (5-8)")
parser.add_argument("--out", default="test-config.json", help="имя файла результата")
args = parser.parse_args()

with open(os.path.join("rfn_app", "oapp", "mon", "RfnMonViewer-config.json"), "r") as f:
    cfg = json.load(f)

names = list(cfg["devices"].keys())
half = len(names) // 2
for k, cav in enumerate(names):
    port = args.port
    if args.split is not None and k >= half:
        port = args.split
    cfg["devices"][cav] = [f"tango://localhost:{port}/{p}#dbase=no" for p in cfg["devices"][cav]]
    print(f"{cav}: localhost:{port}")

with open(args.out, "w") as f:
    json.dump(cfg, f, indent=4)
print(f"Записан {args.out}")
