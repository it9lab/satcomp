import subprocess
import random
import time

# Run cs_solver.py for each test input.
while True:
    # time.sleep(0.5)
    test = ''.join(random.choice('abc') for _ in range(30))
    cmd = ["python", "src/cs_solver.py", "--str", test]
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("Standard Output:")
    size = len(result.stdout.split('\n'))
    
    if result.stderr:
        print("Standard Error:")
        print(result.stderr)
        with open('error.log', 'w') as f:
            f.write(test+'\n')
    print("-" * 40)