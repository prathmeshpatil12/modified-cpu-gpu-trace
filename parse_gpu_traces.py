import re
import csv
import bisect
from datetime import datetime, timezone
from collections import defaultdict

# ---------- Helpers for GPU power integration ----------

def parse_csv_power(csv_path):
    """Parse Result/<cgroup>/<cgroup>.csv -> sorted (ts_ns, power_w)."""
    t_ns, p_w = [], []

    def to_ns(ts):
        # Expect ISO 8601 with Z (e.g., 2025-11-03T00:33:57.626206Z)
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone(timezone.utc)
            return int(dt.timestamp() * 1e9)
        except Exception:
            return None

    # Open with tolerant decoding to avoid UnicodeDecodeError on rogue bytes
    with open(csv_path, newline='', encoding='utf-8', errors='replace') as f:
        rdr = csv.reader(f)
        header = next(rdr, None)
        for row in rdr:
            if not row or not row[0]:
                continue
            ts = to_ns(row[0])
            if ts is None:
                continue
            try:
                pw = float(row[-1])  # gpu_power in Watts
            except Exception:
                continue
            if not t_ns or ts > t_ns[-1]:  # enforce strictly increasing
                t_ns.append(ts)
                p_w.append(pw)
    return t_ns, p_w

def integrate_power_overlap(t_ns, p_w, t0_ns, t1_ns):
    """Piecewise-constant power integration over [t0, t1) -> energy Joules."""
    if not t_ns or t1_ns <= t0_ns:
        return 0.0
    i = max(0, bisect.bisect_right(t_ns, t0_ns) - 1)
    e_j = 0.0
    while i < len(t_ns) - 1:
        seg_s, seg_e = t_ns[i], t_ns[i + 1]
        if seg_s >= t1_ns:
            break
        lo = max(seg_s, t0_ns)
        hi = min(seg_e, t1_ns)
        if hi > lo:
            e_j += p_w[i] * ((hi - lo) / 1e9)
        i += 1
    return e_j

# Helper: distance between a timestamp and a [start,end] interval
def _dist_to_interval_ns(t, s, e):
    if s <= t <= e:
        return 0
    return s - t if t < s else t - e

# ---------- Parse CUPTI log (unchanged time-collapsed behavior) ----------

events = []
cupti_min_start = None
for line in open("./Result/python3/python3_cupti.log"):
    if line.startswith(("RUNTIME", "DRIVER", "KERNEL", "MEMCPY")):
        parts = dict(re.findall(r'(\w+)=([^,]+)', line))
        start = int(parts.get('start_ns', 0))
        end = int(parts.get('end_ns', 0))
        if start and (cupti_min_start is None or start < cupti_min_start):
            cupti_min_start = start
        events.append({
            'kind': line.split(',')[0],
            'start': start,
            'end': end,
            'name': parts.get('name', ''),
            'corr': int(parts.get('corr', 0))
        })

# Group by correlation ID
corr_map = defaultdict(list)
for e in events:
    corr_map[e['corr']].append(e)

# Build folded stacks (time) - keep original behavior
stacks = []
for corr, group in corr_map.items():
    group.sort(key=lambda x: x['start'])
    runtime = next((e for e in group if e['kind'] == 'RUNTIME'), None)
    driver = next((e for e in group if e['kind'] == 'DRIVER'), None)
    gpu = next((e for e in group if e['kind'] in ('KERNEL', 'MEMCPY')), None)

    stack_frames = []
    duration = 0
    if runtime:
        stack_frames.append(runtime['name'])
        duration += runtime['end'] - runtime['start']
    if driver:
        stack_frames.append(driver['name'])
        duration += driver['end'] - driver['start']
    if gpu:
        stack_frames.append(f"{gpu['name']} (GPU)")
        duration += gpu['end'] - gpu['start']

    if stack_frames:
        stacks.append(f"{';'.join(stack_frames)} {duration}")

# Write time-collapsed file (ns weights)
with open('gpu_folded.txt', 'w') as f:
    f.write('\n'.join(stacks))

# ---------- Build energy-collapsed stacks (microjoules) ----------
# 1) Load GPU power samples
t_ns, p_w = parse_csv_power("./Result/python3/python3.csv")
csv_min_ts = t_ns[0] if t_ns else None

energy_weights_uJ = defaultdict(float)

if t_ns and cupti_min_start is not None:
    # Align CUPTI and CSV epochs
    cupti_to_csv_offset = csv_min_ts - cupti_min_start

    # Build per-GPU-event stacks with times mapped to CSV time domain
    gpu_events_for_search = []  # list of dicts: {start,end,stack}
    for corr, group in corr_map.items():
        group.sort(key=lambda x: x['start'])
        runtime = next((e for e in group if e['kind'] == 'RUNTIME'), None)
        driver = next((e for e in group if e['kind'] == 'DRIVER'), None)

        for ge in (e for e in group if e['kind'] in ('KERNEL', 'MEMCPY')):
            if ge['end'] <= ge['start']:
                continue
            frames = []
            if runtime:
                frames.append(runtime['name'])
            if driver:
                frames.append(driver['name'])
            frames.append(f"{ge['name']} (GPU)")
            stack = 'gpu;' + ';'.join(frames)

            gpu_events_for_search.append({
                'start': ge['start'] + cupti_to_csv_offset,
                'end': ge['end'] + cupti_to_csv_offset,
                'stack': stack,
            })

    # Sort by start for binary search
    gpu_events_for_search.sort(key=lambda d: d['start'])
    starts = [d['start'] for d in gpu_events_for_search]

    # Attribute each power sample’s energy to the nearest GPU event stack
    # Note: drop the last CSV sample (no next timestamp -> dt)
    for i in range(len(t_ns) - 1):
        ts = t_ns[i]
        dt_ns = t_ns[i + 1] - ts
        if dt_ns <= 0 or not starts:
            continue

        # Find nearest by comparing neighbors around insertion point
        j = max(0, bisect.bisect_right(starts, ts) - 1)
        candidates = (j - 1, j, j + 1)
        best_idx, best_dist = None, None
        for k in candidates:
            if 0 <= k < len(gpu_events_for_search):
                ev = gpu_events_for_search[k]
                d = _dist_to_interval_ns(ts, ev['start'], ev['end'])
                if best_dist is None or d < best_dist:
                    best_dist, best_idx = d, k

        if best_idx is None:
            continue

        stack = gpu_events_for_search[best_idx]['stack']
        # Energy = power (W) * time (s) -> Joules -> microjoules
        e_uJ = p_w[i] * (dt_ns / 1e9) * 1e6
        energy_weights_uJ[stack] += e_uJ

# 2) Emit energy-collapsed file
energy_lines = [f"{k} {int(round(v))}" for k, v in energy_weights_uJ.items()]
energy_lines.sort()
with open('gpu_energy_folded.txt', 'w') as f:
    f.write('\n'.join(energy_lines))