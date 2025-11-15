import json
import sys
import os
from typing import Dict

def load_proportions(filepath: str = 'proportions.json') -> Dict:
    """Load proportions from JSON file."""
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found. Run get_cpu_gpu_times.py first.")
        sys.exit(1)
    
    with open(filepath) as f:
        return json.load(f)

def build_html(cgroup_name: str, props: Dict) -> str:
    """Build simple HTML with equal width panels and percent badges."""
    cpu_pct = props.get('cpu_pct', 0.0)
    gpu_pct = props.get('gpu_pct', 0.0)

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Flamegraph: {cgroup_name}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      display: flex;
      height: 100vh;
      overflow: hidden;
      font-family: sans-serif;
      background: #fff;
    }}
    .panel {{
      position: relative;          /* allow overlay badges */
      display: flex;
      flex-direction: column;
      min-width: 0;
      height: 100vh;
      width: 50%;                  /* fixed 50/50 split */
      flex: 0 0 50%;
    }}
    .panel object {{
      border: none;
      width: 100%;
      height: 100%;
      display: block;
      object-fit: contain;         /* scale to fit without clipping */
      object-position: left top;   /* anchor top-left */
      background: #fff;
    }}
    .badge {{
      position: absolute;
      top: 8px;
      left: 8px;
      padding: 2px 8px;
      font-size: 12px;
      line-height: 18px;
      color: #222;
      background: rgba(255,255,255,0.85);
      border: 1px solid #ddd;
      border-radius: 4px;
      z-index: 10;
      pointer-events: none;        /* allow SVG interactions */
    }}
  </style>
</head>
<body>
  <div class="panel">
    <div class="badge">CPU Percentage of total time consumed: {cpu_pct:.1f}%</div>
    <object type="image/svg+xml" data="{cgroup_name}_pyspy.svg" title="CPU {cpu_pct:.1f}%"></object>
  </div>
  <div class="panel">
    <div class="badge">GPU Percentage of total time consumed: {gpu_pct:.1f}%</div>
    <object type="image/svg+xml" data="gpu.svg" title="GPU {gpu_pct:.1f}%"></object>
  </div>
</body>
</html>
"""

def main(cgroup_name: str = "python3"):
    """Generate simple proportional HTML."""
    props = load_proportions()
    html = build_html(cgroup_name, props)
    
    output_path = f'./Result/{cgroup_name}/combined_flamegraph.html'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"✅ Combined flamegraph: {output_path}")
    print(f"   CPU: {props.get('cpu_pct', 0.0):.1f}% | GPU: {props.get('gpu_pct', 0.0):.1f}%")

if __name__ == "__main__":
    cgroup_name = sys.argv[1] if len(sys.argv) > 1 else "python3"
    main(cgroup_name)