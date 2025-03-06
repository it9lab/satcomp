import subprocess
import random
import time
import sys

# loop test
def test(str):
    # input("Press Enter key to start the loop...")
    # time.sleep(0.5)
    print(f"string : {str}")
    size = []

    for solver_type in ["slp", "rlslp", "cs"]: 
        cmd = ["python", "result2dot.py", solver_type, str]
        result = subprocess.run(cmd, capture_output=True, text=True)

        s = result.stdout.splitlines()[-1]
        size.append(s)
        print(f"{solver_type}size : {s}")

        # エラーがあればエラーログを出力
        if result.stderr:
            print("Standard Error:")
            print(result.stderr)
            with open('test.log', 'w') as f:
                f.write('error string on ' + solver_type + ':' + str +'\n')

    # Collage SystemのサイズがSLPやRLSLPのサイズを超えていないか確認
    if size[2] > size[0] or size[2] > size[1]:
        print("Collage size is larger than SLP or RLSLP size.")
        with open('test.log', 'w') as f:
            f.write('strange string :' + str +'\n')
    
    # Collage Systemのサイズが最も小さいとき
    elif size[2] == min(size):
        print("Collage size is the smallest.")
        with open('test.log', 'w') as f:
            f.write('good string :' + str +'\n')

    print("-" * 40)

if __name__ == "__main__":
    args = sys.argv
    if len(args) != 2:
        print("Usage: python test.py [string]")
        sys.exit(1)
    str = args[1]

    if str is None:
        while True:
            str = ''.join(random.choices(['a', 'b', 'c'], k=100))
            test(str)
    else:
        test(str)