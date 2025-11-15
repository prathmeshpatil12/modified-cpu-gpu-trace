#!/usr/bin/env python3
import re
import csv
import bisect
import sys
import os
from datetime import datetime, timezone
from collections import defaultdict

# ---------- Helpers for GPU power integration ----------
def parse_csv_power(csv_path):
    """Parse Result/<cgroup>/<cgroup>.csv -> sorted (ts_ns, power_w)."""
    t_ns, p_w = [], []

    def to_ns(ts):
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone(timezone.utc)
            return int(dt.timestamp() * 1e9)
        except Exception:
            return None

    if not os.path.exists(csv_path):
        return t_ns, p_w

    with open(csv_path, newline='', encoding='utf-8', errors='replace') as f:
        rdr = csv.reader(f)
        _ = next(rdr, None)
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

# Distance between a timestamp and a [start,end] interval (ns)
def _dist_to_interval_ns(t, s, e):
    if s <= t <= e:
        return 0
    return s - t if t < s else t - e

def main():
    cgroup = sys.argv[1] if len(sys.argv) > 1 else "python3"
    base = os.path.join("Result", cgroup)
    os.makedirs(base, exist_ok=True)

    # Use DW_CUPTI_LOG if set by start_cgroup.sh, else default path in Result/<cgroup>
    cupti_log = os.environ.get("DW_CUPTI_LOG", os.path.join(base, f"{cgroup}_cupti.log"))
    csv_path  = os.path.join(base, f"{cgroup}.csv")

    if not os.path.exists(cupti_log):
        print(f"[GPU] CUPTI log not found: {cupti_log}")
        open(os.path.join(base, "gpu_time.collapsed"), 'w').close()
        open(os.path.join(base, "gpu_energy.collapsed"), 'w').close()
        return

    events = []
    cupti_min_start = None
    with open(cupti_log, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if not line.startswith(("RUNTIME", "DRIVER", "KERNEL", "MEMCPY")):
                continue
            parts = dict(re.findall(r'(\w+)=([^,]+)', line))
            try:
                start = int(parts.get('start_ns', 0))
                end   = int(parts.get('end_ns', 0))
                corr  = int(parts.get('corr', 0))
                name  = parts.get('name', '')
            except Exception:
                continue
            if start and (cupti_min_start is None or start < cupti_min_start):
                cupti_min_start = start
            events.append({
                'kind': line.split(',')[0],
                'start': start,
                'end': end,
                'name': name,
                'corr': corr
            })

    corr_map = defaultdict(list)
    for e in events:
        corr_map[e['corr']].append(e)

    time_weights_ns = defaultdict(int)
    for corr, group in corr_map.items():
        group.sort(key=lambda x: x['start'])
        runtime = next((e for e in group if e['kind'] == 'RUNTIME'), None)
        driver  = next((e for e in group if e['kind'] == 'DRIVER'), None)
        for ge in (e for e in group if e['kind'] in ('KERNEL', 'MEMCPY')):
            if ge['end'] <= ge['start']:
                continue
            frames = []
            if runtime: frames.append(runtime['name'])
            if driver:  frames.append(driver['name'])
            frames.append(f"{ge['name']} (GPU)")
            stack = "all;gpu;" + ";".join(frames)
            dur_ns = ge['end'] - ge['start']
            time_weights_ns[stack] += max(dur_ns, 0)

    gpu_time_out = os.path.join(base, "gpu_time.collapsed")
    with open(gpu_time_out, 'w') as f:
        for s in sorted(time_weights_ns):
            f.write(f"{s} {time_weights_ns[s]}\n")

    t_ns, p_w = parse_csv_power(csv_path)
    energy_weights_uJ = defaultdict(float)

    if t_ns and cupti_min_start is not None:
        csv_min_ts = t_ns[0]
        offset = csv_min_ts - cupti_min_start
 
        gpu_windows = []
        for corr, group in corr_map.items():
            group.sort(key=lambda x: x['start'])
            runtime = next((e for e in group if e['kind'] == 'RUNTIME'), None)
            driver  = next((e for e in group if e['kind'] == 'DRIVER'), None)
            for ge in (e for e in group if e['kind'] in ('KERNEL', 'MEMCPY')):
                if ge['end'] <= ge['start']:
                    continue
                frames = []
                if runtime: frames.append(runtime['name'])
                if driver:  frames.append(driver['name'])
                frames.append(f"{ge['name']} (GPU)")
                stack = "all;gpu;" + ";".join(frames)
                gpu_windows.append({
                    'start': ge['start'] + offset,
                    'end':   ge['end']   + offset,
                    'stack': stack
                })

        gpu_windows.sort(key=lambda d: d['start'])
        starts = [d['start'] for d in gpu_windows]

        for i in range(len(t_ns) - 1):
            ts = t_ns[i]
            dt_ns = t_ns[i + 1] - ts
            if dt_ns <= 0 or not starts:
                continue
            j = max(0, bisect.bisect_right(starts, ts) - 1)
            candidates = (j - 1, j, j + 1)
            best_idx, best_dist = None, None
            for k in candidates:
                if 0 <= k < len(gpu_windows):
                    w = gpu_windows[k]
                    d = _dist_to_interval_ns(ts, w['start'], w['end'])
                    if best_dist is None or d < best_dist:
                        best_dist, best_idx = d, k
            if best_idx is None:
                continue
            stack = gpu_windows[best_idx]['stack']
            e_uJ = p_w[i] * (dt_ns / 1e9) * 1e6  # W * s -> J -> µJ
            energy_weights_uJ[stack] += e_uJ

    gpu_energy_out = os.path.join(base, "gpu_energy.collapsed")
    with open(gpu_energy_out, 'w') as f:
        for s in sorted(energy_weights_uJ):
            f.write(f"{s} {int(round(energy_weights_uJ[s]))}\n")

    print(f"[GPU] Wrote {gpu_time_out} ({len(time_weights_ns)} stacks)")
    print(f"[GPU] Wrote {gpu_energy_out} ({len(energy_weights_uJ)} stacks)")

if __name__ == "__main__":
    main()