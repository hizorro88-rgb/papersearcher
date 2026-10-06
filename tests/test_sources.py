from datetime import date

from collector.sources.clinicaltrials import parse_study
from collector.sources.europepmc import parse_results
from collector.sources.pubmed import parse_efetch_xml

TODAY = date(2026, 10, 6)

PUBMED_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
<PubmedArticle>
 <MedlineCitation Status="MEDLINE" Owner="NLM">
  <PMID Version="1">41000001</PMID>
  <Article PubModel="Print-Electronic">
   <Journal><ISOAbbreviation>Lancet Oncol</ISOAbbreviation><Title>The Lancet. Oncology</Title>
    <JournalIssue><PubDate><Year>2026</Year><Month>Sep</Month><Day>30</Day></PubDate></JournalIssue></Journal>
   <ArticleTitle>Daraxonrasib in previously treated metastatic pancreatic ductal adenocarcinoma: a phase 3 randomised trial.</ArticleTitle>
   <Abstract>
    <AbstractText Label="BACKGROUND">KRAS mutations occur in most pancreatic cancers.</AbstractText>
    <AbstractText Label="FINDINGS">Median overall survival was 11.2 months versus 7.1 months (HR 0.62). NCT06625320.</AbstractText>
   </Abstract>
   <AuthorList><Author><LastName>Kim</LastName><Initials>J</Initials></Author><Author><LastName>Lee</LastName><Initials>S</Initials></Author></AuthorList>
   <PublicationTypeList><PublicationType>Journal Article</PublicationType><PublicationType>Clinical Trial, Phase III</PublicationType></PublicationTypeList>
  </Article>
 </MedlineCitation>
 <PubmedData><ArticleIdList><ArticleId IdType="pubmed">41000001</ArticleId><ArticleId IdType="doi">10.1016/S1470-2045(26)00001-X</ArticleId><ArticleId IdType="pmc">PMC12345678</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle>
</PubmedArticleSet>"""


def test_parse_pubmed():
    items = parse_efetch_xml(PUBMED_XML, TODAY)
    assert len(items) == 1
    it = items[0]
    assert it.id == "pmid:41000001"
    assert it.links.doi == "10.1016/S1470-2045(26)00001-X"
    assert it.links.nct == ["NCT06625320"]
    assert it.published_at == "2026-09-30"
    assert it.source.journal == "Lancet Oncol"
    assert "Clinical Trial, Phase III" in it.pub_types
    assert "FINDINGS:" in it.abstract
    assert it.authors == ["Kim J", "Lee S"]


CT_STUDY = {
    "hasResults": False,
    "protocolSection": {
        "identificationModule": {"nctId": "NCT06625320", "briefTitle": "RASolute 302: Daraxonrasib vs Chemotherapy in PDAC"},
        "statusModule": {"overallStatus": "RECRUITING", "startDateStruct": {"date": "2024-10"},
                         "primaryCompletionDateStruct": {"date": "2027-06"},
                         "lastUpdatePostDateStruct": {"date": "2026-10-01"},
                         "studyFirstPostDateStruct": {"date": "2024-10-03"}},
        "designModule": {"studyType": "INTERVENTIONAL", "phases": ["PHASE3"], "enrollmentInfo": {"count": 460}},
        "descriptionModule": {"briefSummary": "Compare daraxonrasib with standard chemotherapy."},
        "eligibilityModule": {"eligibilityCriteria": "Inclusion Criteria:\n* Metastatic PDAC\n\nExclusion Criteria:\n* Brain metastases",
                              "minimumAge": "18 Years", "sex": "ALL"},
        "armsInterventionsModule": {"interventions": [{"type": "DRUG", "name": "Daraxonrasib"}, {"type": "DRUG", "name": "Gemcitabine"}]},
        "conditionsModule": {"conditions": ["Pancreatic Ductal Adenocarcinoma"], "keywords": ["KRAS"]},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Revolution Medicines, Inc."}},
        "contactsLocationsModule": {
            "centralContacts": [{"name": "Study Director", "phone": "1-800-000-0000", "email": "trials@example.com"}],
            "locations": [
                {"facility": "Seoul National University Hospital", "city": "Seoul", "country": "Korea, Republic of", "status": "RECRUITING"},
                {"facility": "MD Anderson", "city": "Houston", "country": "United States"},
            ]},
    },
}


def test_parse_ct_study():
    it = parse_study(CT_STUDY, TODAY)
    assert it.id == "nct:NCT06625320"
    assert it.type == "trial"
    t = it.trial
    assert t.phase == "PHASE3" and t.status == "RECRUITING"
    assert t.interventions == ["Daraxonrasib", "Gemcitabine"]
    assert len(t.locations_kr) == 1 and t.locations_kr[0].city == "Seoul"
    assert t.location_countries == ["Korea, Republic of", "United States"]
    assert t.enrollment == 460
    assert t.contacts[0].email == "trials@example.com"
    assert it.published_at == "2024-10-03"


def test_parse_europepmc_preprint():
    res = [{"id": "PPR900001", "source": "PPR", "doi": "10.1101/2026.09.30.123456", "title": "Organoid screening in PDAC.",
            "abstractText": "We screened organoids.", "firstPublicationDate": "2026-10-01", "authorString": "A B, C D."}]
    items = parse_results(res, TODAY)
    assert items[0].id == "doi:10.1101/2026.09.30.123456"
    assert items[0].type == "preprint"
    assert items[0].source.name == "Europe PMC (preprint)"
