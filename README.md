# Superbio Python Client

Official Python client for the [Superbio](https://app.superbio.ai) platform API. Access bioinformatics tools and AI models programmatically.

## Installation

```bash
pip install superbio
```

## Quick Start

```python
from superbio import Client

# Initialize client
client = Client("your@email.com", "your_password")

# List available apps
apps = client.get_app_list()

# Get app parameters
app_params = client.get_app_parameters("app_id")

# Submit a job with local files
job = client.post_job(
    app_id="app_id",
    running_mode="cpu",
    config={"param": "value"},
    local_files={"file_key": "path/to/file"}
)
```

## Submit a job with S3 files

```python
job = client.post_job(
    app_id="app_id",
    running_mode="cpu",
    config={"param": "value"},
    remote_file_source_data={
        "file_key": [{
            "protocol": "s3",
            "credentials": {
                "aws_access_key_id": "YOUR_ACCESS_KEY",
                "aws_secret_access_key": "YOUR_SECRET_KEY"
            },
            "path": "bucket/path/to/file.csv"
        }]
    }
)
```

Check job status

```python
status = client.get_job_status("job_id")
```

Download results

```python
client.download_job_results("job_id", "output_directory")
```

## Features

- Browse and search available bioinformatics applications
- Get detailed app configurations and parameters
- Submit computational jobs with:
  - Local files
  - Remote files (S3)
  - Files from Superbio DataHub
- Monitor job status and progress
- Download and manage results
- Track credit balances and usage

## Authentication

You must first create an account at [app.superbio.ai](https://app.superbio.ai). Your email and password from the platform will be used to authenticate API requests.

<!-- ## Documentation

For complete API documentation and examples, visit [docs.superbio.ai](https://docs.superbio.ai). -->

## Examples

### Working with Apps

```python
# Get list of all apps
apps = client.get_app_list()

# List apps with pagination and search
apps = client.get_app_list(
    hits_per_page=10,  # (optional) Number of results per page
    page=1,            # (optional) Page number
    search_string="genomics"  # (optional)Search by keyword
)

# Get app details and parameters
app_config = client.get_app_parameters("app_id")
```

### Job Management

```python
# List jobs with filters
jobs = client.get_jobs(
    hits_per_page=100,           # (optional) Number of jobs per page
    page=1,                      # (optional) Page number
    status="running",            # (optional) Filter by status: "running", "completed", "failed", etc.
    date_from="01/01/2024",      # (optional) Filter by start date (dd/mm/yyyy)
    date_to="31/01/2024",        # Filter by end date (dd/mm/yyyy)
    search_string="analysis"     # Search job titles
)

# Download specific result files
client.download_job_result_file(
    job_id="job_id",
    file_path="path/to/result.csv",  # Path of file in job results
    path_to_download_to="output_dir",         # Local directory to save file
)

# Download all results
client.download_all_job_results(
    job_id="job_id",
    path_to_download_to="output_dir",     # Local directory to save files
)

# Delete a job
client.delete_job("job_id")
```

### Credit Management

```python
# Get credit balances and usage info
balances = client.get_balances()
# Returns:
# {
#     "balances": {
#         "available_credits": 6000,
#         "credits": 6000,
#         "runs_left": 400,
#         "total_runs": 400,
#         "runtime_left": 72000.0,
#         "total_runtime": 72000,
#         "runs_reset_time": "Feb 28 2025, 23:08:05",
#         "runtime_reset_time": "Feb 28 2025, 23:08:05",
#         "tier": "free_organisation"
#     }
# }
```

## Support

For support, contact dmason@superbio.ai.

<!-- For support, contact dmason@superbio.ai or visit our [documentation](https://docs.superbio.ai). -->

<!-- ## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. -->
