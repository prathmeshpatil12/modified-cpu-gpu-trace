#!/usr/bin/python3

import os
import argparse
import configparser
import csv
from collections import defaultdict
import matplotlib.pyplot as plt
from datetime import datetime

def arg_file(arg):
    """Validate that the argument is a valid file."""
    if os.path.isfile(arg):
        return arg
    raise argparse.ArgumentTypeError(f"Not a valid file: '{arg}'.")

def parse_args():
    """Parse command-line arguments.
    
    Now the input CSV file should contain:
      Column1: elapsed timestamp (seconds)
      Column2: callchain records
      Column3: total power consumption (CPU)
      Column4: percentage resource utilization
      Column5: gpu_power consumption
    """
    parser = argparse.ArgumentParser(
        description='Collapse CSV power consumption data into a performance collapse report.'
    )
    parser.add_argument('input_csv', type=arg_file,
                        help='Path to input CSV file with raw data.')
    parser.add_argument('-e', '--scinot', type=int, default=0,
                        help='Multiply power by 10^scinot for scientific notation.')
    return parser.parse_args()

def read_csv_records(csv_path):
    """
    Read CSV file and transform rows into a list of records.
    Each record is a dictionary with keys:
      'timestamp'      -> elapsed time in seconds (string)
      'metadata'       -> dict containing 'callchain'
      'total_power'    -> CPU power consumption (string)
      'resource_util'  -> percentage resource utilization (string)
      'gpu_power'      -> GPU power consumption (string)
    Assumes the CSV file has a header row.
    """
    records = []
    with open(csv_path, newline='', encoding='utf-8', errors='ignore') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # Skip header row
        for row in reader:
            if len(row) < 5:
                continue  # skip malformed rows
            r = {
                'timestamp': row[0],
                'metadata': {'callchain': row[1]},
                'total_power': row[2],
                'resource_util': row[3],
                'gpu_power': row[4]
            }
            records.append(r)
    return records

def process_records(records, scinot):
    """
    Process CSV records to extract timestamps, CPU power consumption,
    effective (actual) power consumption (CPU plus GPU), effective CPU power and aggregate callchain data.
    
    For each record:
      - Total power is from column3.
      - Effective CPU power = (resource_util / 100) * total_power.
      - Overall effective power = effective CPU power + gpu_power.
    """
    if not records:
        raise ValueError("No records found in CSV file.")


    first_timestamp = datetime.fromisoformat(records[0]['timestamp'].rstrip('Z')).timestamp()
    timestamps = []
    total_power_series = []
    effective_power_series = []
    gpu_power_series = []
    effective_cpu_series = []
    callchain_power = defaultdict(float)
    callchain_num = defaultdict(int)

    for record in records:
        current_time = datetime.fromisoformat(record['timestamp'].rstrip('Z')).timestamp()
        timestamps.append(current_time - first_timestamp)
        
        total_power = float(record['total_power'])
        total_power_series.append(total_power)
        
        resource_util = float(record['resource_util'])
        effective_cpu = (resource_util / 100.0) * total_power
        effective_cpu_series.append(effective_cpu)
        
        gpu_power = float(record['gpu_power'])
        gpu_power_series.append(gpu_power)
        
        overall_effective = effective_cpu + gpu_power
        effective_power_series.append(overall_effective)
        
        # Process callchains: split and ignore the last empty element
        callchain_str = record['metadata']['callchain']
        callchains = callchain_str.split('|')[0:-1]
        if len(callchains) == 0:
            continue
        # Distribute overall effective power equally among callchains
        ppc = overall_effective / len(callchains)
        for callchain in callchains:
            processed_chain = ';'.join(callchain.split(';')[:-1][::-1])
            callchain_power[processed_chain] += ppc
            callchain_num[processed_chain] += 1

    # Apply scientific notation multiplier to callchain power values
    for key in callchain_power:
        callchain_power[key] *= (10 ** scinot)
        
    return timestamps, total_power_series, effective_power_series, gpu_power_series, effective_cpu_series, callchain_power, callchain_num

