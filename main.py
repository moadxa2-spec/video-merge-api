import os
import uuid
import subprocess
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import asyncio

app = FastAPI(title="Video Merge API", version="1.0.0")

TEMP_DIR = "/tmp/video_merge"
os.makedirs(TEMP_DIR, exist_ok=True)


class MergeRequest(BaseModel):
    videos: List[str]  # List of video URLs


async def download_video(url: str, path: str):
    """Download a video from a URL to a local path."""
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to download video: {url}")
        with open(path, "wb") as f:
            f.write(response.content)


@app.get("/")
def root():
    return {"status": "ok", "message": "Video Merge API is running. POST to /merge with a list of video URLs."}


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
            video_paths.append(path)

        # Create concat file for FFmpeg
        concat_file = os.path.join(job_dir, "concat.txt")
        with open(concat_file, "w") as f:
            for path in video_paths:
                f.write(f"file '{path}'\n")

        # Output path
        output_path = os.path.join(job_dir, "merged.mp4")

        # Run FFmpeg to merge
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg error: {result.stderr}")

        # Return the merged video file
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
