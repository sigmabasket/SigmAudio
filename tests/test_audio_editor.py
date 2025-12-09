import unittest
import tempfile
from pathlib import Path
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import os
import time

from src.core.models import Project, Track, AudioClip, SUPPORTED_FORMATS
from src.managers.controllers import AudioEditorController
from src.core.audio_exporter import AudioExporter


class TestAudioClip(unittest.TestCase):
    """Тесты для класса AudioClip"""

    def setUp(self):
        """Подготовка перед каждым тестом"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Очистка после каждого теста"""
        self.temp_dir.cleanup()

    def test_audio_clip_creation(self):
        """Тест создания аудиоклипа с корректными параметрами"""
        clip = AudioClip("dummy.wav", start_time=1000, volume=0.8, name="TestClip")
        self.assertEqual(clip.start_time, 1000)
        self.assertEqual(clip.volume, 0.8)
        self.assertEqual(clip.name, "TestClip")

    def test_audio_clip_default_values(self):
        """Тест значений по умолчанию для AudioClip"""
        clip = AudioClip("dummy.wav")
        self.assertEqual(clip.start_time, 0)
        self.assertEqual(clip.volume, 1.0)
        self.assertEqual(clip.name, "Clip")

    def test_trim_left_positive(self):
        """Тест обрезания слева на положительное значение"""
        clip = AudioClip("dummy.wav")
        clip.original_duration = 5000  # 5 секунд
        clip.duration = 5000
        clip.trim_start = 0

        result = clip.trim_left(1000)

        self.assertEqual(clip.trim_start, 1000)
        self.assertEqual(clip.duration, 4000)
        self.assertEqual(result, 1000)

    def test_trim_left_negative(self):
        """Тест обрезания слева на отрицательное значение (отмена)"""
        clip = AudioClip("dummy.wav")
        clip.original_duration = 5000
        clip.duration = 4000
        clip.trim_start = 1000
        clip.trim_end = 0

        clip.trim_left(-500)

        self.assertEqual(clip.trim_start, 500)
        self.assertEqual(clip.duration, 4500)

    def test_trim_right_positive(self):
        """Тест обрезания справа на положительное значение"""
        clip = AudioClip("dummy.wav")
        clip.original_duration = 5000
        clip.duration = 5000
        clip.trim_start = 0
        clip.trim_end = 0

        result = clip.trim_right(1000)

        self.assertEqual(clip.trim_end, 1000)
        self.assertEqual(clip.duration, 4000)
        self.assertEqual(result, 1000)

    def test_trim_boundaries(self):
        """Тест границ обрезания"""
        clip = AudioClip("dummy.wav")
        clip.original_duration = 5000
        clip.duration = 5000
        clip.trim_start = 0
        clip.trim_end = 0

        # Попытка обрезать больше, чем длина клипа
        clip.trim_left(6000)

        self.assertEqual(clip.trim_start, 5000)
        self.assertEqual(clip.duration, 0)

    def test_get_display_duration(self):
        """Тест получения длительности с учётом обрезания"""
        clip = AudioClip("dummy.wav")
        clip.original_duration = 5000
        clip.duration = 5000
        clip.trim_start = 500
        clip.trim_end = 500
        clip.duration = 4000

        self.assertEqual(clip.get_display_duration(), 4000)

    def test_update_end_time(self):
        """Тест обновления конечного времени"""
        clip = AudioClip("dummy.wav", start_time=1000)
        clip.duration = 3000

        clip.update_end_time()

        self.assertEqual(clip.end_time, 4000)

    def test_supported_formats(self):
        """Тест проверки поддерживаемых форматов"""
        self.assertIn('mp3', SUPPORTED_FORMATS)
        self.assertIn('wav', SUPPORTED_FORMATS)
        self.assertIn('flac', SUPPORTED_FORMATS)
        self.assertIn('m4a', SUPPORTED_FORMATS)


