import asyncio
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from google.cloud.pubsub_v1.subscriber.message import Message
from google.cloud.video.transcoder_v1.services.transcoder_service import (
    TranscoderServiceClient,
)

from app.config import settings
from app.consumers.job_request import process_job_request
from app.custom_logger import logger
from app.schemas import AdocJobRequest


async def process_cloud_storage_trigger(subscriber, subscription_path, credentials, t_client: TranscoderServiceClient):
    # logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w")

    async def callback(message: Message) -> None:
        try:
            if message is None:
                print("Received None message. Skipping.")
                logger.warning("Received None message. Skipping.")
                return
            # Decode and parse the message payload as JSON
            request_data = json.loads(message.data.decode('utf-8'))
            name = request_data.get("name")
            content_type = request_data.get("contentType")
            bucket = request_data.get("bucket")
            event_type = message.attributes.get("eventType")

            if name.startswith("input") and content_type == "video/mp4" and event_type == "OBJECT_FINALIZE":
                data = prepare_job_request(name, bucket)
                logger.info(f"custom_name: {data['custom_name']}, content_id:{data['content_id']}, "
                            f"provider_id:{data['provider_id']}, description:{data['description']}, "
                            f"audio_quality:{data['audio_quality']}, drm_type:{data['drm_type']}, "
                            f"image_uri:{data['image_uri']}, manifast_type:{data['manifast_type']}, "
                            f"input_uri:{data['input_uri']}, video_quality:{data['video_quality']}, "
                            f"package_id:{data['package_id']}, "
                            f"output_uri:{data['output_uri']}, created_by:{data['created_by']}")

                print(data)
                # Deserialize the JSON data into a JobRequest object
                job_request = AdocJobRequest(**data)

                # Process the JobRequest object
                await process_job_request(job_request, t_client, credentials)

        except Exception as e:
            print(e)
            logger.error(e)
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


def extract_filename(name: str) -> str:
    # Extract the base name from the path
    base_name = os.path.basename(name)
    # Remove the extension
    file_name, _ = os.path.splitext(base_name)
    return file_name


def get_content_id(name: str) -> str:
    directory = os.path.dirname(name)
    path_parts = directory.split('/') if '/' in directory else ''
    sub_path = os.path.join(*path_parts[1:])
    sub_path_with_dashes = sub_path.replace(os.sep, '-')
    return str(sub_path_with_dashes)


def get_output_sub_path(name: str) -> str:
    directory = os.path.dirname(name)
    path_parts = directory.split('/') if '/' in directory else ''
    sub_path = os.path.join(*path_parts[1:])
    return str(sub_path)


def prepare_job_request(name: str, bucket: str):
    return {
        "audio_quality": [
            64
        ],
        "content_id": get_content_id(name),
        "created_by": "transcoder_service_internally",
        "input_uri": "gs://" + bucket + "/" + name,
        "custom_name": get_content_id(name) + "_" + str(int(time.time())),
        "description": "Fairplay and Widevine encryption for " + extract_filename(name),
        "drm_type": [
            "both"
        ],
        "image_uri": "gs://" + bucket + "/images/toffee-vertical-logo-high-res.png",
        "manifast_type": [
            "dash",
            "hls"
        ],
        "output_uri": "gs://" + settings.OUTPUT_BUCKET_TOFFEE + "/output/" + get_output_sub_path(name) + "/",
        "package_id": get_content_id(name),
        "provider_id": "6d0a6365",
        "video_quality": [
            360,
            480,
            720,
            1080
        ]
    }
