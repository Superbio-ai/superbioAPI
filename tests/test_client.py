import pytest
from unittest.mock import patch, MagicMock
from superbio.client import Client, RUNNING_MODE
import os
import pathlib
from pathlib import Path


def test_client_initialization(mock_credentials):
    """Test that Client properly initializes AuthManager"""
    with patch('superbio.client.AuthManager') as mock_auth:
        mock_auth.return_value.token = mock_credentials['token']
        mock_auth.return_value.user_id = mock_credentials['user_id']
        
        client = Client(
            email=mock_credentials['email'],
            password=mock_credentials['password']
        )
        
        # Verify AuthManager was created with correct parameters
        mock_auth.assert_called_once_with(
            Client.BASE_URL,
            mock_credentials['email'],
            mock_credentials['password'],
            None, None
        )
        
        # Verify client has the mock auth instance
        assert client.auth is mock_auth.return_value


def test_get_jobs(mock_client):
    with patch.object(mock_client, '_request') as mock_request:
        mock_request.return_value = {"hits": []}

        response = mock_client.get_jobs(
            page=1,
            hits_per_page=100,
            status="completed"
        )

        mock_request.assert_called_once()
        assert "hits" in response


def test_get_jobs_invalid_status(mock_client):
    with pytest.raises(ValueError, match="Invalid status"):
        mock_client.get_jobs(status="invalid")


def test_get_app_parameters(mock_client):
    app_id = "test_app_id"
    mock_response = {
        "config": {"test": "config"},
        "running_modes": [{"mode_id": 1}]
    }

    with patch.object(mock_client, '_request') as mock_request:
        mock_request.return_value = mock_response

        response = mock_client.get_app_parameters(app_id)

        mock_request.assert_called_once_with(
            "GET",
            f"api/apps/{app_id}"
        )
        assert "test" in response
        assert "running_modes" in response


@pytest.fixture
def test_files_dir():
    return os.path.join(os.path.dirname(__file__), 'test_files')

sample_app_config = {
    "parameter_settings": {
        "parameters": [{"field_name": "analysis", "optional": False}]
    },
    "file_settings": [],
    "running_modes": [{"mode_id": 1}]
}

def test_post_job(mock_client, test_files_dir):
    with patch.object(mock_client, '_request') as mock_request, \
            patch.object(mock_client, 'get_app_parameters') as mock_get_params:
        mock_get_params.return_value = sample_app_config
        mock_request.return_value = {"job_id": "test_job_id"}

        response = mock_client.post_job(
            app_id="test_app_id",
            running_mode="cpu",
            config={"analysis": "test"},
            local_files={
                "control": os.path.join(test_files_dir, "deg_background_preprocessed.csv"),
                "experiment": os.path.join(test_files_dir, "deg_experimental_preprocessed.csv")
            }
        )

        assert response["job_id"] == "test_job_id"


def test_download_job_result_file(mock_client, tmp_path):
    download_dir = tmp_path / "test_download_job_result_file0"
    download_dir.mkdir(exist_ok=True)
    download_path = download_dir / "test_file.txt"
    
    with open(download_path, 'w') as f:
        f.write("test content")
    
    mock_client.download_job_result_file(
        "test_job_id",
        "test_file.txt",
        str(download_dir)
    )
    
    assert download_path.exists()


def test_download_job_result_file_error(mock_client, tmp_path):
    with patch.object(mock_client, '_request') as mock_request:
        mock_request.side_effect = Exception("Download Error")

        with pytest.raises(Exception, match="There was a problem downloading this result file"):
            mock_client.download_job_result_file(
                "test_job_id",
                "test_file.txt",
                str(tmp_path)
            )


def test_delete_job(mock_client):
    with patch.object(mock_client, '_request') as mock_request:
        mock_request.return_value = {"status": "success"}

        response = mock_client.delete_job("test_job_id")

        mock_request.assert_called_once_with(
            "DELETE",
            "api/jobs/test_job_id"
        )
        assert response["status"] == "success"


def test_get_balances(mock_client):
    with patch.object(mock_client, '_request') as mock_request:
        mock_request.return_value = {"credits": 100}

        response = mock_client.get_balances()

        mock_request.assert_called_once_with(
            "GET",
            f"api/users/{mock_client.auth.user_id}/balances"
        )
        assert "credits" in response


def test_get_app_list(mock_client):
    with patch.object(mock_client, '_request') as mock_request:
        mock_request.return_value = {"hits": []}

        response = mock_client.get_app_list(
            page=1,
            hits_per_page=100,
            search_string="test"
        )

        mock_request.assert_called_once()
        assert "hits" in response


def test_download_all_job_results(mock_client, tmp_path):
    mock_results = {
        "download": [{"file": "results.zip", "title": "Results!"}],
        "figures": [[{"file": "plot.png", "title": "Plot!"}]]
    }

    with patch.object(mock_client, 'list_job_result_files') as mock_list_files, \
            patch.object(mock_client, 'download_job_result_file') as mock_download:
        mock_list_files.return_value = mock_results

        # Test compressed download
        mock_client.download_all_job_results(
            "test_job_id",
            str(tmp_path),
            download_compressed=True
        )
        mock_download.assert_called_once()

        # Test uncompressed download
        mock_client.download_all_job_results(
            "test_job_id",
            str(tmp_path),
            download_compressed=False
        )
        assert mock_download.call_count > 1


def test_request_method(mock_client):
    with patch('requests.request') as mock_request:
        mock_request.return_value.json.return_value = {"test": "data"}

        response = mock_client._request(
            "GET",
            "test/endpoint",
            params={"test": "param"}
        )

        mock_request.assert_called_once_with(
            "GET",
            f"{mock_client.BASE_URL}/test/endpoint",
            data=None,
            json=None,
            params={"test": "param"},
            files=None,
            headers={"Authorization": f"Bearer {mock_client.auth.token}"},
            stream=False
        )
        assert response == {"test": "data"}


def test_list_job_result_files_error(mock_client):
    with patch.object(mock_client, '_request') as mock_request:
        mock_request.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="There was a problem finding your job"):
            mock_client.list_job_result_files("invalid_job_id")


def test_create_callback(capsys):
    from superbio.utils import create_callback
    from requests_toolbelt import MultipartEncoder

    encoder = MultipartEncoder(fields={"test": "data"})
    callback = create_callback(encoder)

    class MockMonitor:
        def __init__(self):
            self.bytes_read = 50

    monitor = MockMonitor()
    callback(monitor)

    captured = capsys.readouterr()
    assert "Upload Progress: " in captured.out
