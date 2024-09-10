from typing import Annotated
from google.cloud.video import transcoder_v1
from google.cloud.video.transcoder_v1.services.transcoder_service import TranscoderServiceClient
from fastapi import APIRouter, Depends, Request

from ..exceptions import CustomException
from ..schemas import TranscoderResponse, JobRequest, GetJobRequest, AdocJobRequest
from ..utils import (
    get_transcoder_client,
    create_job_from_template,
    db_dependency,
    build_jobs_data,
    check_custom_header,
    get_job_details
)
from ..config import settings
from ..crud import (
    create_job,
    update_job_id,
    get_jobs,
    get_job_by_job_id,
    get_job_by_custom_name
)
from ..gcp_utils import (
    create_mux_stream,
    create_overlay,
    create_elementary_streams,
    create_manifest,
    create_encryption,
    get_secret_from_key_server,
    create_secret
)

import argparse


router = APIRouter(
    prefix=f"{settings.ROUTE_PREFIX}/{settings.API_VERSION}/job",
    tags=['Transcoding and Packaging']
)

t_client_dependency = Annotated[TranscoderServiceClient, Depends(get_transcoder_client)]


@router.post("/create", response_model=TranscoderResponse)
async def transcode_job(db: db_dependency, request: AdocJobRequest, t_client: t_client_dependency,
                        request_header: Request):
    # logic to process the transcode request

    # input_uri = "gs://{source-bucket-name}/%s" % name  # Source bucket name
    # output_uri = "gs://{output-bucket-name}/%s/" % filename  # Output bucket name
    # template_id = "hd-h264-hls-dash"  # Template ID
    #
    # client = TranscoderServiceClient()
    #
    # parent = f"projects/{project - id}/locations/{location}"  # project id and preferred location
    # job = transcoder_v1.types.Job()
    # job.input_uri = input_uri
    # job.output_uri = output_uri
    # job.template_id = template_id
    #
    # response = client.create_job(parent=parent, job=job)
    # print(f"Job: {response.name}")
    check_custom_header(request_header)

    value = get_secret_from_key_server(request.content_id, request.package_id, request.provider_id,
                                       request.video_quality, request.audio_quality, request.drm_type)

    #version = create_secret(value)

    version = settings.SECRET_VERSION

    print(f"version: {version}")

    # Add job into database
    jobs = create_job(request, db, version)

    # Dispatch Job to GCP Transcoder API
    # transcoding_response = create_job_from_template(t_client, settings.PROJECT_ID, settings.LOCATION, jobs.input_uri,jobs.output_uri, jobs.template_id)

    transcoding_response = create_job_from_ad_hoc(t_client, settings.PROJECT_ID, settings.LOCATION,
                                                  jobs.input_uri, jobs.output_uri, version, request.image_uri,
                                                  request.video_quality, request.audio_quality, request.drm_type,
                                                  request.manifast_type)

    #print(transcoding_response)
    # Update job status and job state
    job = update_job_id(db, request, transcoding_response.name)

    # Mocking a response
    # logic to handle the transcoding process
    # For example: response_data = await handle_transcoding(request)

    # Mock response
    response_data = {
        "success": True,
        "message": "Job is under processing",
        "data": [
            {
                "fully_qualified_name": job.fully_qualified_name,
                "job_id": job.job_id,
                "url": job.input_uri,
                "description": job.description,
                "status": job.status,
                "state": job.state,
                "custom_name": job.custom_name,
                "output_location": job.output_uri,
                "job_start_time": job.created_at
            }
        ]
    }

    # Create a TranscoderResponse object
    return TranscoderResponse(**response_data)



@router.get("/list", response_model=TranscoderResponse)
async def get_all_jobs(db: db_dependency, request: Request):
    try:
        check_custom_header(request)
        # Get all jobs from database

        jobs = get_jobs(db)

        # Bind jobs into Dictionary

        job_data = build_jobs_data(jobs)
        # Mocking a response

        # Mock response
        response_data = {
            "success": True,
            "message": "List of all jobs",
            "data": job_data
        }

        # Create a TranscoderResponse object
        return TranscoderResponse(**response_data)

    except Exception as e:
        # In case of an error, raise an Exception
        raise CustomException(code= 500, status_code=20500, detail=str(e))


@router.post("/list/details", response_model=TranscoderResponse)
async def get_job(db: db_dependency, request: GetJobRequest, request_header: Request):
    check_custom_header(request_header)
    if request.custom_name:
        job = get_job_by_custom_name(request.custom_name, db)

        if job is None:  # If job not found by custom name, try fetching by job ID
            if request.job_id:
                job = get_job_by_job_id(request.job_id, db)

            else:
                raise CustomException(code=404, status_code=20404, detail="Job not found by custom name or job ID")

    elif request.job_id:
        job = get_job_by_job_id(request.job_id, db)

        if job is None:  # If job not found by job ID, raise an error
            print("Job not found by job ID")
            raise CustomException(code=404, status_code=20404, detail="Job not found by job ID")

    else:
        print("Please provide either a job ID or a custom name")
        raise CustomException(code=400, status_code=20400, detail="Please provide either a job ID or a custom name")

    # Mocking a response
    try:
        # Mock response
        response_data = {
            "success": True,
            "message": "Job details",
            "data": [
                {
                    "fully_qualified_name": job.fully_qualified_name,
                    "job_id": job.job_id,
                    "url": job.input_uri,
                    "description": job.description,
                    "state": job.state,
                    "status": job.status,
                    "custom_name": job.custom_name,
                    "output_location": job.output_uri
                }
            ]
        }

        # Create a TranscoderResponse object
        return TranscoderResponse(**response_data)

    except Exception as e:
        print(e)
        # In case of an error, raise an Exception
        raise CustomException(code=500, status_code=20500, detail=str(e))

def create_job_from_ad_hoc(
        client: TranscoderServiceClient,
        project_id: str,
        location: str,
        input_uri: str,
        output_uri: str,
        version: int,
        image_uri: str,
        video_quality: list[int],
        audio_quality: list[int],
        drm_type: list[str],
        manifast_type: list[str]
) -> transcoder_v1.types.resources.Job:
    """Creates a job based on an ad-hoc job configuration.

    Args:
        client (TranscoderServiceClient): Service access token
        project_id: The GCP project ID.
        location: The location to start the job in.
        input_uri: Uri of the video in the Cloud Storage bucket.
        output_uri: Uri of the video output folder in the Cloud Storage bucket.
        version: The version of the Secret Manager
        image_uri: Uri of the image in the Cloud Storage
        video_quality: List of video quality
        audio_quality: List of audio quality
        drm_type: List of DRM
        manifast_type: List of manifast types

    Returns:
        The job resource.
    """
    parent = f"projects/{project_id}/locations/{location}"
    job = transcoder_v1.types.Job()
    job.input_uri = input_uri
    job.output_uri = output_uri
    job.config = transcoder_v1.types.JobConfig(
        elementary_streams=create_elementary_streams(video_quality, audio_quality),
        encryptions=create_encryption(drm_type, version),
        mux_streams=create_mux_stream(drm_type, video_quality, audio_quality),
        manifests=create_manifest(drm_type, video_quality, audio_quality, manifast_type),
        overlays=create_overlay(image_uri),
        pubsub_destination=transcoder_v1.types.PubsubDestination(
            topic=f"projects/{settings.PROJECT_NAME}/topics/{settings.JOB_COMPLETION_TOPIC}",
        ),
    )
    response = client.create_job(parent=parent, job=job)
    print(f"Job: {response.name}")
    return response
