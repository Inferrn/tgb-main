import ast, sys
p='c:\\all_project\\tg_bot\\app\\handlers\\question.py'
try:
    with open(p, 'r', encoding='utf-8') as f:
        src = f.read()
    ast.parse(src)
    print('AST OK')
except SyntaxError as e:
    print('SyntaxError:', e.msg)
    print('Line:', e.lineno)
    print('Offset:', e.offset)
    with open(p, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    start = max(0, e.lineno-6)
    end = min(len(lines), e.lineno+3)
    print('\nContext lines:')
    for i in range(start, end):
        print(f"{i+1:4}: {lines[i].rstrip()}")
    sys.exit(2)
except Exception as e:
    print('Other error:', e)
    raise
else:
    print('No syntax errors')
