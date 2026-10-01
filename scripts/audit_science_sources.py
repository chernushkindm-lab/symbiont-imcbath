"""Inspect supplied scientific source files without executing notebook/script code.

Usage: python scripts/audit_science_sources.py PATH_TO_METHODS_FOLDER
Prints only hashes, notebook metadata, selected constants and code issue locators.
"""
import ast
import hashlib
import json
from pathlib import Path
import sys


def main(directory):
    folder = Path(directory)
    names = ['Kinetics.ipynb', 'kla OTR ФА-10 (2).docx',
             'SYMBIONT_Exhaust_Soft_Sensor_Report.pdf', 'Mass_balance_with_medium_analytics.py',
             'FINAL_MASS_BALANCE_WITH_FULL_STATISTICS_14-06.py']
    manifest = []
    for name in names:
        path = folder / name
        if not path.is_file():
            manifest.append({'name': name, 'access': 'missing'})
            continue
        manifest.append({'name': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'bytes': path.stat().st_size, 'access': 'read', 'executed': False})
    notebook_path = folder / 'Kinetics.ipynb'
    variants = []
    if notebook_path.is_file():
        notebook = json.loads(notebook_path.read_text(encoding='utf-8-sig'))
        for index, cell in enumerate(notebook['cells']):
            source = ''.join(cell.get('source', []))
            if cell.get('cell_type') != 'code' or not source.strip():
                continue
            constants, syntax_error = {}, None
            try:
                tree = ast.parse(source)
                for node in tree.body:
                    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                        key = node.targets[0].id
                        if key in {'V_reactor', 'D', 'mu_max', 'kLa_1atm', 'L_per_mol'}:
                            try:
                                constants[key] = ast.literal_eval(node.value)
                            except (ValueError, TypeError):
                                constants[key] = '<expression>'
            except SyntaxError as error:
                syntax_error = str(error)
            variants.append({'cell_index': index, 'execution_count': cell.get('execution_count'),
                             'lines': len(source.splitlines()), 'selected_constants': constants,
                             'syntax_error': syntax_error})
    issues = []
    for name in names[-2:]:
        path = folder / name
        if path.is_file():
            for index, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
                for marker, category in [('f_acc =', 'inventory_dimension'), ('.ffill()', 'unbounded_forward_fill'),
                                         ('.fillna(0)', 'missing_to_zero'), ("'nearest'", 'future_assay_join'),
                                         ('.interpolate(', 'interpolation_without_event_gate')]:
                    if marker in line:
                        issues.append({'filename': name, 'line': index, 'category': category})
    print(json.dumps({'sources': manifest, 'notebook_variants': variants, 'script_issue_locators': issues,
                      'status': 'text_audit_only', 'source_code_executed': False}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: audit_science_sources.py METHODS_DIRECTORY')
    main(sys.argv[1])
