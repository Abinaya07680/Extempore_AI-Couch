"""
Extempore AI Coach — Python backend version
=============================================
Records (or accepts) a speech sample, transcribes it, and scores the speaker on
filler-word usage, speaking pace, pauses, and an overall confidence score.

Install dependencies:
    pip install SpeechRecognition pydub pyaudio nltk

You also need ffmpeg installed and on PATH (pydub uses it for audio decoding):
    Windows : https://ffmpeg.org/download.html  (add to PATH)
    macOS   : brew install ffmpeg
    Linux   : sudo apt install ffmpeg

Usage:
    python extempore_coach.py                 # live mic recording
    python extempore_coach.py --file myrecording.wav   # analyze existing audio

"""

import argparse
import random
import re
import sys
import time
import wave
from dataclasses import dataclass, field

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    from pydub import AudioSegment
    from pydub.silence import detect_silence
except ImportError:
    AudioSegment = None
    detect_silence = None


# --------------------------------------------------------------------------
# Topics
# --------------------------------------------------------------------------

TOPICS = [
    "Should social media platforms be held responsible for misinformation?",
    "Is artificial intelligence a threat to job security?",
    "The role of failure in personal growth",
    "Should college education be free for everyone?",
    "Is work-from-home better than office culture?",
    "The impact of cricket on Indian youth culture",
    "Should exams be the only measure of a student's ability?",
    "Is social media doing more harm than good?",
    "The importance of soft skills in the workplace",
    "Should there be a four-day work week?",
    "Is online learning as effective as classroom learning?",
    "The ethics of using AI in hiring decisions",
    "Should plastic be banned completely in India?",
    "Is competition healthy for students?",
    "The future of electric vehicles in India",
    "Should government make voting mandatory?",
    "Is space exploration worth the cost?",
    "The effect of smartphones on family relationships",
    "Should startups prioritize growth over profitability?",
    "Is traditional banking becoming obsolete?",
]

FILLER_WORDS = [
    "um", "uh", "umm", "uhh", "like", "you know", "basically", "actually",
    "so", "i mean", "kind of", "sort of", "literally", "right", "okay so",
]

IDEAL_WPM_LOW = 110
IDEAL_WPM_HIGH = 160
PAUSE_THRESHOLD_MS = 1200   # silence longer than this counts as a "pause"
MIN_SILENCE_LEN_MS = 700    # minimum gap pydub should even consider


@dataclass
class SpeechReport:
    topic: str
    transcript: str
    duration_sec: float
    word_count: int
    wpm: int
    filler_count: int
    filler_breakdown: dict
    pause_count: int
    pause_total_sec: float
    confidence_score: int
    feedback: list = field(default_factory=list)

    def pretty_print(self):
        bar_len = 30
        filled = int(self.confidence_score / 100 * bar_len)
        bar = "#" * filled + "-" * (bar_len - filled)

        print("\n" + "=" * 60)
        print("  EXTEMPORE AI COACH — SCORECARD")
        print("=" * 60)
        print(f"Topic: {self.topic}")
        print(f"Duration: {self.duration_sec:.1f}s | Words: {self.word_count}")
        print("-" * 60)
        print(f"Speaking speed : {self.wpm} wpm "
              f"({'ideal' if IDEAL_WPM_LOW <= self.wpm <= IDEAL_WPM_HIGH else 'needs work'})")
        print(f"Filler words   : {self.filler_count} "
              f"({', '.join(f'{k}x{v}' for k, v in self.filler_breakdown.items()) or 'none'})")
        print(f"Pauses         : {self.pause_count} (total {self.pause_total_sec:.1f}s silence)")
        print("-" * 60)
        print(f"Confidence score: {self.confidence_score}/100")
        print(f"[{bar}]")
        print("-" * 60)
        print("Feedback:")
        for f in self.feedback:
            print(f"  - {f}")
        print("=" * 60)
        print(f"\nFull transcript:\n  \"{self.transcript}\"\n")


