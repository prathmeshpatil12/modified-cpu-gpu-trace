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


# Build GPU CUPTI injector (libdwcupti.so) if missing
build_gpu_injector() {
    local so="./CPU_GPU_Trace/libdwcupti.so"
    if [ ! -f "$so" ]; then
        echo "Building GPU CUPTI injector (libdwcupti.so)..."
        ( cd ./CPU_GPU_Trace && make libdwcupti.so ) || {
            echo "Failed to build libdwcupti.so"
            exit 1
        }
    fi
}

# Function to run the executable
run_executable() {
    build_gpu_injector
    LIBDW="$PWD/CPU_GPU_Trace/libdwcupti.so"

    LD_PRELOAD="$LIBDW" \
    LD_LIBRARY_PATH="${CUDA_PATH}/lib64:${LD_LIBRARY_PATH}" \
    DW_CUPTI_LOG="${DW_CUPTI_LOG}" \
    "$EXECUTABLE_PATH" "$@" &
    PID=$!
    if [ $? -ne 0 ]; then
        echo "Failed to start the executable"
        sudo rmdir /sys/fs/cgroup/$CONTROLLER/$CGROUP_NAME
        exit 1
    fi
}


# Function to start tracing using dw-pid and turbostat
start_tracing() {
    echo "Starting dw-pid tracer for PID $PID..."
    sudo ./CPU_Trace/dw-pid $PID > "./Result/${CGROUP_NAME}/${CGROUP_NAME}.csv" 2> "./Result/${CGROUP_NAME}/${CGROUP_NAME}_errors.log" & DW_PID=$!
    echo "Tracing executable PID $PID with dw-pid..."
    
    # Add a small delay to ensure the target process has started properly
    sleep 0.5
    
    sudo /home/prathmesh/.cargo/bin/py-spy record --pid $PID --native --output "./Result/${CGROUP_NAME}/${CGROUP_NAME}_pyspy.svg" & PYSPY_PID=$!
    sudo chown $(whoami):$(whoami) "./Result/${CGROUP_NAME}/${CGROUP_NAME}_pyspy.svg" 2>/dev/null || true
    sudo chown $(whoami):$(whoami) "./Result/${CGROUP_NAME}/${CGROUP_NAME}_pyspy_timestamps.json" 2>/dev/null || true
    echo "Tracing call stacks with modified PySpy..."
    # sudo turbostat --Summary --quiet --show Time_Of_Day_Seconds,CorWatt --interval 0.1 > "./Result/${CGROUP_NAME}/${CGROUP_NAME}_RAPL.csv" & TURBOSTAT_PID=$!
}

