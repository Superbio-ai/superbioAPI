from datetime import datetime
from typing import List


def data_validation(date_strs: List[str]):
    try:
        for date_str in date_strs:
            if date_str:
                datetime.strptime(date_str, "%d/%m/%Y")
        return True
    except ValueError:
        raise ValueError("Invalid date format. Use dd/mm/yyyy.")


def get_missing_values(required_items, items):
    return [key for key in required_items if key not in items]


def job_post_validation(app_config, job_config, local_files_keys, remote_file_source_data_keys, datahub_file_data_keys,
                        running_mode):
    # TODO: add numeric input range validation
    # TODO: add file extension validation
    # TODO: remote file data format and datahub file validation format

    job_files = []
    if local_files_keys:
        job_files.extend(local_files_keys)
    if remote_file_source_data_keys:
        job_files.extend(remote_file_source_data_keys)
    if datahub_file_data_keys:
        job_files.extend(datahub_file_data_keys)

    app_config_running_modes = app_config["running_modes"]
    print(f"app_config_running_modes {app_config_running_modes}")
    app_config_running_mode_ids = {mode["mode_id"] for mode in app_config_running_modes}
    if running_mode not in ["cpu", "gpu"]:
        raise Exception("Invalid running mode, choose 'gpu' or 'cpu' depending on what running modes the app supports")
    elif running_mode == "gpu" and 2 not in app_config_running_mode_ids:
        raise Exception("")
    elif running_mode == "cpu" and not app_config_running_mode_ids.intersection({1, 3, 4}):
        raise Exception("")

    required_params = []
    for param_config in app_config["parameter_settings"]["parameters"]:
        if param_config.get("optional"):
            continue
        required_params.append(param_config["field_name"])

    file_settings = app_config["file_settings"]
    required_files = [file["name"] for file in file_settings if
                      file.get("optional") is None or file.get("optional") is False]

    missing_params = get_missing_values(required_params, job_config.keys())
    missing_files = get_missing_values(required_files, job_files)

    print("required_params", required_params)
    print("job_config.keys()", job_config.keys())

    if len(missing_params):
        raise Exception(f"Missing the following parameter values: {missing_params}")

    if len(missing_files):
        raise Exception(f"Missing the following files: {missing_files}")
