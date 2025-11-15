#!/usr/bin/env python3
import os
import sys
import json
import re
from datetime import datetime

def parse_iso_z(ts):
    return datetime.fromisoformat(ts.replace('Z', '+00:00'))

def load_pyspy_span(pyspy_path):
    try:
        with open(pyspy_path, 'r', encoding='utf-8', errors='replace') as f:
            samples = json.load(f)
        times = [parse_iso_z(s['timestamp']) for s in samples if 'timestamp' in s]
        if not times:
            return None, None
        return min(times), max(times)
    except Exception:
        return None, None

def load_gpu_events(cupti_log_path):
    events = []
    if not os.path.exists(cupti_log_path):
        return events
    try:
        with open(cupti_log_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                if line.startswith("KERNEL") or line.startswith("MEMCPY"):
                    parts = dict(re.findall(r'(\w+)=([^,]+)', line))
                    try:
                        s = int(parts.get('start_ns', 0))
                        e = int(parts.get('end_ns', 0))
                    except Exception:
                        continue
                    if e > s > 0:
                        events.append({'start': s, 'end': e})
    except Exception:
        pass
    return events

def main():
    cgroup = sys.argv[1] if len(sys.argv) > 1 else "python3"
    base = os.path.join("Result", cgroup)
    os.makedirs(base, exist_ok=True)

    pyspy_path = os.path.join(base, f"{cgroup}_pyspy_timestamps.json")
    cupti_log_path = os.environ.get("DW_CUPTI_LOG", os.path.join(base, f"{cgroup}_cupti.log"))
    cpu_start, cpu_end = load_pyspy_span(pyspy_path)
    gpu_events = load_gpu_events(cupti_log_path)
    if cpu_start and cpu_end and cpu_end > cpu_start:
        total_cpu_time_ms = (cpu_end - cpu_start).total_seconds() * 1000.0
    else:
        total_cpu_time_ms = 0.0

    gpu_time_ns = sum((e['end'] - e['start']) for e in gpu_events)
    total_gpu_time_ms = gpu_time_ns / 1e6
    
    wall_clock_ms = max(total_cpu_time_ms, total_gpu_time_ms)
    total_time_ms = total_cpu_time_ms + total_gpu_time_ms
    if total_time_ms > 0:
        cpu_width_pct = (total_cpu_time_ms / total_time_ms) * 100.0
        gpu_width_pct = (total_gpu_time_ms / total_time_ms) * 100.0
    else:
        cpu_width_pct = gpu_width_pct = 0.0

    print(f"[{cgroup}] Wall-clock time: {wall_clock_ms:.0f} ms")
    print(f"[{cgroup}] CPU time (py-spy span): {total_cpu_time_ms:.0f} ms ({cpu_width_pct:.1f}%)")
    print(f"[{cgroup}] GPU time (kernel sum): {total_gpu_time_ms:.2f} ms ({gpu_width_pct:.1f}%)")

    out_path = os.path.join(base, "proportions.json")
    with open(out_path, 'w') as f:
        json.dump({
            'cgroup': cgroup,
            'wall_clock_ms': wall_clock_ms,
            'cpu_ms': total_cpu_time_ms,
            'gpu_ms': total_gpu_time_ms,
            'cpu_pct': cpu_width_pct,
            'gpu_pct': gpu_width_pct
        }, f, indent=2)
    print(f"[{cgroup}] Wrote {out_path}")

if __name__ == "__main__":
    main()