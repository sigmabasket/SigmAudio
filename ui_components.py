import flet as ft
import threading
import time
import os

# Импортируем новые классы
from drag_drop import create_draggable_clip_visualization
from clip_conflict_manager import ClipConflictManager


class SyncSlider:
    """
    Синхронизированный слайдер для отображения прогресса воспроизведения
    """

    def __init__(self, editor, size_manager, height=40, is_main_slider=False):
        self.editor = editor
        self.size_manager = size_manager
        self.height = height
        self.is_main_slider = is_main_slider
        self.is_dragging = False
        self.was_playing = False

        # Фоновый контейнер (серый)
        self.bg_container = ft.Container(
            expand=True,
            height=height,
            bgcolor=ft.Colors.GREY_600,
            border_radius=height / 2,
        )

        # Прогресс контейнер (жёлтый)
        self.progress_container = ft.Container(
            width=0,
            height=height,
            bgcolor="#FFAB00",
            border_radius=height / 2,
        )

        # Stack с фоном И прогрессом
        self.slider_stack = ft.Stack(
            [self.bg_container, self.progress_container],
            expand=True,
            height=height,
        )

        # GestureDetector напрямую на Stack
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
        print(f"🖱️🖱️🖱️ TAP DOWN CALLED! e={e}, local_x={e.local_x}")

        if e.local_x is not None:
            container_width = self._get_container_width()
            print(f"   Container width: {container_width}px")

            if container_width > 0:
                # Ограничиваем координату в границах [0, container_width]
                corrected_x = max(0, min(e.local_x, container_width))

                # Конвертируем пиксели в время
                if hasattr(self.size_manager, 'time_ruler') and self.size_manager.time_ruler:
                    time_ms = self.size_manager.time_ruler.pixels_to_time(corrected_x)
                    total_duration = self.editor.project.duration
                    percent = time_ms / total_duration if total_duration > 0 else 0
                    percent = max(0, min(1, percent))  # Ограничиваем [0, 1]
                else:
                    percent = corrected_x / container_width

                print(f"   Percent: {percent:.2%}")
                self._update_visual_progress(percent)
                self.editor.set_playback_position(percent, seeking=False)

    def _handle_drag_start(self, e: ft.DragStartEvent):
        """Обработчик начала перетаскивания"""
        print("🎯 DRAG START")
        self.is_dragging = True
        self.was_playing = self.editor.is_playing()
        if self.was_playing:
            self.editor.project.paused = True

    def _handle_drag_update(self, e: ft.DragUpdateEvent):
        """Обработчик перетаскивания"""
        print(f"👆 DRAG UPDATE: local_x={e.local_x}")

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

                percent = max(0, min(1, percent))  # Ограничиваем [0, 1]

                print(f"   Percent: {percent:.2%}")
                self._update_visual_progress(percent)

                if self.on_position_changed:
                    self.on_position_changed(percent, True)  # True = seeking

    def _handle_drag_end(self, e: ft.DragEndEvent):
        """Обработчик окончания перетаскивания"""
        print("🛑 DRAG END")
        if self.is_dragging:
            self.is_dragging = False

            container_width = self._get_container_width()
            if container_width > 0:
                final_percent = self.progress_container.width / container_width
                final_percent = max(0, min(1, final_percent))
                self.editor.set_playback_position(final_percent, seeking=True)

            self.editor.project.seeking = False  # ← ДОБАВЬ!

            if self.was_playing:
                print("▶️ Resuming playback after drag")
                self.editor.project.playing = True
                self.editor.project.paused = False
                print(
                    f"   playing={self.editor.project.playing}, paused={self.editor.project.paused}, seeking={self.editor.project.seeking}")

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
        except Exception as e:
            print(f"   ⚠️ Update failed: {e}")

    def set_position(self, position, visual_only=False):
        """Устанавливает позицию слайдера (от внешних источников)"""
        if not self.is_dragging or visual_only:
            self._update_visual_progress(position)

    def build(self):
        """Возвращает собранный слайдер"""
        return self.slider_gesture


class SizeManager:
    """
    Класс для управления размерами UI компонентов
    """

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

        print(f"Size update - Page: {self.page.width}, Main: {self.main_slider_width}, Tracks: {self.track_clips_width}")


