from typing import List

from src.exceptions import StorageConnectionError, StorageError
from src.models.game import GameEntry
from src.models.remote_config import CredentialField, RemoteConfig
from src.storage.base import register_storage
from src.storage.bundle import BundleStorage


@register_storage("s3")
class S3Storage(BundleStorage):
    """
    Any S3-compatible object storage: AWS S3, Cloudflare R2, MinIO,
    Yandex Object Storage, etc.

    Options:
      bucket            (required) bucket name
      endpoint_url      (optional) custom endpoint for R2/MinIO/etc
      region            (optional)
      prefix            (optional) key prefix
    Secrets:
      access_key_id / secret_access_key  (stored in the OS keyring)
    """

    FIELDS = (
        CredentialField(name="bucket", prompt="S3 bucket name"),
        CredentialField(
            name="endpoint_url",
            prompt="Endpoint URL (blank = AWS)",
            required=False,
        ),
        CredentialField(
            name="region", prompt="Region (optional)", required=False
        ),
        CredentialField(
            name="prefix", prompt="Key prefix (optional)", required=False
        ),
        CredentialField(
            name="access_key_id", prompt="Access key ID", secret=True
        ),
        CredentialField(
            name="secret_access_key", prompt="Secret access key", secret=True
        ),
    )

    def __init__(self, config: RemoteConfig, game: GameEntry):
        super().__init__(config=config, game=game)
        if not self.option("bucket"):
            raise StorageError("s3 storage requires 'bucket' option")

    def _client(self):
        try:
            # TODO: Add stubs
            import boto3  # type: ignore[import-untyped]
        except ImportError as ex:  # pragma: no cover
            raise StorageError(
                "boto3 is not installed - install it to use s3 remotes"
            ) from ex
        return boto3.client(
            "s3",
            endpoint_url=self.option("endpoint_url") or None,
            region_name=self.option("region") or None,
            aws_access_key_id=self.secret("access_key_id"),
            aws_secret_access_key=self.secret("secret_access_key"),
        )

    def test_connection(self) -> None:
        try:
            self._client().head_bucket(Bucket=self.option("bucket"))
        except Exception as ex:
            raise StorageConnectionError(
                f"S3 bucket check failed: {ex}"
            ) from ex

    def push(self, artifact_path: str, remote_name: str) -> None:
        try:
            with open(artifact_path, "rb") as data:
                self._client().put_object(
                    Bucket=self.option("bucket"),
                    Key=remote_name,
                    Body=data,
                )
        except Exception as ex:
            raise StorageError(f"S3 upload failed: {ex}") from ex

    def pull(self, remote_name: str, local_path: str) -> None:
        try:
            obj = self._client().get_object(
                Bucket=self.option("bucket"), Key=remote_name
            )
            stream = obj["Body"]
            with open(local_path, "wb") as f:
                for chunk in stream.iter_chunks(1024 * 512):
                    f.write(chunk)
        except Exception as ex:
            raise StorageError(f"S3 download failed: {ex}") from ex

    def list_artifacts(self, prefix: str = "") -> List[str]:
        base = prefix or self._base()
        try:
            resp = self._client().list_objects_v2(
                Bucket=self.option("bucket"), Prefix=base + "/"
            )
            return sorted(
                obj["Key"]
                for obj in resp.get("Contents", [])
                if obj["Key"].endswith(".bundle")
            )
        except Exception as ex:
            raise StorageError(f"S3 listing failed: {ex}") from ex
