import os
import tempfile
import shutil
import webbrowser
from threading import Timer
from flask import Flask, request, render_template
from werkzeug.utils import secure_filename
from xml_to_csv_converter import convert_xml_to_csv
from xer_to_csv_converter import convert_xer_to_csv
from config import Config
from parser import parse_csv_data
from comparator import find_changes
from diagnostics import run_all_checks

app = Flask(__name__)
# Load all configuration values (SECRET_KEY, MAX_CONTENT_LENGTH, etc.)
app.config.from_object(Config)

TOOLTIPS = {
    'diagnostics': {
        "Late Starts": "Activities that were planned to start on or before the project's official status date (Data Date) but have not yet begun. These tasks are officially behind schedule.",
        "Activities Riding Data Date < 30 Days": "Not-started activities whose start date is the same as the project's Data Date and whose predecessors are all complete. The gap between the last predecessor's finish and the Data Date is less than 30 days.",
        "Activities Riding Data Date > 30 Days": "Not-started activities whose start date is the same as the project's Data Date and whose predecessors are all complete. The gap between the last predecessor's finish and the Data Date is 30 days or more, indicating a significant potential for an out-of-sequence issue.",
        "In-Progress Activities with Zero Float": "Activities that are currently 'In Progress' but have zero total float. These are critical path activities that have no room for delay without impacting the project's finish date.",
        "Activities with Hard Constraints": "Activities with a 'Finish On' constraint. These fixed dates can restrict the schedule's logic and may hide the true critical path.",
        "Activities with Soft Constraints": "Activities with flexible date constraints like 'Start On or After', 'Finish On or Before', or 'As Late As Possible'. While not as rigid as hard constraints, they can still influence the schedule's logic.",
        "Missing Actual Start Dates": "Activities that are marked 'In Progress' but are missing an official Actual Start Date. This is a data quality issue that can affect progress tracking.",
        "Missing Actual Finish Dates": "Activities that are marked 'Completed' but are missing an official Actual Finish Date. This is a data quality issue that affects as-built records.",
        "Activities w/No Driving Predecessor": "Activities (excluding the project start) that are not logically driven by a predecessor with a Finish-to-Start or Start-to-Start relationship. This is also known as an 'Open Start'.",
        "Activities w/No Driving Successor": "Activities (excluding the project finish) that do not logically drive a successor with a Finish-to-Start or Finish-to-Finish relationship. This is also known as an 'Open End'.",
        "Activities with Negative Lag": "Logic links where a successor is scheduled to start or finish *before* its predecessor has finished. This can be confusing and is often considered poor scheduling practice.",
        "Activities with Start-to-Finish Logic": "Activities linked with the rare 'Start-to-Finish' relationship type. This logic is often used incorrectly and should be reviewed for accuracy.",
        "Activities with Zero Original Durations": "Work activities (excluding milestones) that have a planned duration of zero. This is usually a data entry error.",
        "Activities > 30 Calendar Days": "Activities with a planned duration of more than 30 calendar days (240 hours). These tasks may be too large and could potentially be broken down into smaller, more manageable activities.",
        "Duplicate Activity Names": "A list of activities that share the exact same name. This can indicate redundant or duplicate tasks in the schedule."
    },
    'comparison': {
        "Added Tasks": "Activities that exist in the new schedule but did not exist in the old schedule.",
        "Deleted Tasks": "Activities that existed in the old schedule but have been removed from the new schedule.",
        "Name Changes": "Activities whose name or description has been changed between the two schedule updates.",
        "Activities with Modified Original Durations": "Activities whose baseline 'Original Duration' has been changed. This can impact performance metrics and make it difficult to track the true causes of delays.",
        "Added Activities with Fractional Durations": "New activities that have been added to the schedule with a fractional (e.g., 2.5) duration. This is usually a data entry error.",
        "Duration Changes to Fractional Values": "Existing activities whose duration has been changed to a fractional (e.g., 3.2) value. This is usually a data entry error.",
        "Start Date Changes": "Activities whose planned start date has changed between the two schedule updates.",
        "Finish Date Changes": "Activities whose planned finish date has changed between the two schedule updates.",
        "Status Changes": "Activities whose status ('Not Started', 'In Progress', 'Completed') has changed between the two updates.",
        "Percent Complete Changes": "Activities whose reported percent complete has changed.",
        "Active Activities with No Progress": "Activities that were 'In Progress' in both schedules but showed no change in either their percent complete or their actual costs, indicating a potential stall.",
        "In-Progress Activities >30d with No $ Increase": "Long-duration 'In Progress' activities that have not incurred any new actual costs since the last update, suggesting they may be stalled or not properly updated.",
        "Must Finish By Date Set": "Indicates that a 'Must Finish By' constraint has been set at the project level. This is a critical constraint that can override all other logic in the schedule."
    }
}

def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in {'xml', 'xer'}
    )

@app.route('/', methods=['GET', 'POST'])
def upload_and_compare():
    if request.method == 'POST':
        target_file = request.files.get('target_file')
        update_file = request.files.get('update_file')
        date_format = request.form.get('date_format', '%m/%d/%Y')

        if not target_file or not update_file or not target_file.filename or not update_file.filename:
            return "Please select both a Target and an Update schedule file.", 400
        
        target_filename = secure_filename(target_file.filename)
        update_filename = secure_filename(update_file.filename)

        if allowed_file(target_filename) and allowed_file(update_filename):
            target_data_dir, update_data_dir = tempfile.mkdtemp(), tempfile.mkdtemp()
            try:
                target_filepath = os.path.join(target_data_dir, target_filename)
                update_filepath = os.path.join(update_data_dir, update_filename)
                target_file.save(target_filepath)
                update_file.save(update_filepath)

                # choose converter based on file extension
                target_ext = target_filename.rsplit('.', 1)[1].lower()
                update_ext = update_filename.rsplit('.', 1)[1].lower()

                if target_ext == 'xml':
                    target_success = convert_xml_to_csv(target_filepath, target_data_dir, 'target')
                else:  # 'xer'
                    target_success = convert_xer_to_csv(target_filepath, target_data_dir, 'target')

                if update_ext == 'xml':
                    update_success = convert_xml_to_csv(update_filepath, update_data_dir, 'update')
                else:  # 'xer'
                    update_success = convert_xer_to_csv(update_filepath, update_data_dir, 'update')

                if target_success and update_success:
                    target_data = parse_csv_data(target_data_dir, 'target')
                    update_data = parse_csv_data(update_data_dir, 'update')
                    if target_data and update_data:
                        comparison_report = find_changes(target_data, update_data, date_format)
                        diagnostics_report = run_all_checks(update_data, date_format)
                        target_project_data = target_data.get('project', {})
                        update_project_data = update_data.get('project', {})
                        
                        return render_template('_reports.html', 
                                               comparison_report=comparison_report, 
                                               diagnostics_report=diagnostics_report,
                                               target_filename=target_filename, update_filename=update_filename,
                                               target_project_data=target_project_data, update_project_data=update_project_data,
                                               tooltips=TOOLTIPS)
                    else:
                        return "Error processing the converted CSV data.", 500
                else:
                    return "Error converting XML files.", 500
            finally:
                shutil.rmtree(target_data_dir)
                shutil.rmtree(update_data_dir)
        else:
            return "Invalid file type. Please upload .xml or .xer files.", 400

    return render_template('index.html')

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    Timer(1, open_browser).start()
    app.run(debug=True)
