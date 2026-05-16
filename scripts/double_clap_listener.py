#!/usr/bin/env python3
"""
Double-clap → welcome routine; during lab session, listen for stand-down phrases (local Whisper).
Owns one microphone stream; clap mode vs phrase mode.
"""
from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import sys
import time
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import numpy as np

from jarvis_phrase import phrase_matches


def _import_sounddevice():
    try:
        import sounddevice as sd
    except ImportError as e:
        print("Install sounddevice: pip install sounddevice", file=sys.stderr)
        raise SystemExit(1) from e
    return sd


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _expand_state_dir(cfg: dict) -> Path:
    p = Path(os.path.expanduser(cfg.get("state_dir", "~/.jarvis")))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _session_path(cfg: dict) -> Path:
    return _expand_state_dir(cfg) / "lab_session.json"


def _lab_active(cfg: dict) -> bool:
    sp = _session_path(cfg)
    if not sp.is_file():
        return False
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
        return bool(data.get("active"))
    except json.JSONDecodeError:
        return False


def _session_started(cfg: dict) -> float | None:
    sp = _session_path(cfg)
    if not sp.is_file():
        return None
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
        return float(data.get("started", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _rms(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(x), dtype=np.float64)))


def _spectral_flatness_db(block: np.ndarray) -> float:
    """Spectral flatness in dB. Claps score near 0 dB (broadband); speech/music score < -15 dB."""
    mags = np.abs(np.fft.rfft(block))
    power = mags ** 2 + 1e-12
    geom = float(np.exp(float(np.mean(np.log(power)))))
    arith = float(np.mean(power))
    return float(10.0 * np.log10(geom / arith + 1e-300))


def run_welcome(cfg_path: Path) -> bool:
    """Use the wrapper so welcome always prefers the repo venv/runtime."""
    env = os.environ.copy()
    env["JARVIS_CONFIG"] = str(cfg_path)
    root = _root()
    script = Path(__file__).resolve().parent / "jarvis_welcome.sh"
    print(
        f"[runtime] welcome wrapper={script} config={cfg_path} listener_python={sys.executable}",
        flush=True,
    )
    r = subprocess.run(
        [str(script)],
        env=env,
        cwd=str(root),
    )
    if r.returncode != 0:
        print(f"Welcome script failed ({r.returncode})", file=sys.stderr, flush=True)
    return r.returncode == 0


def run_stand_down(cfg_path: Path) -> None:
    env = os.environ.copy()
    env["JARVIS_CONFIG"] = str(cfg_path)
    root = _root()
    script = Path(__file__).resolve().parent / "jarvis_stand_down.sh"
    print(
        f"[runtime] stand-down wrapper={script} config={cfg_path} listener_python={sys.executable}",
        flush=True,
    )
    r = subprocess.run(
        [str(script)],
        env=env,
        cwd=str(root),
    )
    if r.returncode != 0:
        print(f"Stand-down script failed ({r.returncode})", file=sys.stderr, flush=True)


