import threading
from typing import Optional, Callable

import numpy as np
import soundfile as sf

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False


class AudioExporter:
    FORMATS = {
        'wav': {'name': 'WAV (Uncompressed)', 'codec': 'PCM_16'},
        'mp3': {'name': 'MP3 (Compressed)', 'bitrate': '320k'},
        'flac': {'name': 'FLAC (Lossless)', 'codec': 'FLAC'},
        'ogg': {'name': 'OGG (Compressed)', 'bitrate': '320k'},
    }

    def __init__(self, project):
        self.project = project
        self.is_exporting = False
        self.export_progress = 0

    def render_to_array(self) -> tuple[np.ndarray, int]:
        if not self.project.tracks:
            raise ValueError("Нет дорожек для экспорта!")

        sample_rate = 44100
        duration_ms = self.project.duration
        duration_sec = duration_ms / 1000
        num_samples = int(sample_rate * duration_sec)

        audio_buffer = np.zeros((num_samples, 2), dtype=np.float32)

        try:
            import librosa
            LIBROSA_AVAILABLE = True
        except ImportError:
            LIBROSA_AVAILABLE = False

        for track in self.project.tracks:
            for clip in track.get_clips_sorted():
                try:
                    if LIBROSA_AVAILABLE:
                        y, sr = librosa.load(clip.file_path, sr=sample_rate, mono=False)
                    else:
                        y, sr = sf.read(clip.file_path, dtype='float32')

                    if sr != sample_rate:
                        ratio = sample_rate / sr
                        y = np.interp(
                            np.arange(0, len(y), 1/ratio),
                            np.arange(len(y)),
                            y
                        )

                    trim_start_samples = int(clip.trim_start / 1000 * sample_rate)
                    trim_end_samples = int(clip.trim_end / 1000 * sample_rate)
                    y_trimmed = y[trim_start_samples:-trim_end_samples if trim_end_samples > 0 else len(y)]

                    if len(y_trimmed.shape) == 1:
                        y_stereo = np.stack([y_trimmed, y_trimmed], axis=-1)
                    else:
                        y_stereo = y_trimmed

                    start_sample = int(clip.start_time / 1000 * sample_rate)
                    end_sample = start_sample + y_stereo.shape[0]

                    if end_sample > num_samples:
                        y_stereo = y_stereo[:num_samples - start_sample]
                        end_sample = num_samples

                    audio_buffer[start_sample:end_sample] += y_stereo

                except Exception as e:
                    continue

        max_val = np.max(np.abs(audio_buffer))
        if max_val > 1.0:
            audio_buffer = audio_buffer / (max_val * 1.05)

        return audio_buffer, sample_rate

    def export(self, output_path: str, format: str,
               progress_callback: Optional[Callable] = None) -> bool:
        if format not in self.FORMATS:
            raise ValueError(f"Неподдерживаемый формат: {format}")

        self.is_exporting = True
        self.export_progress = 0

        try:
            if progress_callback:
                progress_callback(10, "Рендеринг аудио...")

            audio_array, sample_rate = self.render_to_array()

            if progress_callback:
                progress_callback(50, f"Сохранение в {format.upper()}...")

            if format == 'wav':
                self._export_wav(output_path, audio_array, sample_rate)
            elif format == 'mp3':
                self._export_mp3(output_path, audio_array, sample_rate)
            elif format == 'flac':
                self._export_flac(output_path, audio_array, sample_rate)
            elif format == 'ogg':
                self._export_ogg(output_path, audio_array, sample_rate)

            if progress_callback:
                progress_callback(100, "✅ Готово!")

            return True

        except Exception as e:
            if progress_callback:
                progress_callback(0, f"❌ Ошибка: {e}")
            return False

        finally:
            self.is_exporting = False

    def _export_wav(self, path: str, audio: np.ndarray, sr: int):
        sf.write(path, audio, sr, subtype='PCM_16')

    def _export_flac(self, path: str, audio: np.ndarray, sr: int):
        sf.write(path, audio, sr, subtype='PCM_16', format='FLAC')

    def _export_mp3(self, path: str, audio: np.ndarray, sr: int):
        if not PYDUB_AVAILABLE:
            raise RuntimeError("pydub не установлен. Используй: pip install pydub")

        audio_int16 = np.int16(audio * 32767)
        audio_segment = AudioSegment(
            audio_int16.tobytes(),
            frame_rate=sr,
            sample_width=2,
            channels=2
        )
        audio_segment.export(path, format="mp3", bitrate="320k")

    def _export_ogg(self, path: str, audio: np.ndarray, sr: int):
        if not PYDUB_AVAILABLE:
            raise RuntimeError("pydub не установлен. Используй: pip install pydub")

        audio_int16 = np.int16(audio * 32767)
        audio_segment = AudioSegment(
            audio_int16.tobytes(),
            frame_rate=sr,
            sample_width=2,
            channels=2
        )
        audio_segment.export(path, format="ogg", bitrate="320k")

    def export_async(self, output_path: str, format: str,
                     progress_callback: Optional[Callable] = None,
                     completion_callback: Optional[Callable] = None):
        def export_thread():
            success = self.export(output_path, format, progress_callback)
            if completion_callback:
                completion_callback(success)

        thread = threading.Thread(target=export_thread, daemon=True)
        thread.start()
