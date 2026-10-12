Uploading Large Files
=====================

The browser accepts up to 10 GB at a time. For larger data, upload from your computer with the
``superbio`` command line tool or the Python client. Files are sent directly to storage in
parallel parts, so throughput is limited only by your connection.

If the upload is interrupted (network drop, closed laptop), run the same command again within
24 hours: it continues from the parts already uploaded.

Command line
------------

Installing the package adds a ``superbio`` command. Credentials come from environment variables:

.. code-block:: bash

   export SUPERBIO_EMAIL="your@email.com"
   export SUPERBIO_PASSWORD="your_password"

   # Upload a file to the Data Hub root
   superbio upload sample.bam

   # Upload a folder (recursively) into the "projects" folder
   superbio upload ./run_42 projects

   # Upload to your organisation's shared Data Hub with 16 parallel parts
   superbio upload sample.bam --org --concurrency 16

Instead of an email and password you can set ``SUPERBIO_TOKEN`` and ``SUPERBIO_USER_ID``.

Python
------

.. code-block:: python

   from superbio import Client

   client = Client("your@email.com", "your_password")
   client.upload_to_datahub(
       path="projects",
       local_files={"reads": "run_42/"},
   )

Pass ``on_progress=None`` to silence progress output, or a callable
``on_progress(file_name, uploaded_bytes, total_bytes)`` to report it yourself.

Storage and S3
--------------

Uploads count toward your Data Hub storage quota. If your data is already in Amazon S3, connect
the bucket in the Data Hub instead: its files are available to apps and the assistant without
copying and do not count toward the quota.
