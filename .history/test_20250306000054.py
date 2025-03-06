import subprocess
import random
import time

# Run cs_solver.py for each test input.
while True:
    # time.sleep(0.5)
    test = ''.join(random.choice('abc') for _ in range(30))
    cmd = ["python", "src/cs_solver.py", "--str", test]
    print(f"")
    result = subprocess.run(cmd, capture_output=True, text=True)
    size = len(result.stdout.split('\n'))
    print(size)
    if result.stderr:
        print("Standard Error:")
        print(result.stderr)
        with open('error.log', 'w') as f:
            f.write(test+'\n')
    print("-" * 40)