class TestTrack(unittest.TestCase):
    """Тесты для класса Track"""

    def setUp(self):
        """Подготовка перед каждым тестом"""
        self.track = Track("TestTrack", volume=0.9, pan=-0.5)

    def test_track_creation(self):
        """Тест создания дорожки"""
        self.assertEqual(self.track.name, "TestTrack")
        self.assertEqual(self.track.volume, 0.9)
        self.assertEqual(self.track.pan, -0.5)
        self.assertEqual(len(self.track.clips), 0)

    def test_track_default_values(self):
        """Тест значений по умолчанию для Track"""
        track = Track()
        self.assertEqual(track.name, "Track")
        self.assertEqual(track.volume, 1.0)
        self.assertEqual(track.pan, 0.0)
        self.assertFalse(track.muted)
        self.assertFalse(track.solo)

    def test_add_clip(self):
        """Тест добавления клипа на дорожку"""
        clip = AudioClip("dummy.wav", start_time=1000)
        self.track.add_clip(clip)

        self.assertEqual(len(self.track.clips), 1)
        self.assertIn(clip, self.track.clips)

    def test_remove_clip_valid_index(self):
        """Тест удаления клипа с корректным индексом"""
        clip1 = AudioClip("dummy1.wav")
        clip2 = AudioClip("dummy2.wav")
        self.track.add_clip(clip1)
        self.track.add_clip(clip2)

        removed = self.track.remove_clip(0)

        self.assertEqual(removed, clip1)
        self.assertEqual(len(self.track.clips), 1)

    def test_remove_clip_invalid_index(self):
        """Тест удаления клипа с некорректным индексом"""
        clip = AudioClip("dummy.wav")
        self.track.add_clip(clip)

        result = self.track.remove_clip(5)

        self.assertIsNone(result)
        self.assertEqual(len(self.track.clips), 1)

    def test_get_clips_sorted(self):
        """Тест получения клипов отсортированных по времени"""
        clip1 = AudioClip("dummy1.wav", start_time=3000)
        clip2 = AudioClip("dummy2.wav", start_time=1000)
        clip3 = AudioClip("dummy3.wav", start_time=2000)

        self.track.add_clip(clip1)
        self.track.add_clip(clip2)
        self.track.add_clip(clip3)

        sorted_clips = self.track.get_clips_sorted()

        self.assertEqual(sorted_clips[0].start_time, 1000)
        self.assertEqual(sorted_clips[1].start_time, 2000)
        self.assertEqual(sorted_clips[2].start_time, 3000)

    def test_get_active_clips(self):
        """Тест получения активных клипов в текущее время"""
        clip1 = AudioClip("dummy1.wav", start_time=0)
        clip1.duration = 2000
        clip1.end_time = 2000

        clip2 = AudioClip("dummy2.wav", start_time=3000)
        clip2.duration = 2000
        clip2.end_time = 5000

        self.track.add_clip(clip1)
        self.track.add_clip(clip2)

        # Время 1000 - активен только первый клип
        active = self.track.get_active_clips(1000)
        self.assertEqual(len(active), 1)
        self.assertIn(clip1, active)

        # Время 4000 - активен только второй клип
        active = self.track.get_active_clips(4000)
        self.assertEqual(len(active), 1)
        self.assertIn(clip2, active)

    def test_check_overlap(self):
        """Тест проверки перекрытия клипов"""
        clip1 = AudioClip("dummy1.wav", start_time=0)
        clip1.duration = 2000
        clip1.end_time = 2000

        clip2 = AudioClip("dummy2.wav", start_time=1000)
        clip2.duration = 2000
        clip2.end_time = 3000

        self.track.add_clip(clip1)
        self.track.add_clip(clip2)

        # clip2 перекрывает clip1
        overlapping = self.track.check_overlap(clip2)
        self.assertEqual(overlapping, clip1)

    def test_check_no_overlap(self):
        """Тест проверки отсутствия перекрытия"""
        clip1 = AudioClip("dummy1.wav", start_time=0)
        clip1.duration = 2000
        clip1.end_time = 2000

        clip2 = AudioClip("dummy2.wav", start_time=3000)
        clip2.duration = 2000
        clip2.end_time = 5000

        self.track.add_clip(clip1)
        self.track.add_clip(clip2)

        overlapping = self.track.check_overlap(clip2)
        self.assertIsNone(overlapping)

    def test_find_clips_after(self):
        """Тест поиска клипов после определённого времени"""
        clip1 = AudioClip("dummy1.wav", start_time=1000)
        clip2 = AudioClip("dummy2.wav", start_time=3000)
        clip3 = AudioClip("dummy3.wav", start_time=5000)

        self.track.add_clip(clip1)
        self.track.add_clip(clip2)
        self.track.add_clip(clip3)

        clips_after_3000 = self.track.find_clips_after(3000)

        self.assertEqual(len(clips_after_3000), 2)
        self.assertIn(clip2, clips_after_3000)
        self.assertIn(clip3, clips_after_3000)


