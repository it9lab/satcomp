import subprocess
import random
import time

# Run cs_solver.py for each test input.
while True:
    input("Press Enter key to start the loop...")
    # time.sleep(0.5)
    test = ''.join(random.choice('abc') for _ in range(30))
    
    for solver_type in ["slp", "rlslp", "cs"]:
        cmd = ["python", "src/" + solver_type + "_solver.py", "--str", test]
        print(f"solver: {solver_type}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"stdout: {result.stdout}")
        if result.stderr:
            print("Standard Error:")
            print(result.stderr)
            with open('error.log', 'w') as f:
                f.write(test+'\n')
        print("-" * 40)
    cmd = ["python", "result2dot.py", "cs", test]
    print(f"string: {test}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    size = ''.join(result.stdout.splitlines())
    print(f"cssize: {size}")

    if result.stderr:
        print("Standard Error:")
        print(result.stderr)
        with open('error.log', 'w') as f:
            f.write(test+'\n')
    print("-" * 40)