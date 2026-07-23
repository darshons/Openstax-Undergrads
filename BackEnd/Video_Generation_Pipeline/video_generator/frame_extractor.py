import cv2
import tempfile
import os
import numpy as np
from pathlib import Path


def extract_last_frame(
    video_path: str, save_file: bool, backward_offset: int = 0
) -> str | np.ndarray:
    """
    Extract the last frame from a video file and save it as an image.

    Args:
        video_path (str): Path to the input video file.
        save_file (bool): If True, save the last frame as an image. If False, return the frame data as a numpy array.
        backward_offset (int): Number of frames to go back from the last frame.
    """
    # Open the video file
    video = cv2.VideoCapture(video_path)

    frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

    # Go to the last frame or the frame specified by backward_offset (how many frames to go back from the last frame)
    video.set(cv2.CAP_PROP_POS_FRAMES, (frame_count - 1) - backward_offset)

    # Read the last frame
    ret, frame = video.read()

    if not ret:
        raise ValueError("Could not read the last frame from the video.")

    if not save_file:
        return np.array(frame)
    else:
        dir_path = Path(tempfile.gettempdir()) / "video_generator_last_frames"

        dir_path.mkdir(parents=True, exist_ok=True)

        path = tempfile.NamedTemporaryFile(
            suffix=".png",
            delete=False,
            dir=dir_path,
        ).name

        success = cv2.imwrite(path, frame)

        if not success:
            raise ValueError("Could not save the last frame as an image.")

        video.release()

        return path
