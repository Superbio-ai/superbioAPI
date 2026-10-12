import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from superbio.upload import DataHubUploader, iter_upload_targets, join_datahub_path

FILE_BYTES = b"0123456789"
PART_SIZE = 4


class FakeApi:
    """Records API calls and answers the upload endpoints for a 3-part file."""

    def __init__(self, uploaded_parts=None, refresh_error=None):
        self.calls = []
        self.uploaded_parts = uploaded_parts or {}
        self.refresh_error = refresh_error

    def __call__(self, method, endpoint, _json=None, **kwargs):
        self.calls.append((endpoint, _json))
        if endpoint == "api/data_hub/upload/initiate":
            return {
                "upload_token": "tok",
                "part_size": PART_SIZE,
                "num_parts": 3,
                "presigned_urls": [{"part_number": n, "url": f"https://s3/{n}"} for n in (1, 2, 3)],
            }
        if endpoint == "api/data_hub/upload/refresh":
            if self.refresh_error:
                raise self.refresh_error
            requested = _json.get("part_numbers") or [n for n in (1, 2, 3) if n not in self.uploaded_parts]
            return {
                "part_size": PART_SIZE,
                "num_parts": 3,
                "presigned_urls": [{"part_number": n, "url": f"https://s3/{n}?fresh"} for n in requested],
                "uploaded_parts_detail": [{"PartNumber": n, "ETag": e} for n, e in self.uploaded_parts.items()],
            }
        if endpoint == "api/data_hub/upload/complete":
            return {"status": "success", "file_name": "data.bin"}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    def endpoints(self):
        return [endpoint for endpoint, _ in self.calls]

    def payload(self, endpoint):
        return next(body for name, body in self.calls if name == endpoint)


class FakeS3:
    """Stands in for presigned PUTs; stores the bytes received per URL."""

    def __init__(self, failures=0):
        self.received = {}
        self.failures = failures

    def __call__(self, url, data=None):
        if self.failures:
            self.failures -= 1
            raise requests.ConnectionError("network down")
        self.received[url] = data.read()
        response = MagicMock()
        response.headers = {"ETag": f'"etag-{url.rsplit("/", 1)[1].split("?")[0]}"'}
        return response


@pytest.fixture
def data_file(tmp_path):
    path = tmp_path / "data.bin"
    path.write_bytes(FILE_BYTES)
    return str(path)


@pytest.fixture
def state_dir(tmp_path):
    return tmp_path / "state"


def make_uploader(api, state_dir):
    return DataHubUploader(api, concurrency=1, on_progress=None, state_dir=state_dir)


def test_fresh_upload_streams_every_part_and_completes(data_file, state_dir):
    api, s3 = FakeApi(), FakeS3()
    with patch("superbio.upload.requests.put", side_effect=s3):
        result = make_uploader(api, state_dir).upload_file(data_file, "personal_data", "runs")

    assert result["status"] == "success"
    assert api.payload("api/data_hub/upload/initiate") == {
        "namespace": "personal_data",
        "file_name": "data.bin",
        "file_size": len(FILE_BYTES),
        "file_path": "runs",
        "client": "sdk",
    }
    assert b"".join(s3.received[f"https://s3/{n}"] for n in (1, 2, 3)) == FILE_BYTES
    assert api.payload("api/data_hub/upload/complete") == {
        "upload_token": "tok",
        "parts": [{"PartNumber": n, "ETag": f'"etag-{n}"'} for n in (1, 2, 3)],
        "file_size": len(FILE_BYTES),
    }
    assert list(state_dir.iterdir()) == []


def test_resume_uploads_only_missing_parts(data_file, state_dir):
    api, s3 = FakeApi(uploaded_parts={1: '"etag-1"'}), FakeS3()
    uploader = make_uploader(api, state_dir)
    uploader._save_state(uploader._state_path(data_file, "personal_data", ""), "tok")

    with patch("superbio.upload.requests.put", side_effect=s3):
        uploader.upload_file(data_file, "personal_data", "")

    assert "api/data_hub/upload/initiate" not in api.endpoints()
    assert sorted(s3.received) == ["https://s3/2?fresh", "https://s3/3?fresh"]
    parts = api.payload("api/data_hub/upload/complete")["parts"]
    assert [p["PartNumber"] for p in parts] == [1, 2, 3]


def test_resume_with_expired_token_starts_over(data_file, state_dir):
    api, s3 = FakeApi(refresh_error=requests.HTTPError("expired")), FakeS3()
    uploader = make_uploader(api, state_dir)
    uploader._save_state(uploader._state_path(data_file, "personal_data", ""), "old-tok")

    with patch("superbio.upload.requests.put", side_effect=s3):
        uploader.upload_file(data_file, "personal_data", "")

    assert "api/data_hub/upload/initiate" in api.endpoints()
    assert len(s3.received) == 3


def test_failed_part_is_retried_with_a_fresh_url(data_file, state_dir):
    api, s3 = FakeApi(), FakeS3(failures=1)
    with patch("superbio.upload.requests.put", side_effect=s3), patch("superbio.upload.time.sleep"):
        make_uploader(api, state_dir).upload_file(data_file, "personal_data", "")

    assert ("api/data_hub/upload/refresh", {"upload_token": "tok", "part_numbers": [1]}) in api.calls
    assert "https://s3/1?fresh" in s3.received


