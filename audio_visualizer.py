import flet as ft
from pydub import AudioSegment
import os


class AudioWaveform:
    """Визуализирует волновую форму аудиофайла"""

    def __init__(self, audio_path, width, height, color=ft.Colors.BLUE_400):
        self.audio_path = audio_path
        self.width = max(20, width)
        self.height = height
        self.color = color

    def create_simple_visualization(self):
        """Возвращает простую визуализацию как заглушку"""
        return ft.Container(
            width=self.width,
            height=self.height,
            bgcolor=self.color,
            border_radius=5,
            content=ft.Text(
                "Audio",
                size=10,
                color=ft.Colors.WHITE,
                text_align=ft.TextAlign.CENTER,
            ),
            alignment=ft.alignment.center,
        )

    def build(self):
        """Создаёт контейнер с визуализацией аудиофайла"""
        try:
            if not os.path.exists(self.audio_path):
                return self.create_simple_visualization()

            audio = AudioSegment.from_file(self.audio_path)
            duration_ms = len(audio)

            return ft.Container(
                width=self.width,
                height=self.height,
                bgcolor=self.color,
                border_radius=5,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.center_left,
                    end=ft.alignment.center_right,
                    colors=[ft.Colors.BLUE_400, ft.Colors.BLUE_700],
                ),
                content=ft.Text(
                    f"{os.path.basename(self.audio_path)}",
                    size=10,
                    color=ft.Colors.WHITE,
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.alignment.center,
                tooltip=f"{duration_ms / 1000:.1f}s",
            )
        except Exception:
            return self.create_simple_visualization()


def create_waveform_clip_visualization(clip, time_ruler, top=25):
    """Создаёт визуализацию клипа с волновой формой"""
    try:
        clip_start_pixels = time_ruler.time_to_pixels(clip.start_time)
        clip_width_pixels = time_ruler.time_to_pixels(clip.duration)
        clip_width_pixels = max(20, min(clip_width_pixels, 5000))

        waveform = AudioWaveform(
            audio_path=clip.filepath,
            width=clip_width_pixels,
            height=30,
            color=ft.Colors.BLUE_400
        )

        waveform_content = waveform.build()

        positioned_container = ft.Container(
            content=waveform_content,
            left=clip_start_pixels,
            top=top,
            width=clip_width_pixels,
            height=30,
            border_radius=5,
            tooltip=f"{clip.name}\n{clip.start_time / 1000:.1f}s - {clip.duration / 1000:.1f}s",
        )

        return positioned_container

    except Exception:
        return ft.Container(
            width=100,
            height=30,
            bgcolor=ft.Colors.RED_400,
            border_radius=5,
            content=ft.Text(
                "Error",
                size=10,
                color=ft.Colors.WHITE,
            ),
            alignment=ft.alignment.center,
            tooltip=f"{clip.name}",
        )