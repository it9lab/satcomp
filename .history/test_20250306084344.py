import subprocess
import random
import time

# Run cs_solver.py for each test input.
while True:
    input("Press Enter key to start the loop...")
    # time.sleep(0.5)
    test = ''.join(random.choice('abc') for _ in range(30))
    print(f"string : {test}")
    for solver_type in ["slp", "rlslp", "cs"]: 
        cmd = ["python", "result2dot.py", solver_type, test]
        result = subprocess.run(cmd, capture_output=True, text=True)
        size = result.stdout.splitlines()[-1]
        print(f"{solver_type}size : {size}")
        if result.stderr:
            print("Standard Error:")
            print(result.stderr)
            with open('error.log', 'w') as f:
                f.write('error string on :' + test +'\n')
    print("-" * 40)