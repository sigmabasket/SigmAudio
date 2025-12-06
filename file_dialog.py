import flet as ft
import os


class FileDialog:
    """
    Класс для работы с диалогом выбора файлов
    """

    def __init__(self, page, on_files_selected_callback):
        self.page = page
        self.on_files_selected_callback = on_files_selected_callback

        # Создаем контрол для выбора файлов
        self.file_picker = ft.FilePicker(on_result=self._on_file_picker_result)
        self.page.overlay.append(self.file_picker)

    def _on_file_picker_result(self, e: ft.FilePickerResultEvent):
        """Обработка результата выбора файлов"""
        if e.files:
            file_paths = [f.path for f in e.files]
            self.on_files_selected_callback(file_paths)

    def pick_files(self):
        """Открывает диалог выбора файлов"""
        self.file_picker.pick_files(
            allow_multiple=True,
            allowed_extensions=["wav", "mp3", "flac", "m4a", "aac", "ogg"]
        )