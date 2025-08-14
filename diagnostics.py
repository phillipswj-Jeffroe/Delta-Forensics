import pandas as pd
from datetime import timedelta

def run_all_checks(schedule_data, date_format):
    activities = schedule_data.get('activities', pd.DataFrame())
    relationships = schedule_data.get('relationships', pd.DataFrame())
    data_date = schedule_data.get('data_date')
    results = {}

    if pd.notna(data_date):
        results["Late Starts"] = {"df": check_late_starts(activities, data_date, date_format), "status": "✅"}
        riding_less, riding_more = check_riding_data_date(activities, relationships, data_date, date_format)
        results["Activities Riding Data Date < 30 Days"] = {"df": riding_less, "status": "✅"}
        results["Activities Riding Data Date > 30 Days"] = {"df": riding_more, "status": "✅"}
    
    results["In-Progress Activities with Zero Float"] = {"df": check_zero_float_activities(activities), "status": "⚠️"}
    results["Activities with Hard Constraints"] = {"df": check_hard_constraints(activities, date_format), "status": "✅"}
    results["Activities with Soft Constraints"] = {"df": check_soft_constraints(activities, date_format), "status": "✅"}
    results["Missing Actual Start Dates"] = {"df": check_missing_actual_starts(activities), "status": "✅"}
    results["Missing Actual Finish Dates"] = {"df": check_missing_actual_finishes(activities), "status": "✅"}
    results["Activities w/No Driving Predecessor"] = {"df": check_no_predecessors(activities, relationships, date_format), "status": "✅"}
    results["Activities w/No Driving Successor"] = {"df": check_no_successors(activities, relationships, date_format), "status": "✅"}
    results["Activities with Negative Lag"] = {"df": check_negative_lag(activities, relationships), "status": "✅"}
    results["Activities with Start-to-Finish Logic"] = {"df": check_start_to_finish_logic(activities, relationships), "status": "✅"}
    results["Activities with Zero Original Durations"] = {"df": check_zero_duration(activities), "status": "✅"}
    results["Activities > 30 Calendar Days"] = {"df": check_long_durations(activities), "status": "✅"}
    results["Duplicate Activity Names"] = {"df": check_duplicate_activity_names(activities), "status": "⚠️"}
        
    return results

def check_riding_data_date(activities, relationships, data_date, date_format):
    if activities.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Rule 2 & 3 (Corrected): Find "Not Started" activities with a StartDate equal to the DataDate (ignoring time)
    not_started = activities[activities['status'] == 'Not Started'].copy()
    riding_candidates = not_started[not_started['start_date'].dt.date == data_date.date()]

    if riding_candidates.empty:
        return pd.DataFrame(), pd.DataFrame()

    all_activities_lookup = activities.reset_index().set_index('ObjectId')
    completed_ids = set(all_activities_lookup[all_activities_lookup['status'] == 'Completed'].index)
    
    less_than_30, more_than_30 = [], []

    for task_code, activity in riding_candidates.iterrows():
        activity_obj_id = activity['ObjectId']
        preds = relationships[relationships['SuccessorActivityObjectId'] == activity_obj_id]

        # Rule 4: All predecessors must be "Completed" OR there are no predecessors
        if preds.empty:
            report_data = {
                'Activity ID': task_code,
                'Activity Name': activity['task_name'],
                'Start Date': activity['start_date'],
                'Pred Activity ID': 'None',
                'Last Pred Finish': 'N/A',
                'Days Since Pred Finish': 'N/A'
            }
            more_than_30.append(report_data)
            continue

        pred_ids = set(preds['PredecessorActivityObjectId'])
        if pred_ids.issubset(completed_ids):
            valid_pred_ids = [pid for pid in pred_ids if pid in all_activities_lookup.index]
            if not valid_pred_ids: continue
            
            pred_details = all_activities_lookup.loc[valid_pred_ids]
            latest_pred_finish_date = pred_details['finish_date'].max()

            if pd.notna(latest_pred_finish_date):
                latest_pred_activity = pred_details[pred_details['finish_date'] == latest_pred_finish_date].iloc[0]
                delta = data_date - latest_pred_finish_date
                report_data = {
                    'Activity ID': task_code,
                    'Activity Name': activity['task_name'],
                    'Start Date': activity['start_date'],
                    'Pred Activity ID': latest_pred_activity['task_code'],
                    'Last Pred Finish': latest_pred_finish_date,
                    'Days Since Pred Finish': delta.days
                }
                if delta.days < 30:
                    less_than_30.append(report_data)
                else:
                    more_than_30.append(report_data)

    df_less = pd.DataFrame(less_than_30)
    df_more = pd.DataFrame(more_than_30)
    
    column_order = ['Activity ID', 'Activity Name', 'Start Date', 'Pred Activity ID', 'Last Pred Finish', 'Days Since Pred Finish']

    if not df_less.empty:
        df_less['Start Date'] = pd.to_datetime(df_less['Start Date']).dt.strftime(date_format)
        df_less['Last Pred Finish'] = pd.to_datetime(df_less['Last Pred Finish']).dt.strftime(date_format)
        df_less = df_less[column_order].sort_values(by='Last Pred Finish')
    if not df_more.empty:
        df_more['Start Date'] = pd.to_datetime(df_more['Start Date']).dt.strftime(date_format)
        df_more['Last Pred Finish_dt'] = pd.to_datetime(df_more['Last Pred Finish'], errors='coerce')
        df_more = df_more.sort_values(by='Last Pred Finish_dt').drop(columns=['Last Pred Finish_dt'])
        df_more['Last Pred Finish'] = pd.to_datetime(df_more['Last Pred Finish'], errors='coerce').dt.strftime(date_format)
        df_more = df_more[column_order]
        df_more.fillna('N/A', inplace=True)
        
    return df_less, df_more

