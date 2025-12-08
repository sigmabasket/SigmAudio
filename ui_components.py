import flet as ft
import threading
import time
import os
from pathlib import Path
import platform

from drag_drop import create_draggable_clip_visualization
from audio_exporter import AudioExporter


class SyncSlider:
    """Синхронизированный слайдер для отображения прогресса воспроизведения"""

    def __init__(self, editor, size_manager, height=40, is_main_slider=False):
        self.editor = editor
        self.size_manager = size_manager
        self.height = height
        self.is_main_slider = is_main_slider
        self.is_dragging = False
        self.was_playing = False

        self.bg_container = ft.Container(
            expand=True,
            height=height,
            bgcolor=ft.Colors.GREY_600,
            border_radius=height / 2,
        )

        self.progress_container = ft.Container(
            width=0,
            height=height,
            bgcolor="#FFAB00",
            border_radius=height / 2,
        )

        self.slider_stack = ft.Stack(
            [self.bg_container, self.progress_container],
            expand=True,
            height=height,
        )

        self.slider_gesture = ft.GestureDetector(
            content=self.slider_stack,
            on_tap_down=self._handle_tap_down,
            on_pan_start=self._handle_drag_start,
            on_pan_update=self._handle_drag_update,
            on_pan_end=self._handle_drag_end,
        )

        self.on_position_changed = None

    def _get_container_width(self):
        """Получает ширину контейнера"""
        if hasattr(self.size_manager, 'time_ruler') and self.size_manager.time_ruler:
            return self.size_manager.time_ruler.ruler_width
        return 600

    def _handle_tap_down(self, e: ft.TapEvent):
        """Обработчик клика на слайдер"""
        if e.local_x is not None:
            container_width = self._get_container_width()
            if container_width > 0:
                corrected_x = max(0, min(e.local_x, container_width))
                if hasattr(self.size_manager, 'time_ruler') and self.size_manager.time_ruler:
                    time_ms = self.size_manager.time_ruler.pixels_to_time(corrected_x)
                    total_duration = self.editor.project.duration
                    percent = time_ms / total_duration if total_duration > 0 else 0
                    percent = max(0, min(1, percent))
                else:
                    percent = corrected_x / container_width

                self._update_visual_progress(percent)
                self.editor.set_playback_position(percent, seeking=False)

    def _handle_drag_start(self, e: ft.DragStartEvent):
        """Обработчик начала перетаскивания"""
        self.is_dragging = True
        self.was_playing = self.editor.is_playing()
        if self.was_playing:
            self.editor.project.paused = True

    def _handle_drag_update(self, e: ft.DragUpdateEvent):
        """Обработчик перетаскивания"""
        if e.local_x is not None and self.is_dragging:
            container_width = self._get_container_width()
            if container_width > 0:
                corrected_x = max(0, min(e.local_x, container_width))
                if hasattr(self.size_manager, 'time_ruler') and self.size_manager.time_ruler:
                    time_ms = self.size_manager.time_ruler.pixels_to_time(corrected_x)
                    total_duration = self.editor.project.duration
                    percent = time_ms / total_duration if total_duration > 0 else 0
                else:
                    percent = corrected_x / container_width
                percent = max(0, min(1, percent))

                self._update_visual_progress(percent)
                if self.on_position_changed:
                    self.on_position_changed(percent, True)

    def _handle_drag_end(self, e: ft.DragEndEvent):
        """Обработчик окончания перетаскивания"""
        if self.is_dragging:
            self.is_dragging = False
            container_width = self._get_container_width()
            if container_width > 0:
                final_percent = self.progress_container.width / container_width
                final_percent = max(0, min(1, final_percent))
                self.editor.set_playback_position(final_percent, seeking=True)
                self.editor.project.seeking = False

            if self.was_playing:
                self.editor.project.playing = True
                self.editor.project.paused = False
            self.was_playing = False

    def _update_visual_progress(self, percent):
        """Обновляет визуальный прогресс"""
        container_width = self._get_container_width()
        progress_width = percent * container_width
        self.progress_container.width = progress_width
        try:
            if hasattr(self.progress_container, 'page') and self.progress_container.page:
                self.progress_container.update()
            if hasattr(self.slider_stack, 'page') and self.slider_stack.page:
                self.slider_stack.update()
        except Exception:
            pass

    def set_position(self, position, visual_only=False):
        """Устанавливает позицию слайдера (от внешних источников)"""
        if not self.is_dragging or visual_only:
            self._update_visual_progress(position)

    def build(self):
        """Возвращает собранный слайдер"""
        return self.slider_gesture


