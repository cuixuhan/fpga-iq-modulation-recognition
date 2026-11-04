"""Behavioral tests with artificial fixtures; never accesses a board."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='New JSON result file; refuses overwrite')
    parser.add_argument('--temp-root', help='Existing writable directory for temporary fixtures')
    args = parser.parse_args()
    if args.output and Path(args.output).exists():
        parser.error('output already exists; choose a new file')
    package = Path(__file__).resolve().parents[1]
    cases = []
    temp_root = Path(args.temp_root or tempfile.gettempdir()).resolve()
    if not temp_root.is_dir():
        parser.error('temp-root must be an existing writable directory')
    if temp_root == package or temp_root.is_relative_to(package):
        parser.error('temp-root must be outside the skill package to avoid recursive copying')
    with tempfile.TemporaryDirectory(prefix='fpga_skill_', dir=temp_root) as tmp:
        root = Path(tmp)
        if root.resolve().parent != temp_root:
            raise ValueError('temporary directory escaped intended root')
        # Copy and execute outside the original project to test path portability.
        relocated = root / 'relocated_skill'
        shutil.copytree(package, relocated, ignore=shutil.ignore_patterns('__pycache__', 'validation'))
        checker = relocated / 'scripts' / 'check.py'

        def run(name, argv, expected_exit, assertion=lambda obj: True):
            proc = subprocess.run([sys.executable, str(checker), *map(str, argv)],
                                  cwd=root, capture_output=True, text=True, encoding='utf-8')
            try:
                obj = json.loads(proc.stdout)
                valid = assertion(obj)
            except (ValueError, KeyError, TypeError):
                obj, valid = {}, False
            cases.append({'name': name, 'expected_exit': expected_exit, 'actual_exit': proc.returncode,
                          'passed': proc.returncode == expected_exit and valid,
                          'stdout': obj, 'stderr': proc.stderr})

        schema = root / 'schema.json'
        schema.write_text(json.dumps({'schema_version': 1, 'layout': 'c_order_flat',
                                     'tensors': {'x': {'shape': [2, 2], 'dtype': 'int8'}}}))
        expected = root / 'expected.csv'
        actual = root / 'actual.csv'
        baseline = 'tensor,index,value\nx,0,-128\nx,1,-2\nx,2,0\nx,3,127\n'
        expected.write_text(baseline)

        def compare_case(name, content, exit_code, assertion=lambda obj: True):
            actual.write_text(content)
            run(name, ['compare', '--schema', schema, '--expected', expected, '--actual', actual],
                exit_code, assertion)

        compare_case('equal_including_int8_edges', baseline, 0, lambda r: r['elements'] == 4)
        compare_case('row_order_independent', 'tensor,index,value\nx,3,127\nx,2,0\nx,1,-2\nx,0,-128\n', 0)
        compare_case('changed_value', baseline.replace('x,1,-2', 'x,1,-3'), 1,
                     lambda r: r['mismatch_count'] == 1)
        compare_case('missing_tail', baseline.replace('x,3,127\n', ''), 1)
        compare_case('duplicate_index', baseline + 'x,1,-2\n', 1)
        compare_case('unknown_tensor', baseline.replace('x,3,127', 'y,3,127'), 1)
        compare_case('out_of_range_index', baseline.replace('x,3,127', 'x,4,127'), 1)
        compare_case('out_of_range_value', baseline.replace('x,3,127', 'x,3,128'), 1)
        compare_case('unknown_logic_value', baseline.replace('x,3,127', 'x,3,X'), 1)
        compare_case('float_value_rejected', baseline.replace('x,3,127', 'x,3,127.0'), 1)
        compare_case('extra_column', baseline.replace('x,3,127', 'x,3,127,extra'), 1)
        short = baseline.replace('x,3,127\n', '')
        expected.write_text(short)
        compare_case('both_files_missing_same_tail', short, 1)
        expected.write_text(baseline)
        schema.write_text('{"schema_version":1,"layout":"c_order_flat","tensors":{}}')
        compare_case('empty_schema', baseline, 1)
        schema.write_text('{"schema_version":1,"schema_version":1,"layout":"c_order_flat","tensors":{}}')
        compare_case('duplicate_json_key', baseline, 1)

        source = root / 'source.txt'
        source.write_bytes(b'fixture only\n')
        manifest = root / 'manifest.json'
        entry = {'id': 'fixture', 'snapshot': 'source.txt', 'source': 'source.txt',
                 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}

        def write_manifest(item):
            manifest.write_text(json.dumps({'schema_version': 1, 'sources': [item]}))

        write_manifest(entry)
        verify_args = ['verify', '--manifest', manifest, '--root', root]
        run('source_hash_equal', verify_args, 0)
        source.write_bytes(b'changed fixture\n')
        run('source_hash_changed', verify_args, 1)
        source.unlink()
        run('source_file_missing', verify_args, 1)
        write_manifest(dict(entry, snapshot='../escape.txt'))
        run('path_escape_rejected', verify_args, 1)
        write_manifest(dict(entry, snapshot='C:/absolute.txt'))
        run('absolute_path_rejected', verify_args, 1)
        manifest.write_text('{"schema_version":1,"sources":[]}')
        run('empty_manifest_rejected', verify_args, 1)
        run('relocated_snapshot_verification', ['verify', '--manifest', relocated / 'evidence/source_manifest.json',
                                              '--root', relocated], 0)
        example = relocated / 'assets/example'
        run('relocated_example_comparison', ['compare', '--schema', example / 'schema.json',
                                            '--expected', example / 'expected.csv', '--actual', example / 'actual.csv'],
            0, lambda r: r['elements'] == 7)

    result = {'status': 'PASS' if all(c['passed'] for c in cases) else 'FAIL',
              'evidence_kind': 'artificial_fixture_and_package_portability',
              'time_utc': datetime.now(timezone.utc).isoformat(), 'python_version': sys.version,
              'case_count': len(cases), 'passed': sum(c['passed'] for c in cases), 'cases': cases,
              'hardware_actions': False, 'cnn_oracle_rerun': False}
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with Path(args.output).open('x', encoding='utf-8') as stream:
            stream.write(serialized + '\n')
    print(serialized)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
