"""Portable evidence checks. No serial, FPGA, subprocess, or third-party imports."""
import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path, PurePosixPath


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def contained(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError(f'invalid relative path: {relative!r}')
    p = PurePosixPath(relative)
    if p.is_absolute() or any(s in ('..', '.') for s in relative.split('/')):
        raise ValueError(f'unsafe relative path: {relative}')
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f'path escapes root: {relative}')
    return target


def verify(args):
    manifest = read_json(args.manifest)
    entries = manifest.get('sources')
    if manifest.get('schema_version') != 1 or not isinstance(entries, list) or not entries:
        raise ValueError('manifest requires schema_version=1 and non-empty sources')
    failures, checked, seen, paths = [], 0, set(), set()
    for entry in entries:
        identifier, sha = entry['id'], entry['sha256']
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError('missing/duplicate source id')
        seen.add(identifier)
        if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{64}', sha):
            raise ValueError(f'invalid SHA256 for {identifier}')
        targets = [('snapshot', args.root, entry['snapshot'])]
        # Validate source path even when project files are not requested.
        contained(args.project_root or args.root, entry['source'])
        if args.project_root:
            targets.append(('source', args.project_root, entry['source']))
        for kind, root, relative in targets:
            target = contained(root, relative)
            key = (kind, str(target))
            if key in paths:
                raise ValueError(f'duplicate {kind} path: {relative}')
            paths.add(key)
            checked += 1
            if not target.is_file():
                failures.append({'id': identifier, 'kind': kind, 'reason': 'missing', 'path': relative})
            elif digest(target) != sha:
                failures.append({'id': identifier, 'kind': kind, 'reason': 'hash_mismatch', 'path': relative})
    return {'status': 'FAIL' if failures else 'PASS', 'evidence_kind': 'file_integrity_only',
            'checked_files': checked, 'failures': failures,
            'limitation': 'Does not establish authenticity, measurement correctness, or board state.'}


def specification(path):
    spec = read_json(path)
    if spec.get('schema_version') != 1 or spec.get('layout') != 'c_order_flat':
        raise ValueError('schema_version=1 and layout=c_order_flat required')
    tensors = spec.get('tensors')
    if not isinstance(tensors, dict) or not tensors:
        raise ValueError('non-empty tensors object required')
    result = {}
    for name, item in tensors.items():
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', name):
            raise ValueError(f'invalid tensor name: {name!r}')
        shape, dtype = item['shape'], item['dtype']
        if not isinstance(shape, list) or not shape or any(type(x) is not int or x <= 0 for x in shape):
            raise ValueError(f'invalid shape: {name}')
        match = re.fullmatch(r'(u?)int(8|16|32|64)', dtype)
        if not match:
            raise ValueError(f'unsupported integer dtype: {dtype}')
        unsigned, width = bool(match[1]), int(match[2])
        lo = 0 if unsigned else -(1 << (width - 1))
        hi = (1 << (width if unsigned else width - 1)) - 1
        result[name] = (math.prod(shape), lo, hi)
    return result


def scalar(text):
    if not isinstance(text, str) or not re.fullmatch(r'-?(0|[1-9][0-9]*)', text):
        raise ValueError(f'not a canonical decimal integer: {text!r}')
    return int(text)


def read_values(path, spec):
    values = {}
    counts = {name: 0 for name in spec}
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ['tensor', 'index', 'value']:
            raise ValueError('CSV header must be exactly tensor,index,value')
        for line, row in enumerate(reader, 2):
            if set(row) != {'tensor', 'index', 'value'} or any(v is None for v in row.values()):
                raise ValueError(f'invalid CSV fields at line {line}')
            name = row['tensor']
            if name not in spec:
                raise ValueError(f'unknown tensor at line {line}: {name}')
            idx, val = scalar(row['index']), scalar(row['value'])
            count, lo, hi = spec[name]
            if not 0 <= idx < count or not lo <= val <= hi:
                raise ValueError(f'index/value out of range at line {line}')
            key = (name, idx)
            if key in values:
                raise ValueError(f'duplicate index at line {line}: {key}')
            values[key] = val
            counts[name] += 1
    for name, (count, _, _) in spec.items():
        if counts[name] != count:
            raise ValueError(f'incomplete tensor {name}: got {counts[name]}, expected {count}')
    return values


def compare(args):
    spec = specification(args.schema)
    expected, actual = read_values(args.expected, spec), read_values(args.actual, spec)
    mismatch = 0
    first = []
    for key, value in expected.items():
        if actual[key] != value:
            mismatch += 1
            if len(first) < 10:
                first.append({'tensor': key[0], 'index': key[1], 'expected': value, 'actual': actual[key]})
    return {'status': 'FAIL' if mismatch else 'PASS', 'evidence_kind': 'normalized_integer_csv',
            'tensors': len(spec), 'elements': len(expected), 'mismatch_count': mismatch,
            'first_mismatches': first,
            'input_sha256': {k: digest(getattr(args, k)) for k in ('schema', 'expected', 'actual')},
            'limitation': 'Does not parse wire frames, compute an oracle, or prove classification accuracy.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    v = sub.add_parser('verify', help='Verify evidence snapshot and optional original source hashes')
    v.add_argument('--manifest', required=True)
    v.add_argument('--root', required=True)
    v.add_argument('--project-root')
    c = sub.add_parser('compare', help='Compare complete integer tensors under an explicit schema')
    c.add_argument('--schema', required=True)
    c.add_argument('--expected', required=True)
    c.add_argument('--actual', required=True)
    args = parser.parse_args()
    try:
        result = verify(args) if args.command == 'verify' else compare(args)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result = {'status': 'FAIL', 'reason': str(exc), 'evidence_kind': 'input_rejected'}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
