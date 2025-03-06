import subprocess
import random
import time

# loop test
def loop_test(str):
    # input("Press Enter key to start the loop...")
    # time.sleep(0.5)
    print(f"string : {str}")
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
            with open('test.log', 'w') as f:
                f.write('error string on ' + solver_type + ':' + test +'\n')

    # Collage SystemのサイズがSLPやRLSLPのサイズを超えていないか確認
    if size[2] > size[0] or size[2] > size[1]:
        print("Collage size is larger than SLP or RLSLP size.")
        with open('test.log', 'w') as f:
            f.write('strange string :' + test +'\n')
    
    # Collage Systemのサイズが最も小さいとき
    elif size[2] == min(size):
        print("Collage size is the smallest.")
        with open('test.log', 'w') as f:
            f.write('good string :' + test +'\n')

    print("-" * 40)

if __name__ == "__main__":
    for _ in range(10):
        loop_test()