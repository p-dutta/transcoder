import json
import os
import requests
from google.cloud import secretmanager
from google.cloud.video import transcoder_v1
from google.protobuf import duration_pb2 as duration

from .config import settings
from .utils import get_keys, call_key_server
from .custom_logger import logger

#os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./key_stage.json"

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./key.json"

def create_elementary_stream_360p(
) -> transcoder_v1.types.ElementaryStream:
    return transcoder_v1.types.ElementaryStream(
        key="video-stream-360",
        video_stream=transcoder_v1.types.VideoStream(
            h264=transcoder_v1.types.VideoStream.H264CodecSettings(
                height_pixels=360,
                width_pixels=640,
                bitrate_bps=603000,
                frame_rate=25,
                profile="baseline",
                tune="film",
            ),
        )
    )


def create_elementary_stream_480p(
) -> transcoder_v1.types.ElementaryStream:
    return transcoder_v1.types.ElementaryStream(
        key="video-stream-480",
        video_stream=transcoder_v1.types.VideoStream(
            h264=transcoder_v1.types.VideoStream.H264CodecSettings(
                height_pixels=480,
                width_pixels=854,
                bitrate_bps=1080000,
                frame_rate=25,
                profile="main",
                tune="film",
            ),
        ),
    )


def create_elementary_stream_720p(
) -> transcoder_v1.types.ElementaryStream:
    return transcoder_v1.types.ElementaryStream(
        key="video-stream-720",
        video_stream=transcoder_v1.types.VideoStream(
            h264=transcoder_v1.types.VideoStream.H264CodecSettings(
                height_pixels=720,
                width_pixels=1280,
                bitrate_bps=2430000,
                frame_rate=25,
                profile="main",
                tune="film",
            ),
        ),
    )


def create_elementary_stream_1080p(
) -> transcoder_v1.types.ElementaryStream:
    return transcoder_v1.types.ElementaryStream(
        key="video-stream-1080",
        video_stream=transcoder_v1.types.VideoStream(
            h264=transcoder_v1.types.VideoStream.H264CodecSettings(
                height_pixels=1080,
                width_pixels=1920,
                bitrate_bps=5850000,
                frame_rate=25,
                profile="high",
                tune="film",
            ),
        ),
    )


def create_elementary_stream_audio_64(
) -> transcoder_v1.types.ElementaryStream:
    return transcoder_v1.types.ElementaryStream(
        key="audio-stream-64",
        audio_stream=transcoder_v1.types.AudioStream(
            codec="aac",
            bitrate_bps=64000,
        )
    )


def create_fairplay_aes_encryption(
        version: int
) -> transcoder_v1.types.Encryption:
    return transcoder_v1.types.Encryption(
        id="fairplay_aes",
        secret_manager_key_source=transcoder_v1.types.Encryption.SecretManagerSource(
            secret_version=f"projects/{settings.PROJECT_ID}/secrets/{settings.SECRET_ID}/versions/{version}",
        ),
        drm_systems=transcoder_v1.types.Encryption.DrmSystems(
            fairplay=transcoder_v1.types.Encryption.Fairplay(),
        ),
        sample_aes=transcoder_v1.types.Encryption.SampleAesEncryption()
    )


def create_fairplay_cbcs_encryption(
        version: int
) -> transcoder_v1.types.Encryption:
    return transcoder_v1.types.Encryption(
        id="fairplay",
        secret_manager_key_source=transcoder_v1.types.Encryption.SecretManagerSource(
            secret_version=f"projects/{settings.PROJECT_ID}/secrets/{settings.SECRET_ID}/versions/{version}",
        ),
        drm_systems=transcoder_v1.types.Encryption.DrmSystems(
            fairplay=transcoder_v1.types.Encryption.Fairplay(),
        ),
        mpeg_cenc=transcoder_v1.types.Encryption.MpegCommonEncryption(
            scheme="cbcs",
        )
    )


