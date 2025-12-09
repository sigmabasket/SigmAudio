import os
from pydub import AudioSegment
from pydub.utils import which
import numpy as np
import pyaudio


def _setup_ffmpeg():
    """Проверяет наличие ffmpeg и настраивает его при необходимости"""
    try:
        ffmpeg_path = which("ffmpeg")
        ffprobe_path = which("ffprobe")
        if ffmpeg_path and ffprobe_path:
            return True
        return False
    except Exception:
        return False


_setup_ffmpeg()

SUPPORTED_FORMATS = {
    'mp3': 'MPEG Audio',
    'wav': 'WAV Audio',
    'flac': 'FLAC Audio',
    'm4a': 'MPEG-4 Audio',
    'aac': 'AAC Audio',
    'ogg': 'OGG Audio',
    'wma': 'Windows Media Audio',
    'aiff': 'AIFF Audio',
}

SUPPORTED_EXTENSIONS = list(SUPPORTED_FORMATS.keys())


class AudioClip:
    """Класс для представления аудиоклипа

    Поддерживает: MP3, WAV, FLAC, M4A, AAC, OGG, WMA, AIFF
    """

    def __init__(self, file_path, start_time=0, volume=1.0, name="Clip"):
        self.file_path = file_path
        self.start_time = start_time
        self.volume = volume
        self.name = name
        self.original_format = None

        try:
            _, file_ext = os.path.splitext(file_path)
            file_ext = file_ext.lstrip('.').lower()
            self.original_format = file_ext

            self.audio = AudioSegment.from_file(file_path,
                                                format=file_ext if file_ext in SUPPORTED_EXTENSIONS else None)
            self.duration = len(self.audio)
            self.end_time = self.start_time + self.duration
            self.raw_data = self.audio.raw_data
            self.sample_width = self.audio.sample_width
            self.channels = self.audio.channels
            self.frame_rate = self.audio.frame_rate
            self.trim_start = 0
            self.trim_end = 0
            self.original_duration = self.duration

        except FileNotFoundError:
            self._set_error_defaults()
        except ValueError:
            self._set_error_defaults()
        except Exception:
            self._set_error_defaults()

    def _set_error_defaults(self):
        """Устанавливает значения по умолчанию при ошибке загрузки"""
        self.duration = 0
        self.end_time = self.start_time
        self.raw_data = b''
        self.sample_width = 2
        self.channels = 2
        self.frame_rate = 44100
        self.trim_start = 0
        self.trim_end = 0
        self.original_duration = 0
        self.audio = None

    def get_audio_chunk(self, start_ms, duration_ms):
        """Получает chunk аудио данных для указанного временного интервала"""
        if not self.audio or start_ms >= self.duration:
            return None

        end_ms = min(start_ms + duration_ms, self.duration)
        actual_start_ms = start_ms + self.trim_start
        actual_end_ms = end_ms + self.trim_start
        bytes_per_ms = self.frame_rate * self.sample_width * self.channels / 1000
        start_byte = int(actual_start_ms * bytes_per_ms)
        end_byte = int(actual_end_ms * bytes_per_ms)
        sample_size = self.sample_width * self.channels
        start_byte = (start_byte // sample_size) * sample_size
        end_byte = (end_byte // sample_size) * sample_size

        if start_byte >= len(self.raw_data) or start_byte >= end_byte:
            return None

        return self.raw_data[start_byte:end_byte]

    def trim_left(self, amount_ms):
        """Обрезает слева на amount_ms миллисекунд"""
        if amount_ms < 0:
            self.trim_start = max(0, self.trim_start + amount_ms)
            self.duration = self.original_duration - self.trim_start - self.trim_end
        else:
            new_trim = min(self.trim_start + amount_ms, self.original_duration)
            amount_applied = new_trim - self.trim_start
            self.trim_start = new_trim
            self.duration = max(0, self.original_duration - self.trim_start - self.trim_end)
            return amount_applied

        return abs(amount_ms)

    def trim_right(self, amount_ms):
        """Обрезает справа на amount_ms миллисекунд"""
        if amount_ms < 0:
            self.trim_end = max(0, self.trim_end + amount_ms)
            self.duration = self.original_duration - self.trim_start - self.trim_end
        else:
            new_trim = min(self.trim_end + amount_ms, self.original_duration)
            amount_applied = new_trim - self.trim_end
            self.trim_end = new_trim
            self.duration = max(0, self.original_duration - self.trim_start - self.trim_end)
            return amount_applied

        return abs(amount_ms)

    def get_display_duration(self):
        """Возвращает текущую длительность (с учётом обрезания)"""
        return self.duration

    def update_end_time(self):
        """Обновляет конечное время"""
        self.end_time = self.start_time + self.duration

    def export_to_format(self, output_path, format=None):
        """Экспортирует клип в указанный формат

        Args:
            output_path: Путь для сохранения
            format: Формат файла (mp3, wav, flac и т.д.)
        """
        if not self.audio:
            return False

        try:
            if format is None:
                _, ext = os.path.splitext(output_path)
                format = ext.lstrip('.').lower()

            export_audio = self.audio[self.trim_start:len(self.audio) - self.trim_end]
            export_audio.export(output_path, format=format)
            return True

        except Exception:
            return False


class Track:
    """Класс для представления аудиодорожки"""

    def __init__(self, name="Track", volume=1.0, pan=0.0):
        self.name = name
        self.volume = volume
        self.pan = pan
        self.clips = []
        self.muted = False
        self.solo = False

    def add_clip(self, clip):
        self.clips.append(clip)

    def remove_clip(self, clip_index):
        if 0 <= clip_index < len(self.clips):
            return self.clips.pop(clip_index)
        return None

    def get_active_clips(self, current_time, lookahead_ms=50):
        """Возвращает клипы, активные в текущее время + lookahead"""
        active_clips = []
        for clip in self.clips:
            if (clip.start_time <= current_time < clip.end_time or
                    clip.start_time <= current_time + lookahead_ms < clip.end_time):
                active_clips.append(clip)
        return active_clips

    def get_clips_sorted(self):
        """Возвращает клипы отсортированные по start_time"""
        return sorted(self.clips, key=lambda c: c.start_time)

    def check_overlap(self, clip):
        """Проверяет перекрывает ли клип другие клипы на дорожке"""
        for other_clip in self.clips:
            if other_clip is clip:
                continue
            if (clip.start_time < other_clip.end_time and
                    clip.end_time > other_clip.start_time):
                return other_clip
        return None

    def find_clips_after(self, time_ms):
        """Находит все клипы, начинающиеся после time_ms"""
        return [clip for clip in self.clips if clip.start_time >= time_ms]


class Project:
    """Класс для управления проектом аудиоредактора"""

    def __init__(self, sample_rate=44100, channels=2):
        self.tracks = []
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = 2
        self.playing = False
        self.paused = False
        self.seeking = False
        self.current_time = 0
        self.duration = 0

        import threading
        self.py_audio = pyaudio.PyAudio()
        self.stream = None
        self.stop_flag = False
        self.lock = threading.Lock()
        self.update_callback = None

    def add_track(self, track):
        self.tracks.append(track)
        self._update_duration()

    def _update_duration(self):
        """Обновляет общую длительность проекта"""
        max_end = 0
        for track in self.tracks:
            for clip in track.clips:
                max_end = max(max_end, clip.end_time)

        new_duration = max(10000, max_end)
        if new_duration > self.duration:
            self.duration = new_duration

    def add_duration(self, duration_ms):
        """Добавляет дополнительное время к проекту"""
        if duration_ms > 0:
            new_duration = self.duration + duration_ms
            self.duration = new_duration

            if self.update_callback:
                progress = self.current_time / self.duration if self.duration > 0 else 0
                self.update_callback(progress)

    def set_update_callback(self, callback):
        self.update_callback = callback

    def toggle_play(self):
        if not self.playing:
            self.playing = True
            self.paused = False
            self.stop_flag = False
            import threading
            threading.Thread(target=self._playback_loop, daemon=True).start()
        elif self.paused:
            self.paused = False
        else:
            self.paused = True
            self._stop_stream()

    def set_playback_time(self, time_ms, seeking=False):
        """Устанавливает время воспроизведения"""
        self.current_time = max(0, min(time_ms, self.duration))
        self.seeking = seeking
        if self.update_callback:
            self.update_callback(self.current_time / self.duration if self.duration > 0 else 0)

    def _stop_stream(self):
        """Безопасная остановка потока"""
        with self.lock:
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                    self.stream = None
                except Exception:
                    pass

    def _generate_silence(self, duration_ms):
        """Генерирует тишину указанной длительности"""
        bytes_per_ms = self.sample_rate * self.sample_width * self.channels / 1000
        num_bytes = int(duration_ms * bytes_per_ms)
        return b'\x00' * num_bytes

    def _mix_audio_chunk(self, start_time, chunk_duration_ms):
        """Микширует аудио из всех дорожек для указанного временного интервала"""
        active_tracks = [track for track in self.tracks if not track.muted]

        if not active_tracks:
            return self._generate_silence(chunk_duration_ms)

        target_bytes = int(self.sample_rate * self.sample_width * self.channels * chunk_duration_ms / 1000)
        mixed_data = None

        for track in active_tracks:
            active_clips = track.get_active_clips(start_time, chunk_duration_ms)
            for clip in active_clips:
                clip_position = start_time - clip.start_time
                if clip_position < 0:
                    continue

                audio_chunk = clip.get_audio_chunk(clip_position, chunk_duration_ms)

                if audio_chunk:
                    if clip.volume != 1.0 or track.volume != 1.0:
                        audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
                        adjusted_array = (audio_array * clip.volume * track.volume).astype(np.int16)
                        audio_chunk = adjusted_array.tobytes()

                    if mixed_data is None:
                        mixed_data = audio_chunk
                    else:
                        arr1 = np.frombuffer(mixed_data, dtype=np.int16)
                        arr2 = np.frombuffer(audio_chunk, dtype=np.int16)
                        min_len = min(len(arr1), len(arr2))
                        arr1 = arr1[:min_len]
                        arr2 = arr2[:min_len]
                        mixed = np.clip(arr1 + arr2, -32768, 32767).astype(np.int16)
                        mixed_data = mixed.tobytes()

        if mixed_data is None:
            return self._generate_silence(chunk_duration_ms)

        if len(mixed_data) < target_bytes:
            mixed_data += b'\x00' * (target_bytes - len(mixed_data))
        elif len(mixed_data) > target_bytes:
            mixed_data = mixed_data[:target_bytes]

        return mixed_data

    def _playback_loop(self):
        """Основной цикл воспроизведения"""
        self.stop_flag = False
        chunk_duration_ms = 50

        while self.playing and not self.stop_flag:
            if self.seeking or self.paused:
                import time
                time.sleep(0.01)
                continue

            if self.current_time >= self.duration:
                self.playing = False
                self.current_time = 0
                if self.update_callback:
                    self.update_callback(0.0)
                break

            try:
                if self.current_time >= self.duration:
                    break

                chunk_end_time = min(self.current_time + chunk_duration_ms, self.duration)
                actual_chunk_duration = chunk_end_time - self.current_time
                mixed_audio = self._mix_audio_chunk(self.current_time, actual_chunk_duration)

                with self.lock:
                    if not self.stream:
                        try:
                            self.stream = self.py_audio.open(
                                format=pyaudio.paInt16,
                                channels=self.channels,
                                rate=self.sample_rate,
                                output=True
                            )
                        except Exception:
                            break

                    if self.stream:
                        try:
                            self.stream.write(mixed_audio)
                            self.current_time += chunk_duration_ms
                            if self.update_callback and self.duration > 0:
                                progress = min(1.0, self.current_time / self.duration)
                                self.update_callback(progress)
                        except Exception:
                            with self.lock:
                                if self.stream:
                                    self.stream.close()
                                    self.stream = None
                            continue

            except Exception:
                import time
                time.sleep(0.01)

        self._stop_stream()
        if not self.paused:
            self.playing = False

    def cleanup(self):
        """Очистка ресурсов"""
        self.stop_flag = True
        self.playing = False
        self._stop_stream()
        if self.py_audio:
            self.py_audio.terminate()

    def add_audio_clip(self, track_index, filepath, start_time=0, name=""):
        """Добавляет аудиоклип на дорожку"""
        if not (0 <= track_index < len(self.tracks)):
            return None

        try:
            clip = AudioClip(filepath, start_time, name=name)
            self.tracks[track_index].add_clip(clip)
            self._update_duration()
            return clip
        except Exception:
            return None
