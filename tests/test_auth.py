import pytest
import requests
from unittest.mock import patch, MagicMock
from superbio.auth import AuthManager


@pytest.fixture
def mock_auth_response():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "test_token",
        "id": "test_user_id"
    }
    return mock_response


def test_auth_manager_initialization(mock_credentials):
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            "access_token": mock_credentials['token'],
            "id": mock_credentials['user_id']
        }

        auth = AuthManager(
            "http://test.com",
            mock_credentials['email'],
            mock_credentials['password']
        )

        assert auth.token == mock_credentials['token']
        assert auth.user_id == mock_credentials['user_id']


def test_auth_manager_failed_login():
    """Test handling of failed authentication"""
    with patch('requests.post') as mock_post:
        # Create a mock response with 401 status code
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_error = requests.exceptions.HTTPError(response=mock_response)
        mock_post.side_effect = mock_error

        with pytest.raises(PermissionError, match="Authentication failed"):
            AuthManager(
                "http://test.com",
                "invalid@email.com",
                "wrong_password"
            )


def test_auth_manager_other_http_error():
    """Test handling of non-auth HTTP errors"""
    with patch('requests.post') as mock_post:
        # Create a mock response with 500 status code
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_error = requests.exceptions.HTTPError(response=mock_response)
        mock_post.side_effect = mock_error

        with pytest.raises(requests.exceptions.HTTPError):
            AuthManager(
                "http://test.com",
                "test@example.com",
                "password"
            )


def test_auth_manager_with_token(mock_credentials):
    """Test initialization with an existing token"""
    with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
        # Setup mock response for token validation
        mock_get.return_value.status_code = 200
        
        auth = AuthManager(
            "http://test.com",
            mock_credentials['email'],
            mock_credentials['password'],
            token=mock_credentials['token'],
            user_id=mock_credentials['user_id']
        )
        
        mock_get.assert_called_once()
        mock_post.assert_not_called()
        assert auth.token == mock_credentials['token']


def test_auth_manager_invalid_response():
    """Test handling of invalid response format"""
    with patch('requests.post') as mock_post:
        # Mock a successful response but with missing fields
        mock_response = MagicMock()
        mock_response.status_code = 200  # Successful response
        mock_response.raise_for_status.return_value = None  # Won't raise an error
        mock_response.json.return_value = {}  # Missing required fields
        mock_post.return_value = mock_response
        
        with pytest.raises(PermissionError, match="Invalid response from server"):
            AuthManager(
                "http://test.com",
                "test@example.com",
                "password"
            )


def test_auth_manager_partial_response():
    """Test handling of response with only some required fields"""
    with patch('requests.post') as mock_post:
        # Mock a response with only one of the required fields
        mock_response = MagicMock()
        mock_response.status_code = 200  # Successful response
        mock_response.raise_for_status.return_value = None  # Won't raise an error
        mock_response.json.return_value = {"access_token": "token"}  # Missing id
        mock_post.return_value = mock_response
        
        with pytest.raises(PermissionError, match="Invalid response from server"):
            AuthManager(
                "http://test.com",
                "test@example.com",
                "password"
            )
