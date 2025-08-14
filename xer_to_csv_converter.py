import pandas as pd
import os
import re

def safe_float(v, d=0.0):
    try:
        return float(v) if v not in (None, '') else d
    except (ValueError, TypeError):
        return d

def find_col(headers, names):
    if not headers:
        return None
    for n in names:
        for h in headers:
            if h.lower() == n.lower():
                return h
    for n in names:
        for h in headers:
            if n.lower() in h.lower():
                return h
    return None

def process_project(tbl, out_dir, ident):
    if not tbl or not tbl.get('rows'):
        return
    r = tbl['rows'][0]
    pid = find_col(tbl['headers'], ['proj_id'])
    pname = find_col(tbl['headers'], ['proj_short_name', 'name'])
    mfb = find_col(tbl['headers'], ['scd_end_date', 'must_finish_by_date'])
    nd = find_col(tbl['headers'], ['next_data_date'])
    ls = find_col(tbl['headers'], ['last_schedule_date'])
    data = {
        'Id': r.get(pid, 'N/A') if pid else 'N/A',
        'Name': r.get(pname, 'N/A') if pname else 'N/A',
        'MustFinishByDate': r.get(mfb, '') if mfb else ''
    }
    pd.DataFrame([data]).to_csv(os.path.join(out_dir, f'{ident}_project.csv'), index=False)
    datadate = ''
    if nd and r.get(nd):
        datadate = r.get(nd)
    elif ls and r.get(ls):
        datadate = r.get(ls)
    with open(os.path.join(out_dir, f'{ident}_datadate.txt'), 'w') as f:
        f.write(datadate or '')

def parse_hours_from_clndr_data(clndr_data: str) -> float:
    if not clndr_data:
        return 8.0
    try:
        clean = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clndr_data)
        start = clean.find('DaysOfWeek')
        end = clean.find('VIEW(')
        segment = clean[start:end] if start != -1 and end != -1 else clean
        pattern = re.compile(r's\|(\d{2}):(\d{2})\|f\|(\d{2}):(\d{2})')
        matches = list(pattern.finditer(segment))
        if not matches:
            return 8.0

        total_hours = 0.0
        for m in matches:
            h1, m1, h2, m2 = map(int, m.groups())
            hours = (h2 + m2 / 60) - (h1 + m1 / 60)
            if hours > 0:
                total_hours += hours

        # Estimate days as half the number of work-period segments (2 segments ≈ 1 working day)
        day_count = max(1, round(len(matches) / 2))
        return total_hours / day_count
    except Exception:
        return 8.0

def build_calendar_hours_map(calendar_tbl) -> dict:
    if not calendar_tbl or not calendar_tbl.get('rows'):
        return {}
    hc = calendar_tbl['headers'] or []
    cid_col = find_col(hc, ['clndr_id'])
    data_col = find_col(hc, ['clndr_data'])
    if not cid_col or not data_col:
        return {}
    out = {}
    for r in calendar_tbl['rows']:
        cid = r.get(cid_col)
        hpd = parse_hours_from_clndr_data(r.get(data_col, ''))
        try:
            out[int(cid)] = hpd
        except (ValueError, TypeError):
            out[cid] = hpd
    return out

