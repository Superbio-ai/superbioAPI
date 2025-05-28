Examples
========

Working with Apps
----------------

.. code-block:: python

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

Job Management
-------------

.. code-block:: python

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

Credit Management
---------------

.. code-block:: python

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