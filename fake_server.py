import json
import math
import random
import time

from tango import Attr, AttrWriteType, DevDouble, DevState
from tango.server import Device, run

CFG = "RfnMonViewer-config.json"
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


if __name__ == "__main__":
    dlist = [p for paths in cfg["devices"].values() for p in paths]
    run((FakeRf,), args=["fake_server", "test", "-nodb", "-port", str(PORT),
                         "-dlist", ",".join(dlist)])