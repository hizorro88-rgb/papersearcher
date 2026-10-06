"""ClinicalTrials.gov API v2 어댑터."""
from __future__ import annotations

from datetime import date

from ..models import Item, Links, Source, TrialContact, TrialInfo, TrialLocation, make_id
from .base import SourceAdapter

API = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = ",".join([
    "NCTId", "BriefTitle", "OfficialTitle", "BriefSummary", "DetailedDescription", "OverallStatus",
    "Phase", "StudyType", "LeadSponsorName", "InterventionName", "InterventionType", "Condition",
    "EligibilityCriteria", "MinimumAge", "MaximumAge", "Sex", "EnrollmentCount", "StartDate",
    "PrimaryCompletionDate", "LastUpdatePostDate", "StudyFirstPostDate", "LocationFacility",
    "LocationCity", "LocationCountry", "LocationStatus", "CentralContactName", "CentralContactPhone",
    "CentralContactEMail", "HasResults", "Keyword",
])


def _listify(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def parse_study(s: dict, today: date) -> Item:
    proto = s.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status = proto.get("statusModule", {})
    design = proto.get("designModule", {})
    desc = proto.get("descriptionModule", {})
    elig = proto.get("eligibilityModule", {})
    arms = proto.get("armsInterventionsModule", {})
    cond = proto.get("conditionsModule", {})
    sponsor = proto.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name")
    contacts_mod = proto.get("contactsLocationsModule", {})

    nct = ident["nctId"]
    locations = contacts_mod.get("locations", []) or []
    countries = sorted({loc.get("country") for loc in locations if loc.get("country")})
    kr = [TrialLocation(facility=loc.get("facility"), city=loc.get("city"), country=loc.get("country"),
                        status=loc.get("status"))
          for loc in locations if loc.get("country") in ("Korea, Republic of", "South Korea")]
    contacts = [TrialContact(name=c.get("name"), phone=c.get("phone"), email=c.get("email"))
                for c in contacts_mod.get("centralContacts", []) or []][:2]
    interventions = [i.get("name") for i in arms.get("interventions", []) or [] if i.get("name")]
    phases = design.get("phases") or []
    phase = "/".join(phases) if phases else None
    enrollment = (design.get("enrollmentInfo") or {}).get("count")

    trial = TrialInfo(
        nct_id=nct,
        phase=phase,
        status=status.get("overallStatus"),
        study_type=design.get("studyType"),
        sponsor=sponsor,
        interventions=interventions,
        conditions=cond.get("conditions", []) or [],
        eligibility_text=elig.get("eligibilityCriteria"),
        min_age=elig.get("minimumAge"),
        max_age=elig.get("maximumAge"),
        sex=elig.get("sex"),
        enrollment=int(enrollment) if isinstance(enrollment, int) else None,
        start_date=(status.get("startDateStruct") or {}).get("date"),
        primary_completion_date=(status.get("primaryCompletionDateStruct") or {}).get("date"),
        has_results=bool(s.get("hasResults")),
        locations_kr=kr,
        location_countries=countries,
        n_locations=len(locations),
        contacts=contacts,
        last_update_posted=(status.get("lastUpdatePostDateStruct") or {}).get("date"),
    )
    summary = desc.get("briefSummary")
    if desc.get("detailedDescription"):
        summary = f"{summary or ''}\n\n{desc['detailedDescription']}".strip()
    posted = (status.get("studyFirstPostDateStruct") or {}).get("date")
    return Item(
        id=make_id(nct=nct),
        type="trial",
        title=ident.get("briefTitle") or ident.get("officialTitle") or nct,
        abstract=summary,
        published_at=posted,
        source=Source(name="ClinicalTrials.gov", url=f"https://clinicaltrials.gov/study/{nct}", journal=sponsor),
        links=Links(nct=[nct]),
        pub_types=[f"Trial:{phase or 'NA'}"],
        tags=[k for k in (cond.get("keywords") or [])[:10]],
        trial=trial,
        first_seen=today.isoformat(),
        last_updated=today.isoformat(),
    )


class ClinicalTrialsSource(SourceAdapter):
    name = "ClinicalTrials.gov"

    def _page(self, params: dict) -> list[dict]:
        studies: list[dict] = []
        token = None
        limit = params.pop("_limit")
        while len(studies) < limit:
            p = dict(params, pageSize=min(100, limit - len(studies)))
            if token:
                p["pageToken"] = token
            r = self.client.get(API, params=p)
            r.raise_for_status()
            data = r.json()
            studies.extend(data.get("studies", []))
            token = data.get("nextPageToken")
            if not token:
                break
        return studies

    def fetch(self, since: date, today: date, *, bootstrap: bool = False) -> list[Item]:
        base = {"query.cond": self.cfg["condition"], "fields": FIELDS, "format": "json",
                "filter.advanced": f"AREA[StudyType]INTERVENTIONAL"}
        studies: list[dict] = []
        if bootstrap and self.cfg.get("bootstrap_recruiting", True):
            studies += self._page(dict(base, _limit=self.cfg.get("bootstrap_max_results", 400),
                                       **{"filter.overallStatus": "RECRUITING,NOT_YET_RECRUITING,ENROLLING_BY_INVITATION",
                                          "filter.advanced": "AREA[StudyType]INTERVENTIONAL AND AREA[Phase](PHASE1 OR PHASE2 OR PHASE3)"}))
        studies += self._page(dict(base, _limit=self.cfg.get("max_results", 300),
                                   **{"filter.advanced": f"AREA[StudyType]INTERVENTIONAL AND AREA[LastUpdatePostDate]RANGE[{since.isoformat()},MAX]"}))
        seen: set[str] = set()
        items = []
        for s in studies:
            nct = s.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
            if not nct or nct in seen:
                continue
            seen.add(nct)
            items.append(parse_study(s, today))
        return items
