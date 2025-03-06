import subprocess
import random
import time

# Run cs_solver.py for each test input.
while True:
    # input("Press Enter key to start the loop...")
    # time.sleep(0.5)
    test = ''.join(random.choice('abc') for _ in range(30))
    print(f"string : {test}")
    size = []

    for solver_type in ["slp", "rlslp", "cs"]: 
        cmd = ["python", "result2dot.py", solver_type, test]
        result = subprocess.run(cmd, capture_output=True, text=True)

        s = result.stdout.splitlines()[-1]
        size.append(s)
        print(f"{solver_type}size : {s}")

        # エラーがあればエラーログを出力
        if result.stderr:
            print("Standard Error:")
            print(result.stderr)
            with open('error.log', 'w') as f:
                f.write('error string on ' + solver_type + ':' + test +'\n')

    # Collage SystemのサイズがSLPやRLSLPのサイズを超えていないか確認
    if size[2] > size[0] or size[2] > size[1]:
        print("Collage size is larger than SLP or RLSLP size.")
        with open('error.log', 'w') as f:
            f.write('strange string :' + test +'\n')
    
    # Collage SystemのサイズがSLPより小さく，かつ

    print("-" * 40)