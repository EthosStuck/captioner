"""Base interface for subtitle synchronization engines."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path


@dataclass
class SyncResult:
    """Result of subtitle synchronization."""
    
    success: bool
    output_path: Path
    offset_seconds: float
    framerate_scale_factor: float
    confidence: float
    engine_name: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "output_path": str(self.output_path),
            "offset_seconds": self.offset_seconds,
            "framerate_scale_factor": self.framerate_scale_factor,
            "confidence": self.confidence,
            "engine_name": self.engine_name,
            "metadata": self.metadata,
        }


class BaseEngine(ABC):
    """Abstract base class for subtitle synchronization engines."""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def sync(
        self,
        reference_path: Path,
        subtitle_path: Path,
        output_path: Path,
        **kwargs
    ) -> SyncResult:
        """
        Synchronize subtitles to reference.
        
        Args:
            reference_path: Path to reference (video or subtitle file)
            subtitle_path: Path to input subtitle file
            output_path: Path to write synchronized subtitle
            **kwargs: Engine-specific options
            
        Returns:
            SyncResult with synchronization details
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine dependencies are available."""
        pass