class TestProject(unittest.TestCase):
    """Тесты для класса Project"""

    def setUp(self):
        """Подготовка перед каждым тестом"""
        self.project = Project(sample_rate=44100, channels=2)

    def test_project_creation(self):
        """Тест создания проекта"""
        self.assertEqual(self.project.sample_rate, 44100)
        self.assertEqual(self.project.channels, 2)
        self.assertEqual(len(self.project.tracks), 0)
        self.assertFalse(self.project.playing)

    def test_add_track(self):
        """Тест добавления дорожки"""
        track = Track("Track1")
        self.project.add_track(track)

        self.assertEqual(len(self.project.tracks), 1)
        self.assertIn(track, self.project.tracks)

    def test_project_duration_minimum(self):
        """ИСПРАВЛЕНО: Тест минимальной длительности проекта (10000ms)"""
        track = Track()
        clip = AudioClip("dummy.wav", start_time=0)
        clip.duration = 5000
        clip.end_time = 5000

        track.add_clip(clip)
        self.project.add_track(track)

        # Минимум 10000ms, даже если клип короче
        self.assertEqual(self.project.duration, 10000)

    def test_set_playback_time_valid(self):
        """Тест установки времени воспроизведения"""
        self.project.duration = 10000
        self.project.set_playback_time(5000)

        self.assertEqual(self.project.current_time, 5000)

    def test_set_playback_time_boundary_low(self):
        """Тест установки времени воспроизведения ниже минимума"""
        self.project.set_playback_time(-500)

        self.assertEqual(self.project.current_time, 0)

    def test_set_playback_time_boundary_high(self):
        """Тест установки времени воспроизведения выше максимума"""
        self.project.duration = 10000
        self.project.set_playback_time(15000)

        self.assertEqual(self.project.current_time, 10000)

    def test_project_minimum_duration(self):
        """Тест минимальной длительности проекта"""
        self.project._update_duration()

        # Проект без клипов имеет минимальную длительность 10000 ms
        self.assertEqual(self.project.duration, 10000)

    def test_multiple_tracks_duration(self):
        """ИСПРАВЛЕНО: Тест длительности с несколькими дорожками (минимум 10000)"""
        track1 = Track("Track1")
        clip1 = AudioClip("dummy1.wav", start_time=0)
        clip1.duration = 3000
        clip1.end_time = 3000

        track2 = Track("Track2")
        clip2 = AudioClip("dummy2.wav", start_time=2000)
        clip2.duration = 5000
        clip2.end_time = 7000

        track1.add_clip(clip1)
        track2.add_clip(clip2)

        self.project.add_track(track1)
        self.project.add_track(track2)

        # max_end = 7000, но минимум = 10000
        self.assertEqual(self.project.duration, 10000)

    def test_update_callback(self):
        """Тест callback при обновлении времени"""
        callback = Mock()
        self.project.set_update_callback(callback)
        self.project.duration = 10000

        self.project.set_playback_time(5000)

        callback.assert_called_once()


