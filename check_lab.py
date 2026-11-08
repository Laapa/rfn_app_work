"""
Read-only check of the Tango devices from the config (nothing is written).

For every resonator and every device in "devices":
  - ping the device;
  - read its attribute list (get_attribute_list);
  - check that the attributes of the matching group in "tango_attr" are there.
Group j is read from device j (by position), so the order of groups must match
the order of devices. If attributes are missing on device j but found on another
device of the same resonator, the order is probably wrong.

Usage:
    python check_lab.py                          RfnMonViewer-config.json, TANGO_HOST from env
    python check_lab.py test-config.json         the test bench config
    python check_lab.py --host 10.18.113.66:10000
    python check_lab.py --timeout 3000
"""
import argparse
import json
import os
import sys
import time

import tango

DEFAULT_TANGO_HOST = "10.18.113.66:10000"   # same as in rfn_mon_viewer.py


def error_text(e):
    """Short text of a Tango error: the line naming the device, otherwise the first line"""
    if isinstance(e, tango.DevFailed):
        lines = [err.desc.strip() for err in e.args if err.desc.strip()]
    else:
        lines = [f"{type(e).__name__}: {e}"]
    lines = [line for text in lines for line in text.splitlines() if line.strip()]
    if not lines:
        return "нет ответа"
    reason = lines[0]
    for line in lines:
        if "device" in line.lower():
            reason = line
            break
    return reason[:100]


def check_device(path, timeout_ms):
    """
    Returns (ping text, attribute list or None, problem text).
    Never raises: any error goes into the result.
    """
    try:
        dev = tango.DeviceProxy(path)
        dev.set_timeout_millis(timeout_ms)
        t = time.time()
        dev.ping()
        ping = f"ok {(time.time() - t) * 1000:.0f} мс"
    except Exception as e:
        return "НЕТ", None, error_text(e)

    try:
        # Tango attribute names do not depend on letter case
        attrs = [a.lower() for a in dev.get_attribute_list()]
    except Exception as e:
        return ping, None, "get_attribute_list: " + error_text(e)

    return ping, attrs, ""


def print_table(header, rows):
    widths = [max(len(str(row[i])) for row in [header] + rows) for i in range(len(header))]
    line = "  ".join(str(h).ljust(w) for h, w in zip(header, widths))
    print(line.rstrip())
    print("-" * len(line))
    for row in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip())


def main():
    parser = argparse.ArgumentParser(description="Проверка Tango-девайсов из конфига (только чтение)")
    parser.add_argument("config", nargs="?", default="RfnMonViewer-config.json",
                        help="конфиг (по умолчанию RfnMonViewer-config.json)")
    parser.add_argument("--host", default=None,
                        help=f"TANGO_HOST (по умолчанию из окружения или {DEFAULT_TANGO_HOST})")
    parser.add_argument("--timeout", type=int, default=1000, help="таймаут, мс (по умолчанию 1000)")
    args = parser.parse_args()

    if args.host:
        os.environ["TANGO_HOST"] = args.host
    elif "TANGO_HOST" not in os.environ:
        os.environ["TANGO_HOST"] = DEFAULT_TANGO_HOST
    print(f"Конфиг: {args.config}")
    print(f"TANGO_HOST: {os.environ['TANGO_HOST']}  (не нужен для адресов вида tango://...#dbase=no)")
    print()

    with open(args.config, "r") as f:
        cfg = json.load(f)
    groups = list(cfg["tango_attr"].items())     # [(group name, [attrs]), ...]

    rows = []
    problems = 0
    res_ok = 0
    for res_name, paths in cfg["devices"].items():
        if len(paths) != len(groups):
            rows.append([res_name, "-", "-", "-", "-",
                         f"девайсов {len(paths)}, а групп в tango_attr {len(groups)}"])
            problems += 1

        # first pass: ping all devices of the resonator and read attribute lists
        results = []
        for j, path in enumerate(paths):
            results.append(check_device(path, args.timeout))

        this_res_ok = len(paths) == len(groups)
        for j, path in enumerate(paths):
            ping, attrs, note = results[j]
            group_name, need = groups[j] if j < len(groups) else ("?", [])
            attr_col = "-"
            if attrs is not None:
                missing = [a for a in need if a.lower() not in attrs]
                attr_col = f"{len(need) - len(missing)}/{len(need)}"
                if missing:
                    note = "нет: " + ", ".join(missing)
                    # are they on another device of the same resonator? then the order is wrong
                    for k, (_, other_attrs, _) in enumerate(results):
                        if k != j and other_attrs is not None and all(a.lower() in other_attrs for a in missing):
                            kind = paths[k].split("#")[0].split("/")[-1]
                            note += f"; найдены на девайсе {k + 1} ({kind}): порядок групп не тот?"
                            break
            if note:
                problems += 1
                this_res_ok = False
            rows.append([res_name, path, group_name, ping, attr_col, note or "OK"])
        if this_res_ok:
            res_ok += 1

    print_table(["Резонатор", "Девайс", "Группа", "Ping", "Атрибуты", "Замечание"], rows)
    print()
    print(f"Резонаторов без замечаний: {res_ok} из {len(cfg['devices'])}, замечаний: {problems}")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
