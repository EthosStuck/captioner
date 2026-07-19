"""Confidence scoring and analysis for subtitle synchronization."""

import logging
from typing import List, Dict, Any
from dataclasses import dataclass
from pathlib import Path

from .engines.base import SyncResult


logger = logging.getLogger(__name__)


@dataclass
class ConfidenceReport:
    """Detailed confidence report for synchronization."""
    
    overall_confidence: float
    engine_confidence: Dict[str, float]
    problem_classification: str
    requires_manual_review: bool
    low_confidence_segments: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_confidence": self.overall_confidence,
            "engine_confidence": self.engine_confidence,
            "problem_classification": self.problem_classification,
            "requires_manual_review": self.requires_manual_review,
            "low_confidence_segments": self.low_confidence_segments,
        }


class ConfidenceAnalyzer:
    """Analyzes synchronization results to determine confidence."""
    
    def __init__(self, manual_review_threshold: float = 0.7):
        self.manual_review_threshold = manual_review_threshold
    
    def analyze(self, results: List[SyncResult]) -> ConfidenceReport:
        """
        Analyze multiple sync results to determine overall confidence.
        
        Args:
            results: List of SyncResult from different engines
            
        Returns:
            ConfidenceReport with detailed analysis
        """
        if not results:
            return ConfidenceReport(
                overall_confidence=0.0,
                engine_confidence={},
                problem_classification="no_results",
                requires_manual_review=True,
                low_confidence_segments=[]
            )
        
        # Extract engine confidences
        engine_confidence = {r.engine_name: r.confidence for r in results}
        
        # Calculate overall confidence (weighted average, preferring successful engines)
        successful_results = [r for r in results if r.success]
        
        if not successful_results:
            return ConfidenceReport(
                overall_confidence=0.0,
                engine_confidence=engine_confidence,
                problem_classification="all_failed",
                requires_manual_review=True,
                low_confidence_segments=[]
            )
        
        # Weight successful engines more heavily
        weights = [2.0 if r.success else 1.0 for r in results]
        total_weight = sum(weights)
        overall_confidence = sum(r.confidence * w for r, w in zip(results, weights)) / total_weight
        
        # Classify the problem type
        problem_classification = self._classify_problem(results)
        
        # Determine if manual review is needed
        requires_manual_review = overall_confidence < self.manual_review_threshold
        
        # Identify low-confidence segments (placeholder for future implementation)
        low_confidence_segments = self._identify_low_confidence_segments(results)
        
        return ConfidenceReport(
            overall_confidence=overall_confidence,
            engine_confidence=engine_confidence,
            problem_classification=problem_classification,
            requires_manual_review=requires_manual_review,
            low_confidence_segments=low_confidence_segments
        )
    
    def _classify_problem(self, results: List[SyncResult]) -> str:
        """
        Classify the type of synchronization problem.
        
        Args:
            results: List of SyncResult
            
        Returns:
            Problem classification string
        """
        # Check for constant offset (small offset, no framerate change)
        for r in results:
            if r.success and abs(r.offset_seconds) < 60 and abs(r.framerate_scale_factor - 1.0) < 0.01:
                return "constant_offset"
        
        # Check for linear drift (framerate correction applied)
        for r in results:
            if r.success and abs(r.framerate_scale_factor - 1.0) > 0.01:
                return "linear_drift"
        
        # Check for discontinuities (large offset or multiple segments)
        for r in results:
            if r.success and abs(r.offset_seconds) > 60:
                return "discontinuity"
        
        # Default classification
        if any(r.success for r in results):
            return "complex_alignment"
        else:
            return "sync_failed"
    
    def _identify_low_confidence_segments(self, results: List[SyncResult]) -> List[Dict[str, Any]]:
        """
        Identify segments with low confidence for manual review.
        
        Args:
            results: List of SyncResult
            
        Returns:
            List of low-confidence segment metadata
        """
        # Placeholder for future implementation
        # This would analyze subtitle density, speech activity, etc.
        # to identify specific segments that need review
        return []