def pick_topic() -> str:
    return random.choice(TOPICS)


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------

def record_from_mic(out_path: str = "recording.wav", max_seconds: int = 120) -> str:
    """Record audio from the default microphone until silence or max_seconds."""
    if sr is None:
        raise RuntimeError("speech_recognition not installed. Run: pip install SpeechRecognition pyaudio")

    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 2.0  # seconds of silence that ends recording

    with sr.Microphone() as source:
        print("Calibrating for ambient noise... please stay quiet for a moment.")
        recognizer.adjust_for_ambient_noise(source, duration=1.5)
        print("\nSpeak now! Recording will stop automatically after a long pause,")
        print(f"or automatically cut off after {max_seconds} seconds.\n")
        print(">>> START SPEAKING <<<")
        audio = recognizer.listen(source, timeout=10, phrase_time_limit=max_seconds)
        print(">>> RECORDING STOPPED <<<\n")

    with open(out_path, "wb") as f:
        f.write(audio.get_wav_data())

    return out_path


# --------------------------------------------------------------------------
# Transcription
# --------------------------------------------------------------------------

def transcribe(audio_path: str) -> str:
    if sr is None:
        raise RuntimeError("speech_recognition not installed. Run: pip install SpeechRecognition")

    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        audio = recognizer.record(source)

    try:
        # Uses Google's free web speech API (requires internet connection)
        text = recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        text = ""
    except sr.RequestError as e:
        raise RuntimeError(f"Speech recognition service error: {e}")

    return text


# --------------------------------------------------------------------------
# Pause detection (via silence gaps in the raw audio)
# --------------------------------------------------------------------------

def get_audio_duration_sec(audio_path: str) -> float:
    with wave.open(audio_path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)


def detect_pauses(audio_path: str):
    """Returns (pause_count, total_pause_seconds) using silence detection."""
    if AudioSegment is None:
        # Fallback: no pydub/ffmpeg available, skip pause analysis
        return 0, 0.0

    audio = AudioSegment.from_wav(audio_path)
    silence_ranges = detect_silence(
        audio,
        min_silence_len=MIN_SILENCE_LEN_MS,
        silence_thresh=audio.dBFS - 16,
    )
    long_pauses = [(s, e) for s, e in silence_ranges if (e - s) >= PAUSE_THRESHOLD_MS]
    total_pause_ms = sum(e - s for s, e in long_pauses)
    return len(long_pauses), total_pause_ms / 1000.0


# --------------------------------------------------------------------------
# Filler word + pace analysis
# --------------------------------------------------------------------------

def count_fillers(transcript: str):
    lower = transcript.lower()
    total = 0
    breakdown = {}
    for filler in FILLER_WORDS:
        pattern = r"\b" + filler.replace(" ", r"\s+") + r"\b"
        matches = re.findall(pattern, lower)
        if matches:
            total += len(matches)
            breakdown[filler] = len(matches)
    return total, breakdown


def compute_confidence(wpm, word_count, filler_ratio, pause_count, duration_sec):
    # pace score: ideal 110-160 wpm
    if wpm == 0:
        pace_score = 0
    elif IDEAL_WPM_LOW <= wpm <= IDEAL_WPM_HIGH:
        pace_score = 100
    else:
        dist = (IDEAL_WPM_LOW - wpm) if wpm < IDEAL_WPM_LOW else (wpm - IDEAL_WPM_HIGH)
        pace_score = max(0, 100 - dist * 1.8)

    filler_score = max(0, 100 - filler_ratio * 100 * 6)

    pause_penalty = max(0, pause_count - 1) * 14
    pause_score = max(0, 100 - pause_penalty)

    length_factor = min(1.0, duration_sec / 30.0)  # ramps up to 30s
    raw = pace_score * 0.35 + filler_score * 0.35 + pause_score * 0.30
    confidence = round(raw * (0.5 + 0.5 * length_factor))
    return int(confidence)


