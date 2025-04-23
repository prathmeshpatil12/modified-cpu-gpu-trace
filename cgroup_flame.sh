#!/bin/bash

# Check if sufficient arguments are provided
if [ $# -lt 1 ]; then
    echo "Usage: $0 <executable_path> [<executable_args>...]"
    exit 1
fi

executable="$1"

EXECUTABLE_PATH="$1"
shift 1  # Shift the positional parameters to skip the first argument

# Derive cgroup name from the executable name
BASENAME=$(basename "$EXECUTABLE_PATH")
CGROUP_NAME="${BASENAME%.*}"

CONTROLLER="perf_event"

# Create a new cgroup under the specified controller
sudo mkdir -p /sys/fs/cgroup/$CONTROLLER/$CGROUP_NAME

# Check if the cgroup was created successfully
if [ $? -ne 0 ]; then
    echo "Failed to create cgroup"
    exit 1
fi

# Function to clean up the cgroup
cleanup() {
    # Remove the cgroup
    sudo rmdir /sys/fs/cgroup/$CONTROLLER/$CGROUP_NAME
    echo "Cgroup $CGROUP_NAME under controller $CONTROLLER has been removed"
}

# Trap the EXIT signal to clean up the cgroup when the script exits
trap cleanup EXIT

# Start the executable with arguments in the background and get its PID
$EXECUTABLE_PATH "$@" &
PID=$!

# Check if the executable started successfully
if [ $? -ne 0 ]; then
    echo "Failed to start the executable"
    sudo rmdir /sys/fs/cgroup/$CONTROLLER/$CGROUP_NAME
    exit 1
fi

# Add the PID to the cgroup
echo $PID | sudo tee /sys/fs/cgroup/$CONTROLLER/$CGROUP_NAME/cgroup.procs

# Check if the PID was added to the cgroup successfully
if [ $? -ne 0 ]; then
    echo "Failed to add PID to cgroup"
    sudo kill $PID
    sudo rmdir /sys/fs/cgroup/$CONTROLLER/$CGROUP_NAME
    exit 1
fi

# Copy the /proc/<pid>/maps file to the current directory
#sudo cp /proc/$PID/maps ./${CGROUP_NAME}.maps
#echo "Copied /proc/$PID/maps to ./${CGROUP_NAME}.maps"

echo "Executable is running in cgroup $CGROUP_NAME under controller $CONTROLLER with PID $PID"

output_dir="$(dirname $executable)"

# Set the output file name
output_file="$output_dir/$(basename $executable).perf"

# Run perf record with the specified call graph and PID
sudo perf record -e cpu-clock --call-graph=dwarf --cgroup=$CGROUP_NAME -o $output_file


# Wait for the executable to finish
wait $PID

echo "Process $PID has exited"

output_script="$output_dir/$(basename $executable).data"

# Pass the output file as input to perf script and set the output to output.data
perf script -i $output_file > $output_script

# Pass output.data as input to stackcollapse-perf.pl and set the output to output.collapsed
./stackcollapse-perf.pl $output_script > "$output_dir/$(basename $executable).collapsed"

output_perf="$output_dir/$(basename $executable).collapsed"

./flamegraph.pl $output_perf > "$output_dir/$(basename $executable).svg"
