#!/bin/bash

# Check if an executable is provided as an argument
if [ $# -eq 0 ]; then
    echo "Usage: $0 <executable>"
    exit 1
fi

# Store the file name of the executable in a variable
executable="$1"

# Launch the executable in the background
"$@" &

# Get the PID of the last background process
pid=$!

# Print the PID
echo "Process ID: $pid"

# Set the output directory to the same directory as the executable
output_dir="$(dirname $executable)"

# Set the output file name
output_file="$output_dir/$(basename $executable).perf"

# Run perf record with the specified call graph and PID
perf record --call-graph=fp -p $pid -o $output_file

# dwarf|fp|lbr|no

# perf record -e task-clock -F 1000 -p $pid --call-graph fp -- sleep 60 -o $output_file

# Wait for the process to exit
wait $pid

# Print a message when the process has exited
echo "Process $pid has exited"

output_script="$output_dir/$(basename $executable).data"

# Pass the output file as input to perf script and set the output to output.data
perf script -i $output_file > $output_script

# Pass output.data as input to stackcollapse-perf.pl and set the output to output.collapsed
./stackcollapse-perf.pl $output_script > "$output_dir/$(basename $executable).collapsed"

output_perf="$output_dir/$(basename $executable).collapsed"

./flamegraph.pl $output_perf > "$output_dir/$(basename $executable).svg"
