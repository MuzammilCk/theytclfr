import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from ytclfr.core.config import get_settings
from ytclfr.ingestion.s3_storage import S3StorageManager

def test_s3():
    settings = get_settings()
    manager = S3StorageManager(settings)
    
    test_prefix = "health-check-test"
    object_key = f"{test_prefix}/test.txt"
    test_file_path = Path("test_upload.txt")
    download_file_path = Path("test_download.txt")
    
    # 1. Create a dummy file
    test_file_path.write_text("hello aws integration")
    
    try:
        # 2. Upload file
        print(f"Uploading file to {object_key}...")
        s3_uri = manager.upload_file(test_file_path, object_key)
        print(f"Uploaded successfully. URI: {s3_uri}")
        
        # 3. Download file
        print(f"Downloading file from {object_key}...")
        manager.download_file(object_key, download_file_path)
        content = download_file_path.read_text()
        assert content == "hello aws integration", "Downloaded content mismatch"
        print("Downloaded successfully.")
        
        # 4. Delete directory
        print(f"Deleting prefix {test_prefix}...")
        manager.delete_directory(test_prefix)
        print("Deleted successfully.")
        
    finally:
        if test_file_path.exists():
            test_file_path.unlink()
        if download_file_path.exists():
            download_file_path.unlink()

if __name__ == "__main__":
    test_s3()
