"""Configuration management for captioner."""

import json
import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Captioner configuration."""
    
    # Language preferences (in order of priority)
    languages: List[str] = None
    
    # Whether to download multiple languages
    download_multiple: bool = False
    
    # Minimum subtitle score
    min_score: int = 0
    
    # Maximum offset seconds for sync
    max_offset_seconds: int = 300
    
    # Voice activity detection method
    vad: str = "subs_then_webrtc"
    
    # Confidence threshold for manual review
    confidence_threshold: float = 0.7
    
    # Subtitle providers to use
    providers: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.languages is None:
            # Default: Chinese > English
            self.languages = ["zho", "eng"]
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from file or return defaults."""
        if config_path is None:
            config_path = cls.default_config_path()
        
        if not config_path.exists():
            logger.debug(f"Config file not found: {config_path}, using defaults")
            return cls()
        
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded config from: {config_path}")
            return cls(**data)
        except Exception as e:
            logger.error(f"Failed to load config: {e}, using defaults")
            return cls()
    
    def save(self, config_path: Optional[Path] = None):
        """Save configuration to file."""
        if config_path is None:
            config_path = self.default_config_path()
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
        
        logger.info(f"Saved config to: {config_path}")
    
    @staticmethod
    def default_config_path() -> Path:
        """Get default configuration file path."""
        # Check common config directories
        config_dir = Path.home() / ".config" / "captioner"
        if not config_dir.exists():
            # Fallback to home directory
            config_dir = Path.home()
        
        return config_dir / "config.json"
    
    def get_effective_languages(self, override_languages: Optional[List[str]] = None) -> List[str]:
        """Get languages to use, preferring override over config."""
        if override_languages:
            return override_languages
        return self.languages
