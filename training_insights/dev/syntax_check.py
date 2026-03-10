import ast, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
files = [
    'evaluation/checkpoint_eval.py',
    'evaluation/parser.py',
    'evaluation/runner.py',
    'evaluation/report.py',
    'evaluation/insights.py',
    'evaluation/behavioral_delta.py',
    'evaluation/__init__.py',
    '__init__.py',
    '__main__.py',
]
errors = []
for f in files:
    try:
        ast.parse(open(f).read())
        print(f'OK  {f}')
    except SyntaxError as e:
        print(f'ERR {f}: {e}')
        errors.append(f)
print(f'\n{len(files) - len(errors)}/{len(files)} files OK')
sys.exit(len(errors))
