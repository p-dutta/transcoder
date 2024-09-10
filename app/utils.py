import json
#import logging
import requests
from datetime import datetime
from enum import Enum
from fastapi import Request, Depends, HTTPException
from google.cloud import storage
from google.cloud.video import transcoder_v1
from google.cloud.video.transcoder_v1.services.transcoder_service import (
    pagers,
    TranscoderServiceClient,
)
from google.cloud.video.transcoder_v1.types import JobTemplate
from google.oauth2 import service_account
from sqlalchemy.orm import Session
from typing import List, Any, Annotated

from .config import settings
from .database import get_db
from .exceptions import CustomException
from .custom_logger import logger

db_dependency = Annotated[Session, Depends(get_db)]


class JobStatusEnum(Enum):
    WAITING = "WAITING"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"


class JobStateEnum(Enum):
    INIT = "INIT"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ProtectionTypeEnum(Enum):
    AES128 = "aes128"
    DRM = "drm"
    BOTH = "both"


class DrmTypeEnum(Enum):
    WIDEVINE = "widevine"
    FAIRPLAY = "fairplay"


def get_gcp_transcoder_client() -> TranscoderServiceClient:
    #credentials = service_account.Credentials.from_service_account_file('../key_stage.json')
    credentials = service_account.Credentials.from_service_account_file('../key.json')
    client = TranscoderServiceClient(credentials=credentials)
    # client = TranscoderServiceClient()
    return client


def get_transcoder_client(request: Request) -> TranscoderServiceClient:
    return request.app.state.transcoder_client


def get_gcp_credentials(request: Request):
    return request.app.state.credentials


def pager_to_dict(pager: pagers.ListJobTemplatesPager) -> List[Any]:
    # Convert the pager object to a list of dictionaries
    # This requires knowledge of the structure of the objects in the pager
    result = []
    for item in pager:
        result.append(item.to_dict())
    return result


def job_template_to_dict(job_template: JobTemplate) -> dict:
    # Manually extract and return relevant fields from the JobTemplate object
    # This is an example, adjust according to the actual structure of JobTemplate
    return {
        "name": job_template.name,
        "config": job_template.config,  # or any other relevant fields
        # Add more fields as necessary
    }


def pager_to_list(pager: pagers.ListJobTemplatesPager) -> List[dict]:
    return [job_template_to_dict(job_template) for job_template in pager]


def build_jobs_data(jobs):
    """
    Construct a list of dictionaries representing job data.
    """
    for job in jobs:
        if isinstance(job.updated_at, str):
            job.updated_at = datetime.fromisoformat(job.updated_at)

    # Sort data by updated_time
    jobs.sort(key=lambda job: job.updated_at, reverse=True)

    jobs_data = [{
        "job_start_time": job.created_at,
        "job_end_time": job.updated_at,
        "job_id": job.job_id,
        "input_url": job.input_uri,
        "output_url": job.output_uri,
        "project_id": job.project_id,
        "content_id": job.content_id,
        "package_id": job.package_id,
        "description": job.description,
        "name": job.custom_name,
        "location": job.location,
        "created_by": job.created_by,
        "status": job.status,
        "state": job.state,
        "duration_in_seconds": job.duration_in_sec,
        "dash_media_cdn": settings.MEDIA_CDN_BASE + remove_bucket_name(
            job.output_uri) + "manifest_dash.mpd",
        "hls_media_cdn": settings.MEDIA_CDN_BASE + remove_bucket_name(
            job.output_uri) + "manifest_hls.m3u8"
    } for job in jobs]
    return jobs_data


def remove_bucket_name(url: str):
    if url.startswith("https://storage.cloud.google.com/"):
        url_without_scheme = url.replace('https://storage.cloud.google.com/', '')
    elif url.startswith("gs://"):
        url_without_scheme = url.replace('gs://', '')

    parts = url_without_scheme.split('/', 1)

    file_path = parts[1]
    return file_path