class TimeRuler:
    """
    Класс для создания и управления линейкой времени
    """

    def __init__(self, editor, size_manager, track_manager=None):
        self.editor = editor
        self.size_manager = size_manager
        self.track_manager = track_manager

        # Базовая конфигурация
        self.base_pixels_per_second = 100
        self.pixels_per_second = self.base_pixels_per_second
        self.min_pixels_per_second = 50
        self.max_pixels_per_second = 500

        # Основные компоненты
        self.ruler_container = None
        self.markers_container = None
        self.slider = None
        self.ruler_width = 0
        self._setup_ui()

    def _setup_ui(self):
        """Настраивает UI компоненты линейки"""
        # Контейнер для маркеров
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
            )
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
                        )
                    ],
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER),
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

        print(f"Ruler updated: duration={self.editor.project.duration}ms, "
              f"width={total_width}px, scale={self.pixels_per_second}px/sec, "
              f"step={seconds_step}s")

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
            print(f"Zoom in: {old_scale} -> {self.pixels_per_second} px/sec")
            self.ruler_width = self.calculate_ruler_width()
            return True
        return False

    def zoom_out(self):
        """Уменьшает масштаб"""
        old_scale = self.pixels_per_second
        self.pixels_per_second = max(self.min_pixels_per_second, self.pixels_per_second / 1.5)
        if old_scale != self.pixels_per_second:
            print(f"Zoom out: {old_scale} -> {self.pixels_per_second} px/sec")
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
    """
    Класс для синхронизации прокрутки между различными элементами
    """

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
                except Exception as e:
                    print(f"Error syncing scroll for {control_id}: {e}")
        self.is_syncing = False