def write_collapsed_files(target, directory, callchain_power, callchain_num):
    """
    Write collapsed energy and CPU data to files.
    Format for each file:
      target;callchain value
    """
    # Write energy data (includes both CPU and GPU power)
    #filename_energy = f'{target}_energy.collapsed'
    #file_path_energy = os.path.join(directory, filename_energy)
    #with open(file_path_energy, 'w') as file:
    #    for callchain, power in callchain_power.items():
    #        file.write(f'{target};{callchain} {power}\n')

    # Write CPU (number of calls) data
    filename_cpu = f'{target}_cpu.collapsed'
    file_path_cpu = os.path.join(directory, filename_cpu)
    with open(file_path_cpu, 'w') as file:
        for callchain, num in callchain_num.items():
            file.write(f'{target};{callchain} {num}\n')

def plot_power_consumption(timestamps, total_power_series, directory, target):
    """Plot total CPU power consumption over time and save to an SVG file."""
    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, total_power_series)
    plt.xlabel('Timestamp (seconds)')
    plt.ylabel('Total CPU Power Consumption (watts)')
    plt.title('Total CPU Power Consumption over Time')
    filename = f'{target}_power_consumption.svg'
    filepath = os.path.join(directory, filename)
    plt.savefig(filepath)
    plt.close()

def plot_effective_power(timestamps, effective_power_series, directory, target):
    """
    Plot effective power consumption (CPU+GPU) over time and save to an SVG file.
    """
    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, effective_power_series, label='Effective (CPU+GPU) Power', color='orange')
    plt.xlabel('Timestamp (seconds)')
    plt.ylabel('Effective Power Consumption (watts)')
    plt.title('Effective (CPU+GPU) Power Consumption over Time')
    plt.legend()
    filename = f'{target}_effective.svg'
    filepath = os.path.join(directory, filename)
    plt.savefig(filepath)
    plt.close()

def plot_effective_cpu_power(timestamps, effective_cpu_series, directory, target):
    """
    Plot effective CPU power consumption over time and save to an SVG file.
    """
    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, effective_cpu_series, label='Effective CPU Power', color='red')
    plt.xlabel('Timestamp (seconds)')
    plt.ylabel('Effective CPU Power (watts)')
    plt.title('Effective CPU Power Consumption over Time')
    plt.legend()
    filename = f'{target}_rapl.svg'
    filepath = os.path.join(directory, filename)
    plt.savefig(filepath)
    plt.close()

def plot_gpu_power(timestamps, gpu_power_series, directory, target):
    """Plot GPU power consumption over time and save to an SVG file."""
    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, gpu_power_series, label='GPU Power', color='green')
    plt.xlabel('Timestamp (seconds)')
    plt.ylabel('GPU Power Consumption (watts)')
    plt.title('GPU Power Consumption over Time')
    plt.legend()
    filename = f'{target}_gpu_power.svg'
    filepath = os.path.join(directory, filename)
    plt.savefig(filepath)
    plt.close()

def ensure_directory(target):
    """Create directory for saving results if it does not exist."""
    target_clean = target[1:] if target.startswith('/') else target
    directory = os.path.join('./Result', target_clean)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    return target_clean, directory

def main():
    # Parse command-line arguments
    args = parse_args()

    # Read CSV records from the input file
    records = read_csv_records(args.input_csv)
    
    # Process records to extract data and aggregate callchain data
    (timestamps, total_power_series, effective_power_series, gpu_power_series,
     effective_cpu_series, callchain_power, callchain_num) = process_records(records, args.scinot)

    # Determine target name from the CSV file name (without extension)
    target = os.path.splitext(os.path.basename(args.input_csv))[0]
    
    # Ensure output directory exists
    target_clean, directory = ensure_directory(target)

    # Write collapsed data files
    write_collapsed_files(target_clean, directory, callchain_power, callchain_num)

    # Plot total CPU power consumption over time
    plot_power_consumption(timestamps, total_power_series, directory, target_clean)

    # Plot effective CPU power consumption over time
    plot_effective_cpu_power(timestamps, effective_cpu_series, directory, target_clean)

    # Plot effective (CPU+GPU) power consumption over time
    plot_effective_power(timestamps, effective_power_series, directory, target_clean)
    
    # Plot GPU power consumption over time
    plot_gpu_power(timestamps, gpu_power_series, directory, target_clean)

if __name__ == '__main__':
    main()