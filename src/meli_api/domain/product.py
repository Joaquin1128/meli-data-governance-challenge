from dataclasses import dataclass, field
from enum import Enum


class EnrichmentStatus(str, Enum):
    """Espeja el `status` que ya persiste el pipeline offline en SQLite."""

    PENDING = "pending"
    ENRICHED = "enriched"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(frozen=True)
class Product:
    """Entidad de dominio. No conoce SQLite, FastAPI ni Redis."""

    item_id: str
    name: str
    price: float | None
    currency: str | None
    image_url: str | None
    permalink: str | None
    rating: float | None
    original_description: str
    enriched_description: str | None
    specifications: dict[str, str] = field(default_factory=dict)
    status: EnrichmentStatus = EnrichmentStatus.PENDING

    @property
    def description(self) -> str:
        """Descripción a exponer: la enriquecida si existe, si no la original.

        Un producto que no llegó a `enriched` (pending/skipped/error) igual debe
        servirse con algo usable; el consumidor distingue el caso mirando
        `enrichment_status` en vez de recibir un campo vacío.
        """
        return self.enriched_description or self.original_description
