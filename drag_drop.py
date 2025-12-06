import flet as ft


class ClipBorderHandle:
    """
    Класс для управления границами клипа (обрезание)
    """
    HANDLE_WIDTH = 8
    HOVER_WIDTH = 12

    def __init__(self, clip, time_ruler, on_trim_callback=None, is_left=True, draggable_clip_ref=None):
        self.clip = clip
        self.time_ruler = time_ruler
        self.on_trim_callback = on_trim_callback
        self.is_left = is_left
        self.is_dragging = False
        self.original_clip_duration = clip.duration
        self.draggable_clip_ref = draggable_clip_ref

        # Визуальный элемент для границы
        self.handle = ft.Container(
            width=self.HANDLE_WIDTH,
            height=30,
            bgcolor=ft.Colors.ORANGE_400 if is_left else ft.Colors.RED_400,
            border_radius=2,
            opacity=0.7,
        )

        self.gesture_detector = ft.GestureDetector(
            content=self.handle,
            on_pan_start=self._on_pan_start,
            on_pan_update=self._on_pan_update,
            on_pan_end=self._on_pan_end,
            mouse_cursor=ft.MouseCursor.RESIZE_COLUMN,
            expand=False,
        )

    def _on_pan_start(self, e: ft.DragStartEvent):
        """Начало перетаскивания границы"""
        self.is_dragging = True
        self.original_clip_duration = self.clip.duration
        self.handle.opacity = 1.0
        print(
            f"🎯 Drag start {'LEFT' if self.is_left else 'RIGHT'}: trim_start={self.clip.trim_start}, trim_end={self.clip.trim_end}")

    def _on_pan_update(self, e: ft.DragUpdateEvent):
        """Обновление позиции границы при перетаскивании"""
        if self.is_dragging:
            delta_time_ms = self.time_ruler.pixels_to_time(e.delta_x)

            if self.is_left:
                new_trim_start = self.clip.trim_start + delta_time_ms
                new_trim_start = max(0, new_trim_start)
                new_trim_start = min(new_trim_start, self.clip.original_duration - self.clip.trim_end - 100)

                delta_trim = new_trim_start - self.clip.trim_start

                self.clip.trim_start = new_trim_start

                self.clip.start_time = max(0, self.clip.start_time + delta_trim)

                print(
                    f"✂️ LEFT: trim_start={self.clip.trim_start}ms, start_time={self.clip.start_time}ms, delta={delta_trim}ms")


            else:

                # ПРАВАЯ граница

                new_trim_end = self.clip.trim_end - delta_time_ms

                new_trim_end = max(0, new_trim_end)

                new_trim_end = min(new_trim_end, self.clip.original_duration - self.clip.trim_start - 100)

                max_duration_ms = self.time_ruler.pixels_to_time(self.time_ruler.ruler_width)

                clip_end_time = self.clip.start_time + (
                            self.clip.original_duration - self.clip.trim_start - new_trim_end)

                if clip_end_time > max_duration_ms:
                    max_allowed_duration = max_duration_ms - self.clip.start_time

                    new_trim_end = max(0, self.clip.original_duration - self.clip.trim_start - max_allowed_duration)

                    print(f"⛔ Обрезка ограничена!")

                self.clip.trim_end = new_trim_end

            # Пересчитываем длительность
            self.clip.duration = self.clip.original_duration - self.clip.trim_start - self.clip.trim_end
            self.clip.update_end_time()

            if self.on_trim_callback:
                self.on_trim_callback(self.clip)

            if self.draggable_clip_ref:
                self.draggable_clip_ref.update_on_trim()

    def _on_pan_end(self, e: ft.DragEndEvent):
        """Завершение перетаскивания границы"""
        self.is_dragging = False
        self.handle.opacity = 0.7

    def build(self):
        """Возвращает визуальный элемент границы"""
        return self.gesture_detector


