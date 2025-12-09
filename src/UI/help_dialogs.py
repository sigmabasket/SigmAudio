import flet as ft


class HelpDialog:
    """Диалог справки для аудиоредактора"""

    def __init__(self, page):
        self.page = page
        self.dialog = None

    def show(self):
        """Показать диалог справки"""
        content_items = [
            ft.Text("🎵 ОСНОВНЫЕ ФУНКЦИИ", size=14, weight="bold", color=ft.Colors.BLUE),
            ft.Text("• Добавить трек - создаёт новую дорожку", size=11),
            ft.Text("• Загрузить аудио - добавляет файлы на дорожку", size=11),
            ft.Text("• Воспроизведение - проигрывает проект", size=11),
            ft.Text("• Экспорт - сохраняет в MP3/WAV/FLAC/OGG", size=11),

            ft.Divider(),

            ft.Text("⏱️ УПРАВЛЕНИЕ ВРЕМЕНЕМ", size=14, weight="bold", color=ft.Colors.BLUE),
            ft.Text("• Слайдер - перемотка по проекту", size=11),
            ft.Text("• Кнопка +5 сек - добавляет 5 секунд", size=11),
            ft.Text("• Лента времени - показывает секунды", size=11),
            ft.Text("• Zoom In/Out - масштабирование", size=11),

            ft.Divider(),

            ft.Text("🎬 РАБОТА С КЛИПАМИ", size=14, weight="bold", color=ft.Colors.BLUE),
            ft.Text("• Перетаскивание - движение клипов", size=11),
            ft.Text("• Обрезание - сокращение клипа", size=11),
            ft.Text("• Громкость - уровень звука клипа", size=11),
            ft.Text("• Удаление - удаление клипа", size=11),

            ft.Divider(),

            ft.Text("📊 ФОРМАТЫ ЭКСПОРТА", size=14, weight="bold", color=ft.Colors.BLUE),
            ft.Text("• WAV - без сжатия, лучшее качество", size=11),
            ft.Text("• MP3 - сжатие, малый размер", size=11),
            ft.Text("• FLAC - без потерь, хорошее качество", size=11),
            ft.Text("• OGG - альтернативный формат", size=11),
        ]

        self.dialog = ft.AlertDialog(
            title=ft.Text("📖 Справка - Аудиоредактор", size=20, weight="bold"),
            content=ft.Column(
                content_items,
                scroll=ft.ScrollMode.AUTO,
                spacing=8,
            ),
            actions=[
                ft.TextButton(
                    "Закрыть",
                    on_click=lambda e: self._close(),
                    style=ft.ButtonStyle(color=ft.Colors.BLUE),
                )
            ],
            modal=True,
        )
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def _close(self):
        """Закрыть диалог"""
        if self.dialog:
            self.dialog.open = False
            self.page.update()