def create_job_from_template(
        client: TranscoderServiceClient,
        project_id: str,
        location: str,
        input_uri: str,
        output_uri: str,
        template_id: str,
) -> transcoder_v1.types.resources.Job:
    """Creates a job based on a job template.

    Args:
        client (TranscoderServiceClient): The client
        project_id: The GCP project ID.
        location: The location to start the job in.
        input_uri: Uri of the video in the Cloud Storage bucket.
        output_uri: Uri of the video output folder in the Cloud Storage bucket.
        template_id: The user-defined template ID.

    Returns:
        The job resource.
    """

    parent = f"projects/{project_id}/locations/{location}"
    job = transcoder_v1.types.Job()
    job.input_uri = input_uri
    job.output_uri = output_uri
    job.template_id = template_id

    response = client.create_job(parent=parent, job=job)
    print(f"Job: {response.name}")
    return response


def list_job_templates(
        client: TranscoderServiceClient,
        project_id: str,
        location: str,
) -> List[Any]:
    """Lists all job templates in a location.

    Args:
        client (TranscoderServiceClient): The client
        project_id: The GCP project ID.
        location: The location of the templates.

    Returns:
        An iterable object containing job template resources.
    """

    templates = []

    parent = f"projects/{project_id}/locations/{location}"
    response = client.list_job_templates(parent=parent)
    print("Job templates:")
    for jobTemplate in response.job_templates:
        # print({jobTemplate.name})
        # print(jobTemplate)
        # print(jobTemplate.config)
        templates.append(jobTemplate.name)

    return templates


def get_job_details(
        client: TranscoderServiceClient,
        project_id: str,
        location: str,
        job_id: str,
) -> transcoder_v1.types.resources.Job:
    """Gets a job.

    Args:
        client:
        project_id: The GCP project ID.
        location: The location this job is in.
        job_id: The job ID.

    Returns:
        The job resource.
    """

    name = f"projects/{project_id}/locations/{location}/jobs/{job_id}"
    response = client.get_job(name=name)
    #print(response.config.edit_list[0].end_time_offset)
    return response.config.edit_list[0].end_time_offset


def get_video_duration(client: TranscoderServiceClient, job_id: str):
    response = get_job_details(client, settings.PROJECT_ID, settings.LOCATION, job_id)

    time = response.total_seconds()
    return str(time)

def get_job_state(
        client: TranscoderServiceClient,
        project_id: str,
        location: str,
        job_id: str,
) -> transcoder_v1.types.resources.Job:
    """Gets a job's state.

    Args:
        client:
        project_id: The GCP project ID.
        location: The location this job is in.
        job_id: The job ID.

    Returns:
        The job resource.
    """

    # client = TranscoderServiceClient()

    name = f"projects/{project_id}/locations/{location}/jobs/{job_id}"
    response = client.get_job(name=name)

    print(f"Job state: {str(response.state.name)}")
    return response


def list_jobs(
        client: TranscoderServiceClient,
        project_id: str,
        location: str,
) -> pagers.ListJobsPager:
    """Lists all jobs in a location.

    Args:
        client:
        project_id: The GCP project ID.
        location: The location of the jobs.

    Returns:
        An iterable object containing job resources.
    """

    # client = TranscoderServiceClient()

    parent = f"projects/{project_id}/locations/{location}"
    response = client.list_jobs(parent=parent)
    print("Jobs:")
    for job in response.jobs:
        print({job.name})

    return response


def delete_job(
        client: TranscoderServiceClient,
        project_id: str,
        location: str,
        job_id: str,
) -> None:
    """Gets a job.

    Args:
        client: TranscoderServiceClient
        project_id: The GCP project ID.
        location: The location this job is in.
        job_id: The job ID."""

    # client = TranscoderServiceClient()

    name = f"projects/{project_id}/locations/{location}/jobs/{job_id}"
    client.delete_job(name=name)
    print("Deleted job")
    return None


