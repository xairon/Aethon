"""Gestion audio — capture micro et lecture haut-parleur avec support barge-in."""

import logging
import threading
import queue
import numpy as np
import sounddevice as sd

from aethon.config import AudioConfig

log = logging.getLogger(__name__)


class AudioManager:
    """Gère la capture micro en continu et la lecture audio avec interruption."""

    def __init__(self, config: AudioConfig):
        self.config = config
        self.capture_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._is_capturing = False
        self._is_playing = False
        self._stop_playback = threading.Event()
        self._capture_stream = None
        self._play_lock = threading.Lock()

        # AGC (Automatic Gain Control)
        self._agc_gain: float = 1.0
        self._agc_rms_sum: float = 0.0
        self._agc_count: int = 0
        self._agc_update_every: int = 100  # Recalcul toutes les ~3.2s (100 * 32ms)
        self._agc_logged: bool = False

    def start_capture(self):
        """Démarre la capture micro en continu."""
        if self._is_capturing:
            return
        self._is_capturing = True
        chunk_samples = int(
            self.config.sample_rate * self.config.chunk_duration_ms / 1000
        )
        self._capture_stream = sd.InputStream(
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype="int16",
            blocksize=chunk_samples,
            device=self.config.input_device,
            callback=self._audio_callback,
        )
        self._capture_stream.start()

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback appelé par sounddevice pour chaque chunk audio.

        Applique le gain d'entrée (manuel + AGC automatique) avant d'envoyer
        les samples dans la queue de capture.
        """
        audio = indata[:, 0].copy()  # int16

        # --- Gain manuel ---
        if self.config.input_gain != 1.0:
            audio = np.clip(
                audio.astype(np.float32) * self.config.input_gain,
                -32768, 32767,
            ).astype(np.int16)

        # --- AGC automatique (suspendu pendant la lecture pour eviter d'amplifier l'echo) ---
        if self.config.auto_gain and not self._is_playing:
            audio = self._apply_agc(audio)

        self.capture_queue.put(audio)

    def _apply_agc(self, audio: np.ndarray) -> np.ndarray:
        """Contrôle de gain automatique (AGC).

        Mesure le RMS moyen sur une fenêtre glissante et ajuste le gain
        pour atteindre le RMS cible. Ne réduit jamais le gain en dessous de 1.0.

        Les chunks silencieux (RMS < 0.002) sont ignorés pour éviter que le
        gain n'explose pendant les pauses et ne sature le début de la parole.
        """
        # Calculer le RMS de ce chunk
        audio_f32 = audio.astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(audio_f32 ** 2)))

        # Ignorer le silence dans le calcul du gain (évite gain → 55x)
        if rms > 0.002:
            self._agc_rms_sum += rms
            self._agc_count += 1

        # Recalcul périodique du gain (seulement si assez de chunks non-silencieux)
        if self._agc_count >= self._agc_update_every:
            avg_rms = self._agc_rms_sum / self._agc_count
            self._agc_rms_sum = 0.0
            self._agc_count = 0

            if avg_rms > 0.002:
                target_rms = self.config.auto_gain_target_rms
                new_gain = target_rms / avg_rms
                # Clamp : jamais réduire, max 20x (80x causait des saturations)
                new_gain = max(1.0, min(new_gain, 20.0))
                # Lissage exponentiel pour éviter les sauts brusques
                self._agc_gain = self._agc_gain * 0.7 + new_gain * 0.3

                log.info(
                    "AGC: RMS moyen=%.5f, gain=%.1fx (cible RMS=%.3f)",
                    avg_rms, self._agc_gain, target_rms,
                )

        # Appliquer le gain AGC
        if self._agc_gain > 1.05:
            audio = np.clip(
                audio.astype(np.float32) * self._agc_gain,
                -32768, 32767,
            ).astype(np.int16)

        return audio

    def stop_capture(self):
        """Arrête la capture micro."""
        self._is_capturing = False
        if self._capture_stream:
            self._capture_stream.stop()
            self._capture_stream.close()
            self._capture_stream = None

    def get_audio_chunk(self, timeout: float = 0.1) -> np.ndarray | None:
        """Récupère un chunk audio de la queue."""
        try:
            return self.capture_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def play_audio(self, audio_data: np.ndarray, sample_rate: int | None = None):
        """Joue de l'audio sur le haut-parleur. Interruptible via stop_playback()."""
        sr = sample_rate or self.config.playback_sample_rate
        self._stop_playback.clear()
        self._is_playing = True

        try:
            with self._play_lock:
                if audio_data.dtype != np.float32:
                    audio_data = audio_data.astype(np.float32)

                sd.play(audio_data, samplerate=sr, device=self.config.output_device)
                # Attendre la fin reelle de la lecture (pas de drift temporel)
                while True:
                    stream = sd.get_stream()
                    if not stream or not stream.active:
                        break
                    if self._stop_playback.is_set():
                        sd.stop()
                        break
                    sd.sleep(30)
        finally:
            self._is_playing = False

    def play_audio_stream(self, chunks, sample_rate: int | None = None):
        """Joue des chunks audio en streaming. Démarre la lecture dès le 1er chunk.

        Args:
            chunks: Iterable de np.ndarray float32.
            sample_rate: Taux d'échantillonnage (défaut: playback_sample_rate).
        """
        sr = sample_rate or self.config.playback_sample_rate
        self._stop_playback.clear()
        self._is_playing = True

        try:
            with self._play_lock:
                buf = queue.Queue(maxsize=32)  # Back-pressure si TTS génère plus vite que lecture
                finished = threading.Event()

                def _callback(outdata, frames, time_info, status):
                    try:
                        data = buf.get_nowait()
                    except queue.Empty:
                        if finished.is_set():
                            raise sd.CallbackStop
                        outdata[:] = 0
                        return
                    if len(data) < frames:
                        outdata[:len(data), 0] = data
                        outdata[len(data):] = 0
                    else:
                        outdata[:, 0] = data[:frames]
                    # Re-queue leftover
                    if len(data) > frames:
                        buf.put(data[frames:])

                stream = sd.OutputStream(
                    samplerate=sr,
                    channels=1,
                    dtype="float32",
                    blocksize=1024,
                    device=self.config.output_device,
                    callback=_callback,
                )
                stream.start()

                for chunk in chunks:
                    if self._stop_playback.is_set():
                        break
                    if chunk.dtype != np.float32:
                        chunk = chunk.astype(np.float32)
                    # Timeout loop pour back-pressure avec vérification barge-in
                    while not self._stop_playback.is_set():
                        try:
                            buf.put(chunk, timeout=0.5)
                            break
                        except queue.Full:
                            continue

                finished.set()
                # Drain remaining buffer
                while stream.active and not self._stop_playback.is_set():
                    sd.sleep(30)

                stream.stop()
                stream.close()
        finally:
            self._is_playing = False

    def stop_playback(self):
        """Interrompt la lecture en cours (barge-in)."""
        self._stop_playback.set()
        try:
            sd.stop()
        except Exception:
            pass

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def drain_capture_queue(self):
        """Vide la queue de capture (utile après une réponse TTS)."""
        while not self.capture_queue.empty():
            try:
                self.capture_queue.get_nowait()
            except queue.Empty:
                break

    def cleanup(self):
        """Nettoie les ressources."""
        self.stop_capture()
        self.stop_playback()
