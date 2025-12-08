import flet as ft
import threading
import time
from controllers import AudioEditorController
from utils import create_transport_controls
from ui_components import TrackManager


def main(page: ft.Page):
    page.title = "Audio editor"
    page.theme_mode = "dark"
    page.padding = 20
    page.scroll = ft.ScrollMode.ADAPTIVE

    editor = AudioEditorController()
    track_manager = TrackManager(editor, page)

    editor.set_track_manager(track_manager)

    transport_controls = create_transport_controls(editor, page)

    def on_resize(e):
        print(f"Окно изменено: {page.width}x{page.height}")
        track_manager.update_all_visualizations()
        page.update()

    page.on_resize = on_resize

    content = ft.Column([
        ft.Text("SigmAudio",
                size=24, weight="bold", color=ft.Colors.BLUE_200),
        track_manager.get_track_list_container(),
        transport_controls
    ],
        scroll=ft.ScrollMode.AUTO,
        expand=True)

    page.add(content)

    def delayed_update():
        time.sleep(0.3)
        track_manager.update_all_visualizations()
        page.update()

    threading.Thread(target=delayed_update, daemon=True).start()


if __name__ == "__main__":
    ft.app(target=main)