"""
Main Application File for our FastApi Server
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google.cloud import pubsub_v1
from google.cloud.video.transcoder_v1.services.transcoder_service import (
    TranscoderServiceClient,
)
from google.oauth2 import service_account

from app.consumers.job_completion import consume_message_on_job_completion
from app.consumers.process_cloud_storage_trigger import process_cloud_storage_trigger
from . import models
from .config import settings
from .consumers.job_request import consume_job_request
from .database import engine
from .exceptions import CustomException
from .routers import job, job_template

@asynccontextmanager
async def app_lifespan(application: FastAPI):
    # application.state.super_secret = secrets.token_hex(16)
    print("within lifespan context")
    #credentials = service_account.Credentials.from_service_account_file('./key_stage.json')
    credentials = service_account.Credentials.from_service_account_file('./key.json')
    # credentials = None
    # application.state.credentials = credentials

    transcoder_client = TranscoderServiceClient(credentials=credentials)
    # transcoder_client = TranscoderServiceClient()

    application.state.transcoder_client = transcoder_client


    # Initialize the subscriber client

    subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
    # subscriber = pubsub_v1.SubscriberClient()

    subscription_path_job_request = subscriber.subscription_path(settings.PROJECT_NAME,
                                                                 settings.JOB_REQUEST_SUBSCRIPTION_ID)
    subscription_path = subscriber.subscription_path(settings.PROJECT_NAME, settings.JOB_COMPLETION_SUBSCRIPTION_ID)

    trigger_path = subscriber.subscription_path(settings.PROJECT_NAME_TOFFEE, settings.CLOUD_STORAGE_TRIGGER_SUBSCRIPTION)

    # Start the background task to consume messages
    task_listen_for_job_request = asyncio.create_task(
        consume_job_request(subscriber, subscription_path_job_request, credentials, transcoder_client))
    task_listen_for_trigger_request = asyncio.create_task(
        process_cloud_storage_trigger(subscriber, trigger_path, credentials, transcoder_client))
    task_job_completion_sub = asyncio.create_task(
        consume_message_on_job_completion(transcoder_client, subscriber, subscription_path, credentials))
    print("Started the background task to consume messages")
    try:
        print("before yield")
        yield  # Application is running
        print("after yield")
    finally:
        print("within finally")
        task_listen_for_job_request.cancel()
        task_job_completion_sub.cancel()
        task_listen_for_trigger_request.cancel()
        try:
            # await task_job_completion_sub  # Wait for the task cancellation to complete
            await asyncio.gather(task_listen_for_job_request, task_job_completion_sub,
                                 task_listen_for_trigger_request, return_exceptions=True)
        except asyncio.CancelledError:
            print("Task was cancelled.")
        subscriber.close()


app = FastAPI(lifespan=app_lifespan)
# app = FastAPI()

models.Base.metadata.create_all(bind=engine)

# @app.on_event("startup")
# async def startup_event():
#     credentials = service_account.Credentials.from_service_account_file('./key.json')
#     app.state.transcoder_client = TranscoderServiceClient(credentials=credentials)


origins = [
    "http://localhost",
    "http://localhost:8080",
    "https://www.google.com"
]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(job.router)
app.include_router(job_template.router)

@app.exception_handler(CustomException)
def custom_exception_handler(request: Request, exc: CustomException):
    return JSONResponse(
        status_code=exc.code,
        content={
            "status": False,
            "code": exc.status_code,
            "message": exc.detail
    }
)

@app.get(f"/{settings.API_VERSION}/health", response_class=JSONResponse)
async def health():
    return JSONResponse(
        status_code=200,
        content={"message": "Service is healthy", "status": "ok"}
    )
