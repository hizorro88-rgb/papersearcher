"""PubMed E-utilities 어댑터 (esearch + efetch)."""
from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import date

from ..models import Item, Links, Source, make_id
from .base import SourceAdapter

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCT_RE = re.compile(r"NCT\d{8}")


def _text(el, path: str) -> str | None:
    node = el.find(path)
    if node is None:
        return None
    return "".join(node.itertext()).strip() or None


def _pub_date(article) -> str | None:
    """ArticleDate(전자출판) > PubDate 순으로 ISO 날짜를 만든다."""
    for path in ("Article/ArticleDate", "Article/Journal/JournalIssue/PubDate"):
        node = article.find(path)
        if node is None:
            continue
        y = _text(node, "Year")
        m = _text(node, "Month") or "01"
        d = _text(node, "Day") or "01"
        if not y:
            medline = _text(node, "MedlineDate")
            if medline and (mm := re.match(r"(\d{4})", medline)):
                y = mm.group(1)
            else:
                continue
        months = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
                  "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}
        m = months.get(m, m)
        try:
            return date(int(y), int(m), int(d)).isoformat()
        except ValueError:
            return f"{y}-01-01"
    return None


def parse_efetch_xml(xml_text: str, today: date) -> list[Item]:
    root = ET.fromstring(xml_text)
    items: list[Item] = []
    for art in root.findall("PubmedArticle"):
        medline = art.find("MedlineCitation")
        if medline is None:
            continue
        pmid = _text(medline, "PMID")
        title = _text(medline, "Article/ArticleTitle") or "(제목 없음)"
        abstract_parts = []
        for ab in medline.findall("Article/Abstract/AbstractText"):
            label = ab.get("Label")
            txt = "".join(ab.itertext()).strip()
            abstract_parts.append(f"{label}: {txt}" if label else txt)
        abstract = "\n".join(abstract_parts) or None
        journal = _text(medline, "Article/Journal/ISOAbbreviation") or _text(medline, "Article/Journal/Title")
        authors = []
        for a in medline.findall("Article/AuthorList/Author")[:8]:
            last, init = _text(a, "LastName"), _text(a, "Initials")
            if last:
                authors.append(f"{last} {init or ''}".strip())
        pub_types = [("".join(p.itertext())).strip() for p in medline.findall("Article/PublicationTypeList/PublicationType")]
        doi = None
        pmcid = None
        for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = (aid.text or "").strip() or None
            elif aid.get("IdType") == "pmc":
                pmcid = (aid.text or "").strip() or None
        ncts = sorted(set(NCT_RE.findall((abstract or "") + " ".join(
            (d.text or "") for d in medline.findall("Article/DataBankList/DataBank/AccessionNumberList/AccessionNumber")))))
        items.append(Item(
            id=make_id(pmid=pmid),
            type="paper",
            title=title.rstrip("."),
            abstract=abstract,
            published_at=_pub_date(medline),
            authors=authors,
            source=Source(name="PubMed", url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", journal=journal),
            links=Links(doi=doi, pmid=pmid, pmcid=pmcid, nct=ncts),
            pub_types=pub_types,
            first_seen=today.isoformat(),
            last_updated=today.isoformat(),
        ))
    return items


class PubMedSource(SourceAdapter):
    name = "PubMed"

    def _params(self, extra: dict) -> dict:
        p = {"db": "pubmed", "tool": "papersearcher", "email": "papersearcher@users.noreply.github.com"}
        key = os.environ.get(self.cfg.get("api_key_env", "NCBI_API_KEY"), "")
        if key:
            p["api_key"] = key
        p.update(extra)
        return p

    def fetch(self, since: date, today: date, *, bootstrap: bool = False) -> list[Item]:
        term = " ".join(self.cfg["term"].split())
        # [edat]=PubMed 등록일 기준: 과거 논문이 뒤늦게 색인돼도 잡힌다
        term = f"({term}) AND ({since:%Y/%m/%d}:{today:%Y/%m/%d}[edat])"
        r = self.client.get(f"{EUTILS}/esearch.fcgi", params=self._params({
            "term": term, "retmax": self.cfg.get("max_results", 300), "retmode": "json", "sort": "date"}))
        r.raise_for_status()
        ids = r.json()["esearchresult"].get("idlist", [])
        items: list[Item] = []
        for i in range(0, len(ids), 100):
            chunk = ids[i:i + 100]
            time.sleep(0.4)  # 키 없이 초당 3회 제한
            r = self.client.get(f"{EUTILS}/efetch.fcgi", params=self._params({
                "id": ",".join(chunk), "retmode": "xml"}))
            r.raise_for_status()
            items.extend(parse_efetch_xml(r.text, today))
        return items
