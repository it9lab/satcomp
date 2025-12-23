import subprocess
import random
import sys

# loop test
def test_once(str):
    print(f"string : {str}")

    size = {}
    for solver_type in ["slp", "rlslp", "cs"]: 
        cmd = ["python", "migita/json2img.py", solver_type, str]
        result = subprocess.run(cmd, capture_output=True, text=True)

        s = result.stdout.splitlines()[-1]
        size[solver_type] = int(s)
        print(f"{solver_type} size : {s}")

        # エラーがあればエラーログを出力
        if result.stderr:
            print("Standard Error:")
            print(result.stderr)

    # Collage SystemのサイズがSLPやRLSLPのサイズを超えていないか確認
    if size["cs"] > size["slp"] or size["cs"] > size["rlslp"]:
        print("cs is larger than SLP or RLSLP size.")
    
    # Collage Systemのサイズが最も小さいとき
    elif size["cs"] < size["slp"] and size["cs"] < size["rlslp"]:
        print("cs is the smallest.")

    print("-" * 40)

def loop_test(string, score):
    # input("Press Enter key to start the loop...")
    print(f"string : {string}")

    size = {}
    for solver_type in ["cs", "rlslp", "slp"]: 
        cmd = ["python", "migita/json2img.py", solver_type, string]
        result = subprocess.run(cmd, capture_output=True, text=True)
        s = result.stdout.splitlines()[-1]
        size[solver_type] = int(s)
        print(f"{solver_type} size : {s}")

        # エラーがあればエラーログを出力
        if result.stderr:
            print("Standard Error:")
            print(result.stderr)
            with open('migita/log/test.log', 'a') as f:
                f.write('error string on ' + solver_type + ':' + string +'\n')

    # Collage SystemのサイズがSLPやRLSLPのサイズを超えていないか確認
    if size["cs"] > size["slp"] or size["cs"] > size["rlslp"]:
        print("cs is larger than SLP or RLSLP size.")
        with open('migita/log/test.log', 'a') as f:
            f.write('strange string :' + string +'\n')
    

    # Collage Systemのサイズが最も小さいとき
    elif size["cs"] < size["slp"] and size["cs"] < size["rlslp"]:
        score["cs"] += 1
        with open('migita/log/test.log', 'a') as f:
            f.write('good string :' + string + ', size : ' + str(size["slp"]) + "-" + str(size["rlslp"]) + "-" + str(size["cs"]) + '\n')
    
    elif size["cs"] == size["rlslp"] and size["rlslp"] < size["slp"]:
        score["rlslp"] += 1
    
    else:
        score["slp"] += 1 
    score["total"] += 1
    print(f"score : SLP {score['slp']}, RLSLP {score['rlslp']}, CS {score['cs']}")
    print(f"total : {score['total']}")
    print("-" * 40)

if __name__ == "__main__":
    args = sys.argv
    if len(args) == 1:
        score = {"slp": 0, "rlslp": 0, "cs": 0, "total": 0}
        while True:
            string = ''.join(random.choices("AB", k=35))
            loop_test(string, score)
    elif len(args) == 2:
        string = args[1]
        test_once(string)
    else:
        print("Usage: python migita/test.py [string]")
        sys.exit(1)