class SizeManager:
    """Класс для управления размерами UI компонентов"""

    def __init__(self, page):
        self.page = page
        self.main_slider_width = 0
        self.track_clips_width = 0
        self.time_ruler_width = 0
        self.controls_panel_width = 150
        self.page_padding = 40

    def update_sizes(self):
        """Обновляет все размеры на основе текущего размера страницы"""
        if not self.page:
            return
        self.main_slider_width = self.page.width - self.page_padding
        self.track_clips_width = self.page.width - self.controls_panel_width - self.page_padding
        self.time_ruler_width = self.page.width - self.page_padding


class TimeRuler:
    """Класс для создания и управления линейкой времени"""

    def __init__(self, editor, size_manager, track_manager=None):
        self.editor = editor
        self.size_manager = size_manager
        self.track_manager = track_manager

        self.base_pixels_per_second = 100
        self.pixels_per_second = self.base_pixels_per_second
        self.min_pixels_per_second = 50
        self.max_pixels_per_second = 500

        self.ruler_container = None
        self.markers_container = None
        self.slider = None
        self.ruler_width = 0
        self._setup_ui()

    def _setup_ui(self):
        """Настраивает UI компоненты линейки"""
        self.markers_container = ft.Container(
            height=40,
            bgcolor=ft.Colors.GREY_800,
        )

        self.slider = SyncSlider(
            self.editor,
            self.size_manager,
            height=40,
            is_main_slider=True
        )

        self.ruler_container = ft.Column([
            self.markers_container,
            ft.Container(
                content=self.slider.build(),
                padding=ft.padding.only(top=5, bottom=5),
                bgcolor=ft.Colors.GREY_700,
                expand=True,
            ),
        ], spacing=0)

    def calculate_ruler_width(self):
        """Вычисляет ширину линейки на основе длительности проекта и масштаба"""
        total_duration_sec = max(10, self.editor.project.duration / 1000)
        self.ruler_width = total_duration_sec * self.pixels_per_second
        return self.ruler_width

    def update_ruler(self):
        """Обновляет линейку с правильными расчетами"""
        if not self.size_manager.page:
            return

        total_width = self.calculate_ruler_width()
        markers = []
        total_duration_sec = max(10, self.editor.project.duration / 1000)
        seconds_step = self._calculate_optimal_step()

        for second in range(0, int(total_duration_sec) + seconds_step, seconds_step):
            position_px = second * self.pixels_per_second
            markers.append(
                ft.Container(
                    content=ft.Column([
                        ft.Container(
                            width=2,
                            height=15,
                            bgcolor=ft.Colors.WHITE,
                        ),
                        ft.Container(
                            content=ft.Text(
                                f"{second}s",
                                size=10,
                                color=ft.Colors.WHITE,
                                weight="bold"
                            ),
                            margin=ft.margin.only(top=2),
                            alignment=ft.alignment.center,
                        ),
                    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    left=position_px - 1,
                    width=40,
                )
            )

            if seconds_step > 1 and self.pixels_per_second >= 100:
                for i in range(1, seconds_step):
                    sub_second = second + i
                    if sub_second <= total_duration_sec:
                        sub_position_px = sub_second * self.pixels_per_second
                        markers.append(
                            ft.Container(
                                content=ft.Container(
                                    width=1,
                                    height=8,
                                    bgcolor=ft.Colors.GREY_400
                                ),
                                left=sub_position_px,
                            )
                        )

        markers_stack = ft.Stack(
            markers,
            width=total_width,
            height=40,
            clip_behavior=ft.ClipBehavior.NONE
        )

        self.markers_container.content = markers_stack
        self.markers_container.width = total_width
        self.ruler_container.width = total_width

        if self.slider:
            slider_build = self.slider.build()
            if slider_build:
                slider_build.width = total_width

    def _calculate_optimal_step(self):
        """Вычисляет оптимальный шаг маркеров"""
        if self.pixels_per_second >= 200:
            return 1
        elif self.pixels_per_second >= 100:
            return 2
        elif self.pixels_per_second >= 50:
            return 5
        else:
            return 10

    def zoom_in(self):
        """Увеличивает масштаб"""
        old_scale = self.pixels_per_second
        self.pixels_per_second = min(self.max_pixels_per_second, self.pixels_per_second * 1.5)
        if old_scale != self.pixels_per_second:
            self.ruler_width = self.calculate_ruler_width()
            return True
        return False

    def zoom_out(self):
        """Уменьшает масштаб"""
        old_scale = self.pixels_per_second
        self.pixels_per_second = max(self.min_pixels_per_second, self.pixels_per_second / 1.5)
        if old_scale != self.pixels_per_second:
            self.ruler_width = self.calculate_ruler_width()
            return True
        return False

    def time_to_pixels(self, time_ms):
        """Конвертирует время в миллисекундах в пиксели"""
        time_sec = time_ms / 1000
        return time_sec * self.pixels_per_second

    def pixels_to_time(self, pixels):
        """Конвертирует пиксели в время в миллисекундах"""
        time_sec = pixels / self.pixels_per_second
        return time_sec * 1000

    def build(self):
        return ft.Container(
            content=self.ruler_container,
            bgcolor=ft.Colors.GREY_900,
            border_radius=8,
            padding=10,
            width=self.ruler_width,
        )


class ScrollSyncManager:
    """Класс для синхронизации прокрутки между различными элементами"""

    def __init__(self):
        self.scroll_controls = {}
        self.is_syncing = False

    def register_control(self, control_id, scrollable_control):
        """Регистрирует контрол для синхронизации"""
        self.scroll_controls[control_id] = scrollable_control

    def sync_scroll(self, source_id, delta_x):
        """Синхронизирует прокрутку всех контролов"""
        if self.is_syncing:
            return
        self.is_syncing = True
        for control_id, control in self.scroll_controls.items():
            if control_id != source_id:
                try:
                    current_scroll = getattr(control, 'scroll_offset', 0)
                    new_scroll = current_scroll + delta_x
                    control.scroll_to(offset=new_scroll, duration=0)
                except Exception:
                    pass
        self.is_syncing = False


class TrackManager:
    """Класс для управления дорожками и UI компонентами"""

    def __init__(self, editor, page):
        self.editor = editor
        self.page = page
        self.size_manager = SizeManager(page)
        self.scroll_sync = ScrollSyncManager()
        self.size_manager.update_sizes()

        self.sync_sliders = []
        self.track_ui_elements = []
        self.track_clips_visualizations = []
        self.track_scroll_controls = []
        self.track_listviews = []

        self.tracks_column = ft.Column(
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self._setup_ui()

        self.time_ruler = TimeRuler(editor, self.size_manager, self)
        self.size_manager.time_ruler = self.time_ruler
        self.main_slider = self.time_ruler.slider
        self.main_slider.on_position_changed = self._on_all_sliders_changed
        self.editor.set_ui_update_callback(self._on_playback_position_changed)

        from file_dialog import FileDialog
        self.file_dialog = FileDialog(page, self._on_files_selected)

        self._initialize_default_tracks()

    def _setup_ui(self):
        """Настраивает UI компоненты"""
        self.add_track_button = ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            tooltip="Добавить Дорожку",
            on_click=self.add_track,
            bgcolor=ft.Colors.BLUE,
        )

        self.zoom_buttons = ft.Row([
            ft.IconButton(
                ft.Icons.ZOOM_OUT,
                on_click=lambda e: self.zoom_out(),
                tooltip="Уменьшить масштаб (показать больше времени)"
            ),
            ft.IconButton(
                ft.Icons.ZOOM_IN,
                on_click=lambda e: self.zoom_in(),
                tooltip="Увеличить масштаб (показать меньше времени)"
            ),
            ft.IconButton(
                ft.Icons.ADD_CIRCLE,
                on_click=self._on_add_duration_click,
                tooltip="Добавить 5 секунд к проекту"
            ),
        ])

        self.export_button = ft.ElevatedButton(
            text="Экспортировать",
            icon=ft.Icons.DOWNLOAD,
            on_click=self.on_export_click,
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
        )

    def _on_files_selected(self, file_paths):
        """Обработчик выбора файлов для добавления в дорожку"""
        if hasattr(self, '_current_track_index') and file_paths:
            self._add_clips_to_track(self._current_track_index, file_paths)
        self._current_track_index = None

    def _add_clips_to_track(self, track_index, file_paths):
        """Добавляет клипы в указанную дорожку в конец"""
        if 0 <= track_index < len(self.editor.project.tracks):
            track = self.editor.project.tracks[track_index]

            if track.clips:
                last_clip_end = max(clip.end_time for clip in track.clips)
            else:
                last_clip_end = 0

            current_start_time = last_clip_end
            added_clips = []

            for file_path in file_paths:
                clip_name = os.path.splitext(os.path.basename(file_path))
                clip = self.editor.add_audio_clip(track_index, file_path, current_start_time, clip_name)
                if clip:
                    current_start_time = clip.end_time
                    added_clips.append(clip)

            if added_clips:
                self.update_all_visualizations()

    def _open_file_dialog_for_track(self, track_index):
        """Открывает диалог выбора файлов для конкретной дорожки"""
        self._current_track_index = track_index
        track_ui = self.track_ui_elements[track_index]
        original_border = track_ui.border
        track_ui.border = ft.border.all(2, ft.Colors.BLUE_400)

        if self.page:
            self.page.update()

        self.file_dialog.pick_files()

        def reset_border():
            time.sleep(2)
            track_ui.border = original_border
            if self.page:
                self.page.update()

        threading.Thread(target=reset_border, daemon=True).start()

    def _on_playback_position_changed(self, progress):
        """Обновляет все слайдеры при изменении позиции воспроизведения"""
        def update_ui():
            for slider in self.sync_sliders:
                slider.set_position(progress)
            if hasattr(self, 'main_slider'):
                self.main_slider.set_position(progress)
            if self.page:
                self.page.update()

        if self.page:
            self.page.run_thread(update_ui)

    def _on_all_sliders_changed(self, position, visual_only=False):
        """Синхронизирует все слайдеры при изменении любого из них"""
        for slider in self.sync_sliders:
            slider.set_position(position, visual_only)

    def _initialize_default_tracks(self):
        """Создает начальные дорожки с клипами"""
        track1 = self.editor.create_track("Дорожка 1")
        track2 = self.editor.create_track("Дорожка 2")

        self.editor.project._update_duration()
        self.time_ruler.update_ruler()

        for i, track in enumerate(self.editor.project.tracks):
            track_ui = self._create_track_ui(track, i)
            self.tracks_column.controls.append(track_ui)
            self.track_ui_elements.append(track_ui)

        self.tracks_column.controls.append(
            ft.Container(
                content=self.add_track_button,
                alignment=ft.alignment.center,
                padding=10
            )
        )

        self.update_all_visualizations()

        if self.page:
            self.page.update()

    def _create_track_ui(self, track, index):
        """Создает UI для одной дорожки"""
        track_slider = SyncSlider(self.editor, self.size_manager, height=40)
        track_slider.on_position_changed = self._on_all_sliders_changed
        self.sync_sliders.append(track_slider)

        clips_visualization = self._create_clips_visualization(track, index)
        self.track_clips_visualizations.append(clips_visualization)

        current_ruler_width = self.time_ruler.ruler_width
        new_width = current_ruler_width

        time_markers = []
        total_duration_sec = max(10, self.editor.project.duration / 1000)
        pixels_per_second = self.time_ruler.pixels_per_second

        for second in range(0, int(total_duration_sec) + 1, 2):
            pos_px = second * pixels_per_second
            time_markers.append(
                ft.Container(
                    left=pos_px,
                    top=85,
                    content=ft.Text(
                        f"{second}s",
                        size=8,
                        color=ft.Colors.GREY_400,
                        weight=ft.FontWeight.BOLD
                    ),
                )
            )

        time_markers_stack = ft.Stack(
            time_markers,
            width=new_width,
            height=100
        ) if time_markers else None

        clips_container = ft.Container(
            expand=True,
            height=100,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=clips_visualization
        )

        background_container = ft.Container(
            expand=True,
            height=100,
            bgcolor=ft.Colors.GREY_700,
            border_radius=5,
        )

        track_content = ft.Container(
            expand=True,
            height=100,
            bgcolor=ft.Colors.GREY_800,
            border_radius=5,
            content=ft.Column([
                ft.Stack([
                    background_container,
                    clips_container,
                    time_markers_stack,
                ], clip_behavior=ft.ClipBehavior.NONE, height=60, expand=True),
                ft.Container(
                    content=track_slider.build(),
                    expand=False,
                    height=15,
                ),
            ], spacing=0)
        )

        list_view = ft.ListView(
            [track_content],
            horizontal=True,
            expand=True,
        )

        self.track_listviews.append(list_view)

        track_ui = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text(track.name, size=14, weight="bold"),
                        ft.IconButton(
                            ft.Icons.ADD,
                            on_click=lambda e, idx=index: self._open_file_dialog_for_track(idx),
                            tooltip="Добавить файл"
                        ),
                    ], spacing=0),
                    width=150,
                ),
                ft.Container(
                    content=list_view,
                    expand=True,
                    height=110,
                    clip_behavior=ft.ClipBehavior.NONE,
                ),
            ], spacing=10, expand=True),
            border=ft.border.all(1, ft.Colors.GREY_500),
            border_radius=8,
            padding=10,
            margin=ft.margin.only(bottom=10),
        )

        return track_ui

    def add_clip_to_track_visualization(self, track_index, clip):
        """Добавляет ТОЛЬКО ОДИН новый клип в визуализацию дорожки"""
        if track_index >= len(self.editor.project.tracks):
            return

        track = self.editor.project.tracks[track_index]

        if track_index >= len(self.track_clips_visualizations):
            return

        clips_stack = self.track_clips_visualizations[track_index]

        if not isinstance(clips_stack, ft.Stack):
            return

        try:
            draggable_vis = create_draggable_clip_visualization(
                clip,
                track,
                self.time_ruler,
                editor=self.editor,
                top=30,
                on_drag_end_callback=self._on_clip_drag_end,
                on_state_changed=self._on_clip_state_changed
            )

            clip.draggable_vis = draggable_vis
            clips_stack.controls.append(draggable_vis)

            try:
                clips_stack.update()
            except Exception:
                pass

        except Exception:
            pass

    def _create_clips_visualization(self, track, track_index):
        """Создает визуализацию всех клипов на дорожке"""
        clips_stack = ft.Stack([], height=100)

        def on_drag_end(clip):
            self.update_all_visualizations()
            self.editor.project._update_duration()
            self.time_ruler.update_ruler()

        def on_state_changed(state):
            if state == "trimmed":
                self.time_ruler.update_ruler()
                if self.page:
                    self.page.update()

        for clip in track.get_clips_sorted():
            try:
                draggable_obj = create_draggable_clip_visualization(
                    clip,
                    track,
                    self.time_ruler,
                    editor=self.editor,
                    top=30,
                    on_drag_end_callback=on_drag_end,
                    on_state_changed=on_state_changed
                )

                clip._draggable_vis = draggable_obj
                clips_stack.controls.append(draggable_obj)

            except Exception:
                pass

        return clips_stack

    def _on_clip_drag_end(self, clip):
        """Обработчик окончания перетаскивания клипа"""
        self.update_all_visualizations()
        self.editor.project._update_duration()
        self.time_ruler.update_ruler()

    def _update_clip_visualization_only(self, clip):
        """Обновляет визуализацию ТОЛЬКО конкретного клипа"""
        track_index = None
        for idx, track in enumerate(self.editor.project.tracks):
            if clip in track.clips:
                track_index = idx
                break

        if track_index is None:
            return

        if track_index >= len(self.track_clips_visualizations):
            return

        clips_stack = self.track_clips_visualizations[track_index]

        if not isinstance(clips_stack, ft.Stack):
            return

        from drag_drop import create_draggable_clip_visualization

        try:
            new_viz = create_draggable_clip_visualization(
                clip,
                self.editor.project.tracks[track_index],
                self.time_ruler,
                editor=self.editor,
                top=30,
                on_drag_end_callback=self._on_clip_drag_end,
                on_state_changed=self._on_clip_state_changed
            )

            for i, control in enumerate(clips_stack.controls):
                clips_stack.controls[i] = new_viz

            try:
                clips_stack.update()
            except Exception:
                pass
            return

        except Exception:
            pass

    def _on_clip_state_changed(self, state):
        """Обработчик изменения состояния клипа"""
        if state == "trimmed":
            self.time_ruler.update_ruler()
            if self.page:
                self.page.update()

    def update_all_visualizations(self):
        """Обновляет визуализации для всех дорожек"""
        try:
            new_width = self.time_ruler.ruler_width

            for i, track_ui in enumerate(self.track_ui_elements):
                try:
                    if isinstance(track_ui, ft.Container) and track_ui.content:
                        row = track_ui.content
                        if isinstance(row, ft.Row) and len(row.controls) > 1:
                            list_container = row.controls[1]
                            if isinstance(list_container, ft.Container):
                                if i < len(self.track_listviews):
                                    listview = self.track_listviews[i]
                                    if isinstance(listview, ft.ListView) and len(listview.controls) > 0:
                                        track_content = listview.controls[0]
                                        if isinstance(track_content, ft.Container):
                                            if isinstance(track_content.content, ft.Column):
                                                column = track_content.content
                                                if len(column.controls) > 0 and isinstance(column.controls[0], ft.Stack):
                                                    stack = column.controls[0]

                                                    time_markers = []
                                                    total_duration_sec = max(10, self.editor.project.duration / 1000)
                                                    pixels_per_second = self.time_ruler.pixels_per_second

                                                    for second in range(0, int(total_duration_sec) + 1, 2):
                                                        pos_px = second * pixels_per_second
                                                        time_markers.append(
                                                            ft.Container(
                                                                left=pos_px,
                                                                top=85,
                                                                content=ft.Text(
                                                                    f"{second}s",
                                                                    size=8,
                                                                    color=ft.Colors.GREY_400,
                                                                    weight=ft.FontWeight.BOLD
                                                                ),
                                                            )
                                                        )

                                                    new_markers_stack = ft.Stack(
                                                        time_markers,
                                                        width=new_width,
                                                        height=100,
                                                        clip_behavior=ft.ClipBehavior.NONE
                                                    )

                                                    if len(stack.controls) > 2:
                                                        stack.controls[2] = new_markers_stack

                except Exception:
                    pass

            for i, track_vis in enumerate(self.track_clips_visualizations):
                if isinstance(track_vis, ft.Stack):
                    track_vis.controls.clear()
                    track_vis.width = new_width

            for track_index, track in enumerate(self.editor.project.tracks):
                if track_index < len(self.track_clips_visualizations):
                    track_vis_stack = self.track_clips_visualizations[track_index]
                    if isinstance(track_vis_stack, ft.Stack):
                        for clip_idx, clip in enumerate(track.clips):
                            try:
                                draggable_vis = create_draggable_clip_visualization(
                                    clip,
                                    track,
                                    self.time_ruler,
                                    editor=self.editor,
                                    top=30,
                                    on_drag_end_callback=self._on_clip_drag_end,
                                    on_state_changed=self._on_clip_state_changed
                                )

                                track_vis_stack.controls.append(draggable_vis)

                            except Exception:
                                pass

            for i, track_ui in enumerate(self.track_ui_elements):
                try:
                    if isinstance(track_ui, ft.Container) and track_ui.content:
                        row = track_ui.content
                        if isinstance(row, ft.Row) and len(row.controls) > 1:
                            list_container = row.controls[1]
                            if isinstance(list_container, ft.Container):
                                if i < len(self.track_listviews):
                                    listview = self.track_listviews[i]
                                    if isinstance(listview, ft.ListView) and len(listview.controls) > 0:
                                        track_content = listview.controls[0]
                                        if isinstance(track_content, ft.Container):
                                            track_content.update()

                except Exception:
                    pass

            new_width = self.time_ruler.ruler_width
            for i, listview in enumerate(self.track_listviews):
                if isinstance(listview, ft.ListView) and len(listview.controls) > 0:
                    track_content = listview.controls[0]
                    if isinstance(track_content, ft.Container):
                        track_content.width = new_width
                        try:
                            track_content.update()
                        except:
                            pass

            if self.page:
                self.page.update()

        except Exception:
            pass

    def add_track(self, e=None):
        """Добавляет новую дорожку"""
        track_name = f"Дорожка {len(self.editor.project.tracks) + 1}"
        track = self.editor.create_track(track_name)
        track_ui = self._create_track_ui(track, len(self.editor.project.tracks) - 1)
        self.track_ui_elements.append(track_ui)
        self.tracks_column.controls.insert(-1, track_ui)
        self.update_all_visualizations()
        if self.page:
            self.page.update()

    def get_track_list_container(self):
        """Возвращает контейнер со списком дорожек"""
        return ft.Column([
            self.zoom_buttons,
            self.export_button,
            self.tracks_column,
        ], spacing=10, expand=True)

    def zoom_in(self):
        """Увеличивает масштаб"""
        if self.time_ruler.zoom_in():
            self.time_ruler.update_ruler()
            self.update_track_contents_width()
            self.update_all_visualizations()
            self.page.update()

    def zoom_out(self):
        """Уменьшает масштаб"""
        if self.time_ruler.zoom_out():
            self.time_ruler.update_ruler()
            self.update_track_contents_width()
            self.update_all_visualizations()
            self.page.update()

    def _on_add_duration_click(self, e):
        """Добавляет 5 секунд к проекту"""
        self.editor.project.add_duration(5000)
        self.time_ruler.update_ruler()
        self.update_all_visualizations()
        if self.page:
            self.page.update()

    def update_track_contents_width(self):
        """Обновляет ширину track_content для всех дорожек"""
        new_width = self.time_ruler.ruler_width

        for i, track_ui in enumerate(self.track_ui_elements):
            if isinstance(track_ui, ft.Container) and track_ui.content:
                row = track_ui.content
                if isinstance(row, ft.Row) and len(row.controls) > 1:
                    list_container = row.controls[1]
                    if isinstance(list_container, ft.Container):
                        list_container.width = new_width
                        listview = self.track_listviews[i]
                        if isinstance(listview, ft.ListView) and len(listview.controls) > 0:
                            track_content = listview.controls[0]
                            if isinstance(track_content, ft.Container):
                                track_content.width = new_width
                                if isinstance(track_content.content, ft.Stack):
                                    stack = track_content.content
                                    stack.width = new_width
                                    for j, element in enumerate(stack.controls):
                                        if isinstance(element, ft.Container):
                                            element.width = new_width
                                            try:
                                                element.update()
                                            except:
                                                pass
                                        elif isinstance(element, ft.GestureDetector):
                                            if isinstance(element.content, ft.Container):
                                                element.content.width = new_width
                                                try:
                                                    element.content.update()
                                                except:
                                                    pass
                                    try:
                                        stack.update()
                                    except:
                                        pass
                                try:
                                    track_content.update()
                                except:
                                    pass
                        try:
                            list_container.update()
                        except:
                            pass

        if self.page:
            try:
                self.page.update()
            except Exception:
                pass

    def on_export_click(self, e):
        """Открывает диалог выбора формата и пути для экспорта"""
        format_dropdown = ft.Dropdown(
            label="Формат",
            options=[
                ft.dropdown.Option("wav", text="WAV (Без сжатия)"),
                ft.dropdown.Option("mp3", text="MP3 (Сжатый)"),
                ft.dropdown.Option("flac", text="FLAC (Без потерь)"),
                ft.dropdown.Option("ogg", text="OGG (Сжатый)"),
            ],
            value="wav",
            width=200,
        )

        filename_field = ft.TextField(
            label="Имя файла",
            value="export",
            width=250,
        )

        progress_text = ft.Text("", size=12, color=ft.Colors.BLUE)
        progress_bar = ft.ProgressBar(value=0, width=300)

        def on_export_confirm(e):
            """Выполняет экспорт"""
            if not filename_field.value:
                filename_field.value = "export"

            format_ext = format_dropdown.value or "wav"
            filename = f"{filename_field.value}.{format_ext}"

            if platform.system() == "Windows":
                download_dir = Path.home() / "Downloads"
            else:
                download_dir = Path.home() / "Downloads"

            output_path = download_dir / filename

            dialog.content.controls.append(ft.Divider())
            dialog.content.controls.append(progress_text)
            dialog.content.controls.append(progress_bar)

            dialog.open = False

            if self.page:
                self.page.update()

            exporter = AudioExporter(self.editor.project)

            def on_progress(progress, message):
                """Обновляет прогресс"""
                progress_text.value = message
                progress_bar.value = progress / 100
                if self.page:
                    try:
                        progress_text.update()
                        progress_bar.update()
                    except:
                        pass

            def on_complete(success):
                """Завершение экспорта"""
                if success:
                    progress_text.value = f"✅ Сохранено: {output_path}"
                    if self.page:
                        snackbar = ft.SnackBar(ft.Text(f"✅ Аудио экспортировано: {output_path}"))
                        self.page.overlay.append(snackbar)
                        snackbar.open = True
                        self.page.update()
                else:
                    progress_text.value = "❌ Ошибка экспорта!"
                    if self.page:
                        snackbar = ft.SnackBar(ft.Text("❌ Ошибка при экспорте"))
                        self.page.overlay.append(snackbar)
                        snackbar.open = True
                        self.page.update()

            exporter.export_async(
                str(output_path),
                format_ext,
                progress_callback=on_progress,
                completion_callback=on_complete
            )

        def close_dialog():
            dialog.open = False
            if self.page:
                self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("📥 Экспортировать аудио"),
            content=ft.Column([
                filename_field,
                format_dropdown,
            ], width=400, spacing=15),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: close_dialog()),
                ft.TextButton(
                    "Экспортировать",
                    on_click=on_export_confirm,
                    style=ft.ButtonStyle(color=ft.Colors.BLUE),
                ),
            ],
        )

        self.page.overlay.append(dialog)
        dialog.open = True

        if self.page:
            self.page.update()