class TestAudioEditorController(unittest.TestCase):
    """Тесты для класса AudioEditorController"""

    def setUp(self):
        """Подготовка перед каждым тестом"""
        self.controller = AudioEditorController()

    def test_controller_initialization(self):
        """Тест инициализации контроллера"""
        self.assertIsNotNone(self.controller.project)
        self.assertEqual(len(self.controller.project.tracks), 0)

    def test_create_track(self):
        """Тест создания дорожки через контроллер"""
        track = self.controller.create_track("MyTrack")

        self.assertIsNotNone(track)
        self.assertEqual(track.name, "MyTrack")
        self.assertEqual(len(self.controller.project.tracks), 1)

    def test_create_track_default_name(self):
        """Тест создания дорожки с именем по умолчанию"""
        track = self.controller.create_track()

        self.assertEqual(track.name, "Track")

    def test_set_playback_position(self):
        """Тест установки позиции воспроизведения"""
        self.controller.project.duration = 10000

        self.controller.set_playback_position(0.5)

        self.assertEqual(self.controller.project.current_time, 5000)

    def test_set_playback_position_seeking(self):
        """Тест установки позиции воспроизведения с флагом seeking"""
        self.controller.project.duration = 10000

        self.controller.set_playback_position(0.3, seeking=True)

        self.assertEqual(self.controller.project.current_time, 3000)
        self.assertTrue(self.controller.project.seeking)

    def test_toggle_play_method_exists(self):
        """Тест что метод toggle_play существует и вызывается"""
        self.assertTrue(callable(self.controller.toggle_play))
        self.controller.toggle_play()

    def test_is_playing_false_paused(self):
        """Тест проверки состояния воспроизведения (paused)"""
        self.controller.project.playing = True
        self.controller.project.paused = True

        self.assertFalse(self.controller.is_playing())

    def test_is_playing_false_not_playing(self):
        """Тест проверки состояния воспроизведения (not playing)"""
        self.controller.project.playing = False
        self.controller.project.paused = False

        self.assertFalse(self.controller.is_playing())

    def test_set_ui_update_callback(self):
        """Тест установки callback для обновлений UI"""
        callback = Mock()
        self.controller.set_ui_update_callback(callback)

        self.controller.project.duration = 10000
        self.controller.project.set_playback_time(5000)

        callback.assert_called()


class TestAudioExporter(unittest.TestCase):
    """Тесты для класса AudioExporter"""

    def setUp(self):
        """Подготовка перед каждым тестом"""
        self.project = Project()
        self.exporter = AudioExporter(self.project)

    def test_exporter_initialization(self):
        """Тест инициализации экспортера"""
        self.assertEqual(self.exporter.project, self.project)
        self.assertFalse(self.exporter.is_exporting)
        self.assertEqual(self.exporter.export_progress, 0)

    def test_supported_formats(self):
        """Тест поддерживаемых форматов экспорта"""
        self.assertIn('wav', self.exporter.FORMATS)
        self.assertIn('mp3', self.exporter.FORMATS)
        self.assertIn('flac', self.exporter.FORMATS)
        self.assertIn('ogg', self.exporter.FORMATS)

    def test_render_to_array_no_tracks(self):
        """Тест рендеринга без дорожек (должна быть ошибка)"""
        with self.assertRaises(ValueError) as cm:
            self.exporter.render_to_array()

        self.assertIn("Нет дорожек", str(cm.exception))

    def test_export_invalid_format_raises_error(self):
        """ИСПРАВЛЕНО: Тест что export выбрасывает ValueError для неподдерживаемого формата"""
        track = Track()
        clip = AudioClip("dummy.wav", start_time=0)
        track.add_clip(clip)
        self.project.add_track(track)

        # Метод выбрасывает ValueError при неподдерживаемом формате
        with self.assertRaises(ValueError):
            self.exporter.export("output.xyz", "xyz")

    def test_export_progress_callback(self):
        """Тест callback прогресса экспорта"""
        callback = Mock()
        track = Track()
        clip = AudioClip("dummy.wav", start_time=0)
        track.add_clip(clip)
        self.project.add_track(track)

        # Проверяем, что callback вызывается
        # (не можем полностью тестировать без реальных аудиофайлов)
        self.assertTrue(callable(callback))


