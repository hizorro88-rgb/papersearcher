"""Europe PMC REST 어댑터 (프리프린트 전용)."""
from __future__ import annotations

from datetime import date

from ..models import Item, Links, Source, make_id
from .base import SourceAdapter

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def parse_results(results: list[dict], today: date) -> list[Item]:
    items = []
    for r in results:
        doi = r.get("doi")
        pmid = r.get("pmid")
        src = r.get("source")
        is_preprint = src == "PPR"
        if not (doi or pmid or r.get("id")):
            continue
        url = f"https://europepmc.org/article/{src}/{r.get('id')}"
        if pmid and not is_preprint:
            item_id = make_id(pmid=pmid)
        else:
            item_id = make_id(doi=doi, url=url)
        items.append(Item(
            id=item_id,
            type="preprint" if is_preprint else "paper",
            title=(r.get("title") or "(제목 없음)").rstrip("."),
            abstract=r.get("abstractText"),
            published_at=r.get("firstPublicationDate"),
            authors=[a.strip() for a in (r.get("authorString") or "").split(",") if a.strip()][:8],
            source=Source(name="Europe PMC (preprint)" if is_preprint else "Europe PMC", url=url,
                          journal=r.get("journalTitle") or r.get("bookOrReportDetails", {}).get("publisher") if isinstance(r.get("bookOrReportDetails"), dict) else r.get("journalTitle")),
            links=Links(doi=doi, pmid=pmid, pmcid=r.get("pmcid")),
            pub_types=["Preprint"] if is_preprint else [],
            first_seen=today.isoformat(),
            last_updated=today.isoformat(),
        ))
    return items


class EuropePMCSource(SourceAdapter):
    name = "Europe PMC"

    def fetch(self, since: date, today: date, *, bootstrap: bool = False) -> list[Item]:
        query = " ".join(self.cfg["query"].split())
        query = f"({query}) AND (FIRST_PDATE:[{since.isoformat()} TO {today.isoformat()}])"
        r = self.client.get(API, params={"query": query, "format": "json", "resultType": "core",
                                         "pageSize": self.cfg.get("max_results", 100), "sort": "P_PDATE_D desc"})
        r.raise_for_status()
        return parse_results(r.json().get("resultList", {}).get("result", []), today)
