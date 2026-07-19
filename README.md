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

### Download and Sync Subtitles (default)

```bash
# Download and sync with config file language preferences
captioner video.mp4

# Download specific languages (overrides config)
captioner video.mp4 -l zho eng

# Force download even if subtitle exists
captioner video.mp4 --force

# Process all MP4 files in a directory (skips existing subtitles unless --force)
captioner /path/to/movies/
```

**Note:** When multiple languages are requested (either via config or `-l`), all available languages are downloaded and synced separately. This is automatic - no flag needed. Missing languages are shown in yellow; errors in red.

### Sync Existing Subtitle

```bash
# Sync existing subtitle to video
captioner video.mp4 -i subtitles.srt

# Specify output file
captioner video.mp4 -i subtitles.srt -o synced.srt

# Generate confidence report
captioner video.mp4 -i subtitles.srt --report report.json
```

### Configuration

Create a config file at `~/.config/captioner/config.json`:

```json
{
  "languages": ["zho"],
  "download_multiple": false,
  "min_score": 0,
  "max_offset_seconds": 300,
  "vad": "subs_then_webrtc",
  "confidence_threshold": 0.7,
  "providers": null
}
```

**Config options:**
- `languages`: Language codes in priority order (e.g., `["zho", "eng"]`)
- `download_multiple`: Download all requested languages instead of just best match
- `min_score`: Minimum subtitle score (0-100)
- `max_offset_seconds`: Maximum offset to search in seconds
- `vad`: Voice activity detection method (webrtc, subs_then_webrtc, silero)
- `confidence_threshold`: Confidence threshold for manual review flag
- `providers`: Subtitle providers to use (null for all)

**Language codes:**
- `zho-hans`: Chinese Simplified
- `zho-hant`: Chinese Traditional
- `zho`: Chinese (includes both simplified and traditional)
- `eng`: English
- `jpn`: Japanese
- `kor`: Korean
- See [IETF language tags](https://en.wikipedia.org/wiki/IETF_language_tag)

**Chinese captions on English movies:**
Subliminal works best with OpenSubtitles (`opensubtitles`, `opensubtitlescom`) for Chinese subtitles. Other supported providers include `podnapisi`, `tvsubtitles`, and `addic7ed`. Set your preferred providers in `~/.config/captioner/config.json` to avoid DNS failures from unreachable sites.

For better Chinese coverage, use `ChineseSubFinder` to bulk-download Chinese subtitles first, then run `captioner` to sync them (see [Workflow with ChineseSubFinder](#workflow-with-chinesesubfinder)).

**Plex/Roku compatibility:**
Subtitles are saved with language codes (e.g., `movie.zh.srt`, `movie.en.srt`) for proper Plex recognition. When multiple languages are requested, each is synced separately as they may come from different sources with different timing.

**Synced-subtitle markers:**
`captioner` writes a sidecar marker file next to each synced subtitle (e.g., `movie.zh.srt.synced`). This lets `captioner` know which subtitles have already been processed so it won't re-sync them on repeated directory runs. Use `--force` to override and re-sync.

### Workflow with ChineseSubFinder

For hard-to-find Chinese subtitles, download them with `ChineseSubFinder` first, then run `captioner` to sync the downloaded files.

#### Install ChineseSubFinder

`ChineseSubFinder` is a Go application. Official releases provide Linux and Windows binaries only; macOS requires Docker or building from source.

**Linux / Windows:**
```bash
# Download the latest release from:
# https://github.com/ChineseSubFinder/ChineseSubFinder/releases
tar -xzf chinesesubfinder_<platform>_<version>.tar.gz
mv chinesesubfinder /usr/local/bin/
```

**macOS:**
```bash
# Option 1: Docker (recommended)
docker pull allanpk716/chinesesubfinder:latest-lite

# Option 2: Build from source (requires Go)
git clone https://github.com/ChineseSubFinder/ChineseSubFinder.git
cd ChineseSubFinder/cmd/chinesesubfinder
go build -o chinesesubfinder
mv chinesesubfinder /usr/local/bin/
```

#### Download Chinese subtitles

```bash
# Run ChineseSubFinder over your movie folder
chinesesubfinder -setconfigselfpath /path/to/config -litemode true
```

`ChineseSubFinder` will download subtitles with names like `movie.chs.srt` or `movie.cht.srt`.

#### Sync them with captioner

```bash
# captioner will sync any pre-existing .srt/.ass/.ssa it finds and add a .srt.synced marker
captioner /path/to/movies/
```

Directory mode now syncs pre-existing subtitle files that haven't been processed yet, in addition to downloading new ones. Existing subtitles with a `.srt.synced` marker are skipped unless `--force` is used.

### Testing Results with VLC

```bash
# View with synchronized subtitles
vlc video.mp4 --sub-file=subtitles.synced.srt

# Compare with original
vlc video.mp4 --sub-file=subtitles.srt
```

### Options

- `-i, --input`: Input subtitle file (if not provided, will download)
- `-o, --output`: Output subtitle file
- `-l, --languages`: Language codes for download (e.g., zho eng)
- `-p, --providers`: Subtitle providers (opensubtitles, opensubtitlescom, podnapisi, tvsubtitles, addic7ed)
- `-f, --force`: Force download even if subtitle exists
- `--config`: Path to config file (default: ~/.config/captioner/config.json)
- `--max-offset-seconds`: Maximum offset to search (default: 300)
- `--vad`: Voice activity detection method (webrtc, subs_then_webrtc, silero)
- `--confidence-threshold`: Confidence threshold for manual review (default: 0.7)
- `--report`: Path to save JSON report
- `--verbose`: Enable verbose logging
- `--debug`: Enable debug output (shows progress bars and detailed info)
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