def test_failed_upload_keeps_state_for_resume(data_file, state_dir):
    api, s3 = FakeApi(), FakeS3(failures=100)
    with patch("superbio.upload.requests.put", side_effect=s3), patch("superbio.upload.time.sleep"):
        with pytest.raises(requests.ConnectionError):
            make_uploader(api, state_dir).upload_file(data_file, "personal_data", "")

    saved = list(state_dir.iterdir())
    assert len(saved) == 1
    assert json.loads(saved[0].read_text()) == {"upload_token": "tok"}
    assert "api/data_hub/upload/complete" not in api.endpoints()


def test_empty_file_is_rejected(tmp_path, state_dir):
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        make_uploader(FakeApi(), state_dir).upload_file(str(empty), "personal_data", "")


def test_concurrency_must_be_positive():
    with pytest.raises(ValueError, match="concurrency"):
        DataHubUploader(FakeApi(), concurrency=0)


def test_progress_reports_cumulative_bytes(data_file, state_dir):
    progress = []
    uploader = DataHubUploader(
        FakeApi(),
        concurrency=1,
        on_progress=lambda name, done, total: progress.append((name, done, total)),
        state_dir=state_dir,
    )
    with patch("superbio.upload.requests.put", side_effect=FakeS3()):
        uploader.upload_file(data_file, "personal_data", "")

    assert progress == [("data.bin", 0, 10), ("data.bin", 4, 10), ("data.bin", 8, 10), ("data.bin", 10, 10)]


def test_iter_upload_targets_for_file(data_file):
    assert list(iter_upload_targets(data_file, "/runs/")) == [(data_file, "runs")]


def test_iter_upload_targets_walks_folder_and_keeps_structure(tmp_path):
    root = tmp_path / "sample"
    (root / "reads").mkdir(parents=True)
    (root / "meta.csv").write_text("a")
    (root / "reads" / "r1.fastq").write_text("b")

    targets = list(iter_upload_targets(str(root), "projects"))

    assert targets == [
        (str(root / "meta.csv"), "projects/sample"),
        (str(root / "reads" / "r1.fastq"), "projects/sample/reads"),
    ]


def test_iter_upload_targets_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        list(iter_upload_targets(str(tmp_path / "missing")))


def test_join_datahub_path_drops_empty_segments():
    assert join_datahub_path("", "/a/", "", "b") == "a/b"


class TestClientUploadToDatahub:
    @staticmethod
    def _namespaces(*types):
        return {"namespaces": [{"type": t} for t in types]}

    @pytest.mark.parametrize(
        ("available", "is_organisation", "expected"),
        [
            (("personal_data",), False, "personal_data"),
            (("org_shared_data", "org_member_data"), False, "org_member_data"),
            (("org_shared_data", "org_member_data"), True, "org_shared_data"),
        ],
    )
    def test_uploads_to_the_right_namespace(self, mock_client, data_file, available, is_organisation, expected):
        with patch.object(mock_client, "_request", return_value=self._namespaces(*available)), \
                patch("superbio.client.DataHubUploader") as uploader_cls:
            uploader_cls.return_value.upload_file.return_value = {"status": "success"}

            results = mock_client.upload_to_datahub("runs", {"f": data_file}, is_organisation=is_organisation)

        assert results == [{"status": "success"}]
        uploader_cls.return_value.upload_file.assert_called_once_with(data_file, expected, "runs")

    def test_org_upload_without_organisation(self, mock_client, data_file):
        with patch.object(mock_client, "_request", return_value=self._namespaces("personal_data")):
            with pytest.raises(ValueError, match="organisation"):
                mock_client.upload_to_datahub("", {"f": data_file}, is_organisation=True)

    def test_remote_file_source_data_is_rejected(self, mock_client):
        with pytest.raises(ValueError, match="Connect your S3 bucket"):
            mock_client.upload_to_datahub("", remote_file_source_data={"f": [{"path": "b/k"}]})

    def test_local_files_are_required(self, mock_client):
        with pytest.raises(ValueError, match="local_files"):
            mock_client.upload_to_datahub("")


class TestCli:
    def test_upload_command(self, monkeypatch, data_file):
        from superbio import cli

        monkeypatch.setenv("SUPERBIO_EMAIL", "a@b.c")
        monkeypatch.setenv("SUPERBIO_PASSWORD", "pw")
        with patch.object(cli, "Client") as client_cls:
            client_cls.return_value.upload_to_datahub.return_value = [{"status": "success"}]

            exit_code = cli.main(["upload", data_file, "runs", "--org", "--concurrency", "2"])

        assert exit_code == 0
        client_cls.return_value.upload_to_datahub.assert_called_once_with(
            "runs", local_files={"upload": data_file}, is_organisation=True, concurrency=2
        )

    def test_upload_command_reports_api_errors(self, monkeypatch, data_file, capsys):
        from superbio import cli

        monkeypatch.setenv("SUPERBIO_TOKEN", "t")
        monkeypatch.setenv("SUPERBIO_USER_ID", "u")
        error = requests.HTTPError(response=MagicMock(text='{"code": "storage_quota_exceeded"}'))
        with patch.object(cli, "Client") as client_cls:
            client_cls.return_value.upload_to_datahub.side_effect = error

            exit_code = cli.main(["upload", data_file])

        assert exit_code == 1
        err = capsys.readouterr().err
        assert "storage_quota_exceeded" in err
        assert "resume" in err

    def test_missing_credentials(self, monkeypatch, data_file):
        from superbio import cli

        for name in ("SUPERBIO_EMAIL", "SUPERBIO_PASSWORD", "SUPERBIO_TOKEN", "SUPERBIO_USER_ID"):
            monkeypatch.delenv(name, raising=False)
        with pytest.raises(SystemExit, match="SUPERBIO_EMAIL"):
            cli.main(["upload", data_file])
