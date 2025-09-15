import requests


class AuthManager:
    def __init__(self, base_url, email, password, token=None, user_id=None):
        self.base_url = base_url
        self.email = email
        self.password = password
        self.token = token
        self.user_id = user_id
        self.login()

    def login(self):
        if self.user_id and self.token:
            headers = {}
            headers.update({"Authorization": f"Bearer {self.token}"})
            response = requests.get(
                f"{self.base_url}/api/users/{self.user_id}", headers=headers
            )
            if response.status_code == 200:
                return
            else:
                raise PermissionError(
                    "Invalid user_id or token. Please login again."
                )
        try:
            response = requests.post(
                f"{self.base_url}/login", json={"email": self.email, "password": self.password}
            )
            response.raise_for_status()
            response_json = response.json()
            
            # Check for required fields in response
            if not response_json.get("access_token") or not response_json.get("id"):
                raise PermissionError(
                    "Invalid response from server. Missing required authentication fields.")
            
            self.token = response_json["access_token"]
            self.user_id = response_json["id"]
            
        except requests.exceptions.HTTPError as e:
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 401:
                raise PermissionError(
                    "Authentication failed. Please check your credentials or refresh your token.") from e
            raise  # Re-raise other HTTP errors