def check_duplicate_activity_names(activities):
    if activities.empty or 'task_name' not in activities.columns:
        return pd.DataFrame()
    
    duplicated_names = activities[activities.duplicated(subset='task_name', keep=False)]['task_name']
    
    if duplicated_names.empty:
        return pd.DataFrame()
        
    result_df = activities[activities['task_name'].isin(duplicated_names)].copy()
    
    report = result_df.reset_index()[['task_code', 'task_name']]
    return report.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name'}).sort_values(by=['Activity Name', 'Activity ID'])

def check_zero_float_activities(activities):
    if activities.empty or 'TotalFloat' not in activities.columns:
        return pd.DataFrame()
    zero_float = activities[(activities['status'] == 'In Progress') & (activities['TotalFloat'] == 0)].copy()
    if zero_float.empty:
        return pd.DataFrame()
    report = zero_float.reset_index()[['task_code', 'task_name', 'TotalFloat']]
    return report.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name', 'TotalFloat': 'Total Float (h)'})

def check_no_predecessors(activities, relationships, date_format):
    if relationships.empty or 'Type' not in relationships.columns or 'SuccessorActivityObjectId' not in relationships.columns or activities.empty:
        return pd.DataFrame()
    first_start = activities['start_date'].min()
    first_tasks = set(activities[activities['start_date'] == first_start].index)
    driving_rels = relationships[relationships['Type'].isin(['Finish to Start', 'Start to Start'])]
    successors = set(activities.reset_index()[activities.reset_index()['ObjectId'].isin(driving_rels['SuccessorActivityObjectId'])]['task_code'])
    to_check = set(activities.index) - first_tasks
    missing_codes = list(to_check - successors)
    if not missing_codes: return pd.DataFrame()
    result_df = activities.loc[missing_codes].copy().sort_values(by='start_date')
    result_df['start_date'] = result_df['start_date'].dt.strftime(date_format)
    report = result_df.reset_index()[['task_code', 'task_name', 'start_date']]
    return report.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name', 'start_date': 'Start Date'})

def check_no_successors(activities, relationships, date_format):
    if relationships.empty or 'Type' not in relationships.columns or 'PredecessorActivityObjectId' not in relationships.columns or activities.empty:
        return pd.DataFrame()
    last_finish = activities['finish_date'].max()
    last_tasks = set(activities[activities['finish_date'] == last_finish].index)
    driving_rels = relationships[relationships['Type'].isin(['Finish to Start', 'Finish to Finish'])]
    predecessors = set(activities.reset_index()[activities.reset_index()['ObjectId'].isin(driving_rels['PredecessorActivityObjectId'])]['task_code'])
    to_check = set(activities.index) - last_tasks
    missing_codes = list(to_check - predecessors)
    if not missing_codes: return pd.DataFrame()
    result_df = activities.loc[missing_codes].copy().sort_values(by='finish_date')
    result_df['finish_date'] = result_df['finish_date'].dt.strftime(date_format)
    report = result_df.reset_index()[['task_code', 'task_name', 'finish_date']]
    return report.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name', 'finish_date': 'Finish Date'})

def check_negative_lag(activities, relationships):
    if 'Lag' not in relationships.columns or relationships.empty: return pd.DataFrame()
    negative_rels = relationships[relationships['Lag'] < 0].copy()
    if negative_rels.empty: return pd.DataFrame()
    id_map = activities.reset_index().set_index('ObjectId')['task_code']
    negative_rels['Predecessor'] = negative_rels['PredecessorActivityObjectId'].map(id_map)
    negative_rels['Successor'] = negative_rels['SuccessorActivityObjectId'].map(id_map)
    return negative_rels[['Predecessor', 'Successor', 'Type', 'Lag']]

