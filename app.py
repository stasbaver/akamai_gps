from flask import Flask, render_template, send_file, abort, Response, request, session, send_from_directory, jsonify

import os
from datetime import datetime
import time
import re
import json

from run_tests import run_tests_bp

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

app.register_blueprint(run_tests_bp)

def regex_replace(value, pattern, replacement):
    return re.sub(pattern, replacement, str(value))

app.jinja_env.filters['regex_replace'] = regex_replace

BASE_DIR = "/data/gps/xml/sbover/SQA/suites/ew/k6_tests/regression_suite/regression2.0"
CONSOLE_FILE = "/data/gps/xml/sbover/SQA/suites/ew/k6_tests/regression_suite/web_app_full_browser/test_console/test.out"
STATUS_FILE = "/data/gps/xml/sbover/SQA/suites/ew/k6_tests/regression_suite/scripts/is_running.txt"
REPORT_FILE = os.path.join(BASE_DIR, "tmp_dynamic_report.html")  # Define report file path

KPIS = [
    '% from origin',
    'Average - r74 CPU flytes',
    'Average high-precision turn-around-time',
    'Average Python Flits:',
    'Average r5 Turnaround time:'
]

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/console')
def console():
    if not os.path.exists(CONSOLE_FILE) or not os.access(CONSOLE_FILE, os.R_OK):
        return "Console file not accessible", 404
    with open(CONSOLE_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    return content, 200, {'Content-Type': 'text/plain'}

@app.route('/console-stream')
def console_stream():
    def generate():
        last_mod_time = 0
        last_content = ''
        while True:
            if os.path.exists(CONSOLE_FILE) and os.access(CONSOLE_FILE, os.R_OK):
                mod_time = os.path.getmtime(CONSOLE_FILE)
                if mod_time != last_mod_time:
                    with open(CONSOLE_FILE, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if content != last_content:
                        yield f"data: {content}\n\n"
                        last_content = content
                    last_mod_time = mod_time
            else:
                yield "data: Console file not found\n\n"
            time.sleep(0.1)
    return Response(generate(), mimetype='text/event-stream')

@app.route('/status')
def status():
    if not os.path.exists(STATUS_FILE) or not os.access(STATUS_FILE, os.R_OK):
        return "Console file not accessible", 404
    with open(STATUS_FILE, 'r', encoding='utf-8') as f:
        content = f.read().strip().lower()
    return content, 200, {'Content-Type': 'text/plain'}

@app.route('/compare', methods=['GET'])
def compare():
    dir_path = request.args.get('dir', '')
    full_path = os.path.normpath(os.path.join(BASE_DIR, dir_path))
    if not os.path.exists(full_path) or not full_path.startswith(os.path.realpath(BASE_DIR)):
        abort(404)
    tests = {}
    for item in sorted(os.listdir(full_path)):
        item_path = os.path.join(full_path, item)
        if os.path.isfile(item_path) and item.lower().startswith('https') and '.js' in item:
            test_name = item.split('.js')[0]
            if test_name not in tests:
                tests[test_name] = []
            with open(item_path, 'r', encoding='utf-8') as f:
                content = f.read()
            metrics = {}
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith(('‾', '/', '✓', '✗', '↳', '(', 'no ghost rolls')):
                    if '=' in line:
                        key, value = [part.strip() for part in line.split('=', 1)]
                    elif ':' in line:
                        key, value = [part.strip() for part in line.split(':', 1)]
                    else:
                        continue
                    for kpi in KPIS:
                        if key.lower() == kpi.lower():
                            if value == 'NA' or re.match(r'^-?\d*\.?\d+$', value):
                                metrics[kpi] = value
                            break
            tests[test_name].append({'name': item, 'metrics': metrics})
    return render_template('compare.html', dir=dir_path, tests=tests, kpis=KPIS)

@app.route('/detailed_results', methods=['GET'])
def detailed_results():
    dir_path = request.args.get('dir', '')
    full_path = os.path.normpath(os.path.join(BASE_DIR, dir_path))
    if not os.path.exists(full_path) or not full_path.startswith(os.path.realpath(BASE_DIR)):
        abort(404)
    result_files = []
    for item in sorted(os.listdir(full_path)):
        item_path = os.path.join(full_path, item)
        if os.path.isfile(item_path) and item.lower().startswith('result'):
            with open(item_path, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            header1 = lines[0] if lines else ''
            header2 = lines[1] if len(lines) > 1 else ''
            table_data = lines[2:] if len(lines) > 2 else []
            if table_data and all(len(line.split()) == 1 for line in table_data):
                values = [line for line in table_data]
            else:
                values = [line.split() for line in table_data]
            result_files.append({
                'filename': item,
                'header1': header1,
                'header2': header2,
                'content': values
            })
    return render_template('detailed_results.html', dir=dir_path, result_files=result_files)

@app.route('/compare_results', methods=['GET'])
def compare_results():
    dir1 = request.args.get('dir1', '')
    dir2 = request.args.get('dir2', '')
    full_path1 = os.path.normpath(os.path.join(BASE_DIR, dir1))
    full_path2 = os.path.normpath(os.path.join(BASE_DIR, dir2))
    if (not os.path.exists(full_path1) or not full_path1.startswith(os.path.realpath(BASE_DIR)) or
        not os.path.exists(full_path2) or not full_path2.startswith(os.path.realpath(BASE_DIR))):
        abort(404)
    results1 = {}
    results2 = {}
    for dir_path, results in [(full_path1, results1), (full_path2, results2)]:
        for item in sorted(os.listdir(dir_path)):
            item_path = os.path.join(dir_path, item)
            if os.path.isfile(item_path) and item.lower().startswith('result'):
                with open(item_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                if len(lines) > 2:
                    kpis = lines[2].split()
                    table_data = lines[3:] if len(lines) > 3 else []
                    sums = {kpi: 0 for kpi in kpis}
                    counts = {kpi: 0 for kpi in kpis}
                    for line in table_data:
                        values = line.split()
                        for i, (kpi, value) in enumerate(zip(kpis, values)):
                            cleaned_value = re.sub(r'[^0-9.]', '', value)
                            if cleaned_value.count('.') <= 1 and cleaned_value and cleaned_value != 'NA' and cleaned_value.replace('.', '').isdigit():
                                sums[kpi] += float(cleaned_value)
                                counts[kpi] += 1
                    averages = {kpi: f"{sums[kpi] / counts[kpi]:.2f}" if counts[kpi] > 0 else 'NA' for kpi in kpis}
                    results[item] = averages
    comparisons = []
    all_filenames = set(results1.keys()) | set(results2.keys())
    for filename in sorted(all_filenames):
        avg1 = results1.get(filename, {})
        avg2 = results2.get(filename, {})
        kpis = sorted(set(avg1.keys()) | set(avg2.keys())) if avg1 or avg2 else []
        if kpis:
            comparison = {'filename': filename, 'averages': []}
            for kpi in kpis:
                val1_str = avg1.get(kpi, 'NA')
                val2_str = avg2.get(kpi, 'NA')
                val1 = float(val1_str) if val1_str != 'NA' else 'NA'
                val2 = float(val2_str) if val2_str != 'NA' else 'NA'
                diff_pct = 'N/A'
                diff_exceeds_3pct = False
                if isinstance(val1, float) and isinstance(val2, float):
                    avg_val = (val1 + val2) / 2 if val1 + val2 != 0 else 1
                    diff = abs(val1 - val2) / avg_val * 100
                    diff_pct = f"{diff:.2f}"
                    diff_exceeds_3pct = diff > 3
                comparison['averages'].append({
                    'kpi': kpi,
                    'dir1': val1_str,
                    'dir2': val2_str,
                    'diff_pct': diff_pct,
                    'diff_exceeds_3pct': diff_exceeds_3pct
                })
            comparisons.append(comparison)
    return render_template('compare_results.html', dir1=dir1, dir2=dir2, comparisons=comparisons)

@app.route('/aggregate_results', methods=['GET'])
def aggregate_results():
    dir_path = request.args.get('dir', '')
    full_path = os.path.normpath(os.path.join(BASE_DIR, dir_path))
    if not os.path.exists(full_path) or not full_path.startswith(os.path.realpath(BASE_DIR)):
        abort(404)
    aggregated_data = []
    for item in sorted(os.listdir(full_path)):
        item_path = os.path.join(full_path, item)
        if os.path.isfile(item_path) and item.lower().startswith('result'):
            with open(item_path, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            if len(lines) > 2:
                test_data = {
                    'filename': item,
                    'header1': lines[0],
                    'header2': lines[1],
                    'kpis': lines[2].split(),
                    'iterations': []
                }
                for line in lines[3:]:
                    values = line.split()
                    iteration = {
                        kpi: float(re.sub(r'[^0-9.]', '', v)) if v and v != 'NA' and v.count('.') <= 1 and re.sub(r'[^0-9.]', '', v).replace('.', '').isdigit() else 'NA'
                        for kpi, v in zip(test_data['kpis'], values)
                    }
                    test_data['iterations'].append(iteration)
                aggregated_data.append(test_data)
    parent_dir_name = os.path.basename(os.path.dirname(full_path))
    output_file = os.path.join(full_path, f'JSON_{parent_dir_name}.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(aggregated_data, f, indent=4)
    return f"JSON file saved as {output_file}", 200

@app.route('/browser', methods=['GET', 'POST'])
@app.route('/browser/<path:subpath>', methods=['GET', 'POST'])
def browse(subpath=""):
    full_path = os.path.normpath(os.path.join(BASE_DIR, subpath))
    if not os.path.exists(full_path) or not full_path.startswith(os.path.realpath(BASE_DIR)):
        abort(404)
    if request.method == 'POST':
        action = request.form.get('action')
        file_path = request.form.get('file')
        if file_path:
            selected_json_files = session.get('selected_json_files', [])
            if action == 'select' and file_path not in selected_json_files and len(selected_json_files) < 2:
                selected_json_files.append(file_path)
            elif action == 'deselect' and file_path in selected_json_files:
                selected_json_files.remove(file_path)
            session['selected_json_files'] = selected_json_files
    if os.path.isdir(full_path):
        dirs = []
        files = []
        selected_json_files = session.get('selected_json_files', [])
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            mod_time = os.path.getmtime(item_path)
            rel_path = os.path.join(subpath, item) if subpath else item
            entry = {
                'name': item,
                'is_dir': os.path.isdir(item_path),
                'path': os.path.join('browser', subpath, item) if subpath else os.path.join('browser', item),
                'mod_time': datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S'),
                'rel_path': rel_path,
                'selected': rel_path in selected_json_files
            }
            if entry['is_dir']:
                dirs.append(entry)
            else:
                files.append(entry)
        dirs.sort(key=lambda x: x['mod_time'], reverse=True)
        files.sort(key=lambda x: x['mod_time'], reverse=True)
        if not subpath:
            parent_path = 'browser'
        else:
            parent_parts = subpath.split('/')
            if len(parent_parts) == 1:
                parent_path = 'browser'
            else:
                parent_path = os.path.join('browser', '/'.join(parent_parts[:-1]))
        return render_template('browse.html', dirs=dirs, files=files, current_path=subpath, parent_path=parent_path, selected_json_files=selected_json_files)
    elif os.path.isfile(full_path):
        filename = os.path.basename(full_path)
        if filename.endswith('.png'):
            return send_file(full_path, mimetype='image/png')
        elif (filename.lower().startswith('https') or
              filename.endswith('.txt') or
              filename.endswith('.log') or
              filename.endswith('.res')):
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return render_template('text.html', content=content, filename=filename, is_table=False)
        elif filename.lower().startswith('result'):
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            header1 = lines[0] if lines else ''
            header2 = lines[1] if len(lines) > 1 else ''
            table_data = lines[2:] if len(lines) > 2 else []
            if table_data and all(len(line.split()) == 1 for line in table_data):
                values = [line for line in table_data]
            else:
                values = [line.split() for line in table_data]
            return render_template('text.html', header1=header1, header2=header2, content=values, filename=filename, is_table=True)
        elif filename.lower().startswith('json'):
            with open(full_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            return render_template('json_results.html', filename=filename, json_data=json_data)
        else:
            abort(415)

@app.route('/compare_json', methods=['GET'])
def compare_json():
    file1 = request.args.get('file1', '')
    file2 = request.args.get('file2', '')
    full_path1 = os.path.normpath(os.path.join(BASE_DIR, file1))
    full_path2 = os.path.normpath(os.path.join(BASE_DIR, file2))
    if (not os.path.exists(full_path1) or not full_path1.startswith(os.path.realpath(BASE_DIR)) or
        not os.path.exists(full_path2) or not full_path2.startswith(os.path.realpath(BASE_DIR)) or
        not os.path.basename(full_path1).lower().startswith('json') or
        not os.path.basename(full_path2).lower().startswith('json')):
        print(f"DEBUG: file1={full_path1}, exists={os.path.exists(full_path1)}, starts_with_BASE_DIR={full_path1.startswith(os.path.realpath(BASE_DIR))}, is_json={os.path.basename(full_path1).lower().startswith('json')}")
        print(f"DEBUG: file2={full_path2}, exists={os.path.exists(full_path2)}, starts_with_BASE_DIR={full_path2.startswith(os.path.realpath(BASE_DIR))}, is_json={os.path.basename(full_path2).lower().startswith('json')}")
        abort(404)
    try:
        with open(full_path1, 'r', encoding='utf-8') as f1:
            json_data1 = json.load(f1)
        with open(full_path2, 'r', encoding='utf-8') as f2:
            json_data2 = json.load(f2)
    except Exception as e:
        print(f"ERROR: Failed to load JSON files - {str(e)}")
        abort(500, f"Failed to load JSON files: {str(e)}")
    if not json_data1 or not json_data2:
        abort(400, "JSON files are empty or invalid")
    comparison_data = []
    for test1, test2 in zip(json_data1, json_data2):
        kpis = sorted(set(test1['kpis']) | set(test2['kpis']))
        test_comparison = {
            'filename1': test1['filename'],
            'filename2': test2['filename'],
            'kpi_data': {}
        }
        for kpi in kpis:
            values1 = [iter.get(kpi, 'NA') for iter in test1.get('iterations', [])]
            values2 = [iter.get(kpi, 'NA') for iter in test2.get('iterations', [])]
            valid1 = [v for v in values1 if v != 'NA']
            valid2 = [v for v in values2 if v != 'NA']
            avg1 = sum(valid1) / len(valid1) if valid1 else 0
            avg2 = sum(valid2) / len(valid2) if valid2 else 0
            cleanValues1 = [v for v in valid1 if v >= avg1 * 0.3 and v <= avg1 * 1.7]
            cleanValues2 = [v for v in valid2 if v >= avg2 * 0.3 and v <= avg2 * 1.7]
            cleanAvg1 = sum(cleanValues1) / len(cleanValues1) if cleanValues1 else 0
            cleanAvg2 = sum(cleanValues2) / len(cleanValues2) if cleanValues2 else 0
            diff_pct = abs(avg1 - avg2) / ((avg1 + avg2) / 2) * 100 if avg1 + avg2 != 0 else 'N/A'
            no_outlier_diff_pct = abs(cleanAvg1 - cleanAvg2) / ((cleanAvg1 + cleanAvg2) / 2) * 100 if cleanAvg1 + cleanAvg2 != 0 else 'N/A'
            test_comparison['kpi_data'][kpi] = {
                'avg1': avg1,
                'avg2': avg2,
                'diff_pct': diff_pct,
                'no_outlier_diff_pct': no_outlier_diff_pct,
                'values1': values1,
                'values2': values2
            }
        comparison_data.append(test_comparison)
    filename1 = os.path.basename(full_path1)
    filename2 = os.path.basename(full_path2)
    return render_template('compare_json.html', file1=filename1, file2=filename2, comparison_data=comparison_data)

@app.route('/interactive_compare_json', methods=['GET'])
def interactive_compare_json():
    file1 = request.args.get('file1', '')
    file2 = request.args.get('file2', '')
    full_path1 = os.path.normpath(os.path.join(BASE_DIR, file1))
    full_path2 = os.path.normpath(os.path.join(BASE_DIR, file2))
    if (not os.path.exists(full_path1) or not full_path1.startswith(os.path.realpath(BASE_DIR)) or
        not os.path.exists(full_path2) or not full_path2.startswith(os.path.realpath(BASE_DIR)) or
        not os.path.basename(full_path1).lower().startswith('json') or
        not os.path.basename(full_path2).lower().startswith('json')):
        print(f"DEBUG: file1={full_path1}, exists={os.path.exists(full_path1)}, starts_with_BASE_DIR={full_path1.startswith(os.path.realpath(BASE_DIR))}, is_json={os.path.basename(full_path1).lower().startswith('json')}")
        print(f"DEBUG: file2={full_path2}, exists={os.path.exists(full_path2)}, starts_with_BASE_DIR={full_path2.startswith(os.path.realpath(BASE_DIR))}, is_json={os.path.basename(full_path2).lower().startswith('json')}")
        abort(404)
    try:
        with open(full_path1, 'r', encoding='utf-8') as f1:
            json_data1 = json.load(f1)
        with open(full_path2, 'r', encoding='utf-8') as f2:
            json_data2 = json.load(f2)
    except Exception as e:
        print(f"ERROR: Failed to load JSON files - {str(e)}")
        abort(500, f"Failed to load JSON files: {str(e)}")
    if not json_data1 or not json_data2:
        abort(400, "JSON files are empty or invalid")

    # Convert JSONs to dictionaries keyed by filename
    tests1 = {test['filename']: test for test in json_data1}
    tests2 = {test['filename']: test for test in json_data2}

    # Identify common and unique filenames
    filenames1 = set(tests1.keys())
    filenames2 = set(tests2.keys())
    common_filenames = filenames1.intersection(filenames2)
    only_in_json1 = filenames1 - filenames2
    only_in_json2 = filenames2 - filenames1
    all_filenames = filenames1.union(filenames2)

    comparison_data = []
    for filename in sorted(all_filenames):
        test1 = tests1.get(filename)
        test2 = tests2.get(filename)
        # If test exists in both, compare them; otherwise, use placeholder
        if test1 and test2:
            kpis = sorted(set(test1['kpis']) | set(test2['kpis']))
            filename1 = test1['filename']
            filename2 = test2['filename']
        elif test1:
            kpis = test1['kpis']
            filename1 = test1['filename']
            filename2 = filename1  # Use same name for display consistency
        else:  # test2 only
            kpis = test2['kpis']
            filename1 = test2['filename']
            filename2 = test2['filename']

        test_comparison = {
            'filename1': filename1,
            'filename2': filename2,
            'kpi_data': {}
        }
        for kpi in kpis:
            values1 = [iter.get(kpi, 'NA') for iter in test1.get('iterations', [])] if test1 else []
            values2 = [iter.get(kpi, 'NA') for iter in test2.get('iterations', [])] if test2 else []
            # If one side is missing, fill with 'NA' to match length or leave empty
            if not values1:
                values1 = ['NA'] * len(values2) if values2 else []
            if not values2:
                values2 = ['NA'] * len(values1) if values1 else []

            valid1 = [v for v in values1 if v != 'NA']
            valid2 = [v for v in values2 if v != 'NA']
            avg1 = sum(valid1) / len(valid1) if valid1 else 0
            avg2 = sum(valid2) / len(valid2) if valid2 else 0
            cleanValues1 = [v for v in valid1 if v >= avg1 * 0.3 and v <= avg1 * 1.7] if valid1 else []
            cleanValues2 = [v for v in valid2 if v >= avg2 * 0.3 and v <= avg2 * 1.7] if valid2 else []
            cleanAvg1 = sum(cleanValues1) / len(cleanValues1) if cleanValues1 else 0
            cleanAvg2 = sum(cleanValues2) / len(cleanValues2) if cleanValues2 else 0
            diff_pct = abs(avg1 - avg2) / ((avg1 + avg2) / 2) * 100 if avg1 + avg2 != 0 else 'N/A'
            no_outlier_diff_pct = abs(cleanAvg1 - cleanAvg2) / ((cleanAvg1 + cleanAvg2) / 2) * 100 if cleanAvg1 + cleanAvg2 != 0 else 'N/A'
            test_comparison['kpi_data'][kpi] = {
                'avg1': avg1,
                'avg2': avg2,
                'diff_pct': diff_pct,
                'no_outlier_diff_pct': no_outlier_diff_pct,
                'values1': values1,
                'values2': values2,
                'included1': [True] * len(values1),
                'included2': [True] * len(values2)
            }
        comparison_data.append(test_comparison)

    filename1 = os.path.basename(full_path1)
    filename2 = os.path.basename(full_path2)
    return render_template('interactive_compare_json.html', file1=filename1, file2=filename2, comparison_data=comparison_data)

# New Route: Create Report
@app.route('/create_report', methods=['GET', 'POST'])
def create_report():
    file1 = request.args.get('file1', '') if request.method == 'GET' else request.form.get('file1', '')
    file2 = request.args.get('file2', '') if request.method == 'GET' else request.form.get('file2', '')
    full_path1 = os.path.normpath(os.path.join(BASE_DIR, file1))
    full_path2 = os.path.normpath(os.path.join(BASE_DIR, file2))
    if (not os.path.exists(full_path1) or not full_path1.startswith(os.path.realpath(BASE_DIR)) or
        not os.path.exists(full_path2) or not full_path2.startswith(os.path.realpath(BASE_DIR)) or
        not os.path.basename(full_path1).lower().startswith('json') or
        not os.path.basename(full_path2).lower().startswith('json')):
        abort(404)
    try:
        with open(full_path1, 'r', encoding='utf-8') as f1:
            json_data1 = json.load(f1)
        with open(full_path2, 'r', encoding='utf-8') as f2:
            json_data2 = json.load(f2)
    except Exception as e:
        abort(500, f"Failed to load JSON files: {str(e)}")
    if not json_data1 or not json_data2:
        abort(400, "JSON files are empty or invalid")
    comparison_data = []
    for test1, test2 in zip(json_data1, json_data2):
        kpis = sorted(set(test1['kpis']) | set(test2['kpis']))
        test_comparison = {
            'filename1': test1['filename'],
            'filename2': test2['filename'],
            'kpi_data': {}
        }
        for kpi in kpis:
            values1 = [iter.get(kpi, 'NA') for iter in test1.get('iterations', [])]
            values2 = [iter.get(kpi, 'NA') for iter in test2.get('iterations', [])]
            valid1 = [v for v in values1 if v != 'NA']
            valid2 = [v for v in values2 if v != 'NA']
            avg1 = sum(valid1) / len(valid1) if valid1 else 0
            avg2 = sum(valid2) / len(valid2) if valid2 else 0
            cleanValues1 = [v for v in valid1 if v >= avg1 * 0.3 and v <= avg1 * 1.7]
            cleanValues2 = [v for v in valid2 if v >= avg2 * 0.3 and v <= avg2 * 1.7]
            cleanAvg1 = sum(cleanValues1) / len(cleanValues1) if cleanValues1 else 0
            cleanAvg2 = sum(cleanValues2) / len(cleanValues2) if cleanValues2 else 0
            diff_pct = abs(avg1 - avg2) / ((avg1 + avg2) / 2) * 100 if avg1 + avg2 != 0 else 'N/A'
            no_outlier_diff_pct = abs(cleanAvg1 - cleanAvg2) / ((cleanAvg1 + cleanAvg2) / 2) * 100 if cleanAvg1 + cleanAvg2 != 0 else 'N/A'
            test_comparison['kpi_data'][kpi] = {
                'avg1': avg1,
                'avg2': avg2,
                'diff_pct': diff_pct,
                'no_outlier_diff_pct': no_outlier_diff_pct,
                'values1': values1,
                'values2': values2,
                'included1': [True] * len(values1),
                'included2': [True] * len(values2)
            }
        comparison_data.append(test_comparison)
    filename1 = os.path.basename(full_path1)
    filename2 = os.path.basename(full_path2)

    if request.method == 'POST':
        test_index = int(request.form.get('test_index', -1))
        if 0 <= test_index < len(comparison_data):
            report_content = session.get('report_content', [])
            test_data = {
                'file1': file1,  # Store full path
                'file2': file2,  # Store full path
                'test': comparison_data[test_index]
            }
            report_content.append(test_data)
            session['report_content'] = report_content
            with open(REPORT_FILE, 'a', encoding='utf-8') as f:
                f.write(f"<h2>{test_data['file1']} vs {test_data['file2']} - {test_data['test']['filename1']} vs {test_data['test']['filename2']}</h2>\n")
                f.write('<table border="1">\n<thead>\n<tr><th>KPI</th><th>Avg1</th><th>Avg2</th><th>Diff (%)</th></tr>\n</thead>\n<tbody>\n')
                for kpi, data in test_data['test']['kpi_data'].items():
                    f.write(f"<tr><td>{kpi}</td><td>{data['avg1']:.2f}</td><td>{data['avg2']:.2f}</td><td>{data['diff_pct'] if data['diff_pct'] != 'N/A' else 'N/A'}</td></tr>\n")
                f.write('</tbody>\n</table>\n<br>\n')
        return jsonify({'status': 'success', 'test_added': test_index}), 200

    return render_template('create_report.html', file1=file1, file2=file2, comparison_data=comparison_data)


# New Route: Clear Report
@app.route('/clear_report', methods=['POST'])
def clear_report():
    session['report_content'] = []
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write('<!DOCTYPE html>\n<html>\n<head>\n<title>Dynamic Report</title>\n<style>\n')
        f.write('body { font-family: Arial, sans-serif; margin: 20px; }\ntable { border-collapse: collapse; width: 100%; margin-bottom: 20px; }\n')
        f.write('th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }\nth { background-color: #f2f2f2; }\n')
        f.write('</style>\n</head>\n<body>\n<h1>Dynamic Report</h1>\n')
        f.write('<!-- Report content will be appended here -->\n</body>\n</html>')
    return '', 204

@app.route('/download_report')
def download_report():
    file1 = request.args.get('file1', '')  # Optional: pass file1/file2 for context
    file2 = request.args.get('file2', '')
    filename = request.args.get('filename', 'report.html')
    if not os.path.exists(REPORT_FILE):
        abort(404, "No report file found.")

    # Read the report content
    with open(REPORT_FILE, 'r', encoding='utf-8') as f:
        report_content = f.read()

    # Create static HTML
    static_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Static Report - {file1} vs {file2}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        h1 {{ color: #333; text-align: center; border-bottom: 2px solid #2196F3; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background-color: #fafafa; }}
        th, td {{ border: 1px solid #ccc; padding: 10px; text-align: center; }}
        th {{ background-color: #e0e0e0; font-weight: bold; color: #333; }}
    </style>
</head>
<body>
    <h1>Static Report: {file1} vs {file2}</h1>
    {report_content}
</body>
</html>
"""
    return Response(static_html, mimetype='text/html', headers={'Content-Disposition': f'attachment; filename="{filename}"'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
