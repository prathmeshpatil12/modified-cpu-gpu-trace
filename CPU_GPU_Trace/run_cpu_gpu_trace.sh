#!/bin/bash
set -e

echo "Starting PyTorch script..."
export LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH
export DW_CUPTI_LOG=${DW_CUPTI_LOG:-/tmp/dwcupti.log}
: > "$DW_CUPTI_LOG"

LD_PRELOAD=$PWD/libdwcupti.so ../venv/bin/python3 pytorch-gpu-sample.py &
PID=$!
echo "PyTorch PID: $PID"

sleep 1

echo "Starting dw-pid tracer..."
sudo ./dw-pid $PID &

echo "Tailing GPU log: $DW_CUPTI_LOG"
tail -f "$DW_CUPTI_LOG" &
TAILPID=$!

wait $PID
kill $TAILPID 2>/dev/null || true
echo "Done!"