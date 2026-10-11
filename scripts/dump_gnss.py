"""Print vehicle_gnss receiver fields around a time window: python scripts/dump_gnss.py sitl1.ulg 76 90"""
import sys
import numpy as np
from pyulog import ULog

u = ULog(sys.argv[1])
lo, hi = float(sys.argv[2]), float(sys.argv[3])
d = next(x for x in u.data_list if x.name == "vehicle_gnss").data
t = d["timestamp"] / 1e6
cols = [c for c in ("receiver.fix_type", "receiver.satellites_used", "receiver.eph", "receiver.hdop",
                    "receiver.noise", "receiver.jamming_state", "receiver.jamming_indicator",
                    "receiver.spoofing_state", "receiver.vel_north", "receiver.vel_east",
                    "receiver.latitude", "receiver.longitude", "usable", "failed_checks") if c in d]
print("t".rjust(7), *[c.replace("receiver.", "")[:12].rjust(12) for c in cols])
last = None
for i in np.where((t >= lo) & (t <= hi))[0]:
    if last is not None and t[i] - last < 0.9:
        continue
    last = t[i]
    print(f"{t[i]:7.1f}", *[f"{float(d[c][i]):12.6g}" for c in cols])
