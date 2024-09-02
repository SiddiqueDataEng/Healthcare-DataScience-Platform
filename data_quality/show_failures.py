import json, glob
files = sorted(glob.glob('data_quality/results/*.json'))
if not files:
    print('No results file found')
else:
    with open(files[-1]) as f:
        data = json.load(f)
    for table, result in data.items():
        failed = [c for c in result.get('checks', []) if c['status'] == 'FAIL']
        if failed:
            print(f'=== {table} FAILURES ===')
            for c in failed:
                print(f'  CHECK  : {c["check_name"]}')
                print(f'  VALUE  : {c["value"]}')
                print(f'  DETAILS: {c["details"]}')
                print()
        else:
            score = result.get('quality_score', '?')
            print(f'OK {table} score={score}%')
