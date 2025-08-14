import pandas as pd

def find_changes(target_data, update_data, date_format):
    target_activities = target_data.get('activities', pd.DataFrame()).copy()
    update_activities = update_data.get('activities', pd.DataFrame()).copy()
    target_expenses = target_data.get('expenses', pd.DataFrame()).copy()
    update_expenses = update_data.get('expenses', pd.DataFrame()).copy()

    # --- Basic Comparison ---
    target_ids = set(target_activities.index)
    update_ids = set(update_activities.index)
    added_ids = list(update_ids - target_ids)
    deleted_ids = list(target_ids - update_ids)
    common_ids = list(target_ids.intersection(update_ids))
    
    added_tasks = update_activities.loc[added_ids] if added_ids else pd.DataFrame()
    deleted_tasks = target_activities.loc[deleted_ids] if deleted_ids else pd.DataFrame()

    if not added_tasks.empty:
        added_tasks = added_tasks.sort_values(by='start_date').reset_index()
        added_tasks['start_date'] = pd.to_datetime(added_tasks['start_date']).dt.strftime(date_format)
        added_tasks['finish_date'] = pd.to_datetime(added_tasks['finish_date']).dt.strftime(date_format)
        added_tasks = added_tasks.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name', 'start_date': 'Start Date', 'finish_date': 'Finish Date'})
    if not deleted_tasks.empty:
        deleted_tasks = deleted_tasks.sort_values(by='start_date').reset_index()
        deleted_tasks['start_date'] = pd.to_datetime(deleted_tasks['start_date']).dt.strftime(date_format)
        deleted_tasks['finish_date'] = pd.to_datetime(deleted_tasks['finish_date']).dt.strftime(date_format)
        deleted_tasks = deleted_tasks.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name', 'start_date': 'Start Date', 'finish_date': 'Finish Date'})

    # --- Field-by-Field & Specialized Checks ---
    changes = { "Name Changes": [], "Activities with Modified Original Durations": [], "Start Date Changes": [], "Finish Date Changes": [], "Status Changes": [], "Percent Complete Changes": [] }
    stalled_activities_data = []
    
    target_actual_totals, update_actual_totals = pd.Series(dtype='float64'), pd.Series(dtype='float64')
    if not target_expenses.empty and 'ActualCost' in target_expenses.columns:
        target_act_with_obj = target_activities[['ObjectId']].reset_index()
        target_expenses_linked = pd.merge(target_expenses, target_act_with_obj, left_on='ActivityObjectId', right_on='ObjectId', how='left').set_index('task_code')
        target_actual_totals = target_expenses_linked.groupby('task_code')['ActualCost'].sum()
    if not update_expenses.empty and 'ActualCost' in update_expenses.columns:
        update_act_with_obj = update_activities[['ObjectId']].reset_index()
        update_expenses_linked = pd.merge(update_expenses, update_act_with_obj, left_on='ActivityObjectId', right_on='ObjectId', how='left').set_index('task_code')
        update_actual_totals = update_expenses_linked.groupby('task_code')['ActualCost'].sum()

    if common_ids:
        for task_id in common_ids:
            target_task, update_task = target_activities.loc[task_id], update_activities.loc[task_id]
            if target_task.get('status') == 'In Progress' and update_task.get('status') == 'In Progress':
                target_cost = target_actual_totals.get(task_id, 0); update_cost = update_actual_totals.get(task_id, 0)
                if target_task.get('percent_complete') == update_task.get('percent_complete') and target_cost == update_cost:
                    stalled_activities_data.append((task_id, update_task.get('task_name'), update_task.get('percent_complete')))
            if target_task.get('task_name') != update_task.get('task_name'):
                changes["Name Changes"].append((task_id, update_task.get('task_name'), target_task.get('task_name'), update_task.get('task_name')))
            if target_task.get('planned_duration_hours') != update_task.get('planned_duration_hours'):
                changes["Activities with Modified Original Durations"].append((task_id, update_task.get('task_name'), target_task.get('planned_duration_hours'), update_task.get('planned_duration_hours')))
            if target_task.get('start_date') != update_task.get('start_date'):
                changes["Start Date Changes"].append((task_id, update_task.get('task_name'), target_task.get('start_date'), update_task.get('start_date')))
            if target_task.get('finish_date') != update_task.get('finish_date'):
                changes["Finish Date Changes"].append((task_id, update_task.get('task_name'), target_task.get('finish_date'), update_task.get('finish_date')))
            if target_task.get('status') != update_task.get('status'):
                changes["Status Changes"].append((task_id, update_task.get('task_name'), target_task.get('status'), update_task.get('status')))
            if target_task.get('percent_complete') != update_task.get('percent_complete'):
                changes["Percent Complete Changes"].append((task_id, update_task.get('task_name'), target_task.get('percent_complete'), update_task.get('percent_complete')))
    
    stalled_df = pd.DataFrame(stalled_activities_data, columns=['Activity ID', 'Activity Name', '% Complete'])
    if not stalled_df.empty:
        stalled_df['% Complete'] = (stalled_df['% Complete'] * 100).map('{:.0f}%'.format)
    
    no_cost_increase_report = check_no_cost_increase(target_activities, update_activities, target_expenses, update_expenses)
    added_fractional_durations = check_added_fractional_durations(added_tasks)
    modified_fractional_durations = check_modified_fractional_durations(target_activities, update_activities)

    name_changes_df = pd.DataFrame(changes["Name Changes"], columns=['Activity ID', 'Activity Name', 'Target Name', 'Update Name'])
    duration_changes_df = pd.DataFrame(changes["Activities with Modified Original Durations"], columns=['Activity ID', 'Activity Name', 'Target (h)', 'Update (h)'])
    start_date_changes_df = pd.DataFrame(changes["Start Date Changes"], columns=['Activity ID', 'Activity Name', 'Target Start', 'Update Start']).sort_values(by='Update Start', ignore_index=True)
    finish_date_changes_df = pd.DataFrame(changes["Finish Date Changes"], columns=['Activity ID', 'Activity Name', 'Target Finish', 'Update Finish']).sort_values(by='Update Finish', ignore_index=True)
    status_changes_df = pd.DataFrame(changes["Status Changes"], columns=['Activity ID', 'Activity Name', 'Target Status', 'Update Status'])
    percent_changes_df = pd.DataFrame(changes["Percent Complete Changes"], columns=['Activity ID', 'Activity Name', 'Target %', 'Update %'])

    if not start_date_changes_df.empty:
        start_date_changes_df['Target Start'] = pd.to_datetime(start_date_changes_df['Target Start']).dt.strftime(date_format)
        start_date_changes_df['Update Start'] = pd.to_datetime(start_date_changes_df['Update Start']).dt.strftime(date_format)
    if not finish_date_changes_df.empty:
        finish_date_changes_df['Target Finish'] = pd.to_datetime(finish_date_changes_df['Target Finish']).dt.strftime(date_format)
        finish_date_changes_df['Update Finish'] = pd.to_datetime(finish_date_changes_df['Update Finish']).dt.strftime(date_format)
    if not percent_changes_df.empty:
        percent_changes_df['Target %'] = (percent_changes_df['Target %'] * 100).map('{:.0f}%'.format)
        percent_changes_df['Update %'] = (percent_changes_df['Update %'] * 100).map('{:.0f}%'.format)

    return {
        "Must Finish By Date Set": {"df": check_must_finish_by_date(target_data, update_data), "status": "⚠️"},
        "Added Tasks": {"df": added_tasks, "status": "✅"},
        "Deleted Tasks": {"df": deleted_tasks, "status": "✅"},
        "Added Activities with Fractional Durations": {"df": added_fractional_durations, "status": "⚠️"},
        "Duration Changes to Fractional Values": {"df": modified_fractional_durations, "status": "⚠️"},
        "Active Activities with No Progress": {"df": stalled_df, "status": "⚠️"},
        "In-Progress Activities >30d with No $ Increase": {"df": no_cost_increase_report, "status": "⚠️"},
        "Name Changes": {"df": name_changes_df, "status": "✅"},
        "Activities with Modified Original Durations": {"df": duration_changes_df, "status": "✅"},
        "Start Date Changes": {"df": start_date_changes_df, "status": "✅"},
        "Finish Date Changes": {"df": finish_date_changes_df, "status": "✅"},
        "Status Changes": {"df": status_changes_df, "status": "✅"},
        "Percent Complete Changes": {"df": percent_changes_df, "status": "✅"}
    }

