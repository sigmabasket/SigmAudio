from models import Project, Track, AudioClip
import threading


class AudioEditorController:
    """
    Контроллер аудио редактора - управляет логикой приложения
    """
    def __init__(self):
        self.project = Project()
        self.ui_update_callback = None
        self.track_manager = None  # Будет устанавливаться извне

    def create_track(self, name="Track"):
        track = Track(name)
        self.project.add_track(track)
        return track

    def set_track_manager(self, track_manager):
        """Устанавливает ссылку на track_manager для обновления UI"""
        self.track_manager = track_manager

    def add_audio_clip(self, track_index, file_path, start_time=0, name="Clip"):
        if 0 <= track_index < len(self.project.tracks):
            try:
                clip = AudioClip(file_path, start_time, name=name)
                self.project.tracks[track_index].add_clip(clip)
                self.project._update_duration()
                print(f"Added audio clip: {name} to track {track_index}, project duration: {self.project.duration}ms")

                # Автоматически обновляем линейку при добавлении клипа
                if self.track_manager:
                    self.track_manager.time_ruler.update_ruler()
                    self.track_manager.update_all_visualizations()

                return clip
            except Exception as e:
                print(f"Error adding audio clip: {e}")
                return None
        return None

    def set_playback_position(self, percent, seeking=False):
        time_ms = percent * self.project.duration
        self.project.set_playback_time(time_ms, seeking)

    def toggle_play(self):
        self.project.toggle_play()

    def is_playing(self):
        return self.project.playing and not self.project.paused

    def set_ui_update_callback(self, callback):
        self.project.set_update_callback(callback)

    def cleanup(self):
        self.project.cleanup()