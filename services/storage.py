from google.cloud import storage
from datetime import timedelta
import os

from dotenv import load_dotenv
load_dotenv(override=True)

GOOGLE_STORAGE_BUCKET_NAME = os.getenv("GOOGLE_STORAGE_BUCKET_NAME")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

storage_client = storage.Client()

def uploudFile(file, content_type: str = "", name: str = ""):
    destination_blob_name = f"{name}"

    bucket = storage_client.bucket(GOOGLE_STORAGE_BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(file, content_type=content_type)

    gs_uri = f"gs://{GOOGLE_STORAGE_BUCKET_NAME}/{destination_blob_name}"
    gs_uri_public = blob.public_url

    return {
        'gs_uri': gs_uri,
        'gs_uri_public': gs_uri_public
    }

def uploudFileStream(file, name: str = ""):
    destination_blob_name = f"{name}/{file.filename}"
    bucket = storage_client.bucket(GOOGLE_STORAGE_BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_file(file.file, content_type=file.content_type)

    gs_uri = f"gs://{GOOGLE_STORAGE_BUCKET_NAME}/{destination_blob_name}"
    gs_uri_public = blob.public_url

    return {
        'gs_uri': gs_uri,
        'gs_uri_public': gs_uri_public
    }


def allowedEncodingFile(extension):
    allowed = ['.pdf']
    return True if extension in allowed else False

def getMimeTypeFromGcs(gcs_uri):
    uri_parts = gcs_uri.replace("gs://", "").split("/", 1)
    bucket_name = uri_parts[0]
    blob_name = uri_parts[1]

    client = storage.Client()

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    blob.reload()
    mime_type = blob.content_type

    return mime_type

def getDirectoryNameFromGcs(gs_uri):
    path = gs_uri.replace("gs://", "")
    
    parts = path.split('/')
    
    if len(parts) > 2:
        return parts[1]
    else:
        return None

def generateSignedUrl(bucket_name, blob_name, expiration=3600):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    signed_url = blob.generate_signed_url(expiration=timedelta(seconds=expiration))
    return signed_url