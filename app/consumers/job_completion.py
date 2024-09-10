import asyncio
import json
# import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.subscriber.message import Message
from google.cloud.video.transcoder_v1.services.transcoder_service import (
    TranscoderServiceClient,
)

from app.exceptions import CustomException
from app.config import settings
from app.consumers.job_request import data_to_json
from app.crud import async_update_job_state, async_get_job
from app.gcp_utils import delete_secret
from app.custom_logger import logger
from app.utils import remove_bucket_name


async def consume_message_on_job_completion(t_client: TranscoderServiceClient, subscriber, subscription_path,
                                            credentials):
    # logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w")

    async def callback(message: Message) -> None:
        # print(f"Received {message}.")
        # the message data from Pub/Sub is received in a binary format (as a byte string).
        # When you receive this binary data in Python, it's represented as a byte string (bytes type).
        # To convert this byte string into a human-readable string (a str type in Python), you need to decode it.
        try:
            if message is None:
                logger.warning("Received None message. Skipping.")
                return

            message_data = json.loads(message.data.decode('utf-8'))

            logger.info(f"{message_data}")
            # Access and print each element
            if 'job' in message_data:
                job_data = message_data['job']
                logger.info(f"{job_data['name']} state is {job_data['state']}")

                await async_update_job_state(t_client, job_data['name'], job_data["state"])

                job = await async_get_job(job_data['name'])

                if job is not None:
                    logger.info(f"timestamp: {job.updated_at}")
                    # delete_secret(job.version)
                    data = {
                        "success": True,
                        "message": "Job Final Status",
                        "data": [
                            {
                                "fully_qualified_name": job.fully_qualified_name,
                                "job_id": job.job_id,
                                "url": job.input_uri,
                                "description": job.description,
                                "state": job.state,
                                "status": job.status,
                                "custom_name": job.custom_name,
                                "output_location": job.output_uri,
                                "job_start_time": job.created_at,
                                "job_end_time": job.updated_at,
                                "duration": job.duration_in_sec,
                                "dash_media_cdn": settings.MEDIA_CDN_BASE + remove_bucket_name(
                                    job.output_uri) + "manifest_dash.mpd",
                                "hls_media_cdn": settings.MEDIA_CDN_BASE + remove_bucket_name(
                                    job.output_uri) + "manifest_hls.m3u8"
                            }
                        ]
                    }

                    logger.info(data)

                    # Convert data to JSON string
                    message_data = data_to_json(data)

                    # Initialize a PublisherClient
                    publisher = pubsub_v1.PublisherClient(credentials=credentials)

                    # publisher = pubsub_v1.PublisherClient()

                    # project_id = 'your-project-id'
                    # topic_id = 'your-topic-id'
                    # topic_path = publisher.topic_path(project_id, topic_id)

                    # Publish the message
                    future = publisher.publish(settings.JOB_START_TOPIC_PATH, message_data.encode('utf-8'))
                    print(f"Published message ID: {future.result()}")

                else:
                    print("Job not found or failed to update")
                    raise CustomException(code=404, status_code=20404, detail="Job not found or failed to update")

        except Exception as e:
            print(e)
            logger.error(f"{e}")
            raise CustomException(code=500, status_code=20500, detail=str(e))
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


async def dummy_func(subscriber, subscription_path):
    print("inside dummy_func")

    # logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w")

    def callback(message: Message) -> None:
        # print(f"Received {message}.")
        # the message data from Pub/Sub is received in a binary format (as a byte string).
        # When you receive this binary data in Python, it's represented as a byte string (bytes type).
        # To convert this byte string into a human-readable string (a str type in Python), you need to decode it.
        try:
            message_data = json.loads(message.data.decode('utf-8'))

            # Access and print each element
            if 'job' in message_data:
                job_data = message_data['job']
                for key, value in job_data.items():
                    print(f"{key}: {value}")
                    logger.info(f"{key}: {value}")

        except Exception as e:
            print("Exception while parsing message")
            pass
        message.ack()

    def run_subscriber():
        streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
        try:
            # This will block until an exception is raised or the client is stopped.
            streaming_pull_future.result()
        except Exception as e:
            print(f"An exception occurred in subscriber: {e}")
        finally:
            print("Subscriber is stopped.")

    # Run the subscriber in a separate thread to prevent blocking the event loop
    thread = threading.Thread(target=run_subscriber, daemon=True)
    thread.start()
    print("Subscriber thread started")

    async def subscribe():
        streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
        # The future result will block, so we await it in an executor
        await asyncio.get_running_loop().run_in_executor(None, streaming_pull_future.result)

    # Run the subscriber in the default executor
    await subscribe()