class ClapDetector:
    """Two transients: first onset, dip below hysteresis, second onset within gap window."""

    def __init__(self, cfg: dict) -> None:
        c = cfg.get("clap", {})
        self.sr = int(c.get("sample_rate", 16000))
        self.block_ms = float(c.get("block_ms", 25))
        self.block_samples = max(1, int(self.sr * self.block_ms / 1000.0))
        self.peak_threshold = float(c.get("peak_threshold", 0.35))
        self.hysteresis = float(c.get("hysteresis", 0.5))  # fraction of threshold for "quiet"
        self.min_gap = float(c.get("min_clap_gap_ms", 200)) / 1000.0
        self.max_gap = float(c.get("max_clap_gap_ms", 650)) / 1000.0
        self.cooldown = float(c.get("cooldown_seconds", 50))
        self.min_flatness_db = float(c.get("min_spectral_flatness_db", -12.0))
        self.max_onset_duration = float(c.get("max_onset_duration_ms", 120.0)) / 1000.0
        self._last_fire = 0.0
        self._prev_peak = 0.0
        self._first_onset: float | None = None
        self._saw_quiet_after_first = False
        self._last_flatness_db = 0.0

    def reset_arm(self) -> None:
        self._first_onset = None
        self._saw_quiet_after_first = False
        self._prev_peak = 0.0

    def clear_cooldown(self) -> None:
        """Allow another double-clap immediately (e.g. welcome subprocess failed)."""
        self._last_fire = 0.0

    def _is_clap_shaped(self, block_mono: np.ndarray) -> bool:
        """Return True if the block looks like a broadband transient (clap), not speech/music/hum."""
        self._last_flatness_db = _spectral_flatness_db(block_mono)
        return self._last_flatness_db >= self.min_flatness_db

    def process_block(self, block_mono: np.ndarray, now: float) -> bool:
        peak = float(np.max(np.abs(block_mono)))
        low = self.peak_threshold * self.hysteresis
        crossed_up = self._prev_peak < self.peak_threshold and peak >= self.peak_threshold
        quiet_enough = peak < low
        self._prev_peak = peak

        if now - self._last_fire < self.cooldown:
            return False

        if self._first_onset is None:
            if crossed_up and self._is_clap_shaped(block_mono):
                self._first_onset = now
                self._saw_quiet_after_first = False
            return False

        if not self._saw_quiet_after_first:
            if quiet_enough:
                self._saw_quiet_after_first = True
            elif now - self._first_onset > self.max_onset_duration:
                # Sustained loud sound — not a clap; reset without re-arming
                self.reset_arm()
            elif now - self._first_onset > self.max_gap:
                self._first_onset = None
                if crossed_up and self._is_clap_shaped(block_mono):
                    self._first_onset = now
            return False

        if crossed_up and self._is_clap_shaped(block_mono):
            dt = now - self._first_onset
            self._first_onset = None
            self._saw_quiet_after_first = False
            self._prev_peak = peak
            if self.min_gap <= dt <= self.max_gap:
                self._last_fire = now
                return True
            self._first_onset = now
            return False

        if now - self._first_onset > self.max_gap:
            self.reset_arm()
            if crossed_up and self._is_clap_shaped(block_mono):
                self._first_onset = now
        return False


def _calibrate_clap_threshold(
    clap: ClapDetector,
    q: queue.Queue,
    cfg: dict,
) -> None:
    cal_sec = float(cfg.get("clap", {}).get("calibrate_seconds", 1.2))
    if cal_sec <= 0:
        return
    peaks: list[float] = []
    deadline = time.time() + cal_sec
    print(
        f"[clap] Calibrating ({cal_sec}s) — stay quiet so we learn background noise…",
        flush=True,
    )
    while time.time() < deadline:
        try:
            chunk = q.get(timeout=0.12)
            peaks.append(float(np.max(np.abs(chunk))))
        except queue.Empty:
            continue
    if not peaks:
        return
    if not bool(cfg.get("clap", {}).get("adaptive_calibration", True)):
        print(
            "[clap] adaptive_calibration is false — using peak_threshold from config (no noise adjust).",
            flush=True,
        )
        return
    arr = np.array(peaks, dtype=np.float64)
    p20 = float(np.percentile(arr, 20))
    p80 = float(np.percentile(arr, 80))
    p95 = float(np.percentile(arr, 95))
    span = max(p80 - p20, 0.002)
    # Use p95 (not p80) as the noise ceiling — more robust against a single transient noise spike
    # during the calibration window that would otherwise overshoot the threshold.
    adaptive = max(clap.peak_threshold, p20 + span * 3.0, p95 * 1.15)
    adaptive = min(adaptive, 0.48)
    if p80 < 1e-4:
        print(
            "[clap] WARNING: Input is nearly silent — allow Microphone for this Python in "
            "System Settings (same binary as the listener / .venv/bin/python3).",
            flush=True,
        )
        if not cfg.get("clap", {}).get("input_device"):
            print(
                "[clap] AirPods/Bluetooth often give silence for background apps. "
                "System Settings → Sound → Input → choose your MacBook mic, or set "
                "clap.input_device in jarvis.json (see scripts/list_audio_devices.py).",
                flush=True,
            )
    orig_t = cfg.get("clap", {}).get("peak_threshold", 0.12)
    print(
        f"[clap] Noise band ~{p20:.3f}–{p80:.3f} (p95={p95:.3f}) → using peak_threshold={adaptive:.3f} "
        f"(config base {orig_t})",
        flush=True,
    )
    clap.peak_threshold = adaptive