def create_widevine_cenc_encryption(
        version: int
) -> transcoder_v1.types.Encryption:
    return transcoder_v1.types.Encryption(
        id="widevine",
        secret_manager_key_source=transcoder_v1.types.Encryption.SecretManagerSource(
            secret_version=f"projects/{settings.PROJECT_ID}/secrets/{settings.SECRET_ID}/versions/{version}",
        ),
        drm_systems=transcoder_v1.types.Encryption.DrmSystems(
            widevine=transcoder_v1.types.Encryption.Widevine(),
        ),
        mpeg_cenc=transcoder_v1.types.Encryption.MpegCommonEncryption(
            scheme="cenc",
        )
    )


def create_hls_manifest(
        mux_stream: list[str]
) -> transcoder_v1.types.Manifest:
    return transcoder_v1.types.Manifest(
        file_name="manifest_hls.m3u8",
        type="HLS",
        mux_streams=mux_stream,
    )


def create_dash_manifest(
        mux_stream: list[str]
) -> transcoder_v1.types.Manifest:
    return transcoder_v1.types.Manifest(
        file_name="manifest_dash.mpd",
        type="DASH",
        mux_streams=mux_stream,
    )


def create_fmp4_mux_stream(
        key: str,
        name: str,
        encryption: list[str]
) -> transcoder_v1.types.MuxStream:
    if "fairplay" in encryption:
        return transcoder_v1.types.MuxStream(
            key=key,
            container="fmp4",
            elementary_streams=[name],
            encryption_id="fairplay"
        )
    elif "widevine" in encryption:
        return transcoder_v1.types.MuxStream(
            key=key,
            container="fmp4",
            elementary_streams=[name],
            encryption_id="widevine"
        )
    else:
        return transcoder_v1.types.MuxStream(
            key=key,
            container="fmp4",
            elementary_streams=[name]
        )


def if_fairplay_drm_exist(
        drm_type: list[str]
):
    if "fairplay" in drm_type or "both" in drm_type:
        return "fairplay"
    else:
        return None


def if_widevine_drm_exist(
        drm_type: list[str]
):
    if "widevine" in drm_type or "both" in drm_type:
        return "widevine"
    else:
        return None


def create_mux_stream(
        drm_type: list[str],
        video_quality: list[int],
        audio_quality: list[int]
):
    mux_stream = []
    if "none" in drm_type:
        if 360 in video_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_1", "video-stream-360", "none"))
        if 480 in video_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_2", "video-stream-480", "none"))
        if 720 in video_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_3", "video-stream-720", "none"))
        if 1080 in video_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_4", "video-stream-1080", "none"))
        if 64 in audio_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_5", "audio-stream-64", "none"))

        return mux_stream

    if if_fairplay_drm_exist(drm_type) is not None:
        if 360 in video_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_fairplay_1", "video-stream-360", "fairplay"))
        if 480 in video_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_fairplay_2", "video-stream-480", "fairplay"))
        if 720 in video_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_fairplay_3", "video-stream-720", "fairplay"))
        if 1080 in video_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_fairplay_4", "video-stream-1080", "fairplay"))
        if 64 in audio_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_fairplay_5", "audio-stream-64", "fairplay"))

    if if_widevine_drm_exist(drm_type) is not None:
        if 360 in video_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_widevine_1", "video-stream-360", "widevine"))
        if 480 in video_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_widevine_2", "video-stream-480", "widevine"))
        if 720 in video_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_widevine_3", "video-stream-720", "widevine"))
        if 1080 in video_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_widevine_4", "video-stream-1080", "widevine"))
        if 64 in audio_quality:
            mux_stream.append(create_fmp4_mux_stream("fmp4_widevine_5", "audio-stream-64", "widevine"))

    return mux_stream


def create_overlay(
        image_uri: str
):
    return [
        transcoder_v1.types.Overlay(
            image=transcoder_v1.types.Overlay.Image(
                uri=image_uri,
                resolution=transcoder_v1.types.Overlay.NormalizedCoordinate(
                    x=0.1,
                    y=0,
                ),
                alpha=1,
            ),
            animations=[
                transcoder_v1.types.Overlay.Animation(
                    animation_static=transcoder_v1.types.Overlay.AnimationStatic(
                        xy=transcoder_v1.types.Overlay.NormalizedCoordinate(
                            x=0.9,
                            y=0.01,
                        ),
                        start_time_offset=duration.Duration(
                            seconds=0,
                        ),
                    ),
                ),
            ],
        ),
    ]


