"""
Data models for the B2B Lead Generation Engine.
Defines structured Lead entity and serialization/deserialization helpers.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import sqlite3


@dataclass
class Lead:
    """
    Represents a single business lead discovered from Google Maps
    and enriched with website contact intelligence.
    """
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    query: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    maps_url: Optional[str] = None
    is_enriched: bool = False
    id: Optional[int] = None
    created_at: Optional[str] = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: Optional[str] = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert lead object to standard dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Lead":
        """Instantiate a Lead from dictionary representation."""
        valid_fields = {
            "id", "name", "phone", "address", "website", "email",
            "query", "rating", "reviews_count", "maps_url",
            "is_enriched", "created_at", "updated_at"
        }
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    @classmethod
    def from_sqlite_row(cls, row: sqlite3.Row) -> "Lead":
        """Instantiate a Lead from an SQLite sqlite3.Row object."""
        return cls(
            id=row["id"],
            name=row["name"],
            phone=row["phone"],
            address=row["address"],
            website=row["website"],
            email=row["email"],
            query=row["query"],
            rating=row["rating"],
            reviews_count=row["reviews_count"],
            maps_url=row["maps_url"],
            is_enriched=bool(row["is_enriched"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def to_db_insert_tuple(self) -> Tuple[Any, ...]:
        """Return tuple of values matching the standard SQLite insert schema."""
        return (
            self.name,
            self.phone,
            self.address,
            self.website,
            self.email,
            self.query,
            self.rating,
            self.reviews_count,
            self.maps_url,
            1 if self.is_enriched else 0,
            self.created_at,
            self.updated_at
        )

    def __repr__(self) -> str:
        enrich_status = "Enriched" if self.is_enriched else "Pending"
        email_str = f" | Email: {self.email}" if self.email else ""
        return f"<Lead [{self.id or 'New'}] '{self.name}' | Phone: {self.phone or 'N/A'} | Web: {self.website or 'N/A'}{email_str} | Status: {enrich_status}>"
