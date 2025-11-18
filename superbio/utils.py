from datetime import datetime
import json
import os
from typing import List
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from superbio.consts import RUNNING_MODE


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

def job_post_validation(app_config, job_config, 
                        local_files_keys, remote_file_source_data_keys, 
                        datahub_file_data_keys, datahub_result_file_data_keys, open_file_data_keys, 
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
    if datahub_result_file_data_keys:
        job_files.extend(datahub_result_file_data_keys)
    if open_file_data_keys:
        job_files.extend(open_file_data_keys)

    app_config_running_modes = app_config["running_modes"]
    app_config_running_mode_ids = {mode["mode_id"] for mode in app_config_running_modes}
    if running_mode not in ["cpu", "gpu"]:
        raise Exception("Invalid running mode, choose 'gpu' or 'cpu' depending on what running modes the app supports")
    elif running_mode == "gpu" and 2 not in app_config_running_mode_ids:
        raise Exception("This app does not support GPU running mode")
    elif running_mode == "cpu" and not app_config_running_mode_ids.intersection({1, 3, 4}):
        raise Exception("This app does not support CPU running mode")

    required_params = []
    for param_config in app_config["parameter_settings"]["parameters"]:
        if param_config.get("optional") or param_config.get("hidden"):
            continue
        required_params.append(param_config["field_name"])

    file_settings = app_config["file_settings"]
    required_files = [file["name"] for file in file_settings if
                      file.get("optional") is None or file.get("optional") is False]

    missing_params = get_missing_values(required_params, job_config.keys())
    missing_files = get_missing_values(required_files, job_files)

    if len(missing_params):
        raise Exception(f"Missing the following parameter values: {missing_params}")

    if len(missing_files):
        raise Exception(f"Missing the following files: {missing_files}")

def format_datahub_file_data(datahub_file_data):
    formatted_datahub_file_data = {}
    if datahub_file_data is not None:
        for file_key in datahub_file_data:
            formatted_datahub_file_data[file_key] = []
            for path in datahub_file_data[file_key]:
                formatted_datahub_file_data[file_key].append({
                    "protocol": "s3",
                    "path": path
                })

    return formatted_datahub_file_data


def _create_multipart_encoder(fields, local_files):
    open_files = {}
    if local_files:
        open_files = {file_key: (os.path.basename(file_path), open(file_path, "rb"), "application/octet-stream") 
                      for file_key, file_path in local_files.items()}
        fields.update(open_files)
    
    encoder = MultipartEncoder(fields)
    monitor = MultipartEncoderMonitor(encoder, create_callback(encoder))
    return open_files, monitor, monitor.content_type


def format_open_file_data(open_file_data):
    formatted_open_file_data = {}
    if open_file_data is not None:
        for file_key in open_file_data:
            formatted_open_file_data[file_key] = []
            for file in open_file_data[file_key]:
                file["protocol"] = "download_link"
                formatted_open_file_data[file_key].append(file)
    return formatted_open_file_data

def create_patch_partial_job_payload(partial_job_id, auth_token, local_files, remote_file_source_data, formatted_datahub_file_data, formatted_datahub_result_file_data, formatted_open_file_data):
    # TODO: add file duplicated handling after adding 'add to data hub'
    headers = {
        "X-File-Name-To-File-Key-Map": json.dumps({}),
        "X-Add-To-Data-Hub-Paths": json.dumps({}),
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "multipart/form-data",  # This will be replaced dynamically
    }
    fields = {
        "partial_job_id": partial_job_id,
        "remote_file_source_data": remote_file_source_data,
        "datahub_file_data": formatted_datahub_file_data,
        "datahub_result_file_data": formatted_datahub_result_file_data,
        "open_file_data": formatted_open_file_data
    }
    open_files, monitor, content_type = _create_multipart_encoder(fields, local_files)
    headers["Content-Type"] = content_type
    return headers, open_files, monitor

def create_datahub_upload_payload(file_path, is_organisation, upload_id, auth_token, local_files, remote_file_source_data):
    headers = {
        "X-File-Path": file_path,
        "X-Is-Organization": str(is_organisation).lower(),
        "X-Upload-Id": upload_id,
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "multipart/form-data",  # This will be replaced dynamically
    }
    
    fields = {
        "path": file_path,
        "is_organisation": str(is_organisation).lower(),
    }
    
    if remote_file_source_data:
        fields["remote_file_source_data"] = remote_file_source_data
    
    open_files, monitor, content_type = _create_multipart_encoder(fields, local_files)
    headers["Content-Type"] = content_type
    return headers, open_files, monitor

def create_callback(encoder):
    def callback(monitor):
        progress = (monitor.bytes_read / encoder.len) * 100
        print(f"Upload Progress: {progress:.2f}%")

    return callback