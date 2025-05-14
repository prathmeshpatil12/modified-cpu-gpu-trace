#!/bin/bash

# sudo apt install nvidia-driver-550 libnvidia-ml-dev

# Function to display usage information
usage() {
    echo "Usage: $0 <executable_path> [<executable_args>...]"
    exit 1
}

# Function to create the result directory
create_result_dir() {
    mkdir -p "./Result/${CGROUP_NAME}"
}

# Function to create a new cgroup under the specified controller
create_cgroup() {
    sudo mkdir -p /sys/fs/cgroup/$CONTROLLER/$CGROUP_NAME
    if [ $? -ne 0 ]; then
        echo "Failed to create cgroup"
        exit 1
    fi
}

# Function to add the PID of the executable to the cgroup
add_pid_to_cgroup() {
    local pid=$1
    echo $pid | sudo tee /sys/fs/cgroup/$CONTROLLER/$CGROUP_NAME/cgroup.procs
    if [ $? -ne 0 ]; then
        echo "Failed to add PID $pid to cgroup"
        sudo kill $pid
        sudo rmdir /sys/fs/cgroup/$CONTROLLER/$CGROUP_NAME
        exit 1
    fi
}

# Function to run the executable
run_executable() {
    $EXECUTABLE_PATH "$@" &
    PID=$!
    if [ $? -ne 0 ]; then
        echo "Failed to start the executable"
        sudo rmdir /sys/fs/cgroup/$CONTROLLER/$CGROUP_NAME
        exit 1
    fi
}

# Function to start tracing using dw-pid and turbostat
start_tracing() {
    sudo ./CPU_Trace/dw-pid $PID > "./Result/${CGROUP_NAME}/${CGROUP_NAME}.csv" & DW_PID=$!
    echo "Tracing executable PID $PID with dw-pid..."
    sudo /home/prathamesh/.cargo/bin/py-spy record --pid $PID --native --output "./Result/${CGROUP_NAME}/${CGROUP_NAME}_pyspy.svg" & PYSPY_PID=$!
    echo "Tracing call stacks with modified PySpy..."
    # sudo turbostat --Summary --quiet --show Time_Of_Day_Seconds,CorWatt --interval 0.1 > "./Result/${CGROUP_NAME}/${CGROUP_NAME}_RAPL.csv" & TURBOSTAT_PID=$!
}

# Function to copy the process maps file into the Result directory
copy_pid_maps() {
    cp /proc/"$1"/maps "./Result/${CGROUP_NAME}/${CGROUP_NAME}.maps"
    if [ $? -ne 0 ]; then
        echo "Failed to copy maps for PID $1"
    else
        echo "Copied maps for PID $1 to ./Result/${CGROUP_NAME}/${CGROUP_NAME}.maps"
    fi
}

# Function to clean up the cgroup on exit
cleanup() {
    sudo rmdir /sys/fs/cgroup/$CONTROLLER/$CGROUP_NAME
    echo "Cgroup $CGROUP_NAME under controller $CONTROLLER has been removed"
}

# Main execution flow

( cd ./CPU_Trace && make dw-pid )

# Check if sufficient arguments are provided
if [ $# -lt 1 ]; then
    usage
fi

EXECUTABLE_PATH="$1"
shift

# Derive cgroup name from the executable name
BASENAME=$(basename "$EXECUTABLE_PATH")
CGROUP_NAME="${BASENAME%.*}"

CONTROLLER="perf_event"

# Create a directory to store the result and trace RAPL data
create_result_dir

# Create a new cgroup under the specified controller
create_cgroup

# Setup cleanup when the script exits
trap cleanup EXIT

# Start the executable in the background
run_executable "$@"

# Add its PID to the created cgroup
add_pid_to_cgroup "$PID"

# Start tracing the running executable
start_tracing

echo "Executable is running in cgroup $CGROUP_NAME under controller $CONTROLLER with PID $PID"

# Copy /proc/<PID>/maps to the Result directory
copy_pid_maps "$PID"

# Wait for the executable to finish
wait $PID
wait $DW_PID
wait $PYSPY_PID
# Kill the tracing processes after the executable ends
# sudo kill $DW_PID
# sudo kill $TURBOSTAT_PID

# Function to process results and generate reports
process_results() {
    # Execute collapse_report.py on the generated csv
    ./collapse_report.py -e 6 "./Result/${CGROUP_NAME}/${CGROUP_NAME}.csv"
    echo "Running collapse file generator to combine results from pyspy and energy measurements..."
    python3 collapse_report_generator.py "./Result/${CGROUP_NAME}/${CGROUP_NAME}_pyspy_timestamps.json" "./Result/${CGROUP_NAME}/${CGROUP_NAME}.csv" -o "Result/${CGROUP_NAME}/${CGROUP_NAME}_energy.collapsed"
    
    # Echo before running flamegraph.pl for energy flame graph
    echo "Running flamegraph.pl for Energy Flame Graph..."
    ./flamegraph.pl --title "Energy Flame Graph" --countname "microwatts" "./Result/${CGROUP_NAME}/${CGROUP_NAME}_energy.collapsed" > "./Result/${CGROUP_NAME}/${CGROUP_NAME}_energy.svg"
    
    # Echo before running flamegraph.pl for CPU flame graph
    echo "Running flamegraph.pl for CPU Flame Graph..."
    ./flamegraph.pl --title "CPU Flame Graph" --countname "samples" "./Result/${CGROUP_NAME}/${CGROUP_NAME}_cpu.collapsed" > "./Result/${CGROUP_NAME}/${CGROUP_NAME}_cpu.svg"
}

# Run the function to process results after tracing is complete
process_results
