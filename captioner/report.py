"""Reporting module for synchronization results."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from .engines.base import SyncResult
from .confidence import ConfidenceReport


logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate reports for synchronization results."""
    
    def __init__(self):
        pass
    
    def generate_report(
        self,
        result: SyncResult,
        confidence_report: ConfidenceReport
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive report.
        
        Args:
            result: SyncResult from engine
            confidence_report: ConfidenceReport from analyzer
            
        Returns:
            Dictionary with report data
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "synchronization": result.to_dict(),
            "confidence": confidence_report.to_dict(),
            "summary": {
                "success": result.success,
                "overall_confidence": confidence_report.overall_confidence,
                "problem_type": confidence_report.problem_classification,
                "requires_manual_review": confidence_report.requires_manual_review,
            }
        }
        
        return report
    
    def save_json_report(
        self,
        result: SyncResult,
        confidence_report: ConfidenceReport,
        output_path: Path
    ) -> None:
        """
        Save report as JSON file.
        
        Args:
            result: SyncResult from engine
            confidence_report: ConfidenceReport from analyzer
            output_path: Path to save report
        """
        report = self.generate_report(result, confidence_report)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"JSON report saved to {output_path}")
    
    def print_summary(
        self,
        result: SyncResult,
        confidence_report: ConfidenceReport
    ) -> None:
        """
        Print a human-readable summary to console.
        
        Args:
            result: SyncResult from engine
            confidence_report: ConfidenceReport from analyzer
        """
        print("\n" + "="*60)
        print("SYNCHRONIZATION SUMMARY")
        print("="*60)
        print(f"Engine: {result.engine_name}")
        print(f"Success: {result.success}")
        print(f"Output: {result.output_path}")
        print(f"Offset: {result.offset_seconds:.2f}s")
        print(f"Framerate scale: {result.framerate_scale_factor:.4f}")
        print(f"Confidence: {confidence_report.overall_confidence:.2%}")
        print(f"Problem type: {confidence_report.problem_classification}")
        print(f"Manual review: {'YES' if confidence_report.requires_manual_review else 'NO'}")
        print("="*60)