def process_task(tbl, cal_hours):
    if not tbl['rows'] or not tbl['headers']:
        return pd.DataFrame()
    hc = tbl['headers']
    c_task_code = find_col(hc, ['task_code'])
    c_task_id = find_col(hc, ['task_id'])
    c_task_name = find_col(hc, ['task_name'])
    c_status = find_col(hc, ['status_code'])
    c_type = find_col(hc, ['task_type'])
    c_dur_type = find_col(hc, ['duration_type'])
    c_tar_dur = find_col(hc, ['target_drtn_hr_cnt'])
    c_act_work = find_col(hc, ['act_work_qty'])
    c_act_start = find_col(hc, ['act_start_date'])
    c_act_end = find_col(hc, ['act_end_date'])
    c_remain = find_col(hc, ['remain_drtn_hr_cnt'])
    c_pct = find_col(hc, ['phys_complete_pct'])
    c_clndr = find_col(hc, ['clndr_id'])
    c_es = find_col(hc, ['early_start_date'])
    c_ef = find_col(hc, ['early_end_date'])
    c_ts = find_col(hc, ['target_start_date'])
    c_tf = find_col(hc, ['target_end_date'])
    c_cstr = find_col(hc, ['cstr_type'])
    c_cdate = find_col(hc, ['cstr_date'])
    c_tflo = find_col(hc, ['total_float_hr_cnt'])
    out = []
    for r in tbl['rows']:
        sc = (r.get(c_status, '') if c_status else '')
        if sc == 'TK_NotStart': s = 'Not Started'
        elif sc == 'TK_Active': s = 'In Progress'
        elif sc == 'TK_Complete': s = 'Completed'
        else: s = 'Unknown'
        tt = (r.get(c_type, '') if c_type else '')
        dt = (r.get(c_dur_type, '') if c_dur_type else '')
        td = safe_float(r.get(c_tar_dur, 0) if c_tar_dur else 0)
        if tt == 'TT_Task': at = 'Task Dependent'
        elif tt == 'TT_LOE': at = 'Level of Effort'
        elif tt == 'TT_Mile': at = 'Start Milestone'
        elif td == 0 and s == 'Completed': at = 'Finish Milestone'
        else: at = tt
        ct = (r.get(c_cstr, '') if c_cstr else '')
        if ct in ('CS_MSO', 'CS_MSOA'): ctype = 'Start On'
        elif ct in ('CS_MEO', 'CS_MEOB'): ctype = 'Finish On'
        else: ctype = ct
        aw = safe_float(r.get(c_act_work, 0) if c_act_work else 0)
        asd = (r.get(c_act_start, '') if c_act_start else '')
        afd = (r.get(c_act_end, '') if c_act_end else '')
        rd = safe_float(r.get(c_remain, 0) if c_remain else 0)
        hpd = 8.0
        if c_clndr:
            hpd = cal_hours.get(safe_float(r.get(c_clndr)), cal_hours.get(r.get(c_clndr), 8.0))
        if aw > 0: ad = aw
        elif asd and afd: ad = 0
        elif td > 0 and rd > 0: ad = td - rd
        else: ad = 0
        pc = safe_float(r.get(c_pct, 0) if c_pct else 0) / 100.0
        rs = r.get(c_es, '') if c_es and r.get(c_es) else (r.get(c_ts, '') if c_ts else '')
        rf = r.get(c_ef, '') if c_ef and r.get(c_ef) else (r.get(c_tf, '') if c_tf else '')
        out.append({
            'task_code': r.get(c_task_code, '') if c_task_code else '',
            'ObjectId': r.get(c_task_id, '') if c_task_id else '',
            'task_name': r.get(c_task_name, '') if c_task_name else '',
            'status': s,
            'activity_type': at,
            'planned_duration_hours': td,
            'planned_duration_days': td / hpd if hpd else 0,
            'actual_duration_hours': ad,
            'actual_duration_days': ad / hpd if hpd else 0,
            'remaining_duration_hours': rd,
            'remaining_duration_days': rd / hpd if hpd else 0,
            'percent_complete': pc,
            'raw_start_date': rs,
            'raw_finish_date': rf,
            'raw_actual_start': asd,
            'raw_actual_finish': afd,
            'ConstraintType': ctype,
            'ConstraintDate': r.get(c_cdate, '') if c_cdate else '',
            'TotalFloat': safe_float(r.get(c_tflo, 0) if c_tflo else 0),
            'TotalFloatDays': (safe_float(r.get(c_tflo, 0) if c_tflo else 0) / hpd) if hpd else 0,
            'hours_per_day': hpd
        })
    return pd.DataFrame(out)

