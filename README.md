# Captioner

Intelligent subtitle synchronization orchestrator.

## Overview

Captioner automatically synchronizes subtitle files (.srt) with video files by correcting subtitle timing without altering subtitle text. It orchestrates proven open-source synchronization engines (primarily ffsubsync) with enhanced confidence reporting and production-grade error handling.

## Features

- **Language-agnostic**: Works with any subtitle language (e.g., Chinese subtitles with English audio)
- **Multiple sync types**: Handles constant offset, linear drift, and discontinuities
- **Confidence reporting**: Flags low-confidence synchronizations for manual review
- **Fast processing**: Typical movie sync in 20-30 seconds
- **Clean CLI**: Simple command-line interface with progress reporting

## Installation

### Prerequisites

- Python 3.9+
- FFmpeg (required by ffsubsync)
- VLC (for testing/verification)

```bash
# Install FFmpeg (macOS)
brew install ffmpeg

# Install VLC (macOS)
brew install --cask vlc
```

### Install Captioner

```bash
# Clone repository
git clone https://github.com/yourusername/captioner.git
cd captioner

# Install in development mode
pip install -e .
```

## Usage

### Basic Synchronization

```bash
captioner sync video.mp4 -i subtitles.srt -o subtitles.synced.srt
```

### With Confidence Report

```bash
captioner sync video.mp4 -i subtitles.srt -o subtitles.synced.srt --report report.json
```

### Testing Results with VLC

```bash
# View with synchronized subtitles
vlc video.mp4 --sub-file=subtitles.synced.srt

# Compare with original
vlc video.mp4 --sub-file=subtitles.srt
```

### Options

- `--max-offset-seconds`: Maximum offset to search in seconds (default: 300)
- `--vad`: Voice activity detection method (webrtc, subs_then_webrtc, silero)
- `--confidence-threshold`: Confidence threshold for manual review flag (default: 0.7)
- `--verbose`: Enable verbose logging
- `--no-progress`: Disable progress bar

## Architecture

Captioner orchestrates existing subtitle synchronization engines:

- **Primary**: ffsubsync (FFT-based alignment, handles 80% of cases)
- **Future**: alass (via FFI for discontinuities)
- **Future**: anchor-sub-sync (optional GPU acceleration for cross-language)

The value add is in:
- Intelligent engine selection and fallback chains
- Enhanced confidence reporting
- Production-grade logging and error handling
- Clean Python API for automation

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black captioner/

# Type check
mypy captioner/
```

## License

MIT
