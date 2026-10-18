"""Data shapes for each content collection.

These mirror `src/content.config.ts` in the CIR website template. When that schema changes, change this file too.
`site-agent validate` reports files that the real site would reject, so drift shows up quickly.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class Event(BaseModel):
    # The site ignores keys it does not know, so extra keys are ignored here too (validate reports them as warnings).
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    title: str = Field(min_length=1)
    kind: Literal["workshop", "programme", "talk"]
    series: str | None = None
    date: dt.date
    end_date: dt.date | None = Field(default=None, alias="endDate")
    venue: str | None = None
    summary: str | None = None
    sample: bool = False

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Event:
        if self.end_date is not None and self.end_date < self.date:
            raise ValueError(f"endDate ({self.end_date}) must not be earlier than date ({self.date})")
        return self

    def to_frontmatter(self) -> dict[str, Any]:
        """Frontmatter keys in the order the template uses. Empty optional values and `sample: false` are left out."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if not self.sample:
            data.pop("sample")
        return data


# Collection name (the folder under src/content) -> the model its files must satisfy.
# Only events are supported so far. See docs/PLANNING.md for the next collections.
COLLECTIONS: dict[str, type[BaseModel]] = {"events": Event}


def describe_errors(exc: ValidationError) -> list[str]:
    """One readable line per problem, naming the field, for example 'date: Input should be a valid date'."""
    lines = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"]) or "record"
        lines.append(f"{field}: {error['msg']}")
    return lines