def _parse_argv() -> tuple[Path, bool] | None:
    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        print(
            "Usage: double_clap_listener.py [--watch|-w] [config/jarvis.json]\n\n"
            "  --watch, -w  Restart automatically when jarvis.json or scripts/*.py change.\n"
            "  JARVIS_CONFIG env sets default config path.\n",
            file=sys.stdout,
        )
        return None
    root = _root()
    default_cfg = Path(os.environ.get("JARVIS_CONFIG", root / "config" / "jarvis.json")).resolve()
    watch = False
    cfg_path: Path | None = None
    for a in sys.argv[1:]:
        if a in ("--watch", "-w"):
            watch = True
        elif not a.startswith("-"):
            cfg_path = Path(a).expanduser().resolve()
    if cfg_path is None:
        cfg_path = default_cfg
    return cfg_path, watch


def _scripts_mtime_map(scripts_dir: Path) -> dict[str, float]:
    m: dict[str, float] = {}
    for p in scripts_dir.glob("*.py"):
        try:
            m[str(p.resolve())] = p.stat().st_mtime
        except OSError:
            pass
    return m


def run_watch(cfg_path: Path) -> int:
    """Restart the listener when jarvis.json or scripts/*.py change."""
    if not cfg_path.is_file():
        print(f"Missing config: {cfg_path}", file=sys.stderr)
        return 1
    listener_py = Path(__file__).resolve()
    scripts_dir = listener_py.parent
    root = _root()
    print(
        "[watch] Auto-restart when config or scripts change. Ctrl+C stops.\n",
        flush=True,
    )
    while True:
        env = os.environ.copy()
        env["JARVIS_CONFIG"] = str(cfg_path)
        cmd = [sys.executable, str(listener_py), str(cfg_path)]
        proc = subprocess.Popen(cmd, env=env, cwd=str(root))
        snap_cfg = cfg_path.stat().st_mtime if cfg_path.is_file() else 0.0
        snap_scripts = _scripts_mtime_map(scripts_dir)
        restart_for_reload = False
        try:
            while proc.poll() is None:
                time.sleep(0.45)
                if cfg_path.is_file() and cfg_path.stat().st_mtime != snap_cfg:
                    print("\n[watch] Config changed — restarting listener…\n", flush=True)
                    restart_for_reload = True
                    proc.send_signal(signal.SIGINT)
                    break
                new_map = _scripts_mtime_map(scripts_dir)
                if new_map != snap_scripts:
                    print("\n[watch] Scripts changed — restarting listener…\n", flush=True)
                    restart_for_reload = True
                    proc.send_signal(signal.SIGINT)
                    break
        except KeyboardInterrupt:
            print("\n[watch] Stopping…", flush=True)
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            return 0
        try:
            rc = proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = proc.wait()
        if not restart_for_reload:
            if rc in (0, 130, 2) or (rc is not None and rc < 0):
                return 0
            print(f"[watch] Listener exited ({rc}); restarting in 1.5s…", flush=True)
            time.sleep(1.5)


def _validate_input_device(sd, idx: int | None) -> int | None:
    """Drop invalid indices (wrong device after OS update, Bluetooth reordering, etc.)."""
    if idx is None:
        return None
    try:
        d = sd.query_devices(idx)
        if int(d.get("max_input_channels", 0)) < 1:
            print(
                f"[clap] input_device index {idx} is not a microphone — using system default. "
                "Set clap.input_device to null or run scripts/list_audio_devices.py",
                flush=True,
            )
            return None
    except Exception as e:
        print(f"[clap] input_device {idx} invalid ({e}) — using default.", flush=True)
        return None
    return idx


