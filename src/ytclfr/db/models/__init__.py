"""DB models init"""

from ytclfr.db.models.extractor_result import ExtractorResultModel
from ytclfr.db.models.job import Job
from ytclfr.db.models.router_decision import RouterDecisionModel
from ytclfr.db.models.aligned_segment import AlignedSegmentModel
from ytclfr.db.models.final_output import FinalOutputModel
from ytclfr.db.models.signal_manifest import SignalManifestORM
from ytclfr.db.models.evidence_graph import EvidenceGraphORM
from ytclfr.db.models.v3.v3_evidence_graphs import V3EvidenceGraphORM
from ytclfr.db.models.v3.v3_extractor_bundles import V3ExtractorBundleORM

__all__ = [
    "Job",
    "RouterDecisionModel",
    "ExtractorResultModel",
    "AlignedSegmentModel",
    "FinalOutputModel",
    "SignalManifestORM",
    "EvidenceGraphORM",
    "V3EvidenceGraphORM",
    "V3ExtractorBundleORM",
]
