
from .config import *

import queue
import threading


class Recorder:

    container = None
    stream = None
    recording = False
    queue = queue.Queue(maxsize=60)
    thread = None
    frame_index = 0

    @classmethod
    def start(cls, title: str, width: int, height: int, fps: int):
        if not cls.recording:
            cls.recording = True
            cls.container = av.open(EXPORT_DIR / (title + ".mp4"), "w")
            cls.stream = cls.container.add_stream("libx264", rate=fps)
            cls.stream.width = width
            cls.stream.height = height
            cls.stream.pix_fmt = "yuv420p"
            cls.stream.options = {"preset": "fast", "crf": "20"}
            cls.thread = threading.Thread(target=cls._encoder_worker, daemon=True)
            cls.thread.start()

    @classmethod
    def stop(cls):
        if cls.recording:
            cls.recording = False
            cls.queue.put(None)
            cls.thread.join()
            for packet in cls.stream.encode():
                cls.container.mux(packet)
            cls.container.close()
            cls.container = None
            cls.stream = None
            cls.thread = None

    @classmethod
    def capture(cls, framebuffer):
        frame = framebuffer.read(components=3, alignment=1)
        frame_data = np.frombuffer(frame, dtype=np.uint8).reshape((cls.stream.height, cls.stream.width, 3))
        frame_data = np.flipud(frame_data)
        try:
            cls.queue.put_nowait(frame_data)
        except queue.Full:
            pass

    @classmethod
    def _encoder_worker(cls):
        while True:
            frame = cls.queue.get()
            if frame is None:
                cls.queue.task_done()
                break
            video = av.VideoFrame.from_ndarray(frame, format="rgb24")
            video.pts = cls.frame_index
            cls.frame_index += 1
            for packet in cls.stream.encode(video):
                cls.container.mux(packet)
            cls.queue.task_done()