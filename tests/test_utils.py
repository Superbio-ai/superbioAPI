import pytest
from datetime import datetime
from superbio.utils import data_validation, get_missing_values, job_post_validation

def test_data_validation_valid_dates():
    valid_dates = ["01/01/2023", "31/12/2023"]
    assert data_validation(valid_dates) is True

def test_data_validation_invalid_dates():
    invalid_dates = ["2023/01/01", "13/13/2023"]
    with pytest.raises(ValueError, match="Invalid date format"):
        data_validation(invalid_dates)

def test_get_missing_values():
    required = ["a", "b", "c"]
    provided = ["a", "c"]
    assert get_missing_values(required, provided) == ["b"]

def test_job_post_validation_valid(sample_app_config):
    job_config = {
        "analysis": "test",
        "index_column": True
    }
    local_files = ["control", "experiment"]
    
    # Should not raise any exceptions
    job_post_validation(
        sample_app_config,
        job_config,
        local_files,
        None,
        None,
        None,
        None,
        "cpu"
    )

def test_job_post_validation_missing_required(sample_app_config):
    job_config = {
        "index_column": True  # Missing required 'analysis'
    }
    local_files = ["control", "experiment"]
    
    with pytest.raises(Exception, match="Missing the following parameter values"):
        job_post_validation(
            sample_app_config,
            job_config,
            local_files,
            None,
            None,
            None,
            None,
            "cpu"
        )

def test_job_post_validation_invalid_mode(sample_app_config):
    job_config = {
        "analysis": "test",
        "index_column": True
    }
    local_files = ["control", "experiment"]
    
    with pytest.raises(Exception, match="Invalid running mode"):
        job_post_validation(
            sample_app_config,
            job_config,
            local_files,
            None,
            None,
            None,
            None,
            "invalid_mode"
        )

def test_job_post_validation_missing_files(sample_app_config):
    job_config = {
        "analysis": "test",
        "index_column": True
    }
    local_files = ["control"]  # Missing 'experiment' file
    
    with pytest.raises(Exception, match="Missing the following files"):
        job_post_validation(
            sample_app_config,
            job_config,
            local_files,
            None,
            None,
            None,
            None,
            "cpu"
        )

def test_job_post_validation_unsupported_mode(sample_app_config):
    # Modify sample config to only support CPU
    sample_app_config["running_modes"] = [{"mode_id": 1}]
    
    job_config = {
        "analysis": "test",
        "index_column": True
    }
    local_files = ["control", "experiment"]
    
    with pytest.raises(Exception):
        job_post_validation(
            sample_app_config,
            job_config,
            local_files,
            None,
            None,
            None,
            None,
            "gpu"
        )

def test_job_post_validation_mixed_file_sources(sample_app_config):
    job_config = {
        "analysis": "test",
        "index_column": True
    }
    local_files = ["control"]
    remote_files = ["experiment"]
    
    # Should not raise any exceptions when files come from different sources
    job_post_validation(
        sample_app_config,
        job_config,
        local_files,
        remote_files,
        None,
        None,
        None,
        "cpu"
    )

def test_data_validation_none_dates():
    # Should handle None values without raising exception
    assert data_validation([None, None]) is True 