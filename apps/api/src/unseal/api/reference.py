"""Reference data routes (docs/api.md "Reference data"): rule values with their sources, and the
curated authority list. Read-only, but behind the session like everything else."""

from datetime import date
from typing import Any, get_args

from fastapi import APIRouter

from unseal.api.deps import CurrentUser
from unseal.api.errors import ApiError
from unseal.rules.authorities import lookup_authority
from unseal.rules.engine import Jurisdiction, load_rules, sources, stale_rules
from unseal.services.intake import AuthorityCandidate

router = APIRouter()


@router.get("/rules/{jurisdiction}")
async def rules(jurisdiction: str, _: CurrentUser) -> dict[str, Any]:
    if jurisdiction not in get_args(Jurisdiction):
        raise ApiError(404, "not_found")
    found = load_rules(jurisdiction)  # @cache erases the Literal; checked above
    local = found.local
    stale = set(stale_rules(found, date.today()))
    return {
        "application_fee": local.application_fee.rupees,
        "copy_fee_per_page": local.copy_fee_per_page.rupees,
        "word_limit": local.word_limit.words if local.word_limit else None,
        "payment_modes": list(local.payment_modes.modes),
        "filing_channels": list(local.filing_channels.channels),
        "bpl_certificate_required": local.bpl_certificate_required.applies,
        "sources": [
            {
                "rule": name,
                "basis": source.basis,
                "source_url": str(source.source_url),
                "checked_on": source.checked_on.isoformat(),
                "recheck": name in stale,
            }
            for name, source in sources(found).items()
        ],
    }


@router.get("/authorities")
async def authorities(
    _: CurrentUser, q: str = "", jurisdiction: Jurisdiction | None = None
) -> list[dict[str, Any]]:
    return [
        AuthorityCandidate.of(authority).model_dump()
        for authority in lookup_authority(q, jurisdiction)
    ]
