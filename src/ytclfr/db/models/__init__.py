"""DB models init"""

from ytclfr.db.models.extractor_result import ExtractorResultModel
from ytclfr.db.models.job import Job
from ytclfr.db.models.router_decision import RouterDecisionModel
from ytclfr.db.models.aligned_segment import AlignedSegmentModel
from ytclfr.db.models.final_output import FinalOutputModel

__all__ = [
    "Job",
    "RouterDecisionModel",
    "ExtractorResultModel",
    "AlignedSegmentModel",
    "FinalOutputModel",
]
