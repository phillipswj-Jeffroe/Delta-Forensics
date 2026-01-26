import pandas as pd
import numpy as np
import os

def parse_csv_data(folder_path, file_identifier):
    try:
        data = {
            "data_date": None, 
            "activities": pd.DataFrame(), 
            "expenses": pd.DataFrame(), 
            "relationships": pd.DataFrame(),
            "project": {},
            "wbs": pd.DataFrame()
        }
        activities_path = os.path.join(folder_path, f'{file_identifier}_activities.csv')
        if not os.path.exists(activities_path): return None
        
        activities_df = pd.read_csv(activities_path)
        
        for col in ['raw_start_date', 'raw_finish_date', 'raw_actual_start', 'raw_actual_finish', 'ConstraintDate']:
            if col in activities_df.columns:
                activities_df[col] = pd.to_datetime(activities_df[col], errors='coerce')

        conditions_start = [(activities_df['status'] == 'Completed'), (activities_df['status'] == 'In Progress')]
        choices_start = [activities_df['raw_actual_start'], activities_df['raw_actual_start']]
        activities_df['start_date'] = np.select(conditions_start, choices_start, default=activities_df['raw_start_date'])
        conditions_finish = [(activities_df['status'] == 'Completed')]
        choices_finish = [activities_df['raw_actual_finish']]
        activities_df['finish_date'] = np.select(conditions_finish, choices_finish, default=activities_df['raw_finish_date'])
        
        activities_df.set_index('task_code', inplace=True)
        data['activities'] = activities_df

        relationships_path = os.path.join(folder_path, f'{file_identifier}_relationships.csv')
        if os.path.exists(relationships_path): data['relationships'] = pd.read_csv(relationships_path)
        expenses_path = os.path.join(folder_path, f'{file_identifier}_expenses.csv')
        if os.path.exists(expenses_path): data['expenses'] = pd.read_csv(expenses_path)
        data_date_path = os.path.join(folder_path, f'{file_identifier}_datadate.txt')
        if os.path.exists(data_date_path):
            with open(data_date_path, 'r') as f:
                data['data_date'] = pd.to_datetime(f.read())
        
        project_path = os.path.join(folder_path, f'{file_identifier}_project.csv')
        if os.path.exists(project_path):
            project_df = pd.read_csv(project_path)
            data['project'] = project_df.iloc[0].to_dict()

        # --- Optional WBS ---
        wbs_path = os.path.join(folder_path, f'{file_identifier}_wbs.csv')
        if os.path.exists(wbs_path):
            data['wbs'] = pd.read_csv(wbs_path)

        return data
    except Exception as e:
        print(f"Error reading or processing CSV data: {e}")
        return None