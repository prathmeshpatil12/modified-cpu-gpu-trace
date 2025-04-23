#!/bin/bash

echo "Running SmartWatts to generate power estimations..."
./smartwatts.sh

# Check for arg
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <container name>"
    exit 1
fi

# Remove leading slash if it exists and assign to FNAME
if [[ "$1" == /* ]]; then
    FNAME="${1#/}"
else
    FNAME="$1"
fi

# Echo before running collapse_report.py
echo "Running collapse_report.py..."
./collapse_report.py -e 6 $1

# Echo before running flamegraph.pl for energy flame graph
echo "Running flamegraph.pl for Energy Flame Graph..."
./flamegraph.pl --title "Energy Flame Graph" --countname "microwatts" ./Result/$FNAME/$FNAME\_energy.collapsed > ./Result/$FNAME/$FNAME\_energy.svg

# Echo before running flamegraph.pl for CPU flame graph
echo "Running flamegraph.pl for CPU Flame Graph..."
./flamegraph.pl --title "CPU Flame Graph" --countname "samples" ./Result/$FNAME/$FNAME\_cpu.collapsed > ./Result/$FNAME/$FNAME\_cpu.svg