def _resolve_input_device(cfg: dict, sd) -> int | None:
    """Optional clap.input_device: int index or substring of device name (case-insensitive)."""
    raw = cfg.get("clap", {}).get("input_device")
    if raw is None or raw == "":
        return None
    if raw is True or raw is False:
        return None
    if isinstance(raw, int):
        return int(raw)
    if isinstance(raw, float):
        return int(raw)
    needle = str(raw).strip().lower()
    for i, d in enumerate(sd.query_devices()):
        try:
            if int(d.get("max_input_channels", 0)) < 1:
                continue
            if needle in d["name"].lower():
                return i
        except (KeyError, TypeError, ValueError):
            continue
    print(
        f"[clap] input_device {raw!r} not found — using system default. "
        "Run: python3 scripts/list_audio_devices.py",
        flush=True,
    )
    return None


def _print_audio_diagnostics(cfg: dict, sd, input_index: int | None) -> None:
    if _lab_active(cfg):
        sp = _session_path(cfg)
        print(
            "\n*** Lab session is already ACTIVE — double-clap will NOT run welcome again. ***\n"
            "    Say your stand-down phrase, or run: ./scripts/jarvis_stand_down.sh\n"
            f"    Or clear: rm {sp}\n",
            flush=True,
        )
    try:
        idx = input_index if input_index is not None else sd.default.device[0]
        d = sd.query_devices(idx)
        print(f"Using microphone: {d['name']!r} (index {idx})", flush=True)
    except Exception as e:
        print(f"Could not query input device: {e}", flush=True)


def _sync_black_lab_wallpaper(cfg: dict, state_dir: Path) -> None:
    hw = cfg.get("holographic_wallpaper", {})
    if not hw.get("enabled", False):
        return
    if not _lab_active(cfg):
        return
    try:
        from jarvis_holographic_wallpaper import apply_black_wallpaper

        apply_black_wallpaper(cfg, state_dir)
    except Exception as e:
        print(f"Warning: could not sync black lab wallpaper: {e}", file=sys.stderr, flush=True)


