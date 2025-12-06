"""
clip_conflict_manager.py
Управление конфликтами между клипами при их перемещении и обрезании
"""


class ClipConflictManager:
    """
    Управляет разрешением конфликтов при перемещении и обрезании клипов
    """

    @staticmethod
    def check_overlap(clip1, clip2):
        """
        Проверяет, перекрываются ли два клипа
        Возвращает True если перекрываются
        """
        return (clip1.start_time < clip2.end_time and
                clip1.end_time > clip2.start_time)

    @staticmethod
    def find_conflicting_clips(track, clip, exclude_self=True):
        """
        Находит все клипы на дорожке, которые перекрываются с переданным
        """
        conflicts = []
        for other_clip in track.clips:
            if exclude_self and other_clip is clip:
                continue
            if ClipConflictManager.check_overlap(clip, other_clip):
                conflicts.append(other_clip)
        return conflicts

    @staticmethod
    def find_clips_after_time(track, time_ms, exclude_clip=None):
        """
        Находит все клипы, начинающиеся после указанного времени
        """
        clips_after = []
        for clip in track.clips:
            if exclude_clip and clip is exclude_clip:
                continue
            if clip.start_time >= time_ms:
                clips_after.append(clip)
        return clips_after

    @staticmethod
    def resolve_move_conflict(track, clip, new_start_time):
        """
        Разрешает конфликт при перемещении клипа в новую позицию
        
        Возвращает: (success, message, moved_clips)
        - success: True если перемещение прошло успешно
        - message: Строка сообщения об ошибке или успехе
        - moved_clips: Список клипов, которые пришлось переместить
        """
        # Сохраняем оригинальные позиции для отката
        original_positions = {c: c.start_time for c in track.clips}

        # Проверяем, свободно ли место в новой позиции
        clip.start_time = new_start_time
        clip.update_end_time()

        conflicts = ClipConflictManager.find_conflicting_clips(track, clip, exclude_self=True)

        if not conflicts:
            # Место свободно!
            return True, "OK", []

        # Есть конфликты - нужно сдвинуть соседние клипы вправо
        moved_clips = []
        try:
            # Сортируем конфликтующие клипы по стартовому времени
            conflicts_sorted = sorted(conflicts, key=lambda c: c.start_time)

            # Сдвигаем каждый конфликтующий клип и все за ним
            for conflict_clip in conflicts_sorted:
                # Вычисляем необходимое смещение
                overlap_end = clip.end_time
                shift_amount = overlap_end - conflict_clip.start_time

                # Находим все клипы, которые нужно сдвинуть
                clips_to_shift = [conflict_clip] + ClipConflictManager.find_clips_after_time(
                    track,
                    conflict_clip.start_time,
                    exclude_clip=conflict_clip
                )

                # Проверяем, не будут ли они конфликтовать с клипом
                for clip_to_shift in clips_to_shift:
                    clip_to_shift.start_time += shift_amount
                    clip_to_shift.update_end_time()
                    if clip_to_shift not in moved_clips:
                        moved_clips.append(clip_to_shift)

                # Проверяем финальную позицию
                final_conflicts = ClipConflictManager.find_conflicting_clips(track, clip, exclude_self=True)
                if not final_conflicts:
                    break

            return True, f"Клип перемещён. Сдвинуто {len(moved_clips)} соседних клипов.", moved_clips

        except Exception as e:
            # При ошибке откатываем все изменения
            for c in track.clips:
                c.start_time = original_positions[c]
                c.update_end_time()
            return False, f"Ошибка при перемещении: {str(e)}", []

    @staticmethod
    def try_place_clip(track, clip, target_position):
        """
        Пытается поместить клип на дорожке
        Если есть конфликт - пытается сдвинуть соседние клипы

        Возвращает: (success, message, affected_clips)
        """
        # Проверяем, свободно ли место
        old_start = clip.start_time
        clip.start_time = target_position
        clip.update_end_time()

        conflicts = ClipConflictManager.find_conflicting_clips(track, clip, exclude_self=True)

        if not conflicts:
            return True, "Место свободно", []

        # Есть конфликты - пытаемся сдвинуть
        return ClipConflictManager.resolve_move_conflict(track, clip, target_position)

    @staticmethod
    def validate_position(track, clip):
        """
        Проверяет, корректна ли текущая позиция клипа
        """
        # Клип не должен быть в отрицательной позиции
        if clip.start_time < 0:
            clip.start_time = 0
            clip.update_end_time()
            return False, "Клип сдвинут на начало дорожки"

        # Проверяем на перекрытия
        conflicts = ClipConflictManager.find_conflicting_clips(track, clip, exclude_self=True)
        if conflicts:
            return False, f"Клип перекрывает {len(conflicts)} других клипов"

        return True, "Позиция корректна"

    @staticmethod
    def sort_clips_by_start_time(track):
        """
        Сортирует клипы на дорожке по стартовому времени
        """
        track.clips.sort(key=lambda c: c.start_time)

    @staticmethod
    def get_timeline_info(track):
        """
        Возвращает информацию о временной шкале дорожки
        Полезно для отладки и визуализации
        """
        info = {
            "track_name": track.name,
            "total_clips": len(track.clips),
            "clips": []
        }

        sorted_clips = sorted(track.clips, key=lambda c: c.start_time)
        for clip in sorted_clips:
            info["clips"].append({
                "name": clip.name,
                "start": clip.start_time,
                "end": clip.end_time,
                "duration": clip.duration,
                "original_duration": clip.original_duration,
                "trim_start": clip.trim_start,
                "trim_end": clip.trim_end
            })

        return info

    @staticmethod
    def print_timeline(track):
        """
        Красиво выводит информацию о временной шкале дорожки
        """
        info = ClipConflictManager.get_timeline_info(track)
        print(f"\n=== Timeline для {info['track_name']} ===")
        print(f"Всего клипов: {info['total_clips']}")

        for i, clip_info in enumerate(info['clips'], 1):
            start_sec = clip_info['start'] / 1000
            end_sec = clip_info['end'] / 1000
            duration_sec = clip_info['duration'] / 1000
            print(f"  {i}. {clip_info['name']}: {start_sec:.2f}s - {end_sec:.2f}s "
                  f"(длительность: {duration_sec:.2f}s)")
            if clip_info['trim_start'] > 0 or clip_info['trim_end'] > 0:
                trim_start_s = clip_info['trim_start'] / 1000
                trim_end_s = clip_info['trim_end'] / 1000
                print(f"     Обрезано: слева {trim_start_s:.2f}s, справа {trim_end_s:.2f}s")

    @staticmethod
    def reorganize_track_to_avoid_gaps(track, min_gap_ms=0):
        """
        Переорганизовывает клипы на дорожке, чтобы избежать пробелов
        
        Args:
            track: Дорожка для переорганизации
            min_gap_ms: Минимальный промежуток между клипами
        """
        if not track.clips:
            return

        # Сортируем клипы
        sorted_clips = sorted(track.clips, key=lambda c: c.start_time)

        # Переставляем их встык (с минимальным промежутком)
        current_time = 0
        for clip in sorted_clips:
            clip.start_time = current_time
            clip.update_end_time()
            current_time = clip.end_time + min_gap_ms

        print(f"Track '{track.name}' reorganized to avoid gaps")
