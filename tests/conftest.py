import pytest
from unittest.mock import patch
from superbio.client import Client

@pytest.fixture(autouse=True)
def no_requests(monkeypatch):
    """Prevent any real HTTP requests from being made during tests."""
    with patch('requests.request'), patch('requests.post'):
        yield

@pytest.fixture
def mock_credentials():
    return {
        'email': 'test@example.com',
        'password': 'test_password',
        'token': 'test_token',
        'user_id': 'test_user_id'
    }

@pytest.fixture
def mock_client(mock_credentials, no_requests):
    with patch('superbio.client.AuthManager') as mock_auth:
        mock_auth.return_value.token = mock_credentials['token']
        mock_auth.return_value.user_id = mock_credentials['user_id']
        client = Client(
            email=mock_credentials['email'],
            password=mock_credentials['password']
        )
        return client

@pytest.fixture
def sample_app_config():
    return {
        "parameter_settings": {
            "parameters": [
                {"field_name": "analysis", "optional": False},
                {"field_name": "index_column", "optional": True}
            ]
        },
        "file_settings": [
            {"name": "control", "optional": False},
            {"name": "experiment", "optional": False},
            {"name": "optional_file", "optional": True}
        ],
        "running_modes": [
            {"mode_id": 1},  # CPU
            {"mode_id": 2}   # GPU
        ]
    } 