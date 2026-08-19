# Groove Trainer

Practice musical groove and micro-timing with a sample-accurate drum loop and metronome.

## Install

```bash
pip install PyQt6 numpy sounddevice
```

## Run

```bash
python main.py
```

## What Changed

- **Sample-accurate audio engine** using a continuous `sounddevice.OutputStream` callback instead of one-shot playback calls
- **Procedural drum grid** with kick on `0, 4`, snare on `2, 6`, and closed hi-hat on every eighth-note slot `0-7`
- **Metronome subdivisions** switchable between quarter notes and eighth notes
- **Legendary bassist presets** grouped into behind, center, and ahead timing families
- **Manual micro-timing slider** from `-50 ms` (behind / delayed) to `+50 ms` (ahead / rushed)
- **Pitch and independent volume controls** for both the drum loop and metronome
