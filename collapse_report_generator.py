#!/usr/bin/python3

import json
import csv
from datetime import datetime
import bisect
import sys
import argparse
from collections import defaultdict

def parse_timestamp(ts_str):
    return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S.%fZ")

def load_json_data(json_file_path):
    with open(json_file_path) as f:
        json_data = json.load(f)
    stacks = []
    for entry in json_data:
        stacks.append({
            'stack': entry['stack'],                         # list of frames (leaf-first)
            'timestamp': parse_timestamp(entry['timestamp']) # datetime
        })
    # Ensure sorted by time
    stacks.sort(key=lambda x: x['timestamp'])
    return stacks

def load_csv_data(csv_file_path):
    """Load power samples. Be tolerant to encoding issues."""
    power_data = []
    try:
        with open(csv_file_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    timestamp = row.get('timestamp')
                    power = row.get('power') or row.get(' power')
                    if not timestamp or not power:
                        continue
                    parsed_ts = parse_timestamp(timestamp.strip())
                    power_data.append({
                        'timestamp': parsed_ts,
                        'power': float(power.strip())  # Watts
                    })
                except (ValueError, KeyError, AttributeError):
                    continue
    except Exception:
        pass
    # Sort and drop non-increasing timestamps
    power_data.sort(key=lambda x: x['timestamp'])
    dedup = []
    for p in power_data:
        if not dedup or p['timestamp'] > dedup[-1]['timestamp']:
            dedup.append(p)
    return dedup

def accumulate_energy_by_nearest_stack(stacks, power_data):
    """
    Attribute each power interval [t_i, t_{i+1}) to the nearest CPU stack timestamp.
    Returns dict: collapsed_stack -> energy_uJ (microjoules)
    """
    if not stacks or len(power_data) < 2:
        return {}

    stack_times = [s['timestamp'] for s in stacks]
    energy_uJ = defaultdict(float)

    for i in range(len(power_data) - 1):
        ts = power_data[i]['timestamp']
        dt_s = (power_data[i + 1]['timestamp'] - ts).total_seconds()
        if dt_s <= 0:
            continue

        # Find closest stack sample around ts
        j = bisect.bisect_left(stack_times, ts)
        candidates = []
        if j > 0:
            candidates.append(j - 1)
        if j < len(stacks):
            candidates.append(j)

        if not candidates:
            continue

        closest_idx = min(
            candidates,
            key=lambda idx: abs((stack_times[idx] - ts).total_seconds())
        )
        # Build stack string: root->...->leaf. Your JSON stack is leaf-first, so reverse it.
        stack_str = ';'.join(reversed(stacks[closest_idx]['stack']))

        # Energy = power (W) * dt (s) -> Joules, then to microjoules
        e_uJ = power_data[i]['power'] * dt_s * 1e6
        energy_uJ[stack_str] += e_uJ

    return energy_uJ

def write_collapsed(energy_uJ, out_path, add_root=True):
    lines = []
    for stack, uJ in energy_uJ.items():
        val = int(round(uJ))
        if val <= 0:
            continue
        s = f"cpu;{stack}" if add_root else stack
        lines.append(f"{s} {val}")
    lines.sort()
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))

def main():
    parser = argparse.ArgumentParser(description='Generate CPU energy-collapsed flamegraph data (microjoules)')
    parser.add_argument('json_file', help='Path to JSON file with py-spy stacks + timestamps (e.g., python3_pyspy_timestamps.json)')
    parser.add_argument('csv_file', help='Path to CSV with power measurements (column "power" in Watts)')
    parser.add_argument('-o', '--output', default='cpu_energy.collapsed',
                        help='Output collapsed file (default: cpu_energy.collapsed)')
    args = parser.parse_args()

    stacks = load_json_data(args.json_file)
    power_data = load_csv_data(args.csv_file)

    energy_uJ = accumulate_energy_by_nearest_stack(stacks, power_data)
    write_collapsed(energy_uJ, args.output)

    total_uJ = sum(energy_uJ.values())
    print(f"Wrote {args.output} (total {int(round(total_uJ))} µJ across {len(energy_uJ)} stacks)")

if __name__ == "__main__":
    main()