# Function to copy the process maps file into the Result directory
copy_pid_maps() {
    sudo cp /proc/"$1"/maps "./Result/${CGROUP_NAME}/${CGROUP_NAME}.maps"
    if [ $? -ne 0 ]; then
        echo "Failed to copy maps for PID $1"
    else
        echo "Copied maps for PID $1 to ./Result/${CGROUP_NAME}/${CGROUP_NAME}.maps"
        # Change ownership to current user
        sudo chown $(whoami):$(whoami) "./Result/${CGROUP_NAME}/${CGROUP_NAME}.maps"
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

# CUDA and CUPTI env; set GPU log path inside Result folder
CUDA_PATH="/usr/local/cuda-12.8"
mkdir -p "./Result/${CGROUP_NAME}"
export LD_LIBRARY_PATH="${CUDA_PATH}/lib64:${LD_LIBRARY_PATH}"
export DW_CUPTI_LOG="./Result/${CGROUP_NAME}/${CGROUP_NAME}_cupti.log"
: > "$DW_CUPTI_LOG"

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

# Check if there were any errors during tracing
if [ -f "./Result/${CGROUP_NAME}/${CGROUP_NAME}_errors.log" ] && [ -s "./Result/${CGROUP_NAME}/${CGROUP_NAME}_errors.log" ]; then
    echo "Warning: Errors detected during tracing:"
    cat "./Result/${CGROUP_NAME}/${CGROUP_NAME}_errors.log"
fi

# Ensure py-spy outputs are owned by the current user and readable
for f in "./Result/${CGROUP_NAME}/${CGROUP_NAME}_pyspy.svg" \
         "./Result/${CGROUP_NAME}/${CGROUP_NAME}_pyspy_timestamps.json"; do
    if [ -f "$f" ]; then
        sudo chown "$(whoami):$(whoami)" "$f" 2>/dev/null || true
        chmod a+r "$f" 2>/dev/null || true
    fi
done

# Kill the tracing processes after the executable ends
# sudo kill $DW_PID
# sudo kill $TURBOSTAT_PID

# Function to process results and generate reports
process_results() {
    echo "Post-processing traces for cgroup ${CGROUP_NAME}"

    # 1. CPU collapsed (time) via existing collapse_report.py (if matplotlib present)
    if python3 -c "import matplotlib.pyplot as plt" 2>/dev/null; then
        echo "Generating CPU time collapsed (samples)..."
        ./collapse_report.py -e 6 "./Result/${CGROUP_NAME}/${CGROUP_NAME}.csv"
    else
        echo "matplotlib missing, skipping CPU time collapse"
        : > "./Result/${CGROUP_NAME}/${CGROUP_NAME}_cpu.collapsed"
    fi

    # 2. CPU energy collapsed (microjoules)
    echo "Generating CPU energy collapsed..."
    python3 collapse_report_generator.py \
        "./Result/${CGROUP_NAME}/${CGROUP_NAME}_pyspy_timestamps.json" \
        "./Result/${CGROUP_NAME}/${CGROUP_NAME}.csv" \
        -o "./Result/${CGROUP_NAME}/${CGROUP_NAME}_energy.collapsed"

    # 3. GPU time + energy collapsed
    echo "Generating GPU time/energy collapsed..."
    python3 parse_gpu_traces.py "${CGROUP_NAME}"

    # 4. Combine CPU + GPU energy
    echo "Combining CPU + GPU energy collapsed..."
    python3 get_cpu_gpu_times.py "${CGROUP_NAME}"
    python3 generate_combined_flamegraph.py "${CGROUP_NAME}"
    python3 generate_combined_collapsed_file_for_energy_flamegraph.py "${CGROUP_NAME}"

    # 5. Flamegraphs (require flamegraph.pl)
    if [ -x ./flamegraph.pl ]; then
        echo "Rendering flamegraphs..."

        # CPU time samples
        if [ -s "./Result/${CGROUP_NAME}/${CGROUP_NAME}_cpu.collapsed" ]; then
            ./flamegraph.pl --title "CPU Time Flame Graph" --countname "samples" \
              "./Result/${CGROUP_NAME}/${CGROUP_NAME}_cpu.collapsed" > "./Result/${CGROUP_NAME}/${CGROUP_NAME}_cpu_time.svg"
        fi

        # CPU energy
        if [ -s "./Result/${CGROUP_NAME}/${CGROUP_NAME}_energy.collapsed" ]; then
            ./flamegraph.pl --title "CPU Energy Flame Graph" --countname "microjoules" \
              "./Result/${CGROUP_NAME}/${CGROUP_NAME}_energy.collapsed" > "./Result/${CGROUP_NAME}/${CGROUP_NAME}_cpu_energy.svg"
        fi

        # GPU time
        if [ -s "./Result/${CGROUP_NAME}/gpu_time.collapsed" ]; then
            ./flamegraph.pl --title "GPU Time Flame Graph" --countname "nanoseconds" --inverted \
              "./Result/${CGROUP_NAME}/gpu_time.collapsed" > "./Result/${CGROUP_NAME}/${CGROUP_NAME}_gpu_time.svg"
        fi

        # GPU energy
        if [ -s "./Result/${CGROUP_NAME}/gpu_energy.collapsed" ]; then
            ./flamegraph.pl --title "GPU Energy Flame Graph" --countname "microjoules" \
              "./Result/${CGROUP_NAME}/gpu_energy.collapsed" > "./Result/${CGROUP_NAME}/${CGROUP_NAME}_gpu_energy.svg"
        fi

        # Combined energy
        if [ -s "./Result/${CGROUP_NAME}/combined_energy.collapsed" ]; then
            ./flamegraph.pl --title "CPU + GPU Energy Flame Graph" --countname "microjoules" \
              "./Result/${CGROUP_NAME}/combined_energy.collapsed" > "./Result/${CGROUP_NAME}/${CGROUP_NAME}_combined_energy.svg"
        fi
    else
        echo "flamegraph.pl not found/executable; skipping SVG generation."
    fi

    echo "Done. Outputs in ./Result/${CGROUP_NAME}"
}

# Run the function to process results after tracing is complete
process_results