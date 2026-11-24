from engine import *
import threading, queue

class Exporter:
    def __init__(self, editor):
        self.editor = editor
        self._ENCODE_SENTINEL = object()
        self._reset_runtime_state()

    def start(self, title, width, height, fps):
        if self.exporting: return
        self._reset_runtime_state()
        duration = float(Audio.get_audio_data("Music").duration)
        self.exporting, self.done = True, False
        self.frame_index, self.offset, self.dt = 0, 0., 1 / fps
        self.total_frames = max(1, int(duration * fps + .5))
        self.video_title, self.video_path = title, EXPORT_DIR / f"{title}.mp4"
        self._encode_queue, self._audio_queue = queue.Queue(8), queue.Queue(32)
        self._encoder_error = self._audio_error = None
        self._stop_requested = False

        self.container = av.open(self.video_path, "w")
        self.stream = self.container.add_stream("libx264", rate=fps)
        self.stream.width, self.stream.height = width, height
        self.stream.pix_fmt = "yuv420p"
        self.stream.options = {"preset": "ultrafast", "crf": "20"}

        self._encoder_thread = threading.Thread(
            target=self._encode_worker, daemon=True)
        self._audio_thread = threading.Thread(
            target=self._audio_worker, daemon=True)
        self._encoder_thread.start()
        self._audio_thread.start()

    def _audio_worker(self):
        try:
            for i in range(self.total_frames):
                if self._stop_requested: break
                self._audio_queue.put((
                    i, np.asarray(
                        Audio.get_spectrum("Music", i * self.dt, 80),
                        dtype=np.float32).copy()))
        except Exception as e:
            self._audio_error = e

    def _encode_worker(self):
        try:
            while True:
                item = self._encode_queue.get()
                if item is self._ENCODE_SENTINEL: break
                i, data = item
                f = av.VideoFrame.from_ndarray(data, format="rgb24")
                f.pts = i
                for p in self.stream.encode(f):
                    self.container.mux(p)
        except Exception as e:
            self._encoder_error = e

    def get_next_spectrum(self, block=True):
        if not self.exporting or self.frame_index >= self.total_frames:
            return None

        while True:
            if self._audio_error: raise self._audio_error
            try:
                i, spectrum = self._audio_queue.get(
                    block=block, timeout=.05 if block else None)
            except queue.Empty:
                if not block: return None
                if self._audio_thread and not self._audio_thread.is_alive():
                    if self._audio_error: raise self._audio_error
                    raise RuntimeError(
                        f"Audio analysis stopped before frame "
                        f"{self.frame_index} was generated.")
                continue

            if i != self.frame_index:
                raise RuntimeError(
                    f"Audio/video sync error: expected frame "
                    f"{self.frame_index}, received frame {i}")
            return spectrum

    def capture(self, framebuffer):
        if not self.exporting or self.frame_index >= self.total_frames:
            return

        data = np.frombuffer(
            framebuffer.read(components=3, alignment=1), np.uint8
        ).reshape(self.stream.height, self.stream.width, 3)
        data = np.flipud(data).copy()

        while self.exporting:
            if self._encoder_error: raise self._encoder_error
            try:
                self._encode_queue.put(
                    (self.frame_index, data), timeout=.05)
                break
            except queue.Full:
                pass

        self.frame_index += 1
        self.offset = min(
            self.frame_index * self.dt,
            self.total_frames * self.dt)

    def finish(self):
        if not self.exporting: return
        self._stop_requested = True

        if self._audio_thread: self._audio_thread.join()
        if self._encode_queue:
            self._encode_queue.put(self._ENCODE_SENTINEL)
        if self._encoder_thread: self._encoder_thread.join()

        if self._encoder_error:
            e = self._encoder_error
            self._close_video_container()
            self._reset_runtime_state()
            raise e

        if self.stream:
            for p in self.stream.encode():
                self.container.mux(p)
        self._close_video_container()

        try:
            self._mux_audio()
        finally:
            self._reset_runtime_state()

    def stop(self):
        if self.exporting:
            self.finish()
            Audio.stop("Music")

    def _close_video_container(self):
        if self.container:
            try: self.container.close()
            except: pass
        self.container = self.stream = None

    def _mux_audio(self):
        video_path = self.video_path
        final_path = EXPORT_DIR / f"{self.video_title}_x264.mp4"
        video = audio = output = None

        try:
            video = av.open(video_path, "r")
            audio = av.open(self.editor.music_path, "r")
            output = av.open(final_path, "w")

            vi, ai = video.streams.video[0], audio.streams.audio[0]
            vo = output.add_stream_from_template(vi)
            ao = output.add_stream_from_template(ai)

            for p in video.demux(vi):
                if p.dts is not None:
                    p.stream = vo
                    output.mux(p)

            for p in audio.demux(ai):
                if p.dts is not None:
                    p.stream = ao
                    output.mux(p)
        finally:
            for f in (output, video, audio):
                if f:
                    f.close()

    def _reset_runtime_state(self):
        self.exporting, self.done = False, True
        self.frame_index = self.total_frames = 0
        self.offset = self.dt = 0.
        self.video_title = self.video_path = ""
        self.container = self.stream = None
        self._encode_queue = self._audio_queue = None
        self._encoder_thread = self._audio_thread = None
        self._encoder_error = self._audio_error = None
        self._stop_requested = False