class DraggableClip:
    """
    Класс для создания перетаскиваемого аудио клипа с поддержкой обрезания
    """
    CLIP_MIN_WIDTH = 10

    def __init__(self, clip, track, time_ruler, editor=None, on_drag_end_callback=None, on_state_changed=None):
        self.clip = clip

        self.track = track
        self.time_ruler = time_ruler
        self.editor = editor
        self.on_drag_end_callback = on_drag_end_callback
        self.on_state_changed = on_state_changed
        self.is_dragging = False
        self.original_left = 0

        if not hasattr(self.clip, 'trim_start'):
            self.clip.trim_start = 0
        if not hasattr(self.clip, 'trim_end'):
            self.clip.trim_end = 0
        if not hasattr(self.clip, 'original_duration'):
            self.clip.original_duration = self.clip.duration
        if not hasattr(self.clip, 'original_start_time'):
            self.clip.original_start_time = self.clip.start_time

        # Создаём визуализацию клипа
        try:
            try:
                from audio_visualizer import AudioWaveform
                waveform = AudioWaveform(clip.filepath, width=100, height=30, color=ft.Colors.BLUE_400)
                clip_visualization = waveform.build()
            except:
                # Fallback - простой текст если не получилось
                clip_visualization = ft.Container(
                    content=ft.Text(clip.name, size=10, color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.BLUE_400,
                )

            # Вычисляем позиции
            clip_start_pixels = time_ruler.time_to_pixels(clip.start_time)
            clip_width_pixels = time_ruler.time_to_pixels(clip.duration)
            clip_width_pixels = max(self.CLIP_MIN_WIDTH, clip_width_pixels)

            clip_content_width = clip_width_pixels - ClipBorderHandle.HANDLE_WIDTH
            clip_content_width = max(self.CLIP_MIN_WIDTH, clip_content_width)

            self.clip_container = ft.Container(
                content=clip_visualization,
                width=clip_content_width,
                height=30,
                border=ft.border.all(2, ft.Colors.GREY_500),
                border_radius=3,
                bgcolor=ft.Colors.BLUE_700,
                tooltip=self._get_tooltip(),
            )

            # Оборачиваем в GestureDetector для перетаскивания
            self.gesture_detector = ft.GestureDetector(
                content=self.clip_container,
                on_pan_start=self._on_pan_start,
                on_pan_update=self._on_pan_update,
                on_pan_end=self._on_pan_end,
                on_hover=self._on_hover,
                mouse_cursor=ft.MouseCursor.MOVE,
            )

            self.left_border = ClipBorderHandle(
                clip, time_ruler, on_trim_callback=self._on_trim, is_left=True, draggable_clip_ref=self
            )
            self.right_border = ClipBorderHandle(
                clip, time_ruler, on_trim_callback=self._on_trim, is_left=False, draggable_clip_ref=self
            )

            # Ширина = ширина клипа + две границы
            self.main_stack = ft.Stack(
                [
                    self.gesture_detector,
                    ft.Container(left=0, top=0, width=ClipBorderHandle.HANDLE_WIDTH, height=30,
                                 content=self.left_border.build()),
                    ft.Container(left=clip_width_pixels - ClipBorderHandle.HANDLE_WIDTH, top=0,
                                 width=ClipBorderHandle.HANDLE_WIDTH, height=30,
                                 content=self.right_border.build()),
                ],
                width=clip_width_pixels + ClipBorderHandle.HANDLE_WIDTH,
                height=30,
                clip_behavior=ft.ClipBehavior.NONE,
            )

            self.spacer_left = ft.Container(width=clip_start_pixels, height=30)

            self.main_container = ft.Row(
                [
                    self.spacer_left,
                    self.main_stack,
                ],
                spacing=0,
                height=30,
                expand=True,
            )

        except Exception as e:
            print(f"❌ Error creating draggable clip: {e}")
            import traceback
            traceback.print_exc()

            # Fallback версия - простой контейнер
            clip_width_pixels = time_ruler.time_to_pixels(clip.duration)
            clip_width_pixels = max(self.CLIP_MIN_WIDTH, clip_width_pixels)

            self.clip_container = ft.Container(
                width=clip_width_pixels,
                height=30,
                bgcolor=ft.Colors.BLUE_400,
                border_radius=3,
                border=ft.border.all(2, ft.Colors.GREY_500),
                tooltip=self._get_tooltip(),
            )

            self.gesture_detector = ft.GestureDetector(
                content=self.clip_container,
                on_pan_start=self._on_pan_start,
                on_pan_update=self._on_pan_update,
                on_pan_end=self._on_pan_end,
                on_hover=self._on_hover,
                mouse_cursor=ft.MouseCursor.MOVE,
            )

            clip_start_pixels = time_ruler.time_to_pixels(clip.start_time)
            self.spacer_left = ft.Container(width=clip_start_pixels, height=30)

            self.main_container = ft.Row(
                [
                    self.spacer_left,
                    self.gesture_detector,
                ],
                spacing=0,
                height=30,
                expand=False,
            )

            self.main_stack = None

    def _get_tooltip(self):
        """Получить актуальный tooltip"""
        return (
            f"{self.clip.name}\n"
            f"Начало: {self.clip.start_time / 1000:.2f}с\n"
            f"Длительность: {self.clip.duration / 1000:.2f}с\n"
            f"Конец: {self.clip.end_time / 1000:.2f}с"
        )

    def _on_hover(self, e: ft.HoverEvent):
        """Обновляем tooltip при наведении"""
        if e.data == "true":
            self.clip_container.tooltip = self._get_tooltip()

    def _on_pan_start(self, e: ft.DragStartEvent):
        """Обработка начала перетаскивания"""
        self.is_dragging = True
        self.original_left = self.clip.start_time
        if self.on_state_changed:
            self.on_state_changed("dragging_start")

    def _on_pan_update(self, e: ft.DragUpdateEvent):
        """Обработка обновления позиции при перетаскивании"""
        if self.is_dragging:
            delta_time_ms = self.time_ruler.pixels_to_time(e.delta_x)
            new_time_ms = self.clip.start_time + delta_time_ms

            print(f"\n📍 DRAG UPDATE для '{self.clip.name}':")
            print(f"   delta_x={e.delta_x}px → delta_time_ms={delta_time_ms}ms")
            print(f"   current start_time={self.clip.start_time}ms")
            print(f"   new_time_ms (до ограничений)={new_time_ms}ms")

            new_time_ms = max(0, new_time_ms)
            print(f"   after max(0)={new_time_ms}ms")

            # конец не может быть за ruler_width
            max_clip_end_time = self.time_ruler.pixels_to_time(self.time_ruler.ruler_width)
            clip_end_time = new_time_ms + self.clip.duration

            print(f"   ruler_width={self.time_ruler.ruler_width}px → max_clip_end_time={max_clip_end_time}ms")
            print(f"   clip_duration={self.clip.duration}ms")
            print(f"   clip_end_time (new_time + duration)={clip_end_time}ms")

            if clip_end_time > max_clip_end_time:
                print(f"   ⛔ ВЫХОДИТ ЗА ПРЕДЕЛЫ! ({clip_end_time}ms > {max_clip_end_time}ms)")
                new_time_ms = max_clip_end_time - self.clip.duration
                print(f"   → сдвинуто на {new_time_ms}ms")
                new_time_ms = max(0, new_time_ms)
                print(f"   → после max(0): {new_time_ms}ms")
            else:
                print(f"   ✅ В пределах")

            print(f"   ИТОГОВАЯ позиция: {new_time_ms}ms\n")

            self.clip.start_time = new_time_ms
            self.clip.original_start_time = new_time_ms
            self.clip.update_end_time()

            # Обновляем позицию
            new_pos = self.time_ruler.time_to_pixels(self.clip.start_time)
            self.spacer_left.width = new_pos

            if hasattr(self.spacer_left, 'page') and self.spacer_left.page:
                self.spacer_left.update()

    def _on_pan_end(self, e: ft.DragEndEvent):
        """Обработка окончания перетаскивания"""
        self.is_dragging = False

        if self.editor and self.editor.project:
            self.editor.project._update_duration()

        if self.on_state_changed:
            self.on_state_changed("dragging_end")

        if self.on_drag_end_callback:
            self.on_drag_end_callback(self.clip)

    def _on_trim(self, clip):
        """Обработчик изменения границ"""
        print(f"📌 Обрезание: {clip.name}, новая длительность: {clip.duration}ms")
        if self.on_state_changed:
            self.on_state_changed("trimmed")

    def update_on_trim(self):
        """Обновляет визуализацию при обрезании"""
        clip_width_pixels = self.time_ruler.time_to_pixels(self.clip.duration)
        clip_width_pixels = max(self.CLIP_MIN_WIDTH, clip_width_pixels)

        clip_start_pixels = self.time_ruler.time_to_pixels(self.clip.start_time)
        self.spacer_left.width = clip_start_pixels

        clip_content_width = clip_width_pixels - ClipBorderHandle.HANDLE_WIDTH
        clip_content_width = max(self.CLIP_MIN_WIDTH, clip_content_width)
        self.clip_container.width = clip_content_width
        self.clip_container.tooltip = self._get_tooltip()

        if self.main_stack:
            self.main_stack.width = clip_width_pixels + ClipBorderHandle.HANDLE_WIDTH

            if len(self.main_stack.controls) >= 3:
                right_border_container = self.main_stack.controls[2]
                right_border_container.left = clip_width_pixels - ClipBorderHandle.HANDLE_WIDTH

        if hasattr(self.spacer_left, 'page') and self.spacer_left.page:
            self.spacer_left.update()

        if hasattr(self.clip_container, 'page') and self.clip_container.page:
            self.clip_container.update()

        if self.main_stack and hasattr(self.main_stack, 'page') and self.main_stack.page:
            self.main_stack.update()

        print(
            f"✅ Trim update: pos={clip_start_pixels}px, width={clip_width_pixels}px, duration={self.clip.duration}ms, stack_width={clip_width_pixels + ClipBorderHandle.HANDLE_WIDTH * 2}px")

    def update_position(self):
        """Обновляет визуальную позицию на основе данных клипа"""
        clip_start_pixels = self.time_ruler.time_to_pixels(self.clip.start_time)
        clip_width_pixels = self.time_ruler.time_to_pixels(self.clip.duration)
        clip_width_pixels = max(self.CLIP_MIN_WIDTH, clip_width_pixels)

        self.spacer_left.width = clip_start_pixels
        self.clip_container.width = clip_width_pixels

        if self.main_stack:
            self.main_stack.width = clip_width_pixels + ClipBorderHandle.HANDLE_WIDTH * 2

        self.clip_container.tooltip = self._get_tooltip()

    def build(self):
        """Возвращает элемент для отображения"""
        return self.main_container


def create_draggable_clip_visualization(clip, track, time_ruler, editor=None, top=25, on_drag_end_callback=None,
                                        on_state_changed=None):
    """
    Создает визуализацию клипа с возможностью перетаскивания и обрезания

    Args:
        clip: Объект AudioClip
        track: Объект Track
        time_ruler: Объект TimeRuler для конвертации пиксели ↔ время
        top: Вертикальная позиция (не используется в текущей версии)
        on_drag_end_callback: Функция обратного вызова при завершении перетаскивания
        on_state_changed: Функция обратного вызова при изменении состояния

    Returns:
        Визуальный элемент клипа
    """
    draggable_clip = DraggableClip(clip, track, time_ruler, editor, on_drag_end_callback, on_state_changed)
    return draggable_clip.build()