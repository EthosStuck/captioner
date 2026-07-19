"""FFSubsync engine wrapper."""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import argparse

try:
    import ffsubsync
    from ffsubsync.ffsubsync import make_parser
    FFSUBSYNC_AVAILABLE = True
except ImportError:
    FFSUBSYNC_AVAILABLE = False

from .base import BaseEngine, SyncResult


logger = logging.getLogger(__name__)


class FFSubsyncEngine(BaseEngine):
    """Wrapper for ffsubsync synchronization engine."""
    
    def __init__(self):
        super().__init__("ffsubsync")
    
    def is_available(self) -> bool:
        """Check if ffsubsync is installed."""
        return FFSUBSYNC_AVAILABLE
    
    def sync(
        self,
        reference_path: Path,
        subtitle_path: Path,
        output_path: Path,
        progress_handler: Optional[Callable] = None,
        **kwargs
    ) -> SyncResult:
        """
        Synchronize subtitles using ffsubsync.
        
        Args:
            reference_path: Path to reference (video or subtitle file)
            subtitle_path: Path to input subtitle file
            output_path: Path to write synchronized subtitle
            progress_handler: Optional callback for progress updates
            **kwargs: Additional ffsubsync options (max_offset_seconds, etc.)
            
        Returns:
            SyncResult with synchronization details
        """
        if not self.is_available():
            raise RuntimeError("ffsubsync is not installed. Install with: pip install ffsubsync")
        
        logger.info(f"Starting ffsubsync sync: {reference_path} + {subtitle_path} -> {output_path}")
        
        # Use ffsubsync's parser to create proper args namespace
        parser = make_parser()
        
        # Build command line args list
        cmd_args = [
            str(reference_path),
            "-i", str(subtitle_path),
            "-o", str(output_path),
            "--vad", kwargs.get("vad", "subs_then_webrtc"),
            "--max-offset-seconds", str(kwargs.get("max_offset_seconds", 300)),
        ]
        
        # Parse args using ffsubsync's parser
        args = parser.parse_args(cmd_args)
        
        # Run ffsubsync with progress handler
        try:
            result = ffsubsync.run(args, progress_handler=progress_handler)
            
            sync_was_successful = result.get("sync_was_successful", False)
            offset_seconds = result.get("offset_seconds", 0.0)
            framerate_scale_factor = result.get("framerate_scale_factor", 1.0)
            
            # Calculate confidence based on ffsubsync's internal scoring
            confidence = self._calculate_confidence(result)
            
            logger.info(f"ffsubsync completed: success={sync_was_successful}, offset={offset_seconds}s, confidence={confidence:.2f}")
            
            return SyncResult(
                success=sync_was_successful,
                output_path=output_path,
                offset_seconds=offset_seconds,
                framerate_scale_factor=framerate_scale_factor,
                confidence=confidence,
                engine_name=self.name,
                metadata={
                    "retval": result.get("retval", 0),
                    "framerate_ratios_tested": result.get("framerate_ratios_tested", []),
                }
            )
            
        except Exception as e:
            logger.error(f"ffsubsync failed: {e}")
            return SyncResult(
                success=False,
                output_path=output_path,
                offset_seconds=0.0,
                framerate_scale_factor=1.0,
                confidence=0.0,
                engine_name=self.name,
                metadata={"error": str(e)}
            )
    
    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """
        Calculate confidence score from ffsubsync result.
        
        Args:
            result: Result dictionary from ffsubsync.run()
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # If sync was not successful, confidence is 0
        if not result.get("sync_was_successful", False):
            return 0.0
        
        # Base confidence from successful sync
        confidence = 0.7
        
        # Increase confidence if framerate correction was successful
        if result.get("framerate_scale_factor", 1.0) != 1.0:
            confidence += 0.1
        
        # Check if multiple framerate ratios were tested (indicates uncertainty)
        ratios_tested = result.get("framerate_ratios_tested", [])
        if len(ratios_tested) > 1:
            confidence -= 0.1  # Slightly reduce confidence if multiple ratios were tried
        
        # Clamp between 0 and 1
        return max(0.0, min(1.0, confidence))
