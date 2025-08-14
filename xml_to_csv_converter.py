import pandas as pd
from defusedxml import ElementTree as ET
import re
import os

def convert_xml_to_csv(file_path, output_folder, file_identifier):
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        namespace = ''
        match = re.match(r'\{.*\}', root.tag)
        if match:
            namespace = match.group(0)

        # --- Process Project Data ---
        project = root.find(f'.//{namespace}Project')
        project_data = {}
        if project is not None:
            data_date = project.find(f'{namespace}DataDate')
            project_data = {
                'Id': project.find(f'{namespace}Id').text if project.find(f'{namespace}Id') is not None else 'N/A',
                'Name': project.find(f'{namespace}Name').text if project.find(f'{namespace}Name') is not None else 'N/A',
                'DataDate': data_date.text if data_date is not None else 'N/A',
                'PlannedStartDate': project.find(f'{namespace}PlannedStartDate').text if project.find(f'{namespace}PlannedStartDate') is not None else None,
                'ScheduledFinishDate': project.find(f'{namespace}ScheduledFinishDate').text if project.find(f'{namespace}ScheduledFinishDate') is not None else None,
                'MustFinishByDate': project.find(f'{namespace}MustFinishByDate').text if project.find(f'{namespace}MustFinishByDate') is not None else None
            }
            if data_date is not None:
                with open(os.path.join(output_folder, f'{file_identifier}_datadate.txt'), 'w') as f:
                    f.write(data_date.text)
        if project_data:
            pd.DataFrame([project_data]).to_csv(os.path.join(output_folder, f'{file_identifier}_project.csv'), index=False)


        # --- Process Activities ---
        activities_data = []
        for act in root.findall(f'.//{namespace}Activity'):
            activities_data.append({
                'task_code': act.find(f'{namespace}Id').text if act.find(f'{namespace}Id') is not None else '',
                'ObjectId': act.find(f'{namespace}ObjectId').text if act.find(f'{namespace}ObjectId') is not None else '',
                'task_name': act.find(f'{namespace}Name').text if act.find(f'{namespace}Name') is not None else '',
                'status': act.find(f'{namespace}Status').text if act.find(f'{namespace}Status') is not None else 'Unknown',
                'activity_type': act.find(f'{namespace}Type').text if act.find(f'{namespace}Type') is not None else 'Task Dependent',
                'planned_duration_hours': float(act.find(f'{namespace}PlannedDuration').text) if act.find(f'{namespace}PlannedDuration') is not None else 0,
                'actual_duration_hours': float(act.find(f'{namespace}ActualDuration').text) if act.find(f'{namespace}ActualDuration') is not None else 0,
                'remaining_duration_hours': float(act.find(f'{namespace}RemainingDuration').text) if act.find(f'{namespace}RemainingDuration') is not None else 0,
                'percent_complete': float(act.find(f'{namespace}PhysicalPercentComplete').text) if act.find(f'{namespace}PhysicalPercentComplete') is not None else 0,
                'raw_start_date': act.find(f'{namespace}StartDate').text,
                'raw_finish_date': act.find(f'{namespace}FinishDate').text,
                'raw_actual_start': act.find(f'{namespace}ActualStartDate').text,
                'raw_actual_finish': act.find(f'{namespace}ActualFinishDate').text,
                'ConstraintType': act.find(f'{namespace}PrimaryConstraintType').text,
                'ConstraintDate': act.find(f'{namespace}PrimaryConstraintDate').text,
                'TotalFloat': float(act.find(f'{namespace}TotalFloat').text) if act.find(f'{namespace}TotalFloat') is not None else 0
            })
        pd.DataFrame(activities_data).to_csv(os.path.join(output_folder, f'{file_identifier}_activities.csv'), index=False)

        # --- Process Relationships ---
        rels_data = []
        for rel in root.findall(f'.//{namespace}Relationship'):
            pred = rel.find(f'{namespace}PredecessorActivityObjectId')
            succ = rel.find(f'{namespace}SuccessorActivityObjectId')
            if pred is not None and succ is not None:
                rels_data.append({
                    'PredecessorActivityObjectId': pred.text,
                    'SuccessorActivityObjectId': succ.text,
                    'Type': rel.find(f'{namespace}Type').text if rel.find(f'{namespace}Type') is not None else 'Finish to Start',
                    'Lag': float(rel.find(f'{namespace}Lag').text) if rel.find(f'{namespace}Lag') is not None else 0
                })
        pd.DataFrame(rels_data).to_csv(os.path.join(output_folder, f'{file_identifier}_relationships.csv'), index=False)
        
        return True
    except Exception as e:
        print(f"Error during XML to CSV conversion: {e}")
        return False