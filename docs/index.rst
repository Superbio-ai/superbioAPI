.. superbioAPI documentation master file, created by
   sphinx-quickstart on Wed May 28 20:13:00 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Superbio Python Client
=====================

Official Python client for the Superbio platform API. Access bioinformatics tools and AI models programmatically.

Installation
-----------

.. code-block:: bash

   pip install superbio

Quick Start
----------

.. code-block:: python

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

Features
--------

- Browse and search available bioinformatics applications
- Get detailed app configurations and parameters
- Submit computational jobs with:
  - Local files
  - Remote files (S3)
  - Files from Superbio DataHub
- Monitor job status and progress
- Download and manage results
- Track credit balances and usage

Authentication
-------------

You must first create an account at `app.superbio.ai <https://app.superbio.ai>`_. Your email and password from the platform will be used to authenticate API requests.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   quickstart
   features
   authentication
   examples
   api_reference
   support

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

