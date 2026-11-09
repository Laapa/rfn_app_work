"""
Fake Tango server for the test bench (no Tango database).

Examples:
    python fake_server.py                       all 8 resonators on port 10000
    python fake_server.py --port 10001          all 8 resonators on port 10001
    python fake_server.py --res 1-4             only resonators 1..4 (order of "devices" in json)
    python fake_server.py --res 2,5,7           only resonators 2, 5 and 7
    python fake_server.py --res 1e1,3e2         the same by short names
    python fake_server.py --res 5-8 --port 10001
"""
import argparse
import json
import os
import math
import random
import time

from tango import Attr, AttrWriteType, DevDouble, DevState
from tango.server import Device, run

CFG = os.path.join("rfn_app", "oapp", "mon", "RfnMonViewer-config.json")
PORT = 10000

with open(CFG, "r") as f:
    cfg = json.load(f)

first_cav = list(cfg["devices"].values())[0]
KINDS = {path.split("/")[-1]: attrs
         for path, attrs in zip(first_cav, cfg["tango_attr"].values())}

ALL_ATTRS = [a for attrs in cfg["tango_attr"].values() for a in attrs]
IDX = {name: i for i, name in enumerate(ALL_ATTRS)}
RES_ORDER = [paths[0].split("/")[1] for paths in cfg["devices"].values()]
RES_IDX = {name: i for i, name in enumerate(RES_ORDER)}


def fake_value(name, res):
    i = IDX[name]
    base = 5 + (i * 1.7) % 20 + res * 1.0
    amp = 2 + (i % 4)
    period = 20 + 4 * i + res * 3
    phase = res * 0.8
    return base + amp * math.sin(2 * math.pi * time.time() / period + phase) + random.gauss(0, 0.2)


class FakeRf(Device):
    def init_device(self):
        Device.init_device(self)
        self.set_state(DevState.ON)

    def initialize_dynamic_attributes(self):
        # device name looks like "rf2/1e1/mod"; the last part is the kind
        kind = self.get_name().split("/")[-1]
        for name in KINDS[kind]:
            self.add_attribute(Attr(name, DevDouble, AttrWriteType.READ), self.read_fake)

    def read_fake(self, attr):
        res = RES_IDX[self.get_name().split("/")[1]]
        attr.set_value(fake_value(attr.get_name(), res))


def parse_res(text):
    """
    Which resonators to serve: "1-4", "2,5,7", "1e1,3e2" or a mix.
    Numbers start from 1 and follow the order of "devices" in json.
    Returns a sorted list of indexes starting from 0.
    """
    result = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if part in RES_IDX:                       # short name like "1e1"
            result.add(RES_IDX[part])
        elif "-" in part:                         # range like "1-4"
            first, last = part.split("-", 1)
            for n in range(int(first), int(last) + 1):
                result.add(n - 1)
        else:                                     # single number like "5"
            result.add(int(part) - 1)

    for i in result:
        if not 0 <= i < len(RES_ORDER):
            raise SystemExit(f"Нет резонатора с номером {i + 1} (всего {len(RES_ORDER)})")
    return sorted(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Фейковый Tango-сервер для стенда")
    parser.add_argument("--port", type=int, default=PORT, help="порт (по умолчанию 10000)")
    parser.add_argument("--res", default="",
                        help='какие резонаторы поднимать: "1-4", "2,5,7", "1e1,3e2" '
                             '(по умолчанию все)')
    args = parser.parse_args()

    if args.res:
        res_list = parse_res(args.res)
    else:
        res_list = list(range(len(RES_ORDER)))

    all_paths = list(cfg["devices"].values())
    dlist = [p for i in res_list for p in all_paths[i]]
    print(f"Порт {args.port}, резонаторы: {', '.join(RES_ORDER[i] for i in res_list)}")

    # the instance name includes the port, so two servers do not clash
    run((FakeRf,), args=["fake_server", f"test{args.port}", "-nodb", "-port", str(args.port),
                         "-dlist", ",".join(dlist)])