def process_taskpred(tbl, cal_hours, task_to_clndr):
    if not tbl['rows'] or not tbl['headers']:
        return pd.DataFrame()
    hc = tbl['headers']
    c_pred = find_col(hc, ['pred_task_id'])
    c_succ = find_col(hc, ['succ_task_id', 'task_id'])
    c_type = find_col(hc, ['pred_type'])
    c_lag = find_col(hc, ['lag_hr_cnt'])
    if not c_pred or not c_succ or not c_type:
        if len(hc) >= 7:
            c_succ = c_succ or hc[1]
            c_pred = c_pred or hc[2]
            c_type = c_type or hc[5]
            c_lag = c_lag or hc[6]
    out = []
    for r in tbl['rows']:
        t = (r.get(c_type, '') if c_type else '')
        if t == 'PR_FS': typ = 'Finish to Start'
        elif t == 'PR_SS': typ = 'Start to Start'
        elif t == 'PR_FF': typ = 'Finish to Finish'
        elif t == 'PR_SF': typ = 'Start to Finish'
        else: typ = 'Finish to Start'
        lag = safe_float(r.get(c_lag, 0) if c_lag else 0)
        pred = r.get(c_pred, '') if c_pred else ''
        succ = r.get(c_succ, '') if c_succ else ''
        succ_clndr = task_to_clndr.get(succ)
        pred_clndr = task_to_clndr.get(pred)
        hpd = cal_hours.get(safe_float(succ_clndr), cal_hours.get(safe_float(pred_clndr), 8.0))
        lag_days = lag / hpd if hpd else 0
        if pred and succ:
            out.append({
                'PredecessorActivityObjectId': pred,
                'SuccessorActivityObjectId': succ,
                'Type': typ,
                'Lag': lag,
                'LagDays': lag_days
            })
    return pd.DataFrame(out)

def convert_xer_to_csv(file_path, output_folder, file_identifier):
    try:
        os.makedirs(output_folder, exist_ok=True)
        tables = {}
        curr = None
        headers = None
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.rstrip('\n\r')
                if not line:
                    continue
                if line.startswith('%T\t'):
                    curr = line.split('\t', 1)[1]
                    tables[curr] = {'headers': None, 'rows': []}
                elif line.startswith('%F\t'):
                    headers = line.split('\t')[1:]
                    if curr:
                        tables[curr]['headers'] = headers
                elif line.startswith('%R\t'):
                    if curr and headers:
                        data = line.split('\t')[1:]
                        if len(data) > len(headers):
                            data = data[:len(headers)]
                        elif len(data) < len(headers):
                            data += [''] * (len(headers) - len(data))
                        tables[curr]['rows'].append(dict(zip(headers, data)))
                elif line.startswith('%E'):
                    curr = None
                    headers = None
        proj = tables.get('PROJECT', {'headers': [], 'rows': []})
        task = tables.get('TASK', {'headers': [], 'rows': []})
        cal_tbl = tables.get('CALENDAR', {'headers': [], 'rows': []})
        pred = tables.get('TASKPRED', {'headers': [], 'rows': []})
        cal_hours = build_calendar_hours_map(cal_tbl)
        task_headers = task.get('headers', [])
        tid_col = find_col(task_headers, ['task_id'])
        tclndr_col = find_col(task_headers, ['clndr_id'])
        task_to_clndr = {r.get(tid_col): r.get(tclndr_col) for r in task.get('rows', []) if tid_col and tclndr_col}
        process_project(proj, output_folder, file_identifier)
        adf = process_task(task, cal_hours)
        rdf = process_taskpred(pred, cal_hours, task_to_clndr)
        if not adf.empty:
            adf.to_csv(os.path.join(output_folder, f'{file_identifier}_activities.csv'), index=False)
        if not rdf.empty:
            rdf.to_csv(os.path.join(output_folder, f'{file_identifier}_relationships.csv'), index=False)
        return True
    except Exception as e:
        print(f"Error during XER to CSV conversion: {e}")
        return False
