from typing import Annotated

from fastapi import APIRouter, Depends, Request
from google.cloud.video.transcoder_v1.services.transcoder_service import TranscoderServiceClient
from sqlalchemy.orm import Session

from ..config import settings
from ..schemas import TranscoderResponse, JobTemplateRequest
from ..exceptions import CustomException
from ..custom_logger import logger
# from ..database import get_db
from ..utils import get_transcoder_client, list_job_templates, pager_to_dict, pager_to_list, db_dependency, \
    delete_job_template, check_custom_header

router = APIRouter(
    prefix=f"{settings.ROUTE_PREFIX}/{settings.API_VERSION}/template",
    tags=['Transcoding and Packaging']
)

# db_dependency = Annotated[Session, Depends(get_db)]
t_client_dependency = Annotated[TranscoderServiceClient, Depends(get_transcoder_client)]


@router.get("/list")
async def list_templates(t_client: t_client_dependency, request: Request):
    check_custom_header(request)
    project_id = settings.PROJECT_ID
    location = settings.LOCATION

    job_templates = list_job_templates(t_client, project_id, location)

    job_templates_list = [{f"Template {i + 1}": job_template} for i, job_template in enumerate(job_templates)]

    try:
        # Mock response
        response_data = {
            "success": True,
            "message": "List of all job templates",
            "data": job_templates_list
        }

        # Create a TranscoderResponse object
        return TranscoderResponse(**response_data)

    except Exception as e:
        # In case of an error, raise an Exception
        print(e)
        raise CustomException(code=500, status_code=20500, detail=str(e))


@router.post("/delete")
async def delete_template(t_client: t_client_dependency, request: JobTemplateRequest, request_header: Request):
    check_custom_header(request_header)
    project_id = settings.PROJECT_ID
    location = settings.LOCATION

    response = delete_job_template(t_client, project_id, location, request.template_id)
    try:
        # Mock response
        response_data = {
            "success": True,
            "message": "Deleted job template",
            "data": [
                {
                    "response": response
                }
            ]
        }

        # Create a TranscoderResponse object
        return TranscoderResponse(**response_data)

    except Exception as e:
        # In case of an error, raise an Exception
        print(e)
        raise CustomException(code=500, status_code=20500, detail=str(e))
