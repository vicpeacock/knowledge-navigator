"""
Cloud Storage Service for persistent file storage on Cloud Run.
Uses Google Cloud Storage instead of ephemeral filesystem.
"""
import logging
from pathlib import Path
from typing import Optional
from uuid import UUID
import io

from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy import - only import if Cloud Storage is enabled
_storage_client = None
_bucket_name = None

def _get_storage_client():
    """Get or create Cloud Storage client (lazy initialization)"""
    global _storage_client, _bucket_name
    
    if not settings.use_cloud_storage:
        return None, None
    
    if _storage_client is None:
        try:
            from google.cloud import storage
            
            # Initialize client (will use default credentials or service account)
            _storage_client = storage.Client()
            _bucket_name = settings.cloud_storage_bucket_name
            
            if not _bucket_name:
                logger.warning("⚠️  Cloud Storage enabled but bucket name not configured")
                return None, None
            
            # Verify bucket exists
            try:
                bucket = _storage_client.bucket(_bucket_name)
                if not bucket.exists():
                    logger.error(f"❌ Cloud Storage bucket '{_bucket_name}' does not exist")
                    return None, None
                logger.info(f"✅ Cloud Storage initialized: bucket '{_bucket_name}'")
            except Exception as e:
                logger.error(f"❌ Error accessing Cloud Storage bucket: {e}")
                return None, None
                
        except ImportError:
            logger.warning("⚠️  google-cloud-storage not installed. Install with: pip install google-cloud-storage")
            return None, None
        except Exception as e:
            logger.error(f"❌ Error initializing Cloud Storage: {e}", exc_info=True)
            return None, None
    
    return _storage_client, _bucket_name


def _get_blob_path(user_id: UUID, file_id: UUID, filename: str) -> str:
    """
    Generate Cloud Storage blob path for a file.
    Format: users/{user_id}/{file_id}{extension}
    """
    file_extension = Path(filename).suffix
    return f"users/{user_id}/{file_id}{file_extension}"


async def upload_file_to_cloud_storage(
    file_content: bytes,
    user_id: UUID,
    file_id: UUID,
    filename: str,
    content_type: Optional[str] = None,
) -> Optional[str]:
    """
    Upload file to Cloud Storage.
    Returns the Cloud Storage path (gs://bucket/path) if successful, None otherwise.
    """
    client, bucket_name = _get_storage_client()
    
    if not client or not bucket_name:
        logger.warning("⚠️  Cloud Storage not available, falling back to filesystem")
        return None
    
    try:
        bucket = client.bucket(bucket_name)
        blob_path = _get_blob_path(user_id, file_id, filename)
        blob = bucket.blob(blob_path)
        
        # Set content type if provided
        if content_type:
            blob.content_type = content_type
        
        # Upload file content
        blob.upload_from_string(file_content, content_type=content_type)
        
        # Return GCS path
        gcs_path = f"gs://{bucket_name}/{blob_path}"
        logger.info(f"✅ File uploaded to Cloud Storage: {gcs_path}")
        return gcs_path
        
    except Exception as e:
        logger.error(f"❌ Error uploading file to Cloud Storage: {e}", exc_info=True)
        return None


async def download_file_from_cloud_storage(
    gcs_path: str,
) -> Optional[bytes]:
    """
    Download file from Cloud Storage.
    Returns file content as bytes if successful, None otherwise.
    """
    client, bucket_name = _get_storage_client()
    
    if not client or not bucket_name:
        return None
    
    try:
        # Parse GCS path (gs://bucket/path or just path)
        if gcs_path.startswith("gs://"):
            path_parts = gcs_path[5:].split("/", 1)
            if len(path_parts) == 2:
                bucket_name_from_path, blob_path = path_parts
                if bucket_name_from_path != bucket_name:
                    logger.warning(f"⚠️  Bucket mismatch: expected {bucket_name}, got {bucket_name_from_path}")
            else:
                blob_path = gcs_path[5:]
        else:
            blob_path = gcs_path
        
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        if not blob.exists():
            logger.warning(f"⚠️  File not found in Cloud Storage: {blob_path}")
            return None
        
        # Download file content
        file_content = blob.download_as_bytes()
        logger.info(f"✅ File downloaded from Cloud Storage: {blob_path} ({len(file_content)} bytes)")
        return file_content
        
    except Exception as e:
        logger.error(f"❌ Error downloading file from Cloud Storage: {e}", exc_info=True)
        return None


async def delete_file_from_cloud_storage(gcs_path: str) -> bool:
    """
    Delete file from Cloud Storage.
    Returns True if successful, False otherwise.
    """
    client, bucket_name = _get_storage_client()
    
    if not client or not bucket_name:
        return False
    
    try:
        # Parse GCS path
        if gcs_path.startswith("gs://"):
            path_parts = gcs_path[5:].split("/", 1)
            if len(path_parts) == 2:
                bucket_name_from_path, blob_path = path_parts
                if bucket_name_from_path != bucket_name:
                    logger.warning(f"⚠️  Bucket mismatch: expected {bucket_name}, got {bucket_name_from_path}")
            else:
                blob_path = gcs_path[5:]
        else:
            blob_path = gcs_path
        
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        if blob.exists():
            blob.delete()
            logger.info(f"✅ File deleted from Cloud Storage: {blob_path}")
            return True
        else:
            logger.warning(f"⚠️  File not found in Cloud Storage for deletion: {blob_path}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error deleting file from Cloud Storage: {e}", exc_info=True)
        return False


def is_cloud_storage_path(filepath: str) -> bool:
    """Check if filepath is a Cloud Storage path (gs://...)"""
    return filepath.startswith("gs://")

