"""Subtitle download module using subliminal."""

import logging
from pathlib import Path
from typing import Optional, List, Set, Tuple
from babelfish import Language

try:
    from subliminal import download_best_subtitles, save_subtitles, scan_video
    from subliminal.core import Episode, Movie
    SUBLIMINAL_AVAILABLE = True
except ImportError:
    SUBLIMINAL_AVAILABLE = False

logger = logging.getLogger(__name__)


class SubtitleDownloader:
    """Download subtitles for video files."""
    
    # Language priority: Chinese > English
    # Note: subliminal will find both simplified and traditional Chinese
    LANGUAGE_PRIORITY = [
        Language('zho'),  # Chinese (includes both simplified and traditional)
        Language('eng'),  # English
    ]
    
    def __init__(self, providers: Optional[List[str]] = None):
        """
        Initialize subtitle downloader.
        
        Args:
            providers: List of subtitle providers to use (default: all available)
        """
        self.providers = providers
        if not SUBLIMINAL_AVAILABLE:
            logger.warning("subliminal is not installed. Install with: pip install subliminal")
    
    def is_available(self) -> bool:
        """Check if subliminal is installed."""
        return SUBLIMINAL_AVAILABLE
    
    def download_subtitles(
        self,
        video_path: Path,
        languages: Optional[List[str]] = None,
        min_score: int = 0,
        force: bool = False,
        download_multiple: bool = False,
    ) -> List[Tuple[Path, str]]:
        """
        Download matching subtitles for a video.
        
        Args:
            video_path: Path to video file
            languages: List of language codes (e.g., ['zho', 'eng']). If None, uses default priority.
            min_score: Minimum score for subtitle acceptance (0-100)
            force: Force download even if subtitle already exists
            download_multiple: Download all requested languages instead of just the best match
            
        Returns:
            List of (subtitle_path, language_code) tuples
        """
        if not self.is_available():
            raise RuntimeError("subliminal is not installed. Install with: pip install subliminal")
        
        logger.info(f"Scanning video: {video_path}")
        
        # Scan video to get metadata
        try:
            video = scan_video(str(video_path))
        except Exception as e:
            logger.error(f"Failed to scan video: {e}")
            return []
        
        # Determine languages to search
        if languages:
            lang_set = {Language(l) for l in languages}
        else:
            # Use default priority
            lang_set = set(self.LANGUAGE_PRIORITY)
        
        logger.info(f"Searching for subtitles in languages: {lang_set}")
        
        # Check if subtitles already exist (unless force)
        if not force:
            existing_subs = self._find_existing_subtitles(video_path, languages)
            if existing_subs:
                logger.info(f"Subtitles already exist: {existing_subs}")
                # Return existing subtitles that match our language preferences
                results = []
                for existing_path, lang in existing_subs:
                    if lang and Language(lang) in lang_set:
                        logger.info(f"Using existing subtitle: {existing_path}")
                        results.append((existing_path, lang))
                if results:
                    return results
        
        # Download subtitles
        try:
            kwargs = {"min_score": min_score}
            if self.providers:
                kwargs["providers"] = self.providers
            
            subtitles = download_best_subtitles([video], lang_set, **kwargs)
            
            if not subtitles or not subtitles[video]:
                logger.warning(f"No subtitles found for {video_path}")
                return []
            
            results = []
            
            if download_multiple:
                # Download one subtitle per language
                downloaded_langs = set()
                for subtitle in subtitles[video]:
                    lang_code = str(subtitle.language)
                    if lang_code not in downloaded_langs:
                        # Save subtitle (subliminal saves next to video with language code)
                        save_subtitles(video, [subtitle], encoding='utf-8')
                        # subliminal saves to video.{lang}.srt
                        subtitle_path = video_path.with_suffix(f'.{lang_code}.srt')
                        if subtitle_path.exists():
                            results.append((subtitle_path, lang_code))
                            downloaded_langs.add(lang_code)
                            logger.info(f"Saved subtitle: {subtitle_path}")
                        else:
                            logger.warning(f"Subtitle not found at expected path: {subtitle_path}")
            else:
                # Download only the best subtitle
                best_subtitle = subtitles[video][0]
                lang_code = str(best_subtitle.language)
                
                # Save subtitle (subliminal saves next to video with language code)
                save_subtitles(video, [best_subtitle], encoding='utf-8')
                # subliminal saves to video.{lang}.srt
                subtitle_path = video_path.with_suffix(f'.{lang_code}.srt')
                if subtitle_path.exists():
                    results.append((subtitle_path, lang_code))
                    logger.info(f"Saved subtitle: {subtitle_path}")
                else:
                    logger.warning(f"Subtitle not found at expected path: {subtitle_path}")
                    return []
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to download subtitles: {e}")
            return []
    
    def _find_existing_subtitles(self, video_path: Path, languages: Optional[List[str]] = None) -> List[Tuple[Path, str]]:
        """Find existing subtitle files for the video with their language codes."""
        video_dir = video_path.parent
        video_stem = video_path.stem
        
        existing = []
        for ext in ['.srt', '.ass', '.ssa', '.sub']:
            # Check for exact match (no language code)
            sub_path = video_dir / f"{video_stem}{ext}"
            if sub_path.exists():
                existing.append((sub_path, ''))
            
            # Check for language-tagged versions
            if languages:
                for lang in languages:
                    sub_path = video_dir / f"{video_stem}.{lang}{ext}"
                    if sub_path.exists():
                        existing.append((sub_path, lang))
            else:
                # Check common language codes
                for lang in ['en', 'eng', 'zh', 'zho', 'chs', 'cht']:
                    sub_path = video_dir / f"{video_stem}.{lang}{ext}"
                    if sub_path.exists():
                        existing.append((sub_path, lang))
        
        return existing
    
    def _extract_language_from_filename(self, subtitle_path: Path) -> Optional[str]:
        """Extract language code from subtitle filename."""
        # Common patterns: video.en.srt, video.zh.srt, video.chs.srt, etc.
        parts = subtitle_path.stem.split('.')
        if len(parts) >= 2:
            lang_part = parts[-1].lower()
            # Map common codes to IETF
            lang_map = {
                'en': 'eng', 'eng': 'eng',
                'zh': 'zho', 'zho': 'zho',
                'chs': 'zho-Hans', 'hans': 'zho-Hans',
                'cht': 'zho-Hant', 'hant': 'zho-Hant',
            }
            return lang_map.get(lang_part)
        return None
    
    def detect_video_language(self, video_path: Path) -> Optional[str]:
        """
        Detect the primary language of the video.
        
        This is a placeholder - actual implementation would use:
        - Audio track language metadata
        - Speech recognition (Whisper)
        - Heuristics from filename
        
        Args:
            video_path: Path to video file
            
        Returns:
            Language code or None if undetectable
        """
        # Placeholder: check filename for language hints
        filename_lower = video_path.name.lower()
        
        # Chinese indicators
        if any(x in filename_lower for x in ['chinese', 'zh', 'cn', 'mandarin']):
            return 'zho'
        
        # English indicators (default assumption)
        return 'eng'
