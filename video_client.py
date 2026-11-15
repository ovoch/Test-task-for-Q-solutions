import os


def UploadVideo(server_url: str, video_path: str, company_name: str) -> str:
    import requests

    upload_url = f"{server_url.rstrip('/')}/upload"
    with open(video_path, "rb") as video_file:
        response = requests.post(
            upload_url,
            files = {"file": (os.path.basename(video_path), video_file)},
            data = {"company_name": company_name},
            timeout = 120,
        )
    response.raise_for_status()
    return response.json()["video_url"]


def GetVideoURL(server_url: str, company_name: str) -> str:
    import requests

    get_url = f"{server_url.rstrip('/')}/get_video_url"
    response = requests.get(get_url, params = {"company_name": company_name}, timeout = 30)
    response.raise_for_status()
    return response.json()["video_url"]