def check_start_to_finish_logic(activities, relationships):
    if 'Type' not in relationships.columns or relationships.empty: return pd.DataFrame()
    sf_rels = relationships[relationships['Type'] == 'Start to Finish'].copy()
    if sf_rels.empty: return pd.DataFrame()
    id_map = activities.reset_index().set_index('ObjectId')['task_code']
    sf_rels['Predecessor'] = sf_rels['PredecessorActivityObjectId'].map(id_map)
    sf_rels['Successor'] = sf_rels['SuccessorActivityObjectId'].map(id_map)
    return sf_rels[['Predecessor', 'Successor', 'Lag']]

def check_late_starts(activities, data_date, date_format):
    not_started = activities[activities['status'] == 'Not Started'].copy()
    late_starts = not_started[not_started['start_date'].dt.date < data_date.date()]
    if late_starts.empty: return pd.DataFrame()
    late_starts = late_starts.sort_values(by='start_date')
    late_starts['start_date'] = late_starts['start_date'].dt.strftime(date_format)
    report = late_starts.reset_index()[['task_code', 'task_name', 'start_date']]
    return report.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name', 'start_date': 'Start Date'})
def check_missing_actual_starts(activities):
    in_progress = activities[activities['status'] == 'In Progress'].copy()
    missing = in_progress[pd.isnull(in_progress['raw_actual_start'])]
    if missing.empty: return pd.DataFrame()
    report = missing.reset_index()[['task_code', 'task_name', 'status']]
    return report.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name', 'status': 'Status'})
def check_missing_actual_finishes(activities):
    completed = activities[activities['status'] == 'Completed'].copy()
    missing = completed[pd.isnull(completed['raw_actual_finish'])]
    if missing.empty: return pd.DataFrame()
    report = missing.reset_index()[['task_code', 'task_name', 'status']]
    return report.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name', 'status': 'Status'})
def check_zero_duration(activities):
    zero_tasks = activities[(~activities['activity_type'].isin(['Start Milestone', 'Finish Milestone', 'Level of Effort', 'WBS Summary'])) & (activities['planned_duration_hours'] == 0)]
    if zero_tasks.empty: return pd.DataFrame()
    report = zero_tasks.reset_index()[['task_code', 'task_name', 'activity_type']]
    return report.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name', 'activity_type': 'Activity Type'})
def check_long_durations(activities, days_threshold=30):
    hours_threshold = days_threshold * 8
    long_tasks = activities[activities['planned_duration_hours'] > hours_threshold]
    if long_tasks.empty: return pd.DataFrame()
    report = long_tasks.reset_index()[['task_code', 'task_name', 'planned_duration_hours']]
    return report.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name', 'planned_duration_hours': 'Planned Duration (h)'})
def check_hard_constraints(activities, date_format):
    hard_constraints = ['Finish On']
    constrained_tasks = activities[activities['ConstraintType'].isin(hard_constraints)].copy()
    if constrained_tasks.empty: return pd.DataFrame()
    constrained_tasks['ConstraintDate_dt'] = pd.to_datetime(constrained_tasks['ConstraintDate'])
    constrained_tasks.sort_values(by='ConstraintDate_dt', inplace=True)
    constrained_tasks['ConstraintDate'] = constrained_tasks['ConstraintDate_dt'].dt.strftime(date_format)
    report = constrained_tasks.reset_index()[['task_code', 'task_name', 'ConstraintType', 'ConstraintDate']]
    return report.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name', 'ConstraintType': 'Constraint Type', 'ConstraintDate': 'Constraint Date'})
def check_soft_constraints(activities, date_format):
    soft_constraints = ['Start On or After', 'Finish On or Before', 'As Late As Possible']
    constrained_tasks = activities[activities['ConstraintType'].isin(soft_constraints)].copy()
    if constrained_tasks.empty: return pd.DataFrame()
    alap_mask = (constrained_tasks['ConstraintType'] == 'As Late As Possible') & (pd.isnull(constrained_tasks['ConstraintDate']))
    constrained_tasks.loc[alap_mask, 'ConstraintDate'] = constrained_tasks.loc[alap_mask, 'finish_date']
    constrained_tasks['ConstraintDate_dt'] = pd.to_datetime(constrained_tasks['ConstraintDate'])
    constrained_tasks.sort_values(by='ConstraintDate_dt', inplace=True)
    constrained_tasks['ConstraintDate'] = constrained_tasks['ConstraintDate_dt'].dt.strftime(date_format)
    report = constrained_tasks.reset_index()[['task_code', 'task_name', 'ConstraintType', 'ConstraintDate']]
    return report.rename(columns={'task_code': 'Activity ID', 'task_name': 'Activity Name', 'ConstraintType': 'Constraint Type', 'ConstraintDate': 'Constraint Date'})