def run_listener(cfg_path: Path) -> int:
    if not cfg_path.is_file():
        print(f"Missing config: {cfg_path}", file=sys.stderr)
        return 1

    sd = _import_sounddevice()
    cfg = _load_config(cfg_path)
    state_dir = _expand_state_dir(cfg)
    state_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"[runtime] listener python={sys.executable} prefix={sys.prefix} config={cfg_path}",
        flush=True,
    )
    _sync_black_lab_wallpaper(cfg, state_dir)

    clap = ClapDetector(cfg)
    clap_debug = bool(cfg.get("clap", {}).get("debug", False))
    _last_debug_t = [0.0]

    phrase_cfg = cfg.get("phrase", {})
    chunk_sec = float(phrase_cfg.get("chunk_seconds", 4.0))
    overlap_sec = float(phrase_cfg.get("overlap_seconds", 1.25))
    min_rms = float(phrase_cfg.get("min_rms", 0.004))
    phrase_vad = bool(phrase_cfg.get("vad_filter", False))
    phrase_debug = bool(phrase_cfg.get("debug", False))
    phrase_fuzzy = float(phrase_cfg.get("fuzzy_ratio", 0.62))
    phrases = [str(p) for p in cfg.get("stand_down_phrases", ["stand down jarvis"])]
    wake_phrases = [str(p) for p in cfg.get("wake_phrases", [])]
    max_lab_min = float(cfg.get("lab_session_max_minutes", 240))

    sr = clap.sr
    block = clap.block_samples
    q: queue.Queue[np.ndarray] = queue.Queue(maxsize=512)

    input_dev = _validate_input_device(sd, _resolve_input_device(cfg, sd))

    _lab_clap_warn_t = [0.0]

    def audio_cb(indata, frames, t, status) -> None:  # type: ignore[no-untyped-def]
        if status:
            pass
        mono = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
        try:
            q.put_nowait(mono)
        except queue.Full:
            pass

    stream_kw: dict = dict(
        samplerate=sr,
        channels=1,
        dtype="float32",
        blocksize=block,
        callback=audio_cb,
    )
    if input_dev is not None:
        stream_kw["device"] = input_dev
    stream = sd.InputStream(**stream_kw)
    stream.start()

    whisper_model = None
    _print_audio_diagnostics(cfg, sd, input_dev)
    try:
        idx = input_dev if input_dev is not None else sd.default.device[0]
        dname = sd.query_devices(idx)["name"]
        print(f"JARVIS // MIC ONLINE // {dname!r} (index {idx})\n", flush=True)
    except Exception:
        print("JARVIS // MIC ONLINE // (device unknown)\n", flush=True)
    wake_hint = f" Or say: {wake_phrases!r}." if wake_phrases else ""
    print(
        f"Jarvis clap listener running. Clap twice (sharp, ~0.2–0.7s apart) for welcome.{wake_hint} Ctrl+C to exit.\n"
        "Tip: set clap.debug to true in jarvis.json to print peak levels while tuning.\n",
        flush=True,
    )

    _calibrate_clap_threshold(clap, q, cfg)

    phrase_buf: list[np.ndarray] = []
    phrase_t0 = 0.0
    wake_buf: list[np.ndarray] = []

    try:
        while True:
            lab = _lab_active(cfg)
            if not lab:
                phrase_buf.clear()
                # Keep whisper_model alive if wake phrase detection is configured;
                # free it only when no phrases need it in clap mode.
                if not wake_phrases:
                    whisper_model = None
            if lab and whisper_model is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError:
                    print(
                        "Lab session active but faster-whisper is not installed. "
                        "pip install faster-whisper",
                        file=sys.stderr,
                    )
                    time.sleep(5)
                    continue
                wmodel = phrase_cfg.get("whisper_model", "tiny.en")
                ctype = phrase_cfg.get("compute_type", "int8")
                print(f"Loading Whisper model {wmodel!r}…", flush=True)
                whisper_model = WhisperModel(wmodel, device="cpu", compute_type=ctype)
                print(
                    f"[phrase] Stand-down: say one of {phrases!r} "
                    f"(~{chunk_sec}s chunks, {overlap_sec}s overlap; phrase.debug=true for details)",
                    flush=True,
                )

            if lab:
                started = _session_started(cfg)
                if started and max_lab_min > 0:
                    if (time.time() - started) / 60.0 > max_lab_min:
                        print("Lab session max duration exceeded; standing down.", flush=True)
                        run_stand_down(cfg_path)
                        whisper_model = None
                        phrase_buf.clear()
                        continue

                try:
                    chunk = q.get(timeout=0.2)
                except queue.Empty:
                    continue
                phrase_buf.append(chunk)
                total = sum(len(x) for x in phrase_buf)
                if total < int(chunk_sec * sr):
                    continue

                audio = np.concatenate(phrase_buf, axis=0)
                phrase_buf.clear()
                rms_a = _rms(audio)
                if rms_a < min_rms:
                    if phrase_debug:
                        print(f"[phrase] skip low rms={rms_a:.5f} < {min_rms}", flush=True)
                    continue

                segments, _ = whisper_model.transcribe(  # type: ignore[union-attr]
                    audio.astype(np.float32),
                    beam_size=1,
                    language="en",
                    vad_filter=phrase_vad,
                )
                # Join with spaces — "".join() can glue words ("Stand"+"down" → "Standdown")
                parts = [(s.text or "").strip() for s in segments]
                parts = [p for p in parts if p]
                text = " ".join(parts).strip()
                if text:
                    print(f"Heard: {text!r}", flush=True)
                elif phrase_debug:
                    print("[phrase] Whisper returned empty text for this chunk", flush=True)

                ovl = int(max(0.0, overlap_sec) * sr)
                if ovl > 0 and len(audio) > ovl:
                    phrase_buf.append(audio[-ovl:].copy())

                if phrase_matches(text, phrases, fuzzy_ratio=phrase_fuzzy):
                    print("Stand-down phrase detected.", flush=True)
                    run_stand_down(cfg_path)
                    whisper_model = None
                    phrase_buf.clear()
                continue

            # Clap mode
            try:
                chunk = q.get(timeout=0.15)
            except queue.Empty:
                continue
            now = time.time()
            if clap_debug:
                pk = float(np.max(np.abs(chunk)))
                if pk > 0.04 and now - _last_debug_t[0] > 0.25:
                    _last_debug_t[0] = now
                    flat = _spectral_flatness_db(chunk)
                    broadband = "broadband" if flat >= clap.min_flatness_db else "NOT broadband"
                    print(
                        f"[clap debug] peak={pk:.3f} (threshold={clap.peak_threshold:.3f}) "
                        f"flatness={flat:.1f}dB ({broadband}, min={clap.min_flatness_db:.0f}dB)",
                        flush=True,
                    )
            if clap.process_block(chunk, now):
                if _lab_active(cfg):
                    clap.reset_arm()
                    if now - _lab_clap_warn_t[0] > 25.0:
                        _lab_clap_warn_t[0] = now
                        sp = _session_path(cfg)
                        print(
                            "\n[clap] Double-clap ignored — lab session already ACTIVE (welcome already ran). "
                            "Say your stand-down phrase, run ./scripts/jarvis_stand_down.sh, or use the HUD.\n"
                            f"        Clear session file if stuck: rm {sp}\n",
                            flush=True,
                        )
                    continue
                print("Double-clap detected → welcome routine.", flush=True)
                if run_welcome(cfg_path):
                    phrase_buf.clear()
                    wake_buf.clear()
                    clap.reset_arm()
                else:
                    print("Welcome script failed.", file=sys.stderr)
                    clap.clear_cooldown()
                    clap.reset_arm()
                continue

            # Wake phrase detection (runs in clap mode when wake_phrases are configured)
            if wake_phrases:
                wake_buf.append(chunk)
                if sum(len(x) for x in wake_buf) >= int(chunk_sec * sr):
                    wake_audio = np.concatenate(wake_buf, axis=0)
                    wake_buf.clear()
                    ovl = int(max(0.0, overlap_sec) * sr)
                    if ovl > 0 and len(wake_audio) > ovl:
                        wake_buf.append(wake_audio[-ovl:].copy())

                    if _rms(wake_audio) >= min_rms:
                        if whisper_model is None:
                            try:
                                from faster_whisper import WhisperModel
                            except ImportError:
                                print(
                                    "wake_phrases configured but faster-whisper not installed. "
                                    "pip install faster-whisper",
                                    file=sys.stderr,
                                )
                                wake_phrases.clear()
                                continue
                            wmodel = phrase_cfg.get("whisper_model", "tiny.en")
                            ctype = phrase_cfg.get("compute_type", "int8")
                            print(f"Loading Whisper {wmodel!r} for wake phrase detection…", flush=True)
                            whisper_model = WhisperModel(wmodel, device="cpu", compute_type=ctype)

                        segments, _ = whisper_model.transcribe(  # type: ignore[union-attr]
                            wake_audio.astype(np.float32),
                            beam_size=1,
                            language="en",
                            vad_filter=phrase_vad,
                        )
                        parts = [(s.text or "").strip() for s in segments]
                        text = " ".join(p for p in parts if p).strip()
                        if phrase_debug and text:
                            print(f"[wake] Heard: {text!r}", flush=True)

                        if phrase_matches(text, wake_phrases, fuzzy_ratio=phrase_fuzzy):
                            print("Wake phrase detected → welcome routine.", flush=True)
                            if run_welcome(cfg_path):
                                wake_buf.clear()
                                clap.reset_arm()
                            else:
                                print("Welcome script failed.", file=sys.stderr)
                                clap.clear_cooldown()
                                clap.reset_arm()
    except KeyboardInterrupt:
        print("Exiting.", flush=True)
    finally:
        stream.stop()
        stream.close()

    return 0


def main() -> int:
    parsed = _parse_argv()
    if parsed is None:
        return 0
    cfg_path, watch = parsed
    if watch:
        return run_watch(cfg_path)
    return run_listener(cfg_path)


if __name__ == "__main__":
    raise SystemExit(main())
