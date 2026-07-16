from dataclasses import dataclass


ALLOWED_DISPLAY_LABELS = {
    "\uc548\uc804",
    "\uc8fc\uc758",
    "\uc704\ud5d8",
    "\ucd94\uac00 \ud655\uc778",
}


@dataclass(frozen=True)
class AnalysisResultData:
    reference_id: str
    display_label: str
    summary: str
    expert_review_recommended: bool

    def validate(self) -> None:
        if not self.reference_id.strip():
            raise ValueError("reference_id must not be empty.")

        if self.display_label not in ALLOWED_DISPLAY_LABELS:
            raise ValueError(
                "display_label must be one of the allowed labels."
            )

        if not self.summary.strip():
            raise ValueError("summary must not be empty.")

        if not isinstance(self.expert_review_recommended, bool):
            raise ValueError(
                "expert_review_recommended must be a boolean."
            )