def check_file_or_directory(url: str):
    # bucket_name = ""
    # file_name = ""
    # # Remove 'gs://' from the beginning
    # if url.startswith("https://"):
    #     url_without_gs = url.replace('https://', '')
    #     # Split the remaining string at the first '/'
    #     parts = url_without_gs.split('/')
    #
    #     # The first part will be the bucket name, and the second part will be the file path
    #     bucket_name = parts[1]
    #     file_name = parts[2]
    #     # client = storage.Client.from_service_account_json('./key.json')
    #     client = storage.Client()
    #     bucket = client.get_bucket(bucket_name)
    #     blob = bucket.blob(file_name)
    #     return blob.exists()
    # else:
    #     url_without_gs = url.replace('gs://', '')
    #     parts = url_without_gs.split('/')
    #     # The first part will be the bucket name, and the second part will be the file path
    #     bucket_name = parts[0]
    #     file_name = parts[1]
    #     # client = storage.Client.from_service_account_json('./key.json')
    #     client = storage.Client()
    #     bucket = client.get_bucket(bucket_name)
    #     blob = bucket.blob(file_name)
    #     return blob.exists()

    # client = storage.Client.from_service_account_json('./key.json')
    # client = storage.Client()
    # bucket = client.get_bucket(bucket_name)
    # blob = bucket.blob(file_name)
    # return blob.exists()

    # Determine if the URL is a GCS or HTTPS URL and adjust accordingly
    if url.startswith("https://storage.cloud.google.com/"):
        url_without_scheme = url.replace('https://storage.cloud.google.com/', '')
    elif url.startswith("gs://"):
        url_without_scheme = url.replace('gs://', '')
    else:
        print("Invalid URL schema")
        raise CustomException(code=404, status_code=20404, detail="Invalid URL scheme")

    # Split the URL into bucket name and file path
    parts = url_without_scheme.split('/', 1)
    if len(parts) < 2:
        print("Invalid URL schema")
        raise CustomException(code=404, status_code=20404, detail="Invalid URL scheme")

    bucket_name, file_path = parts[0], parts[1]

    # Initialize the storage client
    # client = storage.Client()
    #client = storage.Client.from_service_account_json('./key_stage.json')
    client = storage.Client.from_service_account_json('./key.json')
    try:
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(file_path)
    except Exception as e:
        print(e)
        raise CustomException(code=500, status_code=20500, detail=str(e))
    return blob.exists()


def create_directory(url: str, custom_name: str, content_id: str):
    current_datetime = datetime.now().strftime('%Y%m%d%H%M')
    # url_without_gs = url.replace('gs://', '')
    #
    # # Split the remaining string at the first '/'
    # parts = url_without_gs.split('/', 1)
    #
    # # The first part will be the bucket name, and the second part will be the file path
    # bucket_name = parts[0]
    # file_name = parts[1]

    if url.startswith("https://storage.cloud.google.com/"):
        url_without_scheme = url.replace('https://storage.cloud.google.com/', '')
    elif url.startswith("gs://"):
        url_without_scheme = url.replace('gs://', '')
    else:
        print("Invalid URL scheme")
        raise CustomException(code=400, status_code=20400, detail="Invalid URL scheme")

    # Split the URL into bucket name and file path
    parts = url_without_scheme.split('/', 1)
    if len(parts) < 2:
        print("Invalid URL")
        raise CustomException(code=400, status_code=20400, detail="Invalid URL format")

    bucket_name, file_path = parts[0], parts[1]

    #client = storage.Client.from_service_account_json('./key_stage.json')
    client = storage.Client.from_service_account_json('./key.json')
    # client = storage.Client()

    # Get the bucket
    try:
        bucket = client.bucket(bucket_name)

        # Define the directory name with a trailing slash
        #directory_blob_name = file_path + content_id + '/' + f"{current_datetime}-{custom_name}/"

        directory_blob_name = file_path

        # Create an empty blob (zero-byte object) representing the directory
        blob = bucket.blob(directory_blob_name)
        blob.upload_from_string('')  # Upload an empty string

        # print(f"gs://{bucket_name}/{directory_blob_name}")
        return f"gs://{bucket_name}/{directory_blob_name}"
    except Exception as e:
        print(e)
        raise CustomException(code=500, status_code=20500, detail=str(e))


