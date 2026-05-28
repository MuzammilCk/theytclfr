"""Quick S3 connectivity test."""
from ytclfr.core.config import get_settings
from ytclfr.ingestion.s3_storage import S3StorageManager

s = get_settings()
mgr = S3StorageManager(s)

print(f"Region:  {s.aws_region}")
print(f"Bucket:  {mgr.bucket_name}")

try:
    resp = mgr._client.list_objects_v2(Bucket=mgr.bucket_name, MaxKeys=1)
    print(f"Status:  CONNECTED OK")
    print(f"Objects: {resp.get('KeyCount', 0)}")
except Exception as e:
    print(f"ERROR:   {e}")