def create_elementary_streams(
        video_quality: list[int],
        audio_quality: list[int]
):
    elementary_streams = []
    if 360 in video_quality:
        elementary_streams.append(create_elementary_stream_360p())
    if 480 in video_quality:
        elementary_streams.append(create_elementary_stream_480p())
    if 720 in video_quality:
        elementary_streams.append(create_elementary_stream_720p())
    if 1080 in video_quality:
        elementary_streams.append(create_elementary_stream_1080p())
    if 64 in audio_quality:
        elementary_streams.append(create_elementary_stream_audio_64())

    return elementary_streams


def create_manifest(
        drm_type: list[str],
        video_quality: list[int],
        audio_quality: list[int],
        manifest_type: list[str]
):
    manifest_name = []
    manifests = []
    if "none" in drm_type:
        if 360 in video_quality:
            manifest_name.append("fmp4_1")
        if 480 in video_quality:
            manifest_name.append("fmp4_2")
        if 720 in video_quality:
            manifest_name.append("fmp4_3")
        if 1080 in video_quality:
            manifest_name.append("fmp4_4")
        if 64 in audio_quality:
            manifest_name.append("fmp4_5")

        if "hls" in manifest_type:
            manifests.append(create_hls_manifest(manifest_name))
        if "dash" in manifest_type:
            manifests.append(create_dash_manifest(manifest_name))
        return manifests

    if if_fairplay_drm_exist(drm_type) is not None:
        if 360 in video_quality:
            manifest_name.append("fmp4_fairplay_1")
        if 480 in video_quality:
            manifest_name.append("fmp4_fairplay_2")
        if 720 in video_quality:
            manifest_name.append("fmp4_fairplay_3")
        if 1080 in video_quality:
            manifest_name.append("fmp4_fairplay_4")
        if 64 in audio_quality:
            manifest_name.append("fmp4_fairplay_5")
        if "hls" in manifest_type:
            manifests.append(create_hls_manifest(manifest_name))
            manifest_name.clear()

    if if_widevine_drm_exist(drm_type) is not None:
        if 360 in video_quality:
            manifest_name.append("fmp4_widevine_1")
        if 480 in video_quality:
            manifest_name.append("fmp4_widevine_2")
        if 720 in video_quality:
            manifest_name.append("fmp4_widevine_3")
        if 1080 in video_quality:
            manifest_name.append("fmp4_widevine_4")
        if 64 in audio_quality:
            manifest_name.append("fmp4_widevine_5")
        if "dash" in manifest_type:
            manifests.append(create_dash_manifest(manifest_name))

    return manifests


def create_encryption(
        drm_type: list[str],
        version: int
):
    encryption = []
    if if_fairplay_drm_exist(drm_type) is not None:
        encryption.append(create_fairplay_cbcs_encryption(version))
    if if_widevine_drm_exist(drm_type) is not None:
        encryption.append(create_widevine_cenc_encryption(version))
    return encryption


def create_secret(value):
    if value is None:
        return 0

    # Initialize the client.

    # for local & dev
    #client = secretmanager.SecretManagerServiceClient().from_service_account_file('./key_stage.json')
    client = secretmanager.SecretManagerServiceClient().from_service_account_file('./key.json')

    # for stage and prod
    # client = secretmanager.SecretManagerServiceClient()

    # Build the parent secret name.
    parent = f"projects/{settings.PROJECT_ID}/secrets/{settings.SECRET_ID}"

    secret_value = {"encryptionKeys": value}

    # Build the secret payload.
    payload = {"data": json.dumps(secret_value).encode("UTF-8")}

    # Call the API to add the secret version.
    response = client.add_secret_version(
        request={"parent": parent, "payload": payload}
    )

    version_number = response.name.split('/')[-1]
    return version_number


