import json
import os
from typing import List, Literal, Optional
import requests
from superbio.consts import RUNNING_MODE
from superbio.auth import AuthManager
from superbio.upload import DEFAULT_CONCURRENCY, DataHubUploader, ProgressCallback, iter_upload_targets, print_progress
from superbio.utils import create_patch_partial_job_payload, data_validation, job_post_validation, format_datahub_file_data, format_userdata_file_data, format_open_file_data


"""
Superbio API Client

This module provides a client for interacting with the Superbio API. It handles authentication,
job submission, file management, and result retrieval.
"""

PROBLEM_WITH_JOB = "There was a problem finding your job, check the job_id is correct"


class Client:
    """
    Main client class for interacting with the Superbio API.

    The client provides programmatic access to the Superbio platform, allowing users to:
    - List and browse available apps
    - Get app configurations and parameters
    - Submit and manage computational jobs
    - Track job status and retrieve results
    - Monitor balances

    Note:
        You must first create an account at https://app.superbio.ai before using this client.
        Your email and password from the platform will be used to authenticate API requests.

    Attributes:
        auth (AuthManager): Handles authentication with the API
        BASE_URL (str): The base URL for the API
    """

    BASE_URL = "https://api.superbio.ai"
    # BASE_URL = "http://127.0.0.1:8000"

    # TODO:
    # add files to datahub function and handle add to datahub in post job
    # download results to remote storage function
    # cache for app config
    # helper function to return a job_config template
    # get open data list

    def __init__(self, email: str = None, password: str = None, token: str = None, user_id: str = None, job_group_id: str = None):
        """
        Initialize the Superbio client.

        Args:
            email (str): User's email address
            password (str): User's password
            token (str, optional): Existing authentication token
            user_id (str, optional): User id (required to be provided if token is provided)
            job_group_id (str, optional): Used to group jobs together for sorting and filtering
        """
        if (email and password) or (token and user_id):
            self.auth = AuthManager(self.BASE_URL, email, password, token, user_id)
        else:
            raise ValueError("Either email and password or token and user_id must be provided")

        self.job_group_id = job_group_id

    def _request(self, method, endpoint, data=None, _json=None, params=None, files=None, headers=None, stream=False,
                 return_json=True):
        url = f"{self.BASE_URL}/{endpoint}"
        headers = headers or {}
        headers.update({"Authorization": f"Bearer {self.auth.token}"})
        response = requests.request(method, url, data=data, json=_json, params=params, files=files, headers=headers,
                                    stream=stream)

        response.raise_for_status()

        if return_json:
            return response.json()
        else:
            return response

    def post_job(self, app_id: str, running_mode: Literal["gpu", "cpu"], config=None, local_files=None,
                 remote_file_source_data=None, datahub_file_data=None, datahub_result_file_data=None,
                 open_file_data=None, userdata_file_data=None, validate=True,
                 title: str = None, group_id: str = None):
        """
        Submit a new job to the Superbio platform.

        Args:
            app_id (str): ID of the application to run
            running_mode (str): Either "gpu" or "cpu"
            config (dict, optional): Job configuration parameters
            local_files (dict, optional): Mapping of file keys to local file paths
            remote_file_source_data (dict, optional): Remote file source configuration
                Example for S3:
                {
                    "file_key": [{
                        "protocol": "s3",
                        "credentials": {
                            "aws_access_key_id": "YOUR_ACCESS_KEY",
                            "aws_secret_access_key": "YOUR_SECRET_KEY"
                        },
                        "path": "bucket/path/to/file.csv"
                    }]
                }
            datahub_file_data (dict, optional): Mapping of file keys to lists of datahub file paths.
                Personal DataHub (string format):
                {
                    "file_key": ["path/to/datahub/file.csv"]
                }
                Org DataHub (dict format with is_organisation):
                {
                    "file_key": [{"path": "path/to/file.csv", "is_organisation": True}]
                }
            datahub_result_file_data (dict, optional): Mapping of file keys to lists of datahub result file paths
                Example:
                {
                    "file_key": ["path/to/datahub/result/file.csv"]
                }
            open_file_data (dict, optional): Mapping of file keys to lists of open file data
                Example:
                {
                    "file_key": [{
                        "type":"single_cell",
                        "id":"b2005457-dede-4434-a9c3-dbe41fcd542e",
                        "path":"A Coding and Non-Coding Atlas of the Human Arterial Cell/slide-seqV2 analysis of aorta.h5ad",
                        "extension":"h5ad"
                    }]
                }
            userdata_file_data (dict, optional): Org-shared S3 files. Use for files from org
                members' integrated S3 buckets. No credentials needed -- server handles auth.
                Example:
                {
                    "file_key": [{"path": "s3/key/file.csv", "shared_user_id": "owner_user_id"}]
                }
            validate (bool, optional): Whether to validate inputs before submission
            title (str, optional): Human-readable title for the job
            group_id (str, optional): Group ID for job grouping/filtering. Falls back to self.job_group_id if not provided.

        Returns:
            dict: Response from the API containing job details
                Example:
                {
                    "job_id": "job_123abc..."
                }

        Raises:
            Exception: If validation fails or job submission fails
        """
        # TODO: credits validation
        # TODO: handle open data
        # TODO: make remote and datahub data easier
        if config is None:
            config = {}

        if local_files is None:
            local_files = {}

        formatted_datahub_file_data = format_datahub_file_data(datahub_file_data)
        formatted_datahub_result_file_data = format_datahub_file_data(datahub_result_file_data)
        formatted_open_file_data = format_open_file_data(open_file_data)
        formatted_userdata_file_data = format_userdata_file_data(userdata_file_data)
        if validate:
            app_config = self.get_app_parameters(app_id)
            job_post_validation(app_config, config, local_files.keys() if local_files else [], 
                                remote_file_source_data, formatted_datahub_file_data, formatted_datahub_result_file_data, formatted_open_file_data,
                                running_mode)
        running_id = RUNNING_MODE.get(running_mode)
        config = json.dumps(config)
        remote_file_source_data = json.dumps(remote_file_source_data)
        formatted_datahub_file_data = json.dumps(formatted_datahub_file_data)
        formatted_datahub_result_file_data = json.dumps(formatted_datahub_result_file_data)
        formatted_open_file_data = json.dumps(formatted_open_file_data)
        formatted_userdata_file_data = json.dumps(formatted_userdata_file_data)

        payload = {
            "app_id": app_id,
            "partial_job_submit": True,
            "config": config,
            "running_mode": running_id,
            "group_id": group_id or self.job_group_id
        }
        if title:
            payload["title"] = title
            
        response = self._request("POST", "api/jobs", data=payload)

        partial_job_id = response["job_id"]

        headers, open_files, monitor = create_patch_partial_job_payload(partial_job_id, self.auth.token, 
                                                                        local_files, remote_file_source_data, 
                                                                        formatted_datahub_file_data, formatted_datahub_result_file_data,
                                                                        formatted_open_file_data, formatted_userdata_file_data)

        res = self._request("PATCH", f"api/jobs/{partial_job_id}", headers=headers, data=monitor, stream=True)

        for file_obj in open_files.values():
            file_obj[1].close()

        return res

    def get_jobs(self, page: int = 1, hits_per_page: int = 100, search_string: str = None, date_from: str = None,
                 date_to: str = None, status: Literal["running", "failed", "completed"] = None,
                 added_by_me: bool = True, group_id: str = None):
        """
        Retrieve a list of jobs.

        Args:
            page (int): Page number for pagination
            hits_per_page (int): Number of results per page
            search_string (str, optional): Filter jobs by search term
            date_from (str, optional): Start date in format dd/mm/yyyy
            date_to (str, optional): End date in format dd/mm/yyyy
            status (str, optional): Filter by job status
            added_by_me (bool): Only show jobs created by current user
            group_id (str, optional): Filter jobs by group id
        Returns:
            dict: List of jobs and metadata
                Example:
                {
                    "hits": [{
                        "id": "job_123abc...",
                        "title": "DGE-20221028-084933-cpu",
                        "status": "Completed",
                        "app_name": "Differential Gene Expression",
                        "created_at": "2022-10-28T08:49:33",
                        "updated_at": "2022-10-28T08:52:45",
                        "running_mode": "cpu",
                        "config": {...}
                        ...
                    }],
                    "hits_per_page": 100,
                    "total": 1234,
                    "page": 1
                }
        """
        if status not in ["running", "failed", "completed", None]:
            raise ValueError('Invalid status. Choose from: "running", "failed", "completed"')

        if status:
            status = status.capitalize()

        data_validation([date_to, date_from])
        params = {k: v for k, v in locals().items() if k != "self" and v is not None}
        return self._request("GET", "api/jobs", params=params)

    def get_job_status(self, job_id: str):
        """
        Get the status of a job.
        """
        return self._request("GET", f"/api/jobs/{job_id}")["status"]

    def _download_file(self, response, path_to_download_to):
        with open(path_to_download_to, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

    def list_job_result_files(self, job_id: str):
        """
        Get list of result files for a completed job.

        Args:
            job_id (str): ID of the job

        Returns:
            dict: Structure containing file information
                Example:
                {
                    "download": [{"file": "results.zip", "title": "Output results"}],
                    "tables": [[{"file": "table.csv", "title": "Results table"}, ...], ...],
                    "pdbs": [[{"file": "protein.pdb", "title": "Results protein"}, ...], ...],
                    "images": [[{"file": "image.png", "title": "Results Images"}, ...], ...],
                }

        Raises:
            Exception: If job not found, not completed or other error occurs
        """
        try:
            return self._request("GET", f"api/jobs/{job_id}/result_files")
        except Exception:
            raise Exception(PROBLEM_WITH_JOB)

    def download_job_result_file(self, job_id: str, result_file_path: str, path_to_download_to: str,
                                 result_type: str = None):
        """
        Download a specific result file from a job.

        Args:
            job_id (str): ID of the job
            result_file_path (str): Path to the file within job results
            path_to_download_to (str): Local path to save file to
            result_type (str, optional): This is for internal use only
        Raises:
            Exception: If download fails
        """
        url = f"api/jobs/{job_id}/result_files"
        download_path = os.path.join(f"{path_to_download_to.strip('/')}/{result_file_path.lstrip('/')}")
        download_dir = os.path.dirname(download_path)
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        params = {"result_type": result_type, "file_name": result_file_path, "download_file": True}
        try:
            response = self._request("GET", url, params=params, stream=True, return_json=False)
            self._download_file(response, download_path)
        except Exception:
            raise Exception(
                "There was a problem downloading this result file, check the job_id and result_file_path are correct and you have write permissions for path_to_download_to")

    def download_all_job_results(self, job_id: str, path_to_download_to: str, download_compressed: bool = True):
        """
        Download all results for a job.

        Args:
            job_id (str): ID of the job
            path_to_download_to (str): Local path to save files to
            download_compressed (bool): Whether to download as compressed archive

        Raises:
            Exception: If job not found or download fails
        """
        result_files = self.list_job_result_files(job_id)
        if download_compressed:
            download_section = result_files.get("download", [None])[0]
            if download_section:
                self.download_job_result_file(job_id, download_section['file'], path_to_download_to)
            else:
                # Exception for job id not valid
                raise Exception(
                    f"No compressed version is available. Try with download_compressed = False or go to your jobs page on the Superbio.ai platform")
        else:
            if result_files.get("download"):
                del result_files["download"]
            for result_file_key in result_files:
                for result_section in result_files[result_file_key]:
                    for result in result_section:
                        self.download_job_result_file(job_id, result['file'], path_to_download_to)

    def delete_job(self, job_id: str):
        """
        Delete a job.

        Args:
            job_id (str): ID of the job to delete

        Returns:
            dict: Response indicating success/failure
                Example:
                {
                    "message": "Deleted job"

        Raises:
            Exception: If job not found or deletion fails
        """
        try:
            return self._request("DELETE", f"api/jobs/{job_id}")
        except Exception:
            raise Exception(PROBLEM_WITH_JOB)

    def get_balances(self):
        """
        Get current credit balances.

        Returns:
            dict: Credit balance information
                Example:
                {
                    "balances": {
                        "available_credits": 6000,
                        "credits": 6000,
                        "runs_left": 400,
                        "total_runs": 400,
                        "runtime_left": 72000.0,
                        "total_runtime": 72000,
                        "runs_reset_time": "Feb 28 2025, 23:08:05",
                        "runtime_reset_time": "Feb 28 2025, 23:08:05",
                        "tier": "free_organisation",
                        "is_last_billing_cycle": False,
                        "comments_left": 0
                    }
                }
        """
        return self._request("GET", f"api/users/{self.auth.user_id}/balances")

    def get_app_list(self, hits_per_page=None, page=None, search_string=None, mode: Optional[Literal['minimal', 'base', 'user_api']] = 'user_api'):
        """
        Get list of available applications.

        Args:
            hits_per_page (int, optional): Number of results per page
            page (int, optional): Page number to return
            search_string (str, optional): Search by string

        Returns:
            dict: List of applications and metadata
                Example:
                {
                    "hits": [{
                        "id": "job_123abc...", 
                        "name": "App Name",
                        "description": "App description",
                        "author": "Author name",
                        "group_tags": [tag1, tag2, ...]
                    }, ...],
                    "hits_per_page": 100,
                    "total": 1234,
                    "page": 1
                }
        """
        params = {k: v for k, v in locals().items() if k != "self" and v is not None}
        return self._request("GET", f"api/appstore_list", params=params)

    def get_app_parameters(self, app_id: str):
        """
        Get configuration parameters for an application.

        Args:
            app_id (str): ID of the application

        Returns:
            dict: Application configuration
                Example:
                {
                    "parameter_settings": {
                        "parameters": [{
                            "field_name": "parameter_name",
                            "title": "Parameter Title",
                            "tooltip": "Parameter description",
                            "input_type": "dropdown|slider|checkbox|user_input",
                            "type": "str|integer|text",
                            "default_value": "default",
                            "options": [{"label": "Option 1", "value": "opt1"}, ...],
                            "min_value": 0,
                            "max_value": 100,
                            "increment": 1,
                            "hidden": false,
                            "disabled": false,
                            "optional": true
                        }, ...],
                        "disabled_fields": ["field1", "field2"],
                        "inputs_require_files": ["field3"]
                    },
                    "file_settings": [{
                        "name": "file_input_name",
                        "title": "File Input Title", 
                        "allowed_extensions": ["h5ad"],
                        "upload_types": ["local", "remote"],
                        "supports_preview": true,
                        "disabled": false,
                        "data_structure_description": "File format description",
                        "demo_data_details": {
                            "description": "Demo data description",
                            "file_name": "demo.h5ad",
                            "file_path": "path/to/demo.h5ad",
                            "preview_file_name": "preview.h5ad",
                            "file_sources": [{
                                "title": "Source Title",
                                "url": "https://source.url"
                            }]
                        }
                    }],
                    "running_modes": ["cpu", "gpu"]
                }

        Raises:
            Exception: If app not found
        """
        try:
            response = self._request("GET", f"api/apps/{app_id}")
            config = response["config"]

            if config.get("parameter_settings") and config["parameter_settings"].get("parameters"):
                config["parameter_settings"]["parameters"] = [parameter for parameter in config["parameter_settings"]["parameters"] \
                                                                if not parameter.get("hidden")]

            config["running_modes"] = response["running_modes"]
            return config
        except Exception:
            raise Exception("There was a problem finding this app, check app_id is correct")


    def list_datahub(self, list_job_results: bool = False, path: str = "", search_string: str = '', is_organisation: bool = False,
                     date_from: str = None, date_to: str = None, substrings: list = None,
                     substring_and_or: Literal["AND", "OR"] = None, app_ids: list = None):
        """
        List files in the datahub.

        Args:
            path (str): Path to the datahub folder to list
            search_string (str, optional): Search term to filter files
            is_organisation (bool, optional): Whether to list organisation datahub
            date_from (str, optional): Start date in format dd/mm/yyyy
            date_to (str, optional): End date in format dd/mm/yyyy
            substrings (list, optional): List of substrings to search for in file names
            substring_and_or (str, optional): Logic operator for substring matching ("and" or "or")
            app_ids (list, optional): List of app IDs to filter by

        Returns:
            dict: Datahub files and metadata
                Example:
                {
                    "file_tree": [...],
                    "folder_only_tree": [...],
                    "uploading_files": [...]
                }

        Raises:
            Exception: If request fails
        """
        data_validation([date_from, date_to])
        
        params = {
            "path": path,
            "search_string": search_string,
            "is_organisation": is_organisation
        }
        
        if date_from is not None:
            params["date_from"] = date_from
        if date_to is not None:
            params["date_to"] = date_to
        if substrings is not None:
            params["substrings"] = substrings
            if substring_and_or is None:
                substring_and_or = "OR"
        if substring_and_or is not None:
            params["substring_and_or"] = substring_and_or.upper()
        if app_ids is not None:
            params["app_ids"] = app_ids

        if list_job_results:
            return self._request("GET", "api/data_hub_results", params=params)
        else:
            return self._request("GET", "api/data_hub", params=params)

    def upload_to_datahub(self, path: str, local_files: dict = None, remote_file_source_data: dict = None,
                          is_organisation: bool = False, upload_id: str = None,
                          concurrency: int = DEFAULT_CONCURRENCY,
                          on_progress: Optional[ProgressCallback] = print_progress) -> List[dict]:
        """
        Upload local files or folders to the datahub.

        Files are sent directly to storage in parallel parts. If an upload is interrupted,
        calling this method again with the same files continues from the parts already
        uploaded (within 24 hours). Folders are uploaded recursively and keep their structure.

        Args:
            path (str): Destination folder in the datahub ("" for the root)
            local_files (dict): Mapping of file keys to local file or folder paths
                Example:
                {
                    "file_key": "/path/to/local/file.csv"
                }
            remote_file_source_data (dict, optional): No longer supported. Connect your S3 bucket
                in the Data Hub instead; its files are available without copying.
            is_organisation (bool, optional): Whether to upload to the organisation datahub
            upload_id (str, optional): Deprecated and ignored.
            concurrency (int, optional): Number of parts uploaded in parallel per file
            on_progress (callable, optional): Called as ``on_progress(file_name, uploaded_bytes, total_bytes)``.
                Pass None to disable progress output.

        Returns:
            list: One completion response per uploaded file
                Example:
                [{
                    "status": "success",
                    "file_name": "file.csv",
                    "file_size": 1024,
                    "namespace": "personal_data"
                }]

        Raises:
            ValueError: If no local files are given or remote_file_source_data is used
            requests.HTTPError: If the API rejects the upload (for example, storage quota exceeded)
        """
        if remote_file_source_data:
            raise ValueError(
                "Importing remote files into the Data Hub is no longer supported. "
                "Connect your S3 bucket in the Data Hub instead."
            )
        if not local_files:
            raise ValueError("local_files must be provided")

        namespace = self._upload_namespace(is_organisation)
        uploader = DataHubUploader(self._request, concurrency=concurrency, on_progress=on_progress)
        results = []
        for local_path in local_files.values():
            for file_path, datahub_folder in iter_upload_targets(local_path, path):
                results.append(uploader.upload_file(file_path, namespace, datahub_folder))
        return results

    def _upload_namespace(self, is_organisation: bool) -> str:
        available = {ns["type"] for ns in self._request("GET", "api/data_hub/namespaces")["namespaces"]}
        if is_organisation:
            if "org_shared_data" not in available:
                raise ValueError("This account does not belong to an organisation")
            return "org_shared_data"
        return "org_member_data" if "org_member_data" in available else "personal_data"

    def post_external_tool_job(self, external_tool_library_name: str, tool_name: str, config=None, 
                               local_files=None, remote_file_source_data=None, 
                               datahub_file_data=None, datahub_result_file_data=None, open_file_data=None,
                               userdata_file_data=None, title: str = None, group_id: str = None,
                               input_paths=None):
        """
        Submit a new job to the Superbio platform using an external tool. This is to be used in the superbio.ai copilot mode.

        Args:
            external_tool_library_name (str): Name/ID of the external tool library. Currently we support...
            tool_name (str): Name of the specific tool within the library
            config (dict, optional): Job configuration parameters
            input_paths (dict, optional): Chat sandbox only. Mapping of file keys to file paths
                as seen in the sandbox; the server resolves them, so no upload happens. A single
                path may be given as a string. Files only, not folders. Cannot be combined with
                the other file arguments.
                Example:
                {
                    "reads": ["/workspace/sample_R1.fq.gz", "/mnt/datahub/runs/sample_R2.fq.gz"],
                    "reference": "/mnt/results/<job_id>/ref.fa"
                }
            local_files (dict, optional): Mapping of file keys to local file paths
            remote_file_source_data (dict, optional): Remote file source configuration
                Example for S3:
                {
                    "file_key": [{
                        "protocol": "s3",
                        "credentials": {
                            "aws_access_key_id": "YOUR_ACCESS_KEY",
                            "aws_secret_access_key": "YOUR_SECRET_KEY"
                        },
                        "path": "bucket/path/to/file.csv"
                    }]
                }
            datahub_file_data (dict, optional): Mapping of file keys to lists of datahub file paths.
                Personal DataHub (string format):
                {
                    "file_key": ["path/to/datahub/file.csv"]
                }
                Org DataHub (dict format with is_organisation):
                {
                    "file_key": [{"path": "path/to/file.csv", "is_organisation": True}]
                }
            open_file_data (dict, optional): Mapping of file keys to lists of open file data
                Example:
                {
                    "file_key": [{
                        "type":"single_cell",
                        "id":"b2005457-dede-4434-a9c3-dbe41fcd542e",
                        "path":"A Coding and Non-Coding Atlas of the Human Arterial Cell/slide-seqV2 analysis of aorta.h5ad",
                        "extension":"h5ad"
                    }]
                }
            userdata_file_data (dict, optional): Org-shared S3 files. Use for files from org
                members' integrated S3 buckets. No credentials needed -- server handles auth.
                Example:
                {
                    "file_key": [{"path": "s3/key/file.csv", "shared_user_id": "owner_user_id"}]
                }
            title (str, optional): Human-readable title for the job
            group_id (str, optional): Group ID for job grouping/filtering. Falls back to self.job_group_id if not provided.

        Returns:
            dict: Response from the API containing job details
                Example:
                {
                    "job_id": "job_123abc..."
                }

        Raises:
            Exception: If job submission fails
        """
        if config is None:
            config = {}

        payload = {
            "library_name_id": external_tool_library_name,
            "tool_name": tool_name,
            "partial_job_submit": True,
            "config": json.dumps(config),
            "group_id": group_id or self.job_group_id,
        }
        if title:
            payload["title"] = title

        if input_paths is not None:
            other_files = (local_files, remote_file_source_data, datahub_file_data,
                           datahub_result_file_data, open_file_data, userdata_file_data)
            if any(other_files):
                raise ValueError("input_paths cannot be combined with other file arguments")
            if not isinstance(input_paths, dict) or not input_paths:
                raise ValueError("input_paths must map file keys to file paths")
            payload["input_paths"] = json.dumps(input_paths)
            return self._request("POST", "api/jobs/external_tool", data=payload)

        if local_files is None:
            local_files = {}

        formatted_datahub_file_data = format_datahub_file_data(datahub_file_data)
        formatted_datahub_result_file_data = format_datahub_file_data(datahub_result_file_data)
        formatted_open_file_data = format_open_file_data(open_file_data)
        formatted_userdata_file_data = format_userdata_file_data(userdata_file_data)
        remote_file_source_data = json.dumps(remote_file_source_data)
        formatted_datahub_file_data = json.dumps(formatted_datahub_file_data)
        formatted_datahub_result_file_data = json.dumps(formatted_datahub_result_file_data)
        formatted_open_file_data = json.dumps(formatted_open_file_data)
        formatted_userdata_file_data = json.dumps(formatted_userdata_file_data)

        response = self._request("POST", "api/jobs/external_tool", data=payload)

        partial_job_id = response["job_id"]

        headers, open_files, monitor = create_patch_partial_job_payload(partial_job_id, self.auth.token, local_files, remote_file_source_data, formatted_datahub_file_data, formatted_datahub_result_file_data, formatted_open_file_data, formatted_userdata_file_data)

        res = self._request("PATCH", f"api/jobs/{partial_job_id}", headers=headers, data=monitor, stream=True)

        for file_obj in open_files.values():
            file_obj[1].close()

        return res
