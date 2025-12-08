from models import AudioClip


class ClipConflictManager:
    """Управляет конфликтами между клипами на дорожке"""

    @staticmethod
    def detect_conflicts(clips: list[AudioClip]) -> list[tuple[int, int]]:
        """Обнаруживает перекрывающиеся клипы

        Returns: список пар индексов конфликтующих клипов
        """
        conflicts = []
        sorted_clips = sorted(clips, key=lambda c: c.start_time)

        for i in range(len(sorted_clips)):
            for j in range(i + 1, len(sorted_clips)):
                clip_a = sorted_clips[i]
                clip_b = sorted_clips[j]

                if clip_a.end_time > clip_b.start_time:
                    conflicts.append((i, j))

        return conflicts

    @staticmethod
    def resolve_conflict_overlap(clips: list[AudioClip], clip_a_idx: int, clip_b_idx: int) -> bool:
        """Разрешает конфликт путём сдвига второго клипа"""
        clip_a = clips[clip_a_idx]
        clip_b = clips[clip_b_idx]

        if clip_a.end_time > clip_b.start_time:
            clip_b.start_time = clip_a.end_time
            return True

        return False

    @staticmethod
    def resolve_conflict_trim(clips: list[AudioClip], clip_a_idx: int, clip_b_idx: int) -> bool:
        """Разрешает конфликт путём обрезания первого клипа"""
        clip_a = clips[clip_a_idx]
        clip_b = clips[clip_b_idx]

        if clip_a.end_time > clip_b.start_time:
            overlap_duration = clip_a.end_time - clip_b.start_time

            if overlap_duration < clip_a.duration:
                clip_a.end_time = clip_b.start_time
                return True

        return False

    @staticmethod
    def resolve_conflict_delete_shorter(clips: list[AudioClip], clip_a_idx: int, clip_b_idx: int) -> bool:
        """Разрешает конфликт путём удаления более короткого клипа"""
        clip_a = clips[clip_a_idx]
        clip_b = clips[clip_b_idx]

        if clip_a.end_time > clip_b.start_time:
            if clip_a.duration < clip_b.duration:
                clips.pop(clip_a_idx)
                return True
            else:
                clips.pop(clip_b_idx)
                return True

        return False

    @staticmethod
    def get_safe_insert_position(clips: list[AudioClip], new_clip: AudioClip) -> int:
        """Находит безопасную позицию для вставки клипа"""
        sorted_clips = sorted(enumerate(clips), key=lambda x: x[1].start_time)

        for idx, (original_idx, clip) in enumerate(sorted_clips):
            if clip.end_time <= new_clip.start_time:
                continue
            if clip.start_time >= new_clip.end_time:
                return original_idx

        return len(clips)

    @staticmethod
    def auto_resolve_all_conflicts(clips: list[AudioClip], strategy: str = "shift") -> dict:
        """Автоматически разрешает все конфликты"""
        results = {
            "resolved": 0,
            "conflicts_remaining": 0,
        }

        max_iterations = 100
        iteration = 0

        while iteration < max_iterations:
            conflicts = ClipConflictManager.detect_conflicts(clips)

            if not conflicts:
                break

            for clip_a_idx, clip_b_idx in conflicts:
                if strategy == "shift":
                    ClipConflictManager.resolve_conflict_overlap(clips, clip_a_idx, clip_b_idx)
                    results["resolved"] += 1
                elif strategy == "trim":
                    ClipConflictManager.resolve_conflict_trim(clips, clip_a_idx, clip_b_idx)
                    results["resolved"] += 1
                elif strategy == "delete":
                    ClipConflictManager.resolve_conflict_delete_shorter(clips, clip_a_idx, clip_b_idx)
                    results["resolved"] += 1

            iteration += 1

        final_conflicts = ClipConflictManager.detect_conflicts(clips)
        results["conflicts_remaining"] = len(final_conflicts)

        return results