def check_added_fractional_durations(added_tasks):
    if added_tasks.empty:
        return pd.DataFrame()
    fractional = added_tasks[added_tasks['planned_duration_hours'] % 1 != 0].copy()
    if fractional.empty:
        return pd.DataFrame()
    report = fractional[['Activity ID', 'Activity Name', 'planned_duration_hours']]
    return report.rename(columns={'planned_duration_hours': 'Planned Duration (h)'})

def check_modified_fractional_durations(target_activities, update_activities):
    common_ids = list(target_activities.index.intersection(update_activities.index))
    if not common_ids:
        return pd.DataFrame()
    
    target_common = target_activities.loc[common_ids]
    update_common = update_activities.loc[common_ids]
    
    modified = update_common[
        (update_common['planned_duration_hours'] != target_common['planned_duration_hours']) &
        (update_common['planned_duration_hours'] % 1 != 0)
    ]
    
    if modified.empty:
        return pd.DataFrame()
        
    report_data = {
        'Activity ID': modified.index,
        'Activity Name': modified['task_name'],
        'Target Duration (h)': target_common.loc[modified.index]['planned_duration_hours'],
        'Update Duration (h)': modified['planned_duration_hours']
    }
    
    return pd.DataFrame(report_data)

def check_no_cost_increase(target_activities, update_activities, target_expenses, update_expenses):
    duration_threshold_hours = 30 * 8 
    target_activities_filtered = update_activities[
        (update_activities['activity_type'] == 'Task Dependent') &
        (update_activities['actual_duration_hours'] > duration_threshold_hours) &
        (update_activities['status'] == 'In Progress')
    ]
    if target_activities_filtered.empty: return pd.DataFrame()

    target_actual_totals, update_actual_totals = pd.Series(dtype='float64'), pd.Series(dtype='float64')
    if not target_expenses.empty and 'ActualCost' in target_expenses.columns:
        target_act_with_obj = target_activities[['ObjectId']].reset_index()
        target_expenses_linked = pd.merge(target_expenses, target_act_with_obj, left_on='ActivityObjectId', right_on='ObjectId', how='left').set_index('task_code')
        target_actual_totals = target_expenses_linked.groupby('task_code')['ActualCost'].sum()
    if not update_expenses.empty and 'ActualCost' in update_expenses.columns:
        update_act_with_obj = update_activities[['ObjectId']].reset_index()
        update_expenses_linked = pd.merge(update_expenses, update_act_with_obj, left_on='ActivityObjectId', right_on='ObjectId', how='left').set_index('task_code')
        update_actual_totals = update_expenses_linked.groupby('task_code')['ActualCost'].sum()
        
    report_data = []
    for task_code, activity in target_activities_filtered.iterrows():
        target_cost = target_actual_totals.get(task_code, 0)
        update_cost = update_actual_totals.get(task_code, 0)
        if update_cost <= target_cost:
            report_data.append({
                'Activity ID': task_code,
                'Activity Name': activity['task_name'],
                'Actual Duration (h)': activity['actual_duration_hours'],
                'Previous Cost': f"${target_cost:,.2f}",
                'Current Cost': f"${update_cost:,.2f}"
            })
    return pd.DataFrame(report_data)

def check_must_finish_by_date(target_data, update_data):
    target_project = target_data.get('project', {})
    update_project = update_data.get('project', {})
    findings = []

    if pd.notna(target_project.get('MustFinishByDate')):
        findings.append({'File': 'Target Schedule', 'Field': 'Must Finish By Date', 'Value': target_project['MustFinishByDate']})
    
    if pd.notna(update_project.get('MustFinishByDate')):
        findings.append({'File': 'Update Schedule', 'Field': 'Must Finish By Date', 'Value': update_project['MustFinishByDate']})

    return pd.DataFrame(findings)