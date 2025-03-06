import subprocess
import random
import time

# List of test strings to pass as an argument to cs_solver.py.
test_strings = [

]

# Run cs_solver.py for each test input.
while True:
    # time.sleep(0.5)
    test = ''.join(random.choice('ab') for _ in range(18))
    cmd = ["python", "src/cs_solver.py", "--str", test]
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("Standard Output:")
    print(result.stdout)
    if result.stderr:
        print("Standard Error:")
        print(result.stderr)
        with open('error.log', 'w') as f:
            f.write(dot_str)
    print("-" * 40)