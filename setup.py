from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="superbio",
    version="0.1.7",
    author="Superbio",
    author_email="dmason@superbio.ai",
    description="Python client for the Superbio API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Superbio-ai/superbioAPI",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'tests': ['test_files/*'],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.25.0",
        "requests-toolbelt>=0.9.1"
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-mock>=3.10.0",
            "requests-mock>=1.10.0",
            "coverage>=7.0.0"
        ]
    }
)