class TrackManager:
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
        self.clip_conflict_manager = ClipConflictManager

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
            ft.Text("100px/сек", size=12, weight="bold"),
            ft.IconButton(
                ft.Icons.ZOOM_IN,
                on_click=lambda e: self.zoom_in(),
                tooltip="Увеличить масштаб (показать меньше времени)"
            ),
        ], alignment=ft.MainAxisAlignment.CENTER)

    def _on_files_selected(self, file_paths):
        """Обработчик выбора файлов для добавления в дорожку"""
        if hasattr(self, '_current_track_index') and file_paths:
            self._add_clips_to_track(self._current_track_index, file_paths)
        self._current_track_index = None

    def _add_clips_to_track(self, track_index, file_paths):
        """Добавляет клипы в указанную дорожку в конец"""
        print(f"\n🎯 _add_clips_to_track called with {len(file_paths)} files")

        if 0 <= track_index < len(self.editor.project.tracks):
            track = self.editor.project.tracks[track_index]
            print(f"   Track {track_index} found, clips count: {len(track.clips)}")

            if track.clips:
                last_clip_end = max(clip.end_time for clip in track.clips)
                print(f"   Last clip ends at: {last_clip_end}ms")
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
                print(f"\n 🎬 Updating visualizations...")

                self.time_ruler.update_ruler()
                self.update_track_contents_width()
                self.update_all_visualizations()

                print(f" ✅ Visualizations updated")

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
        # Создаём дорожки
        track1 = self.editor.create_track("Дорожка 1")
        track2 = self.editor.create_track("Дорожка 2")

        # Добавляем клипы
        self.editor.add_audio_clip(0, "test.wav", 0, "Клип 1")
        self.editor.add_audio_clip(1, "test.wav", 2000, "Клип 2")

        # Обновляем проект
        self.editor.project._update_duration()
        self.time_ruler.update_ruler()

        # Создаём UI
        for i, track in enumerate(self.editor.project.tracks):
            track_ui = self._create_track_ui(track, i)
            self.tracks_column.controls.append(track_ui)
            self.track_ui_elements.append(track_ui)

        # Добавляем кнопку
        self.tracks_column.controls.append(
            ft.Container(
                content=self.add_track_button,
                alignment=ft.alignment.center,
                padding=10
            )
        )

        # Обновляем визуализацию
        self.update_all_visualizations()
        if self.page:
            self.page.update()

        print("✅ Дорожки инициализированы успешно")

    def _create_track_ui(self, track, index):
        """Создает UI для одной дорожки - ИСПРАВЛЕННАЯ ВЕРСИЯ"""

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
                ],
                    clip_behavior=ft.ClipBehavior.NONE,
                    height=60,
                    expand=True,
                ),
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
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(track.name, size=14, weight="bold"),
                                ft.IconButton(
                                    ft.Icons.ADD,
                                    on_click=lambda e, idx=index: self._open_file_dialog_for_track(idx),
                                    tooltip="Добавить файл"
                                )
                            ],
                            spacing=0
                        ),
                        width=150,
                    ),
                    ft.Container(
                        content=list_view,
                        expand=True,
                        height=110,
                        clip_behavior=ft.ClipBehavior.NONE,
                    ),
                ],
                spacing=10,
                expand=True
            ),
            border=ft.border.all(1, ft.Colors.GREY_500),
            border_radius=8,
            padding=10,
            margin=ft.margin.only(bottom=10),
        )

        return track_ui

    def _create_clips_visualization(self, track, track_index):
        """Создает визуализацию всех клипов на дорожке"""

        clips_stack = ft.Stack(
            [],
            height=100
        )

        def on_drag_end(clip):
            conflicts = ClipConflictManager.find_conflicting_clips(track, clip, exclude_self=True)
            if conflicts:
                success, message, moved_clips = ClipConflictManager.resolve_move_conflict(
                    track, clip, clip.start_time
                )
                if not success:
                    print(f"❌ {message}")
                    self.update_all_visualizations()
                    if self.page:
                        snackbar = ft.SnackBar(ft.Text(message))
                        self.page.overlay.append(snackbar)
                        snackbar.open = True
                        self.page.update()
                else:
                    print(f"✅ {message}")
                    self.update_all_visualizations()
                    if self.page:
                        snackbar = ft.SnackBar(ft.Text(message))
                        self.page.overlay.append(snackbar)
                        snackbar.open = True
                        self.page.update()
            else:
                print(f"✅ Клип '{clip.name}' успешно перемещён")
                self.update_all_visualizations()
                self.editor.project._update_duration()
                self.time_ruler.update_ruler()

        def on_state_changed(state):
            print(f"📌 State changed: {state} for clip {state}")
            if state == "trimmed":
                print(f"✅ Клип обрезан")
                self.update_all_visualizations()
                if self.page:
                    self.page.update()
                self.editor.project._update_duration()
                self.time_ruler.update_ruler()

        for clip in track.get_clips_sorted():
            try:
                draggable_vis = create_draggable_clip_visualization(
                    clip,
                    track,
                    self.time_ruler,
                    editor=self.editor,
                    top=30,
                    on_drag_end_callback=on_drag_end,
                    on_state_changed=on_state_changed
                )
                clips_stack.controls.append(draggable_vis)
            except Exception as e:
                print(f"Error creating visualization for clip {clip.name}: {e}")

        return clips_stack

    def _on_clip_drag_end(self, clip):
        """Обработчик окончания перетаскивания клипа"""
        print(f"\n✅ Drag end: '{clip.name}'")

        track = None
        for t in self.editor.project.tracks:
            if clip in t.clips:
                track = t
                break

        if not track:
            return

        conflicts = ClipConflictManager.find_conflicting_clips(track, clip, exclude_self=True)

        if conflicts:
            success, message, moved_clips = ClipConflictManager.resolve_move_conflict(
                track, clip, clip.start_time
            )

            if not success:
                print(f"❌ {message}")
            else:
                print(f"✅ {message}")

            self.update_all_visualizations()
            if self.page:
                snackbar = ft.SnackBar(ft.Text(message))
                self.page.overlay.append(snackbar)
                snackbar.open = True
                self.page.update()
        else:
            print(f"✅ Клип '{clip.name}' успешно перемещён")

        self.editor.project._update_duration()
        self.time_ruler.update_ruler()

    def _on_clip_state_changed(self, state):
        """Обработчик изменения состояния клипа"""
        print(f"📌 State changed: {state}")
        if state == "trimmed":
            # Обрезание должно только менять trim_start/trim_end, не саму длину проекта
            self.time_ruler.update_ruler()

            if self.page:
                self.page.update()

    def update_all_visualizations(self):
        """Обновляет визуализации для всех дорожек"""
        print(f"\n📊 update_all_visualizations() called")

        try:
            new_width = self.time_ruler.ruler_width
            print(f"new_width = {new_width}px (ruler_width={self.time_ruler.ruler_width}px)")

            print(f"\n⏱️ STEP 1: Updating time markers...")

            for i, track_ui in enumerate(self.track_ui_elements):
                try:
                    print(f"Track {i}: track_ui type = {type(track_ui).__name__}")

                    if isinstance(track_ui, ft.Container) and track_ui.content:
                        row = track_ui.content
                        print(f"row type = {type(row).__name__}")

                        if isinstance(row, ft.Row) and len(row.controls) > 1:
                            list_container = row.controls[1]  # ← ИНДЕКС [1]!
                            print(f"list_container type = {type(list_container).__name__}")

                            if isinstance(list_container, ft.Container):
                                if i < len(self.track_listviews):
                                    listview = self.track_listviews[i]
                                    print(
                                        f"listview type = {type(listview).__name__}, len={len(listview.controls)}")

                                    if isinstance(listview, ft.ListView) and len(listview.controls) > 0:
                                        track_content = listview.controls[0]
                                        print(f"track_content type = {type(track_content).__name__}")

                                        if isinstance(track_content, ft.Container):
                                            print(
                                                f"track_content.content type = {type(track_content.content).__name__}")

                                            if isinstance(track_content.content, ft.Column):  # ← Column!
                                                column = track_content.content
                                                print(f"column controls: {len(column.controls)}")

                                                if len(column.controls) > 0 and isinstance(column.controls[0],
                                                                                           ft.Stack):
                                                    stack = column.controls[0]
                                                    print(
                                                        f"Found Stack with {len(stack.controls)} controls")

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
                                                        print(f"✅ Updated markers for track {i}")
                except Exception as e:
                    print(f"  ❌ Track {i}: {e}")

            print(f"\n🎬 STEP 2: Updating clips...")

            # Очищаем старые
            for i, track_vis in enumerate(self.track_clips_visualizations):
                if isinstance(track_vis, ft.Stack):
                    track_vis.controls.clear()
                    track_vis.width = new_width
                    print(f"  Track {i}: Stack cleared, width={new_width}px")

            # Пересоздаем
            print(f"Total tracks in project: {len(self.editor.project.tracks)}")
            print(f"Total track_clips_visualizations: {len(self.track_clips_visualizations)}")

            for track_index, track in enumerate(self.editor.project.tracks):
                print(f"Processing track {track_index}: {len(track.clips)} clips")

                if track_index < len(self.track_clips_visualizations):
                    track_vis_stack = self.track_clips_visualizations[track_index]
                    print(f"Stack type: {type(track_vis_stack).__name__}")

                    if isinstance(track_vis_stack, ft.Stack):
                        for clip_idx, clip in enumerate(track.clips):
                            try:
                                print(f"Creating viz for clip {clip_idx}: {clip.name}")
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
                                print(f"✅ Added, stack now has {len(track_vis_stack.controls)} controls")
                            except Exception as e:
                                print(f"❌ Clip '{clip.name}': {e}")
                    else:
                        print(f"❌ Not a Stack, it's {type(track_vis_stack).__name__}")
                else:
                    print(
                        f"❌ track_index {track_index} >= len(track_clips_visualizations) {len(self.track_clips_visualizations)}")
            print(f"\n  Updating parent containers...")
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
                                            track_content.update()  # ← Обновляем родителя!
                                            print(f"    ✅ Track {i} parent updated")
                except Exception as e:
                    print(f"    ❌ Track {i}: {e}")

            print(f"\n🎨 STEP 3: Updating all containers...")


            if self.page:
                print(f"✅ Page updated")
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

                self.page.update()

            print(f"📊 Final duration: {self.editor.project.duration}ms\n")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

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

    def update_track_contents_width(self):
        """Обновляет ширину track_content для всех дорожек"""

        new_width = self.time_ruler.ruler_width
        print(f"\n🔄 Updating track_content width to {new_width}px")

        for i, track_ui in enumerate(self.track_ui_elements):
            if isinstance(track_ui, ft.Container) and track_ui.content:
                row = track_ui.content
                if isinstance(row, ft.Row) and len(row.controls) > 1:
                    # Получаем контейнер с ListView
                    list_container = row.controls
                    if isinstance(list_container, ft.Container):
                        list_container.width = new_width

                        listview = self.track_listviews[i]
                        if isinstance(listview, ft.ListView) and len(listview.controls) > 0:
                            track_content = listview.controls
                            if isinstance(track_content, ft.Container):
                                track_content.width = new_width

                                if isinstance(track_content.content, ft.Stack):
                                    stack = track_content.content
                                    stack.width = new_width

                                    # Обновляем ВСЕ контейнеры внутри Stack
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

                                    # Обновляем сам Stack
                                    try:
                                        stack.update()
                                    except:
                                        pass

                                # Обновляем track_content
                                try:
                                    track_content.update()
                                except:
                                    pass
                        # Обновляем list_container
                        try:
                            list_container.update()
                        except:
                            pass

        # Финальное обновление страницы
        if self.page:
            try:
                self.page.update()
                print(f" ✅ Page updated with width {new_width}px")
            except Exception as e:
                print(f" ❌ Page update failed: {e}")






