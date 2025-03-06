import subprocess

# List of test strings to pass as an argument to cs_solver.py.
test_strings = [
    "a
    "aaaaabbbbbbbb",

]

# Run cs_solver.py for each test input.
for test in test_strings:
    cmd = ["python", "src/cs_solver.py", "--output", "csdot", "--str", test]
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("Standard Output:")
    print(result.stdout)
    if result.stderr:
        print("Standard Error:")
        print(result.stderr)
    print("-" * 40)