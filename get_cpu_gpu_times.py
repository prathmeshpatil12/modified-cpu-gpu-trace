import json
import re
from datetime import datetime

# 1. Get wall-clock time range from both sources
pyspy_samples = json.load(open("./Result/python3/python3_pyspy_timestamps.json"))
pyspy_times = [datetime.fromisoformat(s['timestamp'].replace('Z', '+00:00')) for s in pyspy_samples]
cpu_start = min(pyspy_times)
cpu_end = max(pyspy_times)

# Parse CUPTI for GPU start/end
gpu_events = []
for line in open("./Result/python3/python3_cupti.log"):
    if line.startswith("KERNEL") or line.startswith("MEMCPY"):
        parts = dict(re.findall(r'(\w+)=([^,]+)', line))
        gpu_events.append({
            'start': int(parts.get('start_ns', 0)),
            'end': int(parts.get('end_ns', 0))
        })

if gpu_events:
    gpu_start_ns = min(e['start'] for e in gpu_events)
    gpu_end_ns = max(e['end'] for e in gpu_events)
else:
    gpu_start_ns = gpu_end_ns = 0

# 2. Calculate total times
# CPU time = wall-clock span of py-spy (includes idle)
total_cpu_time_ms = (cpu_end - cpu_start).total_seconds() * 1000

# GPU time = sum of all kernel/memcpy durations
gpu_time_ns = sum((e['end'] - e['start']) for e in gpu_events)
total_gpu_time_ms = gpu_time_ns / 1e6

# Wall-clock = max of CPU or GPU span
wall_clock_ms = max(total_cpu_time_ms, total_gpu_time_ms)

# 3. Calculate proportions for display
# Use the larger time as 100% reference for side-by-side widths
total_time = total_cpu_time_ms + total_gpu_time_ms
cpu_width_pct = (total_cpu_time_ms / total_time) * 100
gpu_width_pct = (total_gpu_time_ms / total_time) * 100

# Calculate overlap (if they ran concurrently)
cpu_proportion = total_cpu_time_ms / wall_clock_ms
gpu_proportion = total_gpu_time_ms / wall_clock_ms
overlap_pct = max(0, (cpu_proportion + gpu_proportion - 1) * 100)

print(f"Wall-clock time: {wall_clock_ms:.0f} ms")
print(f"CPU time (py-spy span): {total_cpu_time_ms:.0f} ms ({cpu_width_pct:.1f}% relative)")
print(f"GPU time (kernel sum): {total_gpu_time_ms:.2f} ms ({gpu_width_pct:.1f}% relative)")
print(f"Overlap: {overlap_pct:.1f}%")

# For side-by-side display
total_width_px = 1600
cpu_width_px = int((cpu_width_pct / 100) * total_width_px)
gpu_width_px = int((gpu_width_pct / 100) * total_width_px)

# Save for HTML template
with open('proportions.json', 'w') as f:
    json.dump({
        'wall_clock_ms': wall_clock_ms,
        'cpu_ms': total_cpu_time_ms,
        'gpu_ms': total_gpu_time_ms,
        'cpu_pct': cpu_width_pct,
        'gpu_pct': gpu_width_pct,
        'cpu_width_px': cpu_width_px,
        'gpu_width_px': gpu_width_px,
        'overlap_pct': overlap_pct
    }, f, indent=2)