def delete_secret(version_number):
    print(version_number)
    client = secretmanager.SecretManagerServiceClient().from_service_account_file('./key.json')

    version_name = f"projects/{settings.PROJECT_ID}/secrets/{settings.SECRET_ID}/versions/{version_number}"

    response = client.destroy_secret_version(request={"name": version_name})

    logger.info(f"Destroyed secret version: {response}")

def get_secret_from_key_server(
        content_id: str,
        package_id: str,
        provider_id: str,
        video_quality: list[str],
        audio_quality: list[str],
        drm_type: list[str]
):
    if "none" in drm_type:
        print("drm_type is none")
        return None
    encryption_keys = []
    # keys = get_keys(video_quality, audio_quality, drm_type)
    keys = call_key_server(package_id, content_id, provider_id, video_quality, audio_quality, drm_type)
    for item in keys:
        for key, value in item.items():
            if key == "AUDIO":
                encryption_keys.append(process_keys(video_quality, audio_quality, drm_type, "audio", value))
            # elif key == "HD":
            #    encryption_keys.append(process_keys(video_quality, audio_quality, drm_type, "hd", value))
            # elif key == "SD":
            #    encryption_keys.append(process_keys(video_quality, audio_quality, drm_type, "sd", value))
    return encryption_keys


def process_keys(
        video_quality: list[str],
        audio_quality: list[str],
        drm_type: list[str],
        type: str,
        data
):
    processed_data = {
        "keyId": data["keyId"],
        "key": data["key"],
        "iv": data["keyIv"],
        "keyUri": f"skd://{data['keyId']}",
        "matchers": [create_matchers(video_quality, audio_quality, drm_type, type)]
    }
    return processed_data


def create_matchers(
        video_quality: list[str],
        audio_quality: list[str],
        drm_type: list[str],
        keys: str
):
    matchers = {}
    mux_streams = []
    if keys == "audio":
        if if_fairplay_drm_exist(drm_type) is not None:
            if 64 in audio_quality:
                mux_streams.append("fmp4_fairplay_5")
            if 360 in video_quality:
                mux_streams.append("fmp4_fairplay_1")
            if 480 in video_quality:
                mux_streams.append("fmp4_fairplay_2")
            if 720 in video_quality:
                mux_streams.append("fmp4_fairplay_3")
            if 1080 in video_quality:
                mux_streams.append("fmp4_fairplay_4")
        if if_widevine_drm_exist(drm_type) is not None:
            if 64 in audio_quality:
                mux_streams.append("fmp4_widevine_5")
            if 360 in video_quality:
                mux_streams.append("fmp4_widevine_1")
            if 480 in video_quality:
                mux_streams.append("fmp4_widevine_2")
            if 720 in video_quality:
                mux_streams.append("fmp4_widevine_3")
            if 1080 in video_quality:
                mux_streams.append("fmp4_widevine_4")

    if keys == "sd":
        if if_fairplay_drm_exist(drm_type) is not None:
            if 360 in video_quality:
                mux_streams.append("fmp4_fairplay_1")
            if 480 in video_quality:
                mux_streams.append("fmp4_fairplay_2")
            if 720 in video_quality:
                mux_streams.append("fmp4_fairplay_3")
        if if_widevine_drm_exist(drm_type) is not None:
            if 360 in video_quality:
                mux_streams.append("fmp4_widevine_1")
            if 480 in video_quality:
                mux_streams.append("fmp4_widevine_2")
            if 720 in video_quality:
                mux_streams.append("fmp4_widevine_3")

    if keys == "hd":
        if if_fairplay_drm_exist(drm_type) is not None:
            if 1080 in video_quality:
                mux_streams.append("fmp4_fairplay_4")
        if if_widevine_drm_exist(drm_type) is not None:
            if 1080 in video_quality:
                mux_streams.append("fmp4_widevine_4")

    matchers["muxStreams"] = mux_streams
    return matchers
