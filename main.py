import os
import uuid
import subprocess
import httpx
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Video Merge API", version="2.0.0")

TEMP_DIR = "/tmp/video_merge"
os.makedirs(TEMP_DIR, exist_ok=True)


class MergeRequest(BaseModel):
    videos: List[str]


def extract_gdrive_id(url: str):
    """Extract Google Drive file ID from various URL formats."""
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"id=([a-zA-Z0-9_-]+)",
        r"/d/([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def is_gdrive_url(url: str) -> bool:
    return "drive.google.com" in url or "docs.google.com" in url


async def download_video(url: str, path: str):
    """Download a video from a URL, handling Google Drive specially."""

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # Handle Google Drive URLs
    if is_gdrive_url(url):
        file_id = extract_gdrive_id(url)
        if not file_id:
            raise HTTPException(status_code=400, detail=f"Could not extract Google Drive file ID from: {url}")

        # Use the direct download URL
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"

        async with httpx.AsyncClient(
            timeout=300,
            follow_redirects=True,
            headers=headers
        ) as client:
            response = await client.get(download_url)

            # Handle Google Drive large file warning page
            if response.status_code == 200 and b"virus scan warning" in response.content.lower():
                # Extract confirm token and retry
                match = re.search(r'confirm=([0-9A-Za-z_-]+)', response.text)
                if match:
                    confirm = match.group(1)
                    download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm}"
                    response = await client.get(download_url)

            if response.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Failed to download from Google Drive. Make sure the file is public. ID: {file_id}")

            # Check we got video content not HTML
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type:
                raise HTTPException(
                    status_code=400,
                    detail=f"Google Drive returned HTML instead of video. Make sure the file is shared as 'Anyone with the link'. ID: {file_id}"
                )

            with open(path, "wb") as f:
                f.write(response.content)
    else:
        # Regular URL download
        async with httpx.AsyncClient(timeout=300, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Failed to download video: {url}")
            with open(path, "wb") as f:
                f.write(response.content)


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Video Merge API v2 is running. POST to /merge with a list of video URLs.",
        "supports": ["direct URLs", "Google Drive links"]
    }


@app.post("/merge")
async def merge_videos(request: MergeRequest):
    if len(request.videos) < 2:
        raise HTTPException(status_code=400, detail="At least 2 video URLs are required.")
    if len(request.videos) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 videos allowed.")

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(TEMP_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    video_paths = []

    try:
        # Download all videos
        for i, url in enumerate(request.videos):
            path = os.path.join(job_dir, f"video_{i}.mp4")
            await download_video(url, path)

            # Verify file size
            size = os.path.getsize(path)
            if size < 1000:
                raise HTTPException(
                    status_code=400,
                    detail=f"Video {i+1} downloaded but file is too small ({size} bytes). Check the URL is a direct video link and the file is publicly shared."
                )

            video_paths.append(path)

        # Re-encode videos to ensure compatibility before concat
        reencoded_paths = []
        for i, path in enumerate(video_paths):
            reencoded = os.path.join(job_dir, f"reencoded_{i}.mp4")
            reencode_cmd = [
                "ffmpeg", "-y", "-i", path,
                "-c:v", "libx264", "-c:a", "aac",
                "-strict", "experimental",
                reencoded
            ]
            subprocess.run(reencode_cmd, capture_output=True, timeout=300)
            reencoded_paths.append(reencoded)

        # Create concat file
        concat_file = os.path.join(job_dir, "concat.txt")
        with open(concat_file, "w") as f:
            for path in reencoded_paths:
                f.write(f"file '{path}'\n")

        # Output
        output_path = os.path.join(job_dir, "merged.mp4")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg merge error: {result.stderr[-500:]}")

        return FileResponse(
            output_path,
            media_type="video/mp4",
            filename="merged.mp4",
            headers={"X-Job-ID": job_id}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "healthy"}