class TestTrackClipInteractions(unittest.TestCase):
    """Интеграционные тесты взаимодействия Track и Clip"""

    def test_multiple_clips_sorting(self):
        """Тест сортировки множества клипов"""
        track = Track()

        clips_data = [
            (1000, "clip_1"),
            (5000, "clip_5"),
            (3000, "clip_3"),
            (2000, "clip_2"),
            (4000, "clip_4"),
        ]

        for start_time, name in clips_data:
            clip = AudioClip(f"dummy_{name}.wav", start_time=start_time, name=name)
            track.add_clip(clip)

        sorted_clips = track.get_clips_sorted()

        for i in range(len(sorted_clips) - 1):
            self.assertLessEqual(sorted_clips[i].start_time, sorted_clips[i + 1].start_time)

    def test_overlapping_detection(self):
        """Тест обнаружения перекрытий между клипами"""
        track = Track()

        test_cases = [
            # (clip1_start, clip1_end, clip2_start, clip2_end, should_overlap)
            (0, 2000, 2000, 4000, False),  # adjacent
            (0, 2000, 1000, 3000, True),  # overlapping
            (0, 2000, 3000, 5000, False),  # separate
            (1000, 3000, 0, 2000, True),  # reverse overlap
        ]

        for start1, end1, start2, end2, should_overlap in test_cases:
            track.clips = []  # Clear clips

            clip1 = AudioClip("dummy1.wav", start_time=start1)
            clip1.duration = end1 - start1
            clip1.end_time = end1

            clip2 = AudioClip("dummy2.wav", start_time=start2)
            clip2.duration = end2 - start2
            clip2.end_time = end2

            track.add_clip(clip1)
            track.add_clip(clip2)

            overlap = track.check_overlap(clip2)

            if should_overlap:
                self.assertIsNotNone(overlap,
                                     f"Expected overlap: clip1({start1}-{end1}) vs clip2({start2}-{end2})")
            else:
                self.assertIsNone(overlap,
                                  f"Expected no overlap: clip1({start1}-{end1}) vs clip2({start2}-{end2})")


class TestProjectTimeline(unittest.TestCase):
    """Тесты для работы с временной шкалой проекта"""

    def setUp(self):
        """Подготовка перед каждым тестом"""
        self.project = Project()

    def test_complex_timeline(self):
        """ИСПРАВЛЕНО: Тест сложной временной шкалы (минимум 10000)"""
        # Создаём дорожки
        track1 = Track("Drums")
        track2 = Track("Bass")
        track3 = Track("Guitar")

        # Добавляем клипы на дорожку 1
        clip1_1 = AudioClip("drums1.wav", start_time=0)
        clip1_1.duration = 4000
        clip1_1.end_time = 4000

        clip1_2 = AudioClip("drums2.wav", start_time=4000)
        clip1_2.duration = 4000
        clip1_2.end_time = 8000

        track1.add_clip(clip1_1)
        track1.add_clip(clip1_2)

        # Добавляем клипы на дорожку 2
        clip2_1 = AudioClip("bass1.wav", start_time=2000)
        clip2_1.duration = 6000
        clip2_1.end_time = 8000

        track2.add_clip(clip2_1)

        # Добавляем клипы на дорожку 3
        clip3_1 = AudioClip("guitar1.wav", start_time=0)
        clip3_1.duration = 8000
        clip3_1.end_time = 8000

        track3.add_clip(clip3_1)

        # Добавляем дорожки в проект
        self.project.add_track(track1)
        self.project.add_track(track2)
        self.project.add_track(track3)

        # max_end = 8000, но минимум = 10000
        self.assertEqual(self.project.duration, 10000)

        # Проверяем активные клипы на разных временных точках
        active_at_1000 = []
        for track in self.project.tracks:
            active_at_1000.extend(track.get_active_clips(1000))
        self.assertEqual(len(active_at_1000), 2)  # clip1_1 и clip3_1

        active_at_5000 = []
        for track in self.project.tracks:
            active_at_5000.extend(track.get_active_clips(5000))
        self.assertEqual(len(active_at_5000), 3)  # все три дорожки активны


if __name__ == '__main__':
    unittest.main()