"""
Pydantic Models are used as Schema Validation
for request and responses parameters
"""
from pydantic import BaseModel, field_validator, AnyUrl, validator, ValidationError
from typing import Optional, Any, List


class MediaSpecs(BaseModel):
    video: Any
    audio: Any
    subtitle: Any

    @field_validator('video', 'audio', 'subtitle')
    def check_list_not_empty(cls, v):
        if not v:
            raise ValueError('List cannot be empty')
        return v


class DRMType(BaseModel):
    widevine: Optional[bool] = False
    fairplay: Optional[bool] = False


class ProtectionType(BaseModel):
    aes128: Optional[bool] = False
    drm: Optional[DRMType] = None


class TranscoderRequest(BaseModel):
    project_id: Optional[str]
    content_id: Optional[str]
    provider_id: Optional[str]
    template_id: Optional[str]
    location: Optional[str]
    input_uri: Optional[str]
    output_uri: Optional[str]
    num_manifest_files: Optional[int]
    custom_name: Optional[str]
    created_by: Optional[str]
    description: Optional[str]
    # protection: Optional[ProtectionType]
    # output_spec: Optional[MediaSpecs]
    container_format: Optional[str]

    @field_validator('num_manifest_files')
    def validate_manifest_files(cls, v):
        if v <= 0:
            raise ValueError('Number of manifest files must be positive')
        return v

    @field_validator('container_format')
    def validate_container_format(cls, v):
        if v not in ['fmp4', 'mpegts']:
            raise ValueError('Invalid container format')
        return v

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "project_id": 121243050899,
                "content_id": 124,
                "provider_id": "6d0a6365-b3bf-41da-ae91-3485074d775e",
                "template_id": "hd-h264-hls-dash",
                "location": "asia-southeast1",
                "input_uri": "gs://transcoder-api-video-test/ChromeCast.mp4",
                "output_uri": "gs://transcoder-api-video-test/output/",
                "num_manifest_files": 4,
                "container_format": "fmp4"
            }
        }


class JobRequest(BaseModel):
    content_id: Optional[str]
    provider_id: Optional[str]
    template_id: Optional[str]
    input_uri: Optional[str]
    output_uri: Optional[str]
    custom_name: Optional[str]
    created_by: Optional[str]
    description: Optional[str]

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "content_id": 124,
                "description": "This is the description",
                "custom_name": "custom job name",
                "provider_id": "6d0a6365-b3bf-41da-ae91-3485074d775e",
                "template_id": "hd-h264-hls",
                "input_uri": "gs://transcoder-api-video-test/ChromeCast.mp4",
                "output_uri": "gs://transcoder-api-video-test/output/",
                "created_by": "who created this job",
            }
        }


class GetJobRequest(BaseModel):
    job_id: Optional[str]
    custom_name: Optional[str]

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "custom_name": "custom job name",
                "job_id": "b93643da-dd58-4c26-9825-269df1d19253"
            }
        }


# class GetJob(BaseModel):
#     job_id: Optional[str]
#
#     class Config:
#         extra = "forbid"
#         json_schema_extra = {
#             "example": {
#                 "job_id": "b93643da-dd58-4c26-9825-269df1d19253"
#             }
#         }


class TranscoderResponse(BaseModel):
    success: bool
    message: str
    data: List[dict]  # This can be further detailed based on the structure of package details


class JobTemplateRequest(BaseModel):
    template_id: Optional[str]

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "template_id": "hd-h264-hls"
            }
        }


class AdocJobRequest(BaseModel):
    content_id: Optional[str]
    provider_id: Optional[str]
    package_id: Optional[str]
    input_uri: Optional[str]
    output_uri: Optional[str]
    custom_name: Optional[str]
    created_by: Optional[str]
    description: Optional[str]
    image_uri: Optional[str]
    video_quality: Optional[list[int]]
    audio_quality: Optional[list[int]]
    drm_type: Optional[list[str]]
    manifast_type: Optional[list[str]]

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "content_id": 124,
                "description": "This is the description",
                "package_id": 12345,
                "custom_name": "custom job name",
                "provider_id": "6d0a6365-b3bf-41da-ae91-3485074d775e",
                "input_uri": "gs://transcoder-api-video-test/ChromeCast.mp4",
                "output_uri": "gs://transcoder-api-video-test/output/",
                "created_by": "who created this job",
                "image_uri": "gs://transcoder-api",
                "video_quality": [360, 480, 720, 1080],
                "audio_quality": [64],
                "drm_type": ["fairplay", "widevine", "both", "none"],
                "manifast_type": ["hls", "dash"],
            }
        }
