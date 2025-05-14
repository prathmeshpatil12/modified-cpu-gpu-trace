import re

def extract_functions(call_stack):
    """
    Extract function names from a given call stack.
    Function names are usually in the form of 'function_name' or 'lib_name:function_name'.
    """
    function_pattern = r'([a-zA-Z0-9_]+(?:::[a-zA-Z0-9_]+)?(?:\([a-zA-Z0-9_]*\))?)'
    functions = set(re.findall(function_pattern, call_stack))
    return functions

def find_common_functions(stack1, stack2):
    """
    Find common function names between two call stacks.
    """
    functions_stack1 = extract_functions(stack1)
    functions_stack2 = extract_functions(stack2)

    #print("Stack 1", functions_stack1)
    #print("Stack 2", functions_stack2)
    
    # Find the intersection of the two sets
    common_functions = functions_stack1.intersection(functions_stack2)
    
    print(len(functions_stack1))
    print(len(functions_stack2))
    print(len(common_functions))
    
    return common_functions

def read_file(file_path):
    """
    Read the content of a file and return it as a string.
    """
    with open(file_path, 'r') as file:
        return file.read()

# Paths to your files
cpu_file_path = "./python_cpu.collapsed"
energy_file_path = "./python_energy.collapsed"

# Read the contents of both files
cpu_stack_raw = read_file(cpu_file_path)
energy_stack_raw = read_file(energy_file_path)

# Find common functions
common_functions = find_common_functions(cpu_stack_raw, energy_stack_raw)

# Output result
if common_functions:
    print("Common functions found:")
    for func in common_functions:
        print(func)
else:
    print("No common functions found.")
