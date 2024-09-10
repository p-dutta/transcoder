from .config import settings
from .models import Jobs
from .schemas import JobRequest, AdocJobRequest
from .utils import JobStatusEnum, JobStateEnum


def map_into_create_job(request: AdocJobRequest) -> Jobs:
    return Jobs(
        project_id=settings.PROJECT_ID,
        location=settings.LOCATION,
        content_id=request.content_id,
        provider_id=request.provider_id,
        package_id= request.package_id,
        input_uri=request.input_uri,
        output_uri=request.output_uri,
        created_by=request.created_by,
        description=request.description,
        custom_name=request.custom_name,
    )


def map_job_id_and_name(job: Jobs, full_name: str) -> Jobs:
    job.fully_qualified_name = full_name
    job.job_id = full_name.split("jobs/")[1]
    job.status = JobStatusEnum.PROCESSING
    return job


def update_job_state_and_status(job: Jobs, state: str) -> Jobs:
    job.status = JobStatusEnum.COMPLETE
    job.state = JobStateEnum.SUCCESS if state == 'SUCCEEDED' else JobStateEnum.FAILED
    # job.updated_at = datetime.now()
    return job
