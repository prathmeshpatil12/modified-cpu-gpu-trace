import json
import csv
from datetime import datetime
import bisect
import sys
import argparse

def parse_timestamp(ts_str):
    return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S.%fZ")

def load_json_data(json_file_path):
    with open(json_file_path) as f:
        json_data = json.load(f)
    
    stacks = []
    for entry in json_data:
        stacks.append({
            'stack': entry['stack'],
            'timestamp': parse_timestamp(entry['timestamp'])
        })
    return stacks

def load_csv_data(csv_file_path):
    power_data = []
    
    try:
        with open(csv_file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    timestamp = row.get('timestamp')
                    power = row.get('power') or row.get(' power')
                    
                    if not timestamp or not power:
                        continue
                        
                    parsed_ts = parse_timestamp(timestamp.strip())
                    if parsed_ts is None:
                        continue
                        
                    power_data.append({
                        'timestamp': parsed_ts,
                        'power': float(power.strip())
                    })
                except (ValueError, KeyError, AttributeError):
                    continue
    except Exception as e:
        pass
    
    return power_data

def match_stacks_with_power(stacks, power_data):
    power_timestamps = [entry['timestamp'] for entry in power_data]
    
    matched_data = []
    for stack in stacks:
        idx = bisect.bisect_left(power_timestamps, stack['timestamp'])
        candidates = []
        if idx > 0:
            candidates.append(power_data[idx-1])
        if idx < len(power_data):
            candidates.append(power_data[idx])
        
        if candidates:
            closest = min(candidates, 
                         key=lambda x: abs((x['timestamp'] - stack['timestamp']).total_seconds()))
            
            matched_data.append({
                'stack': stack['stack'],
                'power': closest['power']
            })
    
    return matched_data

def generate_flamegraph_data(matched_data):
    flamegraph_lines = []
    
    for entry in matched_data:
        stack_str = ';'.join(reversed(entry['stack']))
        flamegraph_lines.append(f"{stack_str} {entry['power']}")
    
    return flamegraph_lines

def main():
    parser = argparse.ArgumentParser(description='Generate flamegraph with power data')
    parser.add_argument('json_file', help='Path to JSON file with call stacks')
    parser.add_argument('csv_file', help='Path to CSV file with power measurements')
    parser.add_argument('-o', '--output', default='flamegraph_data.txt',
                       help='Output file path (default: flamegraph_data.txt)')
    
    args = parser.parse_args()
    
    stacks = load_json_data(args.json_file)
    power_data = load_csv_data(args.csv_file)
    
    matched_data = match_stacks_with_power(stacks, power_data)
    
    flamegraph_data = generate_flamegraph_data(matched_data)
    
    with open(args.output, 'w') as f:
        f.write('\n'.join(flamegraph_data))
    
    print(f"Flamegraph data written to {args.output}")
    print("You can visualize it using flamegraph.pl like this:")
    print(f"flamegraph.pl {args.output} > flamegraph.svg")

if __name__ == "__main__":
    main()