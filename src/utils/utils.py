import flet as ft


def create_transport_controls(editor, page):
    """Создает элементы управления воспроизведением"""
    play_button = ft.IconButton("play_arrow", icon_size=40)
    position_text = ft.Text("00:00 / 00:00", size=16)

    def update_position_text():
        """Обновляет текстовое отображение позиции"""
        current_time = editor.project.current_time
        total_time = editor.project.duration

        current_sec = int(current_time / 1000)
        total_sec = int(total_time / 1000)

        position_text.value = f"{current_sec // 60:02d}:{current_sec % 60:02d} / {total_sec // 60:02d}:{total_sec % 60:02d}"

    def toggle_play(e):
        editor.toggle_play()
        play_button.icon = "pause" if editor.is_playing() else "play_arrow"

        update_position_text()

        if editor.is_playing():
            import threading
            import time

            def update_loop():
                while editor.is_playing() and editor.project.playing:
                    update_position_text()
                    page.update()
                    time.sleep(0.1)
                update_position_text()
                page.update()

            threading.Thread(target=update_loop, daemon=True).start()

        page.update()

    play_button.on_click = toggle_play

    update_position_text()

    return ft.Row([
        play_button,
        position_text
    ], alignment=ft.MainAxisAlignment.CENTER)