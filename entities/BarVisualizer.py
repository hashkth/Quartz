from engine import *

class BarVisualizer:
    def __init__(self, editor):
        self.editor = editor
        self.fast_avg = self.slow_avg = 0
        self.spectrum = None
        self.bg_path = None
        self.bg_scale = 1
        self.top_col = self.bottom_col = imgui.Vec4(1, 1, 1, 1)

    def _process_spectrum(self, spectrum):
        self.spectrum = np.asarray(spectrum, dtype=np.float32)
        if np.isscalar(self.fast_avg) or self.fast_avg is None:
            self.fast_avg = self.spectrum.copy()
        if np.isscalar(self.slow_avg) or self.slow_avg is None:
            self.slow_avg = self.spectrum.copy()

        self.fast_avg = self.fast_avg * .4 + self.spectrum * .6
        self.slow_avg = self.slow_avg * .995 + self.spectrum * .005
        target = np.maximum(0, self.fast_avg - self.slow_avg)
        target *= 4 * np.exp(-np.linspace(0, 3, len(target)))
        np.convolve(self.spectrum, [.1, .8, .1], mode="same")
        self.bg_scale = 1 + np.sum(self.spectrum) / 640

    def process(self):
        self._process_spectrum(Audio.get_spectrum("Music", self.editor.offset, 80))

    def process_export(self, spectrum):
        self._process_spectrum(spectrum)

    def reset_animation(self):
        self.fast_avg = self.slow_avg = 0
        self.spectrum = np.zeros(80, np.float32)
        self.bg_scale = 1

    def render(self):
        Core.ctx.clear()
        total = float(np.sum(self.spectrum))

        if self.bg_path:
            Renderer.draw_tex(
                "BarVis_BG",
                self.editor.transform_matrix(0, 0, 1600, 900, self.bg_scale),
                alpha=.5 + total / 80
            )

        bottom = [self.bottom_col.x, self.bottom_col.y, self.bottom_col.z, self.bottom_col.w]
        top = [self.top_col.x, self.top_col.y, self.top_col.z, self.top_col.w]

        for i, val in enumerate(self.spectrum):
            x = i * 20 - 800 + 1600 / 128
            Renderer.draw_line(
                [x, -450, 0, *bottom],
                [x, -450 + val * 500, 0, *top]
            )

        Renderer.render()

    def show_settings(self):
        if imgui.button("Load Background"):
            self.bg_path = tk.filedialog.askopenfilename(
                title="Load Background",
                filetypes=[("Image files", ("*.png",))]
            )
            if self.bg_path:
                Renderer.unload_textures(["BarVis_BG"])
                Data.remove_tex("BarVis_BG")
                Data.load_tex("BarVis_BG", self.bg_path)
                Renderer.load_textures(["BarVis_BG"])

        imgui.text("Top")
        imgui.same_line()
        _, self.top_col = imgui.color_edit4("##Top", self.top_col)
        imgui.text("Bottom")
        imgui.same_line()
        _, self.bottom_col = imgui.color_edit4("##Bottom", self.bottom_col)