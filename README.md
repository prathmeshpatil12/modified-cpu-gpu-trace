# Modified CPU-GPU-trace

## Overview

This repository extends the capabilities of PyTorch profiling by combining **CPU/GPU power usage** data (https://github.com/PranavDani/CPU-GPU-trace) with **timestamped Python call stacks** to generate an **energy-based flamegraph** of a PyTorch program.

## Prerequisites
- A Linux system with cgroup support.
- NVIDIA drivers and development libraries (e.g., nvidia-driver-550 and libnvidia-ml-dev).
- Build tools (e.g., make) to compile dw-pid located in the CPU_Trace directory.
- Perl and any dependencies for flamegraph.pl.
- Modified pyspy installed

## What It Does

- Runs a modified version of [`py-spy`](https://github.com/benfred/py-spy) in the background to sample Python call stacks along with precise UTC timestamps.
- Captures CPU and GPU power usage data, also tagged with UTC timestamps.
- Merges the call stack data with power metrics to generate an **energy flamegraph** that visualizes power consumption across Python function calls.

## Features

- Timestamped power monitoring (CPU and GPU)
- Call stack tracing with temporal resolution
- Energy flamegraph generation for PyTorch scripts

## Installation

1. Clone this repository:

```bash
git clone https://github.com/prathmeshpatil12/modified-cpu-gpu-trace.git
cd CPU-GPU-trace
```

2. On Linux, make sure libunwind is installed:
```bash
sudo apt install libunwind-dev
```

## Usage
```bash
./start_cgroup.sh python3 <python-file.py>
```
This will:
- Start py-spy in the background
- Start power monitoring for CPU and GPU
- Generate two timestamped logs:
    - Call stack data (from py-spy)
    - Power data (from cpu-gpu-trace)
- Merge them into an python_energy.svg


## Output
Adds output to Result/python directory
- Result/: Output directory where trace files and generated reports are saved.
    - Result/python_energy.svg - Energy flamegraph
    - Result/python_pyspy.svg - CPU flamegraph

## Files
- CPU_Trace/: Contains tracing tools including dw-pid.
- start_cgroup.sh: Main shell script to handle cgroup management, tracing, and report generation.

## Cleanup
The script automatically removes the created cgroup upon exit. In case of errors during the execution or PID addition, cleanup routines remove partial configurations.
