import asyncio
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from google.cloud.pubsub_v1.subscriber.message import Message
from google.cloud.video.transcoder_v1.services.transcoder_service import (
    TranscoderServiceClient,
)

from app.config import settings
from app.crud import async_create_job, async_update_job_id
from app.gcp_utils import get_secret_from_key_server, create_secret
from app.mapper import map_into_create_job
from app.models import JobStatusEnum, JobStateEnum
from app.routers.job import create_job_from_ad_hoc
from app.schemas import AdocJobRequest
from app.utils import check_file_or_directory, create_directory
from app.exceptions import CustomException
from app.custom_logger import logger


async def consume_job_request(subscriber, subscription_path, credentials, t_client: TranscoderServiceClient):
    # logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w")

    async def callback(message: Message) -> None:
        try:
            if message is None:
                logger.warning("Received None message. Skipping.")
                return
            # Decode and parse the message payload as JSON
            request_data = json.loads(message.data.decode('utf-8'))

            logger.info(f"custom_name: {request_data['custom_name']}, content_id:{request_data['content_id']}, "
                        f"provider_id:{request_data['provider_id']}, description:{request_data['description']}, "
                        f"audio_quality:{request_data['audio_quality']}, drm_type:{request_data['drm_type']}, "
                        f"image_uri:{request_data['image_uri']}, manifast_type:{request_data['manifast_type']}, "
                        f"input_uri:{request_data['input_uri']}, video_quality:{request_data['video_quality']}, "
                        f"package_id:{request_data['package_id']}, "
                        f"output_uri:{request_data['output_uri']}, created_by:{request_data['created_by']}")

            # Deserialize the JSON data into a JobRequest object
            job_request = AdocJobRequest(**request_data)

            # Process the JobRequest object
            await process_job_request(job_request, t_client, credentials)

        except Exception as e:
            logger.error(f"{e}")
        finally:
            if message is not None:
                message.ack()

    def sync_wrapper(message):
        asyncio.run(callback(message))

    streaming_pull_future = subscriber.subscribe(subscription_path, callback=sync_wrapper)

    print(f"Listening for messages on {subscription_path}")

    # Wrap subscriber in a 'with' block to automatically call close() when done.
    async with subscriber:
        try:
            # When `timeout` is not set, result() will block indefinitely,
            # unless an exception is encountered first.
            # streaming_pull_future.result()
            executor = ThreadPoolExecutor(max_workers=settings.MAX_WORKERS)
            await asyncio.get_running_loop().run_in_executor(executor, streaming_pull_future.result)
        except TimeoutError:
            streaming_pull_future.cancel()  # Trigger the shutdown.
            await streaming_pull_future.result()  # Block until the shutdown is complete.


async def process_job_request(request: AdocJobRequest, t_client: TranscoderServiceClient,
                              credentials):
    jobs = map_into_create_job(request)

    # input_exists = check_file_or_directory(jobs.input_uri)
    # output_exists = check_file_or_directory(jobs.output_uri)

    # if not input_exists:
    #     raise CustomException(code=400, status_code=20400, detail="Input file does not exist.")

    # if not output_exists:
    #    raise CustomException(code=400, status_code=20400, detail="Output directory does not exist.")

    jobs.output_uri = create_directory(jobs.output_uri, jobs.custom_name, jobs.content_id)

    value = get_secret_from_key_server(request.content_id, request.package_id, request.provider_id,
                                       request.video_quality, request.audio_quality, request.drm_type)

    print("After successful key server response")
    # version = create_secret(value)

    version = settings.SECRET_VERSION
    print(f"version: {version}")

    jobs.version = version

    # Add job into database
    await async_create_job(jobs)

    logger.info("After save the jobs in DB")
    # Dispatch Job to GCP Transcoder API
    transcoding_response = create_job_from_ad_hoc(t_client, settings.PROJECT_ID, settings.LOCATION,
                                                  jobs.input_uri, jobs.output_uri, version, request.image_uri,
                                                  request.video_quality, request.audio_quality, request.drm_type,
                                                  request.manifast_type)
    logger.info(transcoding_response.name)
    # print(transcoding_response.name)
    # Update job status and job state
    job = await async_update_job_id(transcoding_response.name, request)

    print("After update the job in DB")
    logger.info("After update the job id")

    # data = {
    #     "success": True,
    #     "message": "Job is under processing",
    #     "data": [
    #         {
    #             "job_start_time": job.created_at,
    #             "fully_qualified_name": job.fully_qualified_name,
    #             "job_id": job.job_id,
    #             "url": job.input_uri,
    #             "description": job.description,
    #             "state": job.state,
    #             "status": job.status,
    #             "custom_name": job.custom_name,
    #             "output_location": job.output_uri,
    #             "input_location": job.input_uri,
    #             "content_id": job.content_id,
    #             "package_id": job.package_id,
    #             "duration": job.duration_in_sec
    #         }
    #     ]
    # }

    if job:
        logger.info("Job Ok")

        # Convert data to JSON string
        # Commented out the following one line temporarily: 03-06-2024
        # message_data = data_to_json(data)

        # Initialize a PublisherClient
        # Commented out the following one line temporarily: 03-06-2024
        # publisher = pubsub_v1.PublisherClient(credentials=credentials)

        # publisher = pubsub_v1.PublisherClient()

        # project_id = 'your-project-id'
        # topic_id = 'your-topic-id'
        # topic_path = publisher.topic_path(project_id, topic_id)

        # Publish the message
        # Commented out the following lines temporarily: 03-06-2024
        # future = publisher.publish(settings.JOB_START_TOPIC_PATH, message_data.encode('utf-8'))
        # print(f"Published message ID: {future.result()}")

    else:
        print("Job not found or failed to update")
        raise CustomException(code=404, status_code=20404, detail="Job not found or failed to update")


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, JobStateEnum):
            return obj.value  # Serialize enum value
        if isinstance(obj, JobStatusEnum):
            return obj.value  # Serialize enum value
        if isinstance(obj, datetime):
            return obj.isoformat()  # Serialize datetime object
        return super().default(obj)


def data_to_json(data):
    return json.dumps(data, cls=CustomJSONEncoder)
