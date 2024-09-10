#import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from sqlalchemy.sql import func
from google.cloud.video.transcoder_v1.services.transcoder_service import (
    TranscoderServiceClient,
)

from .exceptions import CustomException
from .config import settings
from .mapper import map_into_create_job, map_job_id_and_name
from .models import Jobs, JobStatusEnum, JobStateEnum
from .schemas import AdocJobRequest
from .utils import check_file_or_directory, create_directory, get_video_duration
from .custom_logger import logger
import urllib.parse


def add_job(db: Session, job: Jobs):
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job_by_custom_name(name: str, db: Session):
    return db.query(Jobs).filter(Jobs.custom_name == name).first()


def get_job_by_full_name(name: str, db: Session):
    return db.query(Jobs).filter(Jobs.fully_qualified_name == name).first()

def get_job_by_job_id(job_id: str, db: Session):
    logger.info(f"{job_id}")
    return db.query(Jobs).filter(Jobs.job_id == job_id).first()


def create_job(request: AdocJobRequest, db: Session, version: int):
    job = map_into_create_job(request)
    job.version = version

    input_exists = check_file_or_directory(job.input_uri)
    output_exists = check_file_or_directory(job.output_uri)

    if not input_exists:
        print("Input file does not exist.")
        raise CustomException(code=400, status_code=40400, detail="Input file does not exist.")

    if not output_exists:
        print("Output directory does not exist.")
        raise CustomException(code=400, status_code=40400, detail="Output directory does not exist.")

    job.output_uri = create_directory(job.output_uri, job.custom_name, job.content_id)
    return add_job(db, job)


def get_jobs(db: Session):
    jobs = db.query(Jobs).all()
    return jobs


def update_job_id(db: Session, request: AdocJobRequest, name: str):
    job = get_job_by_custom_name(request.custom_name, db)
    jobs = map_job_id_and_name(job, name)
    return add_job(db, jobs)


async def async_update_job_state(t_client: TranscoderServiceClient, name: str, state: str):
    # URL-encode the password
    encoded_password = urllib.parse.quote(settings.DB_PASSWORD)
    database_url = f"postgresql+asyncpg://{settings.DB_USER}:{encoded_password}@{settings.DB_HOSTNAME}:{settings.DB_PORT}/{settings.DB_NAME}"
    async_engine = create_async_engine(database_url, echo=True)
    async_session = sessionmaker(bind=async_engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        async with session.begin():
            logger.info("Into async_update_job_state")
            sql = select(Jobs).filter(Jobs.fully_qualified_name == name)
            result = await session.execute(sql)
            job = result.scalar_one_or_none()
            if job is None:
                logger.info(f"Job with name '{name}' not found in the database.")
                return
            job.status = JobStatusEnum.COMPLETE
            job.state = JobStateEnum.SUCCESS if state == 'SUCCEEDED' else JobStateEnum.FAILED
            job.updated_at = func.now()
            job.duration_in_sec = get_video_duration(t_client, job.job_id)
            logger.info(f"Updating job: {job.job_id}, state: {job.state}, status: {job.status}")
            await session.commit()
            return job


async def async_get_job(name:str):
    encoded_password = urllib.parse.quote(settings.DB_PASSWORD)
    database_url = f"postgresql+asyncpg://{settings.DB_USER}:{encoded_password}@{settings.DB_HOSTNAME}:{settings.DB_PORT}/{settings.DB_NAME}"
    async_engine = create_async_engine(database_url, echo=True)
    async_session = sessionmaker(bind=async_engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        async with session.begin():
            logger.info("Into async_get_job")
            sql = select(Jobs).filter(Jobs.fully_qualified_name == name)
            result = await session.execute(sql)
            job = result.scalar_one_or_none()
            if job is None:
                logger.info(f"Job with name '{name}' not found in the database.")
                return
            logger.info(f"updated_timestamp: {job.updated_at}")
            return job

async def async_create_job(job: Jobs):
    encoded_password = urllib.parse.quote(settings.DB_PASSWORD)
    database_url = f"postgresql+asyncpg://{settings.DB_USER}:{encoded_password}@{settings.DB_HOSTNAME}:{settings.DB_PORT}/{settings.DB_NAME}"
    async_engine = create_async_engine(database_url, echo=True)
    async_session = sessionmaker(bind=async_engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        async with session.begin():
            session.add(job)
            await session.commit()


async def async_update_job_id(name: str, request: AdocJobRequest):
    encoded_password = urllib.parse.quote(settings.DB_PASSWORD)
    database_url = f"postgresql+asyncpg://{settings.DB_USER}:{encoded_password}@{settings.DB_HOSTNAME}:{settings.DB_PORT}/{settings.DB_NAME}"
    async_engine = create_async_engine(database_url, echo=True)
    async_session = sessionmaker(bind=async_engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        async with session.begin():
            logger.info("Into async_update_job_id")
            sql = select(Jobs).filter(Jobs.custom_name == request.custom_name)
            result = await session.execute(sql)
            job = result.scalar_one_or_none()
            if job is None:
                logger.info(f"Job with name '{name}' not found in the database.")
                return
            job.fully_qualified_name = name
            job.job_id = name.split("jobs/")[1]
            job.status = JobStatusEnum.PROCESSING
            await session.commit()
            return job
