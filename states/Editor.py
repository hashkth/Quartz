from entities import *


class Editor(State):

    def __init__(self):
        super().__init__("Editor")
        self.music_file = ""
        self.music_path = ""
        self.offset = 0
        self.project_title = "New Project"

        self.visualizers = ["None", "BarVisualizer"]
        self.visualizer_index = 0
        self.visualizer = None

        self.exporter = Exporter(self)

        self.window_size = [1280, 720]
        self.resolutions = [
            "1920 x 1200", "1920 x 1080", "1600 x 1000", "1600 x 900",
            "1440 x 900", "1366 x 768", "1280 x 800", "1280 x 720"
        ]
        self.res_index = 7

        self.fps = 60
        self.fps_options = ["60", "50", "30", "24"]
        self.fps_index = 0

        # Number of video frames rendered between UI updates.
        # Increase this for faster export if the GPU has enough headroom.
        self.export_batch_size = 8

    def enter(self):
        Core.imgui_io.font_global_scale = 2
        Core.ctx.line_width = 1600 / 80 - 4
        Camera.set_perspective("2d")
        Core.add_render_target("Preview", *self.window_size, 4)

    def exit(self):
        Core.imgui_io.font_global_scale = 1

    def process(self):
        # During export, audio is processed by Exporter in its own thread.
        # Do not advance the live visualizer clock here.
        if self.exporter.exporting:
            return

        if self.music_file and self.visualizer:
            self.visualizer.process()

    def transform_matrix(self, x, y, width, height, scale=1):
        return np.array([
            [width * scale, 0.0, 0.0, x],
            [0.0, height * scale, 0.0, y],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype="f4")

    def _render_one_export_frame(self):
        spectrum = self.exporter.get_next_spectrum(block=True)

        if spectrum is None:
            return False

        # Feed the precomputed audio data into the visualizer.
        self.visualizer.process_export(spectrum)

        Core.set_render_target("Preview")
        self.visualizer.render()
        Core.reset_render_target()

        # capture() only queues the finished RGB frame. Encoding happens
        # asynchronously in Exporter's encoder thread.
        self.exporter.capture(
            Core.get_render_target_framebuffer("Preview")
        )

        return True

    def render(self):
        if self.exporter.exporting:
            if not self.visualizer:
                self.exporter.stop()
                return

            # Render several video frames per UI frame. The Preview texture
            # remains the most recently rendered frame, so the UI only ever
            # displays the current frame rather than every exported frame.
            for _ in range(self.export_batch_size):
                if not self.exporter.exporting:
                    break

                if not self._render_one_export_frame():
                    self.exporter.stop()
                    break

                if self.exporter.frame_index >= self.exporter.total_frames:
                    self.exporter.finish()
                    break

            return

        if self.music_file and self.visualizer:
            Core.set_render_target("Preview")
            self.visualizer.render()
            Core.reset_render_target()

    def render_preview(self):
        imgui.set_next_window_pos(imgui.Vec2(Core.qw, 0))
        imgui.set_next_window_size(imgui.Vec2(Core.qw * 3, Core.h))
        imgui.push_style_var_vec2(imgui.StyleVar.WindowPadding, imgui.Vec2(0, 0))
        imgui.begin("Preview", flags=imgui.WindowFlags.NoResize | imgui.WindowFlags.NoCollapse )

        x, y = imgui.get_cursor_pos()
        w, h = imgui.get_available_region()
        if w >= h:
            scale = h / self.window_size[1]
            if scale * self.window_size[0] > w:
                scale = w / self.window_size[0]
                draw_w = w
                draw_h = int(scale * self.window_size[1])
            else:
                draw_w = int(scale * self.window_size[0])
                draw_h = h
        else:
            scale = w / self.window_size[0]
            if scale * self.window_size[1] > h:
                scale = h / self.window_size[1]
                draw_w = int(scale * self.window_size[0])
                draw_h = h
            else:
                draw_w = w
                draw_h = int(scale * self.window_size[1])
        imgui.set_cursor_pos(
            imgui.Vec2(
                x + (w - draw_w) // 2,
                y + (h - draw_h) // 2
            )
        )
        imgui.image(
            Core.get_render_target_tex("Preview").glo,
            imgui.Vec2(draw_w, draw_h),
            imgui.Vec2(0, 1),
            imgui.Vec2(1, 0)
        )
        imgui.end()
        imgui.pop_style_var()

    def render_ui(self):
        imgui.set_next_window_pos(imgui.Vec2(0, 0))
        imgui.set_next_window_size(imgui.Vec2(Core.qw, Core.h))

        if self.visualizers[self.visualizer_index] != "None":
            imgui.set_next_window_size(
                imgui.Vec2(Core.qw, Core.hh)
            )

        imgui.begin(
            "Controls",
            flags=imgui.WindowFlags.NoResize |
                    imgui.WindowFlags.NoCollapse
        )

        imgui.text("Title ")
        imgui.same_line()
        _, self.project_title = imgui.input_text(
            "##ProjectTitle",
            self.project_title
        )

        imgui.text("Style ")
        imgui.same_line()
        changed, self.visualizer_index = imgui.combo(
            "##Visualizer",
            self.visualizer_index,
            self.visualizers
        )

        if changed:
            if self.visualizers[self.visualizer_index] == "BarVisualizer":
                self.visualizer = BarVisualizer(self)
            else:
                self.visualizer = None

        imgui.text("Size ")
        imgui.same_line()
        changed, self.res_index = imgui.combo(
            "##Resolution",
            self.res_index,
            self.resolutions
        )

        if changed:
            self.window_size = [
                int(x) for x in self.resolutions[self.res_index].split(" x ")
            ]

            Core.delete_render_target("Preview")
            Core.add_render_target("Preview", *self.window_size, 4)

        imgui.text("FPS ")
        imgui.same_line()
        _, self.fps_index = imgui.combo(
            "##FPS",
            self.fps_index,
            self.fps_options
        )
        self.fps = int(self.fps_options[self.fps_index])

        if imgui.button("Load Audio"):
            path = tk.filedialog.askopenfilename(
                title="Load Audio",
                filetypes=[
                    ("Audio files", ("*.mp3", "*.wav", "*.ogg"))
                ]
            )

            if path:
                self.music_path = path
                self.music_file = path.split("/")[-1]

                Audio.remove("Music")
                Audio.add("Music", path)

                self.offset = Audio.get_offset("Music")

        if imgui.button("Play"):
            Audio.play("Music")

        imgui.same_line()

        if imgui.button("Pause"):
            Audio.pause("Music")

        imgui.same_line()

        if imgui.button("Stop"):
            Audio.stop("Music")

        if self.music_file:
            changed, self.offset = imgui.slider_int(
                "##Offset",
                int(self.offset),
                0,
                int(Audio.get_audio_data("Music").duration)
            )

            if changed:
                if (
                    Audio.get_source("Music") is None or
                    not Audio.get_source("Music").playing
                ):
                    Audio.play("Music")
                    Audio.pause("Music")

                Audio.set_offset("Music", self.offset)
            else:
                self.offset = Audio.get_offset("Music")

        if imgui.button("Export"):
            if self.music_file and self.visualizer and not self.exporter.exporting:
                if hasattr(self.visualizer, "reset_animation"):
                    self.visualizer.reset_animation()
                self.exporter.start(
                    self.project_title,
                    *self.window_size,
                    self.fps
                )

        imgui.end()

        if self.visualizers[self.visualizer_index] == "BarVisualizer":
            imgui.set_next_window_pos(
                imgui.Vec2(0, Core.hh)
            )
            imgui.set_next_window_size(
                imgui.Vec2(Core.qw, Core.hh)
            )
            imgui.begin(
                "Style Settings",
                flags=imgui.WindowFlags.NoResize |
                        imgui.WindowFlags.NoCollapse
            )
            self.visualizer.show_settings()
            imgui.end()

        if not self.exporter.exporting:
            self.render_preview()
        else:
            # --------------------------------------------------------------
            # Export progress
            # --------------------------------------------------------------

            self.offset = self.exporter.offset

            imgui.set_next_window_pos(
                imgui.Vec2(Core.qw, 0)
            )

            imgui.set_next_window_size(
                imgui.Vec2(Core.qw * 3, Core.h)
            )

            imgui.begin(
                "Export",
                flags=imgui.WindowFlags.NoResize |
                    imgui.WindowFlags.NoCollapse
            )

            if self.exporter.total_frames > 0:
                progress = (
                    self.exporter.frame_index /
                    self.exporter.total_frames
                )

                progress = max(
                    0.0,
                    min(1.0, progress)
                )
            else:
                progress = 0.0

            # --------------------------------------------------------------
            # Bar dimensions
            # --------------------------------------------------------------

            bar_width = 500
            bar_height = 30

            # Get available content area.
            content_width = imgui.get_available_region()[0]
            content_height = imgui.get_available_region()[1]

            # Center the whole progress section.
            section_height = bar_height + 10 + imgui.get_text_line_height()

            x, y = imgui.get_cursor_pos()
            start_x = (
                x +
                (content_width - bar_width) / 2
            )

            start_y = (
                y +
                (content_height - section_height) / 2
            )

            imgui.set_cursor_pos(
                imgui.Vec2(
                    start_x,
                    start_y
                )
            )

            # --------------------------------------------------------------
            # Draw progress bar
            # --------------------------------------------------------------

            x, y = imgui.get_cursor_screen_pos()

            draw_list = imgui.get_window_draw_list()

            # Background
            draw_list.add_rect_filled(
                imgui.Vec2(x, y),
                imgui.Vec2(
                    x + bar_width,
                    y + bar_height
                ),
                imgui.get_color_u32(
                    imgui.Vec4(0.15, 0.15, 0.15, 1.0)
                )
            )

            # Green progress
            draw_list.add_rect_filled(
                imgui.Vec2(x, y),
                imgui.Vec2(
                    x + bar_width * progress,
                    y + bar_height
                ),
                imgui.get_color_u32(
                    imgui.Vec4(0.0, 1.0, 0.0, 1.0)
                )
            )

            # Reserve bar space
            imgui.dummy(
                imgui.Vec2(
                    bar_width,
                    bar_height
                )
            )

            # --------------------------------------------------------------
            # Center percentage text underneath
            # --------------------------------------------------------------

            percentage = f"{progress * 100:.1f}%"

            text_width = imgui.calc_text_size(
                percentage
            )[0]

            imgui.set_cursor_pos(
                imgui.Vec2(start_x + (bar_width - text_width) / 2, imgui.get_cursor_pos()[1])
            )

            imgui.text(percentage)

            imgui.end()


Core.add_state(Editor)
