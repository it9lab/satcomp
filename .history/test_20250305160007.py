import subprocess

# List of test strings to pass as an argument to cs_solver.py.
test_strings = [
    "simple",
    "123",
    "hello world",
    "--flag",
    "特殊文字",
    "'quoted string'",
    "\"double quoted\"",
    "with space",
    "long-string-with-dashes"
]

# Run cs_solver.py for each test input.
for test in test_strings:
    cmd = ["python", "cs_solver.py", test]
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("Standard Output:")
    print(result.stdout)
    if result.stderr:
        print("Standard Error:")
        print(result.stderr)
    print("-" * 40)