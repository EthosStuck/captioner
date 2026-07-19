"""Command-line interface for captioner."""

import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime

from .engines import FFSubsyncEngine
from .confidence import ConfidenceAnalyzer
from .report import ReportGenerator
from .downloader import SubtitleDownloader
from .config import Config


def _color(text: str, code: str) -> str:
    """Return text in color if stdout is a TTY."""
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text


def _green(text: str) -> str:
    """Return text in green color."""
    return _color(text, "32")


def _yellow(text: str) -> str:
    """Return text in yellow/orange color."""
    return _color(text, "33")


def _red(text: str) -> str:
    """Return text in red color."""
    return _color(text, "31")


def setup_logging(verbose: bool = False, debug: bool = False):
    """Configure logging based on verbosity."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.CRITICAL  # Suppress all logging in normal mode
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)]
    )
    
    # Suppress noisy third-party loggers in non-debug mode
    if not debug:
        logging.getLogger('subliminal').setLevel(logging.CRITICAL)
        logging.getLogger('ffsubsync').setLevel(logging.CRITICAL)
        logging.getLogger('urllib3').setLevel(logging.CRITICAL)
        logging.getLogger('requests').setLevel(logging.CRITICAL)
        logging.getLogger('captioner').setLevel(logging.CRITICAL)
        logging.getLogger('srt').setLevel(logging.CRITICAL)
        # Suppress tqdm progress bars by monkey-patching
        import tqdm
        class DummyTqdm:
            def __init__(self, *args, **kwargs):
                pass
            def __iter__(self):
                return iter([])
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def update(self, *args, **kwargs):
                pass
            def close(self):
                pass
        tqdm.tqdm = DummyTqdm


def progress_handler(info):
    """Progress callback for ffsubsync."""
    if info.fraction is not None:
        print(f"\rProgress: {info.fraction:.0%}", end="", file=sys.stderr)
    else:
        print(f"\rProcessed: {info.processed_seconds:.1f}s", end="", file=sys.stderr)


def _subtitle_exists(video_path: Path, language: str) -> bool:
    """Check if a subtitle file exists for a video and language."""
    return _find_existing_subtitle(video_path, language) is not None


def _find_existing_subtitle(video_path: Path, language: str) -> Optional[Path]:
    """Find the existing subtitle file for a video and language."""
    variants = {
        'eng': [f'.{language}.srt', '.en.srt', '.eng.srt'],
        'zho': [f'.{language}.srt', '.zh.srt', '.zho.srt', '.zho-Hans.srt', '.zho-Hant.srt',
                '.chs.srt', '.cht.srt', '.chs_en.srt', '.cht_en.srt'],
    }
    for variant in variants.get(language, [f'.{language}.srt']):
        sub_path = video_path.with_suffix(variant)
        if sub_path.exists():
            return sub_path
    return None


def _sync_marker_path(subtitle_path: Path) -> Path:
    """Path to the sidecar marker indicating a subtitle has been synced."""
    return subtitle_path.with_suffix('.srt.synced')


def _is_already_synced(subtitle_path: Path) -> bool:
    """Return True if the subtitle has already been synced by captioner."""
    return _sync_marker_path(subtitle_path).exists()


def _mark_as_synced(subtitle_path: Path):
    """Mark a subtitle file as having been synced by captioner."""
    marker = _sync_marker_path(subtitle_path)
    marker.write_text(f"synced_at={datetime.now().isoformat()}\n")


def _process_video(video_path: Path, languages: List[str], args, config, downloader, engine):
    """Download and sync missing subtitles for a single video."""
    show_progress = args.debug and not args.no_progress
    statuses = []
    
    for language in languages:
        existing_path = _find_existing_subtitle(video_path, language)
        
        # If a synced subtitle already exists, skip it unless force
        if existing_path and not args.force and _is_already_synced(existing_path):
            statuses.append((language, 'synced', existing_path))
            continue
        
        # If a pre-existing subtitle exists but is not synced, sync it in place
        if existing_path and (args.force or not _is_already_synced(existing_path)):
            from tempfile import mkstemp
            fd, temp_path = mkstemp(suffix='.srt', dir=str(existing_path.parent))
            os.close(fd)
            temp_output = Path(temp_path)
            
            try:
                result = engine.sync(
                    reference_path=video_path,
                    subtitle_path=existing_path,
                    output_path=temp_output,
                    progress_handler=progress_handler if show_progress else None,
                    max_offset_seconds=args.max_offset_seconds or config.max_offset_seconds,
                    vad=args.vad or config.vad,
                )
                
                if result.success:
                    # Remove old marker if present (it will be recreated below)
                    _sync_marker_path(existing_path).unlink(missing_ok=True)
                    temp_output.replace(existing_path)
                    _mark_as_synced(existing_path)
                    statuses.append((language, 'synced', existing_path))
                else:
                    temp_output.unlink(missing_ok=True)
                    statuses.append((language, 'sync_failed', existing_path))
            except Exception:
                temp_output.unlink(missing_ok=True)
                raise
            continue
        
        # Download subtitle for this language
        downloaded = downloader.download_subtitles(
            video_path=video_path,
            languages=[language],
            min_score=args.min_score or config.min_score,
            force=args.force,
            download_multiple=False,
        )
        
        if not downloaded:
            statuses.append((language, 'not_found', None))
            continue
        
        subtitle_path, lang_code = downloaded[0]
        output_path = video_path.with_suffix(f'.{lang_code}.srt')
        
        # Sync the downloaded subtitle
        result = engine.sync(
            reference_path=video_path,
            subtitle_path=subtitle_path,
            output_path=output_path,
            progress_handler=progress_handler if show_progress else None,
            max_offset_seconds=args.max_offset_seconds or config.max_offset_seconds,
            vad=args.vad or config.vad,
        )
        
        if result.success:
            if subtitle_path != output_path:
                subtitle_path.unlink()
            _mark_as_synced(output_path)
            statuses.append((lang_code, 'synced', output_path))
        else:
            statuses.append((lang_code, 'sync_failed', None))
    
    return statuses


def _print_status(video_path: Path, statuses: List[Tuple[str, str, Optional[Path]]]):
    """Print status line for a video with color-coded language statuses."""
    status_parts = []
    for language, status, path in statuses:
        lang = language.upper()
        if status == 'synced':
            status_parts.append(_green(f"{lang} ✓"))
        elif status == 'existing':
            status_parts.append(_green(f"{lang} existing"))
        elif status == 'not_found':
            status_parts.append(_yellow(f"{lang} not found"))
        elif status == 'sync_failed':
            status_parts.append(_red(f"{lang} sync failed"))
        else:
            status_parts.append(_red(f"{lang} {status}"))
    
    print(f"{video_path.name}: {', '.join(status_parts)}")


def main_command(args):
    """Handle the main command - sync or download based on inputs."""
    logger = logging.getLogger(__name__)
    
    # Load config
    config_path = Path(args.config) if args.config else None
    config = Config.load(config_path)
    
    video_path = Path(args.video)
    if not video_path.exists():
        logger.error(f"Video file or directory not found: {video_path}")
        return 1
    
    # If subtitle file provided, sync it
    if args.input:
        if not video_path.is_file():
            logger.error(f"Input subtitle mode requires a video file, not a directory: {video_path}")
            return 1
        
        subtitle_path = Path(args.input)
        if not subtitle_path.exists():
            logger.error(f"Subtitle file not found: {subtitle_path}")
            return 1
        
        logger.info(f"Syncing: {subtitle_path} to {video_path}")
        
        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            # Default: video.srt
            output_path = video_path.with_suffix('.srt')
            
            # If input is video.srt, rename original to video.srt.timestamp
            if subtitle_path == output_path:
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                backup_path = subtitle_path.with_suffix(f'.srt.{timestamp}')
                logger.info(f"Backing up original to: {backup_path}")
                subtitle_path.rename(backup_path)
        
        # Initialize engine
        engine = FFSubsyncEngine()
        if not engine.is_available():
            logger.error("ffsubsync is not installed. Install with: pip install ffsubsync")
            return 1
        
        show_progress = args.debug and not args.no_progress
        
        # Perform synchronization
        result = engine.sync(
            reference_path=video_path,
            subtitle_path=subtitle_path,
            output_path=output_path,
            progress_handler=progress_handler if show_progress else None,
            max_offset_seconds=args.max_offset_seconds or config.max_offset_seconds,
            vad=args.vad or config.vad,
        )
        
        if args.debug:
            print()  # New line after progress
        
        # Analyze confidence
        analyzer = ConfidenceAnalyzer(manual_review_threshold=args.confidence_threshold or config.confidence_threshold)
        confidence_report = analyzer.analyze([result])
        
        # Generate report
        report_generator = ReportGenerator()
        if args.report:
            report_path = Path(args.report)
            report_generator.save_json_report(result, confidence_report, report_path)
            logger.info(f"Report saved to: {report_path}")
        
        # Print summary
        if args.debug:
            print("\n" + "="*60)
            print("SYNCHRONIZATION COMPLETE")
            print("="*60)
            print(f"Success: {result.success}")
            print(f"Output: {output_path}")
            print(f"Offset: {result.offset_seconds:.2f}s")
            print(f"Framerate scale: {result.framerate_scale_factor:.4f}")
            print(f"Confidence: {confidence_report.overall_confidence:.2%}")
            print(f"Problem type: {confidence_report.problem_classification}")
            print(f"Manual review needed: {confidence_report.requires_manual_review}")
            print("="*60)
            
            if confidence_report.requires_manual_review:
                logger.warning("Low confidence - manual review recommended")
            
            # Print viewing commands
            print("\nTo view with subtitles:")
            print(f"  VLC: vlc \"{video_path}\" --sub-file=\"{output_path}\"")
            print(f"  IINA: iina \"{video_path}\" --mpv-sub-file=\"{output_path}\"")
        else:
            # Simplified output
            if result.success:
                print(_green(f"✓ Synced: {output_path}"))
            else:
                print(_red(f"✗ Sync failed: {output_path}"))
        
        return 0 if result.success else 1
    
    # No subtitle provided - download and sync
    else:
        # Initialize downloader
        downloader = SubtitleDownloader(providers=args.providers or config.providers)
        if not downloader.is_available():
            print(_red("✗ Error: subliminal is not installed. Install with: pip install subliminal"))
            return 1
        
        # Initialize engine
        engine = FFSubsyncEngine()
        if not engine.is_available():
            print(_red("✗ Error: ffsubsync is not installed. Install with: pip install ffsubsync"))
            return 1
        
        # Get effective languages
        languages = config.get_effective_languages(args.languages)
        
        # Determine videos to process
        if video_path.is_dir():
            video_files = sorted([p for p in video_path.rglob('*.mp4')])
            if not video_files:
                print(_yellow("No MP4 files found in directory"))
                return 0
        else:
            video_files = [video_path]
        
        # Process each video
        overall_success = True
        for current_video in video_files:
            if args.debug:
                logger.info(f"Processing: {current_video}")
            
            statuses = _process_video(current_video, languages, args, config, downloader, engine)
            _print_status(current_video, statuses)
            
            # If any failed, mark overall as not fully successful
            if any(status in ('not_found', 'sync_failed') for _, status, _ in statuses):
                overall_success = False
        
        return 0 if overall_success else 0  # Return 0 so partial results don't abort batch


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Captioner: Intelligent subtitle synchronization orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download and sync subtitles (default)
  captioner video.mp4
  captioner video.mp4 -l zho eng
  captioner video.mp4 --force
  
  # Process all MP4 files in a directory
  captioner /path/to/movies/
  
  # Sync existing subtitle
  captioner video.mp4 -i subtitles.srt
  captioner video.mp4 -i subtitles.srt -o synced.srt
  captioner video.mp4 -i subtitles.srt --report report.json
        """
    )
    
    parser.add_argument(
        "video",
        help="Video file or directory of MP4 files"
    )
    
    parser.add_argument(
        "-i", "--input",
        help="Input subtitle file to synchronize (if not provided, will download)"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output subtitle file (default: input.synced.srt or video.synced.srt)"
    )
    
    parser.add_argument(
        "-l", "--languages",
        nargs="+",
        help="Language codes for download (e.g., zho eng). Default: Chinese > English"
    )
    
    parser.add_argument(
        "-p", "--providers",
        nargs="+",
        choices=["opensubtitles", "opensubtitlescom", "podnapisi", "tvsubtitles", "addic7ed"],
        help="Subtitle providers to use (default: all)"
    )
    
    parser.add_argument(
        "-m", "--min-score",
        type=int,
        default=0,
        help="Minimum subtitle score (0-100, default: 0)"
    )
    
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force download even if subtitle already exists"
    )
    
    parser.add_argument(
        "--max-offset-seconds",
        type=int,
        default=300,
        help="Maximum offset to search in seconds (default: 300)"
    )
    
    parser.add_argument(
        "--vad",
        choices=["webrtc", "subs_then_webrtc", "silero"],
        default="subs_then_webrtc",
        help="Voice activity detection method (default: subs_then_webrtc)"
    )
    
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for manual review flag (default: 0.7)"
    )
    
    parser.add_argument(
        "--report",
        help="Path to save JSON report"
    )
    
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output (more verbose than --verbose)"
    )
    
    parser.add_argument(
        "--config",
        help="Path to config file (default: ~/.config/captioner/config.json)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose, args.debug)
    
    # Execute main command
    return main_command(args)


if __name__ == "__main__":
    sys.exit(main())
