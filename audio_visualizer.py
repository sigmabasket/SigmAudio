import flet as ft
import numpy as np
from pydub import AudioSegment
import os


class AudioWaveform:
    """
    Класс для отображения аудио диаграммы (waveform) клипа
    """

    def __init__(self, audio_path, width, height, color=ft.Colors.BLUE_400):
        self.audio_path = audio_path
        self.width = max(20, width)  # Минимальная ширина
        self.height = height
        self.color = color

    def _create_simple_visualization(self):
        """Создает простую визуализацию когда не удалось загрузить аудио"""
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
            alignment=ft.alignment.center
        )

    def build(self):
        """Возвращает контрол для отображения waveform"""
        try:
            # Проверяем существование файла
            if not os.path.exists(self.audio_path):
                print(f"Audio file not found: {self.audio_path}")
                return self._create_simple_visualization()

            # Пробуем загрузить аудио
            audio = AudioSegment.from_file(self.audio_path)
            duration_ms = len(audio)

            print(f"Loaded audio: {self.audio_path}, duration: {duration_ms}ms")

            # Для тестирования создаем простую визуализацию
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
                tooltip=f"Длительность: {duration_ms / 1000:.1f}с"
            )

        except Exception as e:
            print(f"Error creating audio visualization for {self.audio_path}: {e}")
            return self._create_simple_visualization()


def create_waveform_clip_visualization(clip, time_ruler, top=25):
    """
    Создает визуализацию клипа с waveform диаграммой
    """
    try:
        print(f"Creating waveform for clip: {clip.name}")

        # Используем линейку для точного преобразования времени в пиксели
        clip_start_pixels = time_ruler.time_to_pixels(clip.start_time)
        clip_width_pixels = time_ruler.time_to_pixels(clip.duration)

        # Минимальная и максимальная ширина для видимости
        clip_width_pixels = max(20, min(clip_width_pixels, 5000))

        print(f"Clip pixels - start: {clip_start_pixels}, width: {clip_width_pixels}")

        # Создаем waveform визуализацию
        waveform = AudioWaveform(
            audio_path=clip.file_path,
            width=clip_width_pixels,
            height=30,
            color=ft.Colors.BLUE_400
        )

        # Получаем визуализацию
        waveform_content = waveform.build()

        # Оборачиваем в контейнер с позиционированием
        positioned_container = ft.Container(
            content=waveform_content,
            left=clip_start_pixels,
            top=top,
            width=clip_width_pixels,
            height=30,
            border_radius=5,
            tooltip=f"{clip.name}\nНачало: {clip.start_time / 1000:.1f}с\nДлительность: {clip.duration / 1000:.1f}с",
        )
        return positioned_container
    except Exception as e:
        print(f"Error creating waveform visualization: {e}")
        # Fallback контейнер
        return ft.Container(
            width=100,
            height=30,
            bgcolor=ft.Colors.RED_400,
            border_radius=5,
            content=ft.Text("Error", size=10, color=ft.Colors.WHITE),
            alignment=ft.alignment.center,
            tooltip=f"{clip.name} (ошибка визуализации)",
        )