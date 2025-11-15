#!/usr/bin/env python3
import sys, os

def read_lines(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, 'r') as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                s, w = ln.rsplit(' ', 1)
                w = str(int(round(float(w))))
                out.append(f"{s} {w}")
            except Exception:
                continue
    return out

def main(cgroup='python3'):
    base = os.path.join('Result', cgroup)
    cpu_candidates = [
        os.path.join(base, 'cpu_energy.collapsed'),
        os.path.join(base, f'{cgroup}_energy.collapsed')
    ]
    gpu_candidates = [
        os.path.join(base, 'gpu_energy.collapsed'),
        os.path.join(base, 'gpu_energy_folded.txt')
    ]

    cpu_lines = []
    for p in cpu_candidates:
        if os.path.exists(p):
            cpu_lines = read_lines(p)
            if cpu_lines:
                break

    gpu_lines = []
    for p in gpu_candidates:
        if os.path.exists(p):
            gpu_lines = read_lines(p)
            if gpu_lines:
                break

    if not cpu_lines and not gpu_lines:
        print("No CPU/GPU energy collapsed files found.")
        sys.exit(1)

    combined = cpu_lines + gpu_lines
    combined_path = os.path.join(base, 'combined_energy.collapsed')
    os.makedirs(base, exist_ok=True)
    with open(combined_path, 'w') as f:
        f.write('\n'.join(combined) + '\n')
    print(f"Wrote {combined_path} with {len(combined)} entries")

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'python3')