def delete_job_template(
        client: TranscoderServiceClient,
        project_id: str,
        location: str,
        template_id: str,
) -> str:
    """Deletes a job template.

    Args:
        client:
        project_id: The GCP project ID.
        location: The location of the template.
        template_id: The user-defined template ID."""

    name = f"projects/{project_id}/locations/{location}/jobTemplates/{template_id}"
    try:
        client.delete_job_template(name=name)
        response = f"Deleted job template : {template_id}"
    except Exception as e:
        # In case of an error, raise an HTTPException
        raise CustomException(code=400, status_code=20400, detail=str("This template does not exist"))
    return response


def get_quality(
        video_quality: list[int],
        audio_quality: list[int]
):
    quality = []
    if 360 in video_quality or 480 in video_quality or 720 in video_quality:
        quality.append("SD")
    if 1080 in video_quality:
        quality.append("HD")
    if audio_quality is not None:
        quality.append("AUDIO")
    return quality


def get_drm_schema(
        drm_type: list[str]
):
    drm_schema = []
    if "fairplay" in drm_type or "both" in drm_type:
        drm_schema.append("FP")
    if "widevine" in drm_type or "both" in drm_type:
        drm_schema.append("WV")
    return drm_schema


def call_key_server(
        package_id: str,
        content_id: str,
        provider_id: str,
        video_quality: list[int],
        audio_quality: list[int],
        drm_type: list[str]
):
    data = {
        'packageId': package_id,
        'contentId': content_id,
        'providerId': provider_id,
        'quality': get_quality(video_quality, audio_quality),
        'drmScheme': get_drm_schema(drm_type)
    }
    print(data)
    url = settings.KEY_SERVER_URL
    inp_post_response = requests.post(url, json=data)

    if inp_post_response.status_code == 201:
        return extract_keys(json.loads(inp_post_response.content.decode('utf-8')))
    else:
        logger.error(inp_post_response.json())
        raise CustomException(code=404, status_code=20404, detail=f"{inp_post_response.json()}")


def get_keys(
        video_quality: list[int],
        audio_quality: list[int],
        drm_type: list[str]
):
    url = f"{settings.KEY_SERVER_URL}/1/1"
    data = {
        'quality': get_quality(video_quality, audio_quality),
        'drmScheme': get_drm_schema(drm_type)
    }
    inp_post_response = requests.post(url, json=data)

    if inp_post_response.status_code == 200:
        return extract_keys(json.loads(inp_post_response.content.decode('utf-8')))
    else:
        raise CustomException(code=402, status_code=20402, detail="Error to get keys from key server")


def extract_keys(data):
    return data['data']['keys']

def check_custom_header(request: Request):
    return True

    if settings.ENV == 'dev':
        return True
    # Check if the custom header is present
    if settings.CUSTOM_HEADER_FIELD not in request.headers:
        logger.error(f"Missing custom header: {settings.CUSTOM_HEADER_FIELD}")
        raise CustomException(code=401, status_code=20401, detail=f"Missing custom header: {settings.CUSTOM_HEADER_FIELD}")

    # Get the JSON string from the custom header
    header_value = request.headers[settings.CUSTOM_HEADER_FIELD]
    allowed_roles = settings.ALLOWED_ROLES.split(",")

    # Parse the JSON string
    try:
        header_json = json.loads(header_value)
    except json.JSONDecodeError:
        raise CustomException(code=400, status_code=20400, detail=f"Invalid JSON in header: {settings.CUSTOM_HEADER_FIELD}")

    # Check if the type field has the required roles
    if header_json.get("type").lower() not in allowed_roles:
        raise CustomException(code=403, status_code=20403, detail="Forbidden: Insufficient role")

    return header_json
