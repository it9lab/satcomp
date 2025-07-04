import subprocess
import random
import sys

# loop test
def test_once(str):
    print(f"string : {str}")
    size = []

    for solver_type in ["slp", "rlslp", "cs"]: 
        cmd = ["python", "src/json2img.py", solver_type, str]
        result = subprocess.run(cmd, capture_output=True, text=True)

        s = result.stdout.splitlines()[-1]
        size.append(s)
        print(f"{solver_type}size : {s}")

        # エラーがあればエラーログを出力
        if result.stderr:
            print("Standard Error:")
            print(result.stderr)

    # Collage SystemのサイズがSLPやRLSLPのサイズを超えていないか確認
    if size[2] > size[0] or size[2] > size[1]:
        print("cs is larger than SLP or RLSLP size.")
    
    # Collage Systemのサイズが最も小さいとき
    elif size[2] < size[0] and size[2] < size[1]:
        print("cs is the smallest.")

    print("-" * 40)

def loop_test(str, score):
    # input("Press Enter key to start the loop...")
    print(f"string : {str}")
    size = []

    for solver_type in ["slp", "rlslp", "cs"]: 
        cmd = ["python", "src/json2img.py", solver_type, str]
        result = subprocess.run(cmd, capture_output=True, text=True)
        s = result.stdout.splitlines()[-1]
        size.append(s)
        print(f"{solver_type}size : {s}")

        # エラーがあればエラーログを出力
        if result.stderr:
            print("Standard Error:")
            print(result.stderr)
            with open('log/test.log', 'a') as f:
                f.write('error string on ' + solver_type + ':' + str +'\n')

    # Collage SystemのサイズがSLPやRLSLPのサイズを超えていないか確認
    if size[2] > size[0] or size[2] > size[1]:
        print("cs is larger than SLP or RLSLP size.")
        with open('log/test.log', 'a') as f:
            f.write('strange string :' + str +'\n')
    

    # Collage Systemのサイズが最も小さいとき
    elif size[2] < size[0] and size[2] < size[1]:
        score[2] += 1
        with open('log/test.log', 'a') as f:
            f.write('good string :' + str + ', size : ' + '-'.join(size) + '\n')
    
    elif size[2] == size[1] and size[1] < size[0]:
        score[1] += 1
    
    else:
        score[0] += 1 
    score[3] += 1
    print(f"score : SLP {score[0]}, RLSLP {score[1]}, CS {score[2]}")
    print(f"total : {score[3]}")
    print("-" * 40)

if __name__ == "__main__":
    args = sys.argv
    if len(args) == 1:
        score = [0, 0, 0, 0] 
        while True:
            str = ''.join(random.choices("AB", k=32))
            loop_test(str, score)
    elif len(args) == 2:
        str = args[1]
        test_once(str)
    else:
        print("Usage: python src/test.py [string]")
        sys.exit(1)