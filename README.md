# Extempore AI Coach

An AI-powered public speaking trainer that generates random extempore topics, transcribes
your spoken response, and scores you on speaking pace, filler words, pauses, and overall
confidence. Built to help students practice for placement interviews.

## What's included

1. **`extempore_coach.html`** — a self-contained, multi-page web app (topic page →
   recording page → feedback page). Uses the browser's Web Speech API for live
   transcription. No installation needed — but it must be served over `https://` or
   `http://localhost` for the microphone to work (browsers block mic access on files
   opened directly, e.g. `file:///C:/...`).

2. **`extempore_coach.py`** — a Python command-line version for local/offline use,
   using `speech_recognition` for transcription and `pydub` for pause detection. Runs
   entirely in a terminal — no browser involved.

3. **`README.md`** — this file.

Both versions cover the same core features: random topic generation, speech-to-text,
filler word detection, speaking speed (WPM) analysis, pause detection, and a composite
confidence score with actionable feedback.

## Running the web app (`extempore_coach.html`)

You cannot just double-click the file — opening it as `file://...` blocks microphone
access in most browsers. Serve it locally instead:

```bash
# In the folder containing extempore_coach.html:
python -m http.server 8000
```

Then open in Chrome or Edge:
```
http://localhost:8000/extempore_coach.html
```

Leave the terminal window running while you use the app; press `Ctrl+C` to stop it
when you're done.

Alternatively, host it for free via **GitHub Pages**: push this repo to GitHub, go to
**Settings → Pages**, choose "Deploy from a branch" → `main` → `/ (root)` → Save. After
a minute it's live at `https://YOUR_USERNAME.github.io/REPO_NAME/extempore_coach.html`.

### Using the app
1. Click "New topic" for a random prompt, then "Start speaking →".
2. Click the mic and speak for 60–90 seconds. Allow the microphone permission prompt
   if your browser shows one.
3. Click the mic again to stop, then "View feedback →" to see your scorecard.

## Running the Python version (`extempore_coach.py`)

### Install dependencies (one-time)
```bash
pip install SpeechRecognition pydub pyaudio nltk
```

You also need **ffmpeg** on your PATH (used by `pydub` for audio decoding):
- Windows: `winget install ffmpeg`, or download from ffmpeg.org and add it to PATH
- macOS: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

### Run it
```bash
# Record live from your microphone
python extempore_coach.py

# Or analyze an existing WAV recording
python extempore_coach.py --file myrecording.wav
```

This prints your topic, records from your mic, transcribes it, and prints a full
scorecard (confidence score, filler word breakdown, pace, pauses, transcript) directly
in the terminal.

Note: transcription uses Google's free Speech-to-Text web API via `speech_recognition`,
so an internet connection is required even for the Python version.

## How scoring works

- **Pace**: ideal range is 110–160 words per minute; score drops the further you are
  from that band.
- **Filler words**: detects "um", "uh", "like", "basically", "actually", "so", "you
  know", and similar — scored as a percentage of total words.
- **Pauses**: silences longer than ~1.2–1.8 seconds count as hesitations; more than
  one or two start to hurt the score.
- **Confidence score**: a weighted blend of the three above (35% pace, 35% fillers,
  30% pauses), scaled down for very short responses so a 5-second answer can't score
  artificially high.

## Possible extensions

- Swap the rule-based feedback for an LLM call (e.g. via the Anthropic API) to give
  richer, topic-aware coaching on argument structure and content, not just delivery.
- Track scores over multiple sessions to show improvement trends.
- Add a "model answer" structure suggestion (intro – 2 points – conclusion) before
  each topic.

