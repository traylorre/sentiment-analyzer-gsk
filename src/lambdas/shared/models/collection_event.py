"""CollectionEvent model for ingestion audit trail.

Records each data collection attempt for operational monitoring.
Schema defined in specs/072-market-data-ingestion/contracts/collection-event.schema.json
"""

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CollectionEvent(BaseModel):
    """Audit record for a single data collection attempt.

    DynamoDB schema:
        PK: COLLECTION#{date}
        SK: {timestamp_iso}#{event_id[:8]}
        entity_type: COLLECTION_EVENT
    """

    event_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique event identifier"
    )
    triggered_at: datetime = Field(..., description="When collection was initiated")
    completed_at: datetime | None = Field(
        default=None, description="When collection finished"
    )
    status: Literal["success", "partial", "failed"] = Field(
        ..., description="Collection outcome"
    )
    source_used: Literal["tiingo", "finnhub"] = Field(
        ..., description="Which source provided data"
    )
    is_failover: bool = Field(
        default=False, description="True if secondary source was used"
    )
    items_collected: int = Field(
        default=0, ge=0, description="Number of items retrieved"
    )
    items_stored: int = Field(default=0, ge=0, description="New items after dedup")
    items_duplicates: int = Field(
        default=0, ge=0, description="Items skipped as duplicates"
    )
    duration_ms: int | None = Field(
        default=None, ge=0, description="Collection duration in milliseconds"
    )
    error_message: str | None = Field(
        default=None, max_length=500, description="Error details if failed"
    )
    trigger_type: Literal["scheduled", "manual", "retry"] = Field(
        default="scheduled", description="What initiated the collection"
    )

    @property
    def pk(self) -> str:
        """DynamoDB partition key (date-based for efficient queries)."""
        date_str = self.triggered_at.strftime("%Y-%m-%d")
        return f"COLLECTION#{date_str}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key (timestamp + event_id prefix for uniqueness)."""
        return f"{self.triggered_at.isoformat()}#{self.event_id[:8]}"

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        item: dict = {
            "PK": self.pk,
            "SK": self.sk,
            "event_id": self.event_id,
            "triggered_at": self.triggered_at.isoformat(),
            "status": self.status,
            "source_used": self.source_used,
            "is_failover": self.is_failover,
            "items_collected": self.items_collected,
            "items_stored": self.items_stored,
            "items_duplicates": self.items_duplicates,
            "trigger_type": self.trigger_type,
            "entity_type": "COLLECTION_EVENT",
        }
        if self.completed_at:
            item["completed_at"] = self.completed_at.isoformat()
        if self.duration_ms is not None:
            item["duration_ms"] = self.duration_ms
        if self.error_message:
            item["error_message"] = self.error_message
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "CollectionEvent":
        """Create CollectionEvent from DynamoDB item."""
        return cls(
            event_id=item["event_id"],
            triggered_at=datetime.fromisoformat(item["triggered_at"]),
            completed_at=(
                datetime.fromisoformat(item["completed_at"])
                if item.get("completed_at")
                else None
            ),
            status=item["status"],
            source_used=item["source_used"],
            is_failover=item.get("is_failover", False),
            items_collected=item.get("items_collected", 0),
            items_stored=item.get("items_stored", 0),
            items_duplicates=item.get("items_duplicates", 0),
            duration_ms=item.get("duration_ms"),
            error_message=item.get("error_message"),
            trigger_type=item.get("trigger_type", "scheduled"),
        )

    def mark_completed(
        self,
        status: Literal["success", "partial", "failed"],
        items_stored: int = 0,
        items_duplicates: int = 0,
        error_message: str | None = None,
    ) -> "CollectionEvent":
        """Create a copy with completion details filled in.

        Args:
            status: Final collection status
            items_stored: Number of new items stored
            items_duplicates: Number of duplicates skipped
            error_message: Error message if failed

        Returns:
            New CollectionEvent with completion fields set
        """
        completed_at = datetime.now(self.triggered_at.tzinfo)
        duration_ms = int((completed_at - self.triggered_at).total_seconds() * 1000)

        return CollectionEvent(
            event_id=self.event_id,
            triggered_at=self.triggered_at,
            completed_at=completed_at,
            status=status,
            source_used=self.source_used,
            is_failover=self.is_failover,
            items_collected=self.items_collected,
            items_stored=items_stored,
            items_duplicates=items_duplicates,
            duration_ms=duration_ms,
            error_message=error_message,
            trigger_type=self.trigger_type,
        )
