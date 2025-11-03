import re
from collections import defaultdict

# Parse CUPTI log
events = []
for line in open("./Result/python3/python3_cupti.log"):
    if line.startswith("RUNTIME") or line.startswith("DRIVER") or line.startswith("KERNEL") or line.startswith("MEMCPY"):
        parts = dict(re.findall(r'(\w+)=([^,]+)', line))
        events.append({
            'kind': line.split(',')[0],
            'start': int(parts.get('start_ns', 0)),
            'end': int(parts.get('end_ns', 0)),
            'name': parts.get('name', ''),
            'corr': int(parts.get('corr', 0))
        })

# Group by correlation ID
corr_map = defaultdict(list)
for e in events:
    corr_map[e['corr']].append(e)

# Build folded stacks
stacks = []
for corr, group in corr_map.items():
    # Sort by start time
    group.sort(key=lambda x: x['start'])
    # Build stack from RUNTIME → DRIVER → KERNEL/MEMCPY
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

# Write to file for flamegraph.pl
with open('gpu_folded.txt', 'w') as f:
    f.write('\n'.join(stacks))