def build_feedback(wpm, word_count, filler_count, filler_breakdown, pause_count, duration_sec):
    feedback = []

    if word_count == 0:
        feedback.append("No speech was detected. Check your microphone and try again.")
        return feedback

    if wpm < IDEAL_WPM_LOW:
        feedback.append(f"Your pace was {wpm} wpm — a little slow. Aim for "
                         f"{IDEAL_WPM_LOW}-{IDEAL_WPM_HIGH} wpm to sound more energetic.")
    elif wpm > IDEAL_WPM_HIGH:
        feedback.append(f"Your pace was {wpm} wpm — quite fast. Slow down slightly "
                         f"so your points land clearly.")
    else:
        feedback.append(f"Great pacing at {wpm} wpm — well within the ideal range.")

    if filler_count > 0:
        top = sorted(filler_breakdown.items(), key=lambda x: -x[1])[:3]
        top_str = ", ".join(f'"{w}" ({c}x)' for w, c in top)
        feedback.append(f"You used {filler_count} filler words, most often {top_str}. "
                         f"Try pausing silently instead of filling the gap.")
    else:
        feedback.append("No filler words detected — very clean delivery.")

    if pause_count > 3:
        feedback.append(f"You had {pause_count} long pauses. Practice a quick mental "
                         f"structure (intro, 2 points, conclusion) before you start speaking.")
    elif pause_count > 1:
        feedback.append("A couple of longer pauses crept in. A brief outline before "
                         "you begin can smooth this out.")
    else:
        feedback.append("Minimal hesitation — your thoughts flowed continuously.")

    if duration_sec < 20:
        feedback.append("Your response was quite short. Try to speak for at least "
                         "60 seconds to develop your point fully.")

    return feedback


# --------------------------------------------------------------------------
# Main analysis pipeline
# --------------------------------------------------------------------------

def analyze(audio_path: str, topic: str) -> SpeechReport:
    duration_sec = get_audio_duration_sec(audio_path)
    transcript = transcribe(audio_path)

    words = transcript.strip().split()
    word_count = len(words)
    duration_min = max(duration_sec / 60.0, 0.01)
    wpm = round(word_count / duration_min) if word_count else 0

    filler_count, filler_breakdown = count_fillers(transcript)
    filler_ratio = (filler_count / word_count) if word_count else 0.0

    pause_count, pause_total_sec = detect_pauses(audio_path)

    confidence = compute_confidence(wpm, word_count, filler_ratio, pause_count, duration_sec)
    feedback = build_feedback(wpm, word_count, filler_count, filler_breakdown,
                               pause_count, duration_sec)

    return SpeechReport(
        topic=topic,
        transcript=transcript,
        duration_sec=duration_sec,
        word_count=word_count,
        wpm=wpm,
        filler_count=filler_count,
        filler_breakdown=filler_breakdown,
        pause_count=pause_count,
        pause_total_sec=pause_total_sec,
        confidence_score=confidence,
        feedback=feedback,
    )


def main():
    parser = argparse.ArgumentParser(description="Extempore AI Coach — speaking practice scorer")
    parser.add_argument("--file", type=str, default=None,
                         help="Path to an existing WAV file to analyze instead of recording live")
    parser.add_argument("--seconds", type=int, default=90,
                         help="Max recording duration in seconds (live mic mode only)")
    args = parser.parse_args()

    topic = pick_topic()
    print("\n" + "=" * 60)
    print("  EXTEMPORE AI COACH")
    print("=" * 60)
    print(f"\nYour topic:\n  \"{topic}\"\n")

    if args.file:
        audio_path = args.file
    else:
        input("Press Enter when you're ready to start recording...")
        audio_path = record_from_mic(max_seconds=args.seconds)

    print("Transcribing and analyzing... (requires internet for speech recognition)")
    report = analyze(audio_path, topic)
    report.pretty_print()


if __name__ == "__main__":
    main()
