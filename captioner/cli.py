"""Command-line interface for captioner."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .engines import FFSubsyncEngine
from .confidence import ConfidenceAnalyzer
from .report import ReportGenerator
from .downloader import SubtitleDownloader


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)]
    )


def progress_handler(info):
    """Progress callback for ffsubsync."""
    if info.fraction is not None:
        print(f"\rProgress: {info.fraction:.0%}", end="", file=sys.stderr)
    else:
        print(f"\rProcessed: {info.processed_seconds:.1f}s", end="", file=sys.stderr)


def sync_command(args):
    """Handle the sync subcommand."""
    logger = logging.getLogger(__name__)
    
    # Validate inputs
    reference_path = Path(args.reference)
    subtitle_path = Path(args.input)
    output_path = Path(args.output) if args.output else subtitle_path.with_suffix(".synced.srt")
    
    if not reference_path.exists():
        logger.error(f"Reference file not found: {reference_path}")
        return 1
    
    if not subtitle_path.exists():
        logger.error(f"Subtitle file not found: {subtitle_path}")
        return 1
    
    logger.info(f"Syncing: {subtitle_path} to {reference_path}")
    
    # Initialize engine
    engine = FFSubsyncEngine()
    
    if not engine.is_available():
        logger.error("ffsubsync is not installed. Install with: pip install ffsubsync")
        return 1
    
    # Perform synchronization
    result = engine.sync(
        reference_path=reference_path,
        subtitle_path=subtitle_path,
        output_path=output_path,
        progress_handler=progress_handler if not args.no_progress else None,
        max_offset_seconds=args.max_offset_seconds,
        vad=args.vad,
    )
    
    print()  # New line after progress
    
    # Analyze confidence
    analyzer = ConfidenceAnalyzer(manual_review_threshold=args.confidence_threshold)
    confidence_report = analyzer.analyze([result])
    
    # Generate report
    report_generator = ReportGenerator()
    
    if args.report:
        report_path = Path(args.report)
        report_generator.save_json_report(result, confidence_report, report_path)
        logger.info(f"Report saved to: {report_path}")
    
    # Print summary
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
    
    return 0 if result.success else 1


def download_command(args):
    """Handle the download subcommand."""
    logger = logging.getLogger(__name__)
    
    # Validate input
    video_path = Path(args.video)
    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        return 1
    
    logger.info(f"Downloading subtitles for: {video_path}")
    
    # Initialize downloader
    downloader = SubtitleDownloader(providers=args.providers)
    
    if not downloader.is_available():
        logger.error("subliminal is not installed. Install with: pip install subliminal")
        return 1
    
    # Determine languages
    languages = args.languages if args.languages else None
    
    # Download subtitles
    subtitle_path, language = downloader.download_subtitles(
        video_path=video_path,
        languages=languages,
        min_score=args.min_score,
        force=args.force,
    )
    
    if not subtitle_path:
        logger.error("Failed to download subtitles")
        return 1
    
    print("\n" + "="*60)
    print("SUBTITLE DOWNLOAD COMPLETE")
    print("="*60)
    print(f"Video: {video_path}")
    print(f"Subtitle: {subtitle_path}")
    print(f"Language: {language}")
    print("="*60)
    
    # Auto-sync if requested
    if args.auto_sync:
        logger.info("Auto-syncing downloaded subtitle...")
        output_path = subtitle_path.with_suffix(".synced.srt")
        
        engine = FFSubsyncEngine()
        result = engine.sync(
            reference_path=video_path,
            subtitle_path=subtitle_path,
            output_path=output_path,
            progress_handler=progress_handler if not args.no_progress else None,
            max_offset_seconds=args.max_offset_seconds,
            vad=args.vad,
        )
        
        print()  # New line after progress
        
        if result.success:
            print(f"\nAuto-sync complete: {output_path}")
            print(f"Offset: {result.offset_seconds:.2f}s")
            print(f"Framerate scale: {result.framerate_scale_factor:.4f}")
        else:
            logger.warning("Auto-sync failed, but subtitle was downloaded")
    
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Captioner: Intelligent subtitle synchronization orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  captioner sync video.mp4 -i subtitles.srt -o synced.srt
  captioner sync video.mp4 -i subtitles.srt --report report.json
  captioner sync video.mp4 -i subtitles.srt --max-offset-seconds 600
        """
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Sync subcommand
    sync_parser = subparsers.add_parser(
        "sync",
        help="Synchronize subtitles to video or reference subtitle"
    )
    
    # Download subcommand
    download_parser = subparsers.add_parser(
        "download",
        help="Download subtitles for a video file"
    )
    
    download_parser.add_argument(
        "video",
        help="Video file to download subtitles for"
    )
    
    download_parser.add_argument(
        "-l", "--languages",
        nargs="+",
        help="Language codes (e.g., zho eng). Default: Chinese Simplified > Chinese Traditional > English"
    )
    
    download_parser.add_argument(
        "-p", "--providers",
        nargs="+",
        choices=["opensubtitles", "opensubtitlescom", "podnapisi", "tvsubtitles", "addic7ed"],
        help="Subtitle providers to use (default: all)"
    )
    
    download_parser.add_argument(
        "-m", "--min-score",
        type=int,
        default=0,
        help="Minimum subtitle score (0-100, default: 0)"
    )
    
    download_parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force download even if subtitle already exists"
    )
    
    download_parser.add_argument(
        "--auto-sync",
        action="store_true",
        help="Automatically sync downloaded subtitle to video"
    )
    
    download_parser.add_argument(
        "--max-offset-seconds",
        type=int,
        default=300,
        help="Maximum offset to search in seconds for auto-sync (default: 300)"
    )
    
    download_parser.add_argument(
        "--vad",
        choices=["webrtc", "subs_then_webrtc", "silero"],
        default="subs_then_webrtc",
        help="Voice activity detection method for auto-sync (default: subs_then_webrtc)"
    )
    
    download_parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar"
    )
    
    sync_parser.add_argument(
        "reference",
        help="Reference file (video or subtitle)"
    )
    
    sync_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Input subtitle file to synchronize"
    )
    
    sync_parser.add_argument(
        "-o", "--output",
        help="Output subtitle file (default: input.synced.srt)"
    )
    
    sync_parser.add_argument(
        "--max-offset-seconds",
        type=int,
        default=300,
        help="Maximum offset to search in seconds (default: 300)"
    )
    
    sync_parser.add_argument(
        "--vad",
        choices=["webrtc", "subs_then_webrtc", "silero"],
        default="subs_then_webrtc",
        help="Voice activity detection method (default: subs_then_webrtc)"
    )
    
    sync_parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for manual review flag (default: 0.7)"
    )
    
    sync_parser.add_argument(
        "--report",
        help="Path to save JSON report"
    )
    
    sync_parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Execute command
    if args.command == "sync":
        return sync_command(args)
    elif args.command == "download":
        return download_command(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
