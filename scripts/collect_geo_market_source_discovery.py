#!/usr/bin/env python3
"""Discover country-level aesthetics market/statistics source pages.

The goal is to find official or association-grade sources that can extend the
commercial data backbone without mixing hard treatment-volume facts with weaker
channel or demand proxies.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import ssl
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from scrapling.fetchers import Fetcher
except Exception as exc:  # pragma: no cover - import guard for local runs
    raise SystemExit(f"Scrapling is required: {exc}") from exc


PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "data" / "commercial_sources" / "geo_market_sources"
AUDIT_DIR = PROJECT_DIR / "data" / "audits"
INVENTORY_PATH = AUDIT_DIR / "commercial_geo_market_source_discovery_latest.csv"
SUMMARY_PATH = AUDIT_DIR / "commercial_geo_market_source_discovery_latest.json"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/pdf,application/json,text/csv,application/octet-stream,*/*;q=0.8",
}

FIELDS = [
    "source_id",
    "region_group",
    "country_or_region",
    "source_name",
    "source_family",
    "authority_tier",
    "data_role",
    "metric_potential",
    "source_url",
    "source_page_title",
    "discovered_url",
    "link_text",
    "year",
    "artifact_type",
    "status",
    "http_status",
    "content_type",
    "local_path",
    "sha256",
    "bytes",
    "captured_at",
    "note",
]


@dataclass(frozen=True)
class SourceSeed:
    source_id: str
    region_group: str
    country_or_region: str
    source_name: str
    source_family: str
    authority_tier: str
    data_role: str
    metric_potential: str
    url: str
    mode: str = "html"
    link_keywords: tuple[str, ...] = field(default_factory=tuple)
    fallback_links: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    note: str = ""


SOURCE_SEEDS = [
    SourceSeed(
        source_id="korea_mohw_foreign_patient_stats",
        region_group="Asia",
        country_or_region="South Korea",
        source_name="MOHW foreign patient attraction statistics",
        source_family="official_government_statistics",
        authority_tier="official_government",
        data_role="medical_tourism_specialty_proxy",
        metric_potential="annual foreign-patient counts by specialty; dermatology/plastic surgery demand proxy",
        url="https://www.mohw.go.kr/board.es?act=view&bid=0027&list_no=1490280&mid=a10503010100&nPage=1&tag=",
        link_keywords=("download", "boarddownload", "외국인", "환자", "pdf", "hwpx", "통계"),
        note="Proxy for cross-border demand and specialty mix; do not use as domestic treatment volume.",
    ),
    SourceSeed(
        source_id="korea_khiss_health_industry_stats",
        region_group="Asia",
        country_or_region="South Korea",
        source_name="KHISS health industry statistics portal",
        source_family="official_government_statistics_portal",
        authority_tier="official_government",
        data_role="health_industry_portal",
        metric_potential="health industry and medical-tourism statistical tables where public endpoints are exposed",
        url="https://www.khiss.go.kr/",
        link_keywords=("외국인", "환자", "통계", "의료관광", "stats", "khidi"),
        note="Use as a follow-up endpoint for structured Korea tables after page/API mapping.",
    ),
    SourceSeed(
        source_id="taiwan_mohw_aesthetic_medicine_institutions",
        region_group="Asia",
        country_or_region="Taiwan",
        source_name="MOHW aesthetic medicine information area",
        source_family="official_government_provider_statistics",
        authority_tier="official_government",
        data_role="provider_channel_density_proxy",
        metric_potential="approved institutions for specific aesthetic medicine surgery/procedures; quality certification links",
        url="https://dep.mohw.gov.tw/DOMA/lp-3240-106.html",
        link_keywords=("美容醫學", "醫療機構", "品質", "認證", "名單", "查詢", "dl-", "pdf", "ods", "資料"),
        note="Provider/institution coverage proxy; not procedure count.",
    ),
    SourceSeed(
        source_id="taiwan_mohw_medical_facility_open_data",
        region_group="Asia",
        country_or_region="Taiwan",
        source_name="MOHW medical institution and personnel open data",
        source_family="official_government_open_data",
        authority_tier="official_government",
        data_role="provider_denominator",
        metric_potential="medical institution and personnel master data for city/provider denominators",
        url="https://dep.mohw.gov.tw/DOMA/np-4926-106.html",
        link_keywords=("醫療機構", "基本資料", "ods", "資料", "下載"),
        note="Use as denominator/enrichment for Taiwan channel density.",
    ),
    SourceSeed(
        source_id="hong_kong_dh_day_procedure_centres",
        region_group="Asia",
        country_or_region="Hong Kong",
        source_name="DATA.GOV.HK licensed day procedure centres",
        source_family="official_government_open_data",
        authority_tier="official_government",
        data_role="provider_channel_density_proxy",
        metric_potential="licensed day procedure centres; specialty and address fields in CSV where available",
        url="https://data.gov.hk/en-data/api/3/action/package_show?id=hk-dh-dh_hq-dh-orphf-dpcl",
        mode="ckan_package",
        note="Channel/provider proxy under Private Healthcare Facilities Ordinance; not procedure count.",
    ),
    SourceSeed(
        source_id="hong_kong_dh_medical_beauty_guidance",
        region_group="Asia",
        country_or_region="Hong Kong",
        source_name="Department of Health medical beauty guidance",
        source_family="official_government_guidance",
        authority_tier="official_government",
        data_role="regulatory_context_proxy",
        metric_potential="procedure boundary definitions and regulatory context for medical beauty services",
        url="https://www.dh.gov.hk/english/useful/useful_medical_beauty/useful_medical_beauty.html",
        link_keywords=("beauty", "medical", "cosmetic", "procedure", "pdf", "booklet"),
        note="Regulatory context only; useful for scope definitions and channel classification.",
    ),
    SourceSeed(
        source_id="hong_kong_consumer_medical_beauty_complaints",
        region_group="Asia",
        country_or_region="Hong Kong",
        source_name="Consumer Council medical beauty regulation/complaints release",
        source_family="statutory_consumer_research",
        authority_tier="public_statutory_consumer_body",
        data_role="consumer_risk_heat_proxy",
        metric_potential="complaints and consumer-protection signals for medical beauty services",
        url="https://www.consumer.org.hk/en/press-release/medical-beauty",
        link_keywords=("beauty", "medical", "complaint", "survey", "pdf"),
        note="Use only as heat/risk proxy, not market size or treatment volume.",
    ),
    SourceSeed(
        source_id="brazil_sbcp_surgeon_locator",
        region_group="Latin America",
        country_or_region="Brazil",
        source_name="SBCP surgeon locator",
        source_family="professional_association_provider_locator",
        authority_tier="official_association",
        data_role="surgeon_density_proxy",
        metric_potential="member plastic surgeons by location if accessible; channel/professional density proxy",
        url="https://www.cirurgiaplastica.org.br/encontre-um-cirurgiao/",
        link_keywords=("cirurg", "estado", "buscar", "associado", "membro", "pdf", "censo"),
        note="Official association locator; follow-up needs form/endpoint mapping for state-level member counts.",
    ),
    SourceSeed(
        source_id="brazil_sbcp_pesquisas_censo",
        region_group="Latin America",
        country_or_region="Brazil",
        source_name="SBCP pesquisas and censo publications",
        source_family="official_association_statistics",
        authority_tier="official_association",
        data_role="treatment_volume_candidate_and_surgeon_demography",
        metric_potential="SBCP censo/demography publications and linked ISAPS Brazil/global reports",
        url="https://www.cirurgiaplastica.org.br/pesquisas/",
        link_keywords=("censo", "pesquisa", "estat", "isaps", "fliphtml5", "pdf", "2025", "2018", "2017", "proced"),
        fallback_links=(
            ("SBCP Pesquisas page", "https://www.cirurgiaplastica.org.br/pesquisas/"),
            ("PLASTIKO'S - DEMOGRAFIA 2025 flipbook", "https://online.fliphtml5.com/urtuw/REVISTA_CENSO_2025_V06/#p=1"),
            ("SBCP Censo 2018 PDF", "http://www2.cirurgiaplastica.org.br/wp-content/uploads/2019/08/Apresentac%CC%A7a%CC%83o-Censo-2018_V3.pdf"),
            ("SBCP CENSO 2017 PDF", "http://www2.cirurgiaplastica.org.br/wp-content/uploads/2017/12/CENSO-2017.pdf"),
            ("ISAPS Global Survey 2022 linked from SBCP", "https://www.isaps.org/media/a0qfm4h3/isaps-global-survey_2022.pdf"),
        ),
        note="Official association research page. 2025 item is a FlipHTML5 demography/censo publication and needs structure QA before extraction.",
    ),
    SourceSeed(
        source_id="brazil_cfm_medical_demography",
        region_group="Latin America",
        country_or_region="Brazil",
        source_name="CFM medical demography and specialty data",
        source_family="official_professional_registry_statistics",
        authority_tier="official_professional_council",
        data_role="surgeon_denominator_proxy",
        metric_potential="physicians by specialty, including plastic surgery, and state-level medical density",
        url="https://portal.cfm.org.br/",
        link_keywords=("demografia", "médica", "medica", "observatorio", "flip3d", "2024", "2023"),
        note="Strong denominator for provider density; not aesthetic procedure volume.",
    ),
    SourceSeed(
        source_id="uk_baaps_annual_audit",
        region_group="Europe",
        country_or_region="United Kingdom",
        source_name="BAAPS annual audit results",
        source_family="official_association_statistics",
        authority_tier="official_association",
        data_role="treatment_volume_country_year",
        metric_potential="annual cosmetic surgery audit by procedure; UK country-level procedure trend",
        url="https://baaps.org.uk/baaps_annual_audit_results_.aspx",
        link_keywords=("audit", "annual", "results", "pdf", "2020", "2021", "2022", "2023", "2024", "2025"),
        note="High-value phase-1 source; methodology is BAAPS member/audit based and should remain source-labeled.",
    ),
    SourceSeed(
        source_id="germany_dgaepc_statistics",
        region_group="Europe",
        country_or_region="Germany",
        source_name="DGÄPC statistics",
        source_family="official_association_statistics",
        authority_tier="official_association",
        data_role="procedure_mix_country_year",
        metric_potential="annual German aesthetic-plastic surgery statistics and patient survey PDFs",
        url="https://www.dgaepc.de/aktuelles/dgaepc-statistik/",
        link_keywords=("statistik", "pdf", "2020", "2021", "2022", "2023", "2024", "2025", "patientenbefragung"),
        note="Useful Europe country-level companion; verify whether counts are procedure volume or survey shares before loading to market_metrics.",
    ),
    SourceSeed(
        source_id="japan_mhlw_aesthetic_medicine_status",
        region_group="Asia",
        country_or_region="Japan",
        source_name="MHLW aesthetic medicine status materials",
        source_family="official_government_statistics",
        authority_tier="official_government",
        data_role="physician_specialty_demand_proxy",
        metric_potential="clinic physician counts by cosmetic surgery, plastic surgery and dermatology; regulatory and procedure-scope context",
        url="https://www.mhlw.go.jp/content/10803000/001363278.pdf",
        mode="direct_artifact",
        note="Official MHLW material for aesthetic medicine status. Use as physician/specialty demand proxy; not treatment volume.",
    ),
    SourceSeed(
        source_id="japan_mhlw_medical_info_net",
        region_group="Asia",
        country_or_region="Japan",
        source_name="MHLW Medical Information Net provider search",
        source_family="official_government_provider_locator",
        authority_tier="official_government",
        data_role="provider_channel_density_proxy",
        metric_potential="national medical institution search with specialty filters such as plastic surgery and cosmetic surgery",
        url="https://www.iryou.teikyouseido.mhlw.go.jp/znk-web/juminkanja/S2340/initialize",
        link_keywords=("美容外科", "形成外科", "医療機関", "診療科", "search", "initialize"),
        note="Provider locator proxy. Follow-up needs query/form endpoint mapping before city-level counts.",
    ),
    SourceSeed(
        source_id="france_cnom_medical_demography_atlas",
        region_group="Europe",
        country_or_region="France",
        source_name="CNOM medical demography atlas",
        source_family="official_professional_registry_statistics",
        authority_tier="official_professional_council",
        data_role="surgeon_denominator_proxy",
        metric_potential="physician and surgical-specialty demography by region/department; denominator for provider-density work",
        url="https://www.conseil-national.medecin.fr/sites/default/files/cnom_atlas_demographie_2025_tome_1.pdf",
        mode="direct_artifact",
        note="Strong official denominator source for France. Use for physician/surgical-specialty density, not aesthetic procedure volume.",
    ),
    SourceSeed(
        source_id="france_sofcep_surgery_context",
        region_group="Europe",
        country_or_region="France",
        source_name="SOFCEP plastic and aesthetic surgery in France",
        source_family="official_association_context",
        authority_tier="official_association",
        data_role="surgeon_density_context_proxy",
        metric_potential="association context and qualified surgeon count statement for France",
        url="https://sofcep.fr/en/surgery/",
        link_keywords=("statistics", "surgeons", "National Council", "aesthetic", "surgery", "France", "pdf"),
        note="Association context for surgeon-density interpretation; verify against CNOM before using as numeric denominator.",
    ),
    SourceSeed(
        source_id="spain_secpre_aesthetic_surgery_report",
        region_group="Europe",
        country_or_region="Spain",
        source_name="SECPRE aesthetic surgery reality in Spain report",
        source_family="official_association_statistics",
        authority_tier="official_association",
        data_role="treatment_volume_country_year_candidate",
        metric_potential="Spain aesthetic surgery report with procedure, patient and market-context tables where extractable",
        url="https://portalsecpre.org/images/noticias/Informe%20SECPRE_IMOP%202022%20prensa.pdf",
        mode="direct_artifact",
        note="High-value Spain phase-1 candidate. QA required before loading count-like metrics into market_metrics.",
    ),
    SourceSeed(
        source_id="italy_aicpe_observatory_statistics",
        region_group="Europe",
        country_or_region="Italy",
        source_name="AICPE observatory and statistics",
        source_family="official_association_statistics",
        authority_tier="official_association",
        data_role="treatment_volume_country_year_candidate",
        metric_potential="Italy procedure totals and procedure-mix commentary; AICPE statistics archive links",
        url="https://www.aicpe.org/2022/02/comunicato-stampa-osservatorio-aicpe-come-ha-inciso-la-pandemia-sui-numeri-della-chirurgia-plastica-estetica/",
        link_keywords=("statistiche", "Statistiche", "ISAPS", "procedure", "chirurgia", "pdf", "2019", "2020", "2021", "2022", "2023", "2024"),
        fallback_links=(("AICPE statistics archive", "https://www.aicpe.org/press-2/statistiche/"),),
        note="Association observatory source. Treat 2020/2019 procedure totals as candidate rows until methodology/source-label QA is complete.",
    ),
    SourceSeed(
        source_id="italy_sicpre_isaps_statistics",
        region_group="Europe",
        country_or_region="Italy",
        source_name="SICPRE ISAPS report commentary",
        source_family="official_association_statistics_commentary",
        authority_tier="official_association",
        data_role="treatment_volume_secondary_isaps_commentary",
        metric_potential="Italian association commentary on ISAPS global survey and Italy-specific page references",
        url="https://www.sicpre.it/report-2023-isaps-le-procedure-non-invasive-guidano-la-crescita-mondiale/",
        link_keywords=("ISAPS", "report", "procedure", "Italia", "2023", "2024", "pdf"),
        note="Secondary national association commentary on ISAPS. Keep separate from primary ISAPS PDF extraction.",
    ),
    SourceSeed(
        source_id="israel_plastic_surgery_society_news",
        region_group="Middle East",
        country_or_region="Israel",
        source_name="Israel Society of Plastic and Aesthetic Surgery news and locator",
        source_family="official_association_news_locator",
        authority_tier="official_association",
        data_role="association_survey_interest_proxy",
        metric_potential="association survey/news signals and specialist locator links for Israel",
        url="https://www.plasticsurgery.org.il/",
        link_keywords=("סקר", "ניתוחים", "אסתט", "טיפולים", "2026", "2025", "רופאים", "מפתח", "pdf"),
        note="Current evidence is association news/survey and locator context. Use only as interest/channel proxy until official procedure tables are found.",
    ),
    SourceSeed(
        source_id="israel_ima_society_context",
        region_group="Middle East",
        country_or_region="Israel",
        source_name="IMAJ Plastic Surgery in Israel issue context",
        source_family="official_medical_association_journal",
        authority_tier="official_medical_association",
        data_role="association_context_proxy",
        metric_potential="specialty context and society references for Israeli plastic and aesthetic surgery",
        url="https://www.ima.org.il/medicineIMAJ/Article.aspx?aId=6650",
        link_keywords=("Plastic Surgery", "Israel", "aesthetic", "PDF", "Full article", "society"),
        note="Context source only; useful for source discovery and Israel society grounding, not treatment volume.",
    ),
    SourceSeed(
        source_id="asps_plastic_surgery_statistics",
        region_group="North America",
        country_or_region="USA",
        source_name="American Society of Plastic Surgeons statistics",
        source_family="official_association_statistics",
        authority_tier="official_association",
        data_role="treatment_volume_country_year",
        metric_potential="US procedure trends, regional distribution, average fees, age and gender splits",
        url="https://www.plasticsurgery.org/news/plastic-surgery-statistics",
        note="Primary US association statistics lane. PDFs are collected by the phase-1 official-source script; this row exposes the country source card.",
    ),
    SourceSeed(
        source_id="aesthetic_society_statistics",
        region_group="North America",
        country_or_region="USA",
        source_name="The Aesthetic Society procedural statistics",
        source_family="official_association_statistics",
        authority_tier="official_association",
        data_role="treatment_volume_country_year",
        metric_potential="US aesthetic plastic surgery procedural statistics and billing/value context",
        url="https://www.theaestheticsociety.org/media/procedural-statistics",
        note="US private-practice/aesthetic-surgery methodology lane; keep separate from ASPS and ISAPS.",
    ),
    SourceSeed(
        source_id="cms_open_payments",
        region_group="North America",
        country_or_region="USA",
        source_name="CMS Open Payments",
        source_family="official_government_payments",
        authority_tier="official_government",
        data_role="company_physician_touchpoint_proxy",
        metric_potential="company-to-physician payment and engagement signals by reporting entity, specialty, state and year",
        url="https://openpaymentsdata.cms.gov/about/api",
        note="US channel/KOL touchpoint proxy. Use aggregate payment and physician-count rows, not as treatment volume.",
    ),
    SourceSeed(
        source_id="switzerland_fmh_physician_statistics",
        region_group="Europe",
        country_or_region="Switzerland",
        source_name="FMH physician statistics interactive dashboard",
        source_family="official_professional_registry_statistics",
        authority_tier="official_professional_association",
        data_role="surgeon_denominator_proxy",
        metric_potential="physicians by main specialty and gender; plastic surgery denominator for Swiss channel density",
        url="https://aerztestatistik.fmh.ch/",
        mode="direct_reference",
        note="Official FMH physician-statistics entry point. Denominator only; not aesthetic procedure volume.",
    ),
    SourceSeed(
        source_id="switzerland_plastic_surgery_society",
        region_group="Europe",
        country_or_region="Switzerland",
        source_name="Swiss Society for Plastic, Reconstructive and Aesthetic Surgery",
        source_family="official_association_context",
        authority_tier="official_association",
        data_role="association_context_proxy",
        metric_potential="national society context, member/quality links and provider-discovery path",
        url="https://plasticsurgery.ch/en/",
        link_keywords=("members", "surgeon", "quality", "statistics", "aesthetic", "plastic", "pdf"),
        note="Association context and provider-discovery path. Use for channel/professional context only unless statistics are exposed.",
    ),
    SourceSeed(
        source_id="czech_nrpzs_provider_registry",
        region_group="Europe",
        country_or_region="Czech Republic",
        source_name="Czech NRPZS healthcare provider registry",
        source_family="official_government_provider_registry",
        authority_tier="official_government",
        data_role="provider_channel_density_proxy",
        metric_potential="healthcare provider registry with care-profile and specialty fields including plastic surgery",
        url="https://nrpzs.uzis.cz/",
        mode="direct_reference",
        link_keywords=("plastick", "chirurgie", "poskytovatel", "detail", "registr", "specializ"),
        note="Official provider-density proxy. Follow-up should query/aggregate provider records by specialty and geography.",
    ),
    SourceSeed(
        source_id="czech_cspch_society_context",
        region_group="Europe",
        country_or_region="Czech Republic",
        source_name="Czech Society of Plastic Surgery",
        source_family="official_association_context",
        authority_tier="official_association",
        data_role="association_context_proxy",
        metric_potential="national society reference and official website path via EASAPS/ESAPS",
        url="https://esaps.eu/society/12",
        link_keywords=("Official website", "Czech", "Plastic", "Surgery", "society"),
        note="Association context and national-society discovery path; not treatment volume.",
    ),
    SourceSeed(
        source_id="canada_cihi_physician_specialty",
        region_group="North America",
        country_or_region="Canada",
        source_name="CIHI physicians per 100,000 population by specialty",
        source_family="official_health_workforce_statistics",
        authority_tier="official_health_data_agency",
        data_role="surgeon_denominator_proxy",
        metric_potential="physician density by specialty and year; Canada health-workforce denominator",
        url="https://www.cihi.ca/en/indicators/physicians-per-100000-population-by-specialty",
        link_keywords=("data", "download", "specialty", "physicians", "table", "xlsx", "csv", "methodology"),
        note="Official denominator source for Canada. Use as physician/specialty density, not procedure volume.",
    ),
    SourceSeed(
        source_id="canada_csps_society_context",
        region_group="North America",
        country_or_region="Canada",
        source_name="Canadian Society of Plastic Surgeons",
        source_family="official_association_context",
        authority_tier="official_association",
        data_role="association_context_proxy",
        metric_potential="national plastic-surgery society context and member scale statement",
        url="https://plasticsurgery.ca/",
        link_keywords=("surgeon", "member", "statistics", "annual", "profile", "find"),
        note="Association context for Canada; current source is not a treatment-volume table.",
    ),
    SourceSeed(
        source_id="canada_csaps_surgeon_locator",
        region_group="North America",
        country_or_region="Canada",
        source_name="Canadian Society for Aesthetic Plastic Surgery surgeon locator",
        source_family="official_association_provider_locator",
        authority_tier="official_association",
        data_role="surgeon_density_proxy",
        metric_potential="aesthetic plastic surgeon locator by Canadian area/province",
        url="https://csaps.ca/general-information/find-a-csaps-surgeon/",
        link_keywords=("surgeon", "locator", "member", "province", "city", "aesthetic"),
        note="Aesthetic-surgeon locator proxy. Store aggregate geography counts only.",
    ),
    SourceSeed(
        source_id="poland_nil_physician_statistics",
        region_group="Europe",
        country_or_region="Poland",
        source_name="NIL Central Register of Physicians statistics",
        source_family="official_professional_registry_statistics",
        authority_tier="official_professional_council",
        data_role="surgeon_denominator_proxy",
        metric_potential="physician register statistical tables; specialty denominator including plastic surgery where available",
        url="https://nil.org.pl/rejestry/centralny-rejestr-lekarzy/informacje-statystyczne",
        link_keywords=("Zestawienie", "specjalizacji", "chirurgia", "plastyczna", "xlsx", "xls", "pdf"),
        note="Official Polish physician-register statistics. Use as specialist denominator, not procedure volume.",
    ),
    SourceSeed(
        source_id="poland_ptchprie_surgeon_locator",
        region_group="Europe",
        country_or_region="Poland",
        source_name="Polish Society of Plastic, Reconstructive and Aesthetic Surgery locator",
        source_family="official_association_provider_locator",
        authority_tier="official_association",
        data_role="surgeon_density_proxy",
        metric_potential="plastic surgeon finder and hospital-department list for Poland",
        url="https://www.ptchprie.pl/znajdz_lekarza.html",
        link_keywords=("lekarz", "chirurg", "oddzia", "map", "specjal", "szpital"),
        note="Official association locator/channel proxy. Use aggregate counts only.",
    ),
    SourceSeed(
        source_id="sweden_socialstyrelsen_hosp_register",
        region_group="Europe",
        country_or_region="Sweden",
        source_name="Socialstyrelsen HOSP authorised healthcare professionals register",
        source_family="official_government_professional_registry",
        authority_tier="official_government",
        data_role="surgeon_denominator_proxy",
        metric_potential="authorised healthcare professionals and specialist register context for Sweden",
        url="https://www.socialstyrelsen.se/en/statistics-and-data/registers/the-register-of-authorised-healthcare-professionals-hosp/",
        link_keywords=("statistics", "register", "specialist", "data", "healthcare professionals"),
        note="Official professional-register context. Use for denominator mapping if specialty extracts are available.",
    ),
    SourceSeed(
        source_id="sweden_spkf_society_context",
        region_group="Europe",
        country_or_region="Sweden",
        source_name="Swedish Association of Plastic Surgeons",
        source_family="official_association_context",
        authority_tier="official_association",
        data_role="association_context_proxy",
        metric_potential="Swedish plastic-surgery society context for specialists, training and quality",
        url="https://slf.se/spkf/",
        link_keywords=("plastikkirurgi", "medlem", "statistik", "verksamhets", "pdf"),
        note="National society context only unless statistics are exposed.",
    ),
    SourceSeed(
        source_id="sweden_sfep_surgeon_locator",
        region_group="Europe",
        country_or_region="Sweden",
        source_name="Swedish Society for Aesthetic Plastic Surgery",
        source_family="official_association_provider_locator",
        authority_tier="official_association",
        data_role="surgeon_density_proxy",
        metric_potential="aesthetic plastic surgeon locator and association member context",
        url="https://sfep.se/",
        link_keywords=("Sök kirurg", "kirurg", "medlemmar", "plastikkirurgi", "estetisk"),
        note="Aesthetic-surgeon locator proxy. Store aggregate geography counts only.",
    ),
]


def now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def safe_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())


def slugify(value: str, fallback: str = "source") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._").lower()
    return text[:140] or fallback


def infer_year(text: str, url: str) -> str:
    combo = re.search(r"\b(20\d{2})\s*[-_/]\s*(20\d{2})\b", f"{text} {url}")
    if combo:
        return f"{combo.group(1)}-{combo.group(2)}"
    match = re.search(r"\b(20\d{2})\b", f"{text} {url}")
    return match.group(1) if match else ""


def filename_from_content_disposition(value: str) -> str:
    match = re.search(r"filename\*=UTF-8''([^;]+)", value or "", flags=re.I)
    if match:
        return unquote(match.group(1).strip().strip('"'))
    match = re.search(r"filename=\"?([^\";]+)", value or "", flags=re.I)
    if match:
        return unquote(match.group(1).strip().strip('"'))
    return ""


def infer_suffix(url: str, content_type: str = "", content_disposition: str = "") -> str:
    cd_name = filename_from_content_disposition(content_disposition)
    suffix = Path(cd_name).suffix.lower() if cd_name else ""
    if not suffix:
        suffix = Path(urlparse(url).path).suffix.lower()
    if suffix:
        return suffix
    lower = (content_type or "").lower()
    if "pdf" in lower:
        return ".pdf"
    if "csv" in lower:
        return ".csv"
    if "json" in lower:
        return ".json"
    if "spreadsheet" in lower or "opendocument" in lower:
        return ".ods"
    if "html" in lower:
        return ".html"
    if "octet-stream" in lower:
        return ".bin"
    return ".html"


def infer_artifact_type(url: str, link_text: str = "", content_type: str = "") -> str:
    suffix = infer_suffix(url, content_type)
    if suffix in {".pdf", ".csv", ".ods", ".xlsx", ".xls", ".json", ".hwpx", ".hwp"}:
        return suffix.lstrip(".")
    lower = f"{url} {link_text}".lower()
    if "boarddownload" in lower or "/dl-" in lower:
        return "download"
    return "html_link"


def should_download(url: str, artifact_type: str) -> bool:
    lower = url.lower()
    if "www2.cirurgiaplastica.org.br/wp-content/uploads" in lower:
        return False
    return artifact_type in {"pdf", "csv", "ods", "xlsx", "xls", "json", "hwpx", "hwp", "download"} or any(
        marker in lower for marker in ["boarddownload", "/dl-", "datagovhk"]
    )


def relevant_link(seed: SourceSeed, href: str, text: str) -> bool:
    if not seed.link_keywords:
        return False
    haystack = f"{href} {text}".lower()
    if any(token in haystack for token in ["privacy", "privacidade", "cookie", "termos-de-uso"]):
        return False
    return any(keyword.lower() in haystack for keyword in seed.link_keywords)


def make_base_row(seed: SourceSeed, discovered_url: str, link_text: str, artifact_type: str, status: str) -> dict[str, str]:
    return {
        "source_id": seed.source_id,
        "region_group": seed.region_group,
        "country_or_region": seed.country_or_region,
        "source_name": seed.source_name,
        "source_family": seed.source_family,
        "authority_tier": seed.authority_tier,
        "data_role": seed.data_role,
        "metric_potential": seed.metric_potential,
        "source_url": seed.url,
        "source_page_title": "",
        "discovered_url": discovered_url,
        "link_text": link_text,
        "year": infer_year(link_text, discovered_url),
        "artifact_type": artifact_type,
        "status": status,
        "http_status": "",
        "content_type": "",
        "local_path": "",
        "sha256": "",
        "bytes": "",
        "captured_at": now_iso(),
        "note": seed.note,
    }


def local_path_for(row: dict[str, str], suffix: str) -> Path:
    year = slugify(row.get("year") or "unknown-year")
    artifact = slugify(row.get("artifact_type") or "artifact")
    label = slugify(row.get("link_text") or Path(urlparse(row.get("discovered_url", "")).path).stem or "source")[:72]
    short_hash = hashlib.sha1(row.get("discovered_url", "").encode("utf-8")).hexdigest()[:8]
    return RAW_DIR / row["source_id"] / f"{year}__{artifact}__{label}__{short_hash}{suffix}"


def download_url(row: dict[str, str]) -> dict[str, str]:
    request = Request(row["discovered_url"], headers=REQUEST_HEADERS)
    ssl_fallback = False
    try:
        with urlopen(request, timeout=75) as response:
            body = response.read()
            content_type = safe_text(response.headers.get("content-type", ""))
            content_disposition = safe_text(response.headers.get("content-disposition", ""))
            final_url = response.geturl()
            http_status = str(response.status)
    except Exception as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            row.update({"status": "download_failed", "note": f"{row.get('note', '')} | {type(exc).__name__}: {exc}".strip(" |")})
            return row
        try:
            request = Request(row["discovered_url"], headers=REQUEST_HEADERS)
            with urlopen(request, timeout=75, context=ssl._create_unverified_context()) as response:
                body = response.read()
                content_type = safe_text(response.headers.get("content-type", ""))
                content_disposition = safe_text(response.headers.get("content-disposition", ""))
                final_url = response.geturl()
                http_status = str(response.status)
                ssl_fallback = True
        except Exception as retry_exc:
            row.update({"status": "download_failed", "note": f"{row.get('note', '')} | {type(retry_exc).__name__}: {retry_exc}".strip(" |")})
            return row

    suffix = infer_suffix(final_url, content_type, content_disposition)
    target = local_path_for(row, suffix)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    row.update(
        {
            "discovered_url": final_url,
            "artifact_type": infer_artifact_type(final_url, row.get("link_text", ""), content_type),
            "status": "downloaded",
            "http_status": http_status,
            "content_type": content_type,
            "local_path": str(target.relative_to(PROJECT_DIR)),
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": str(len(body)),
            "captured_at": now_iso(),
        }
    )
    if ssl_fallback:
        row["note"] = f"{row.get('note', '')} | ssl_unverified_download_fallback".strip(" |")
    return row


def fetch_html_seed(fetcher: Fetcher, seed: SourceSeed, no_download: bool) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    page = None
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            page = fetcher.get(seed.url, timeout=45, follow_redirects=True)
            break
        except Exception as exc:
            last_exc = exc
            time.sleep(1.5 * (attempt + 1))
    if page is None:
        row = make_base_row(seed, seed.url, "", "html_source_page", "fetch_failed")
        row["note"] = f"{seed.note} | {type(last_exc).__name__}: {last_exc}".strip(" |")
        rows.append(row)
        for link_text, link_url in seed.fallback_links:
            artifact_type = infer_artifact_type(link_url, link_text)
            fallback_row = make_base_row(seed, link_url, link_text, artifact_type, "fallback_discovered")
            fallback_row["note"] = f"{seed.note} | fallback link retained after live fetch failure"
            rows.append(fallback_row)
        return rows

    title_node = page.css_first("title")
    title = safe_text(getattr(title_node, "text", "")) if title_node else ""
    page_status = str(getattr(page, "status", ""))
    content_type = safe_text(getattr(page, "headers", {}).get("content-type", ""))
    page_row = make_base_row(seed, seed.url, "", "html_source_page", "fetched" if page_status.startswith("2") else "fetch_http_error")
    page_row.update({"source_page_title": title, "http_status": page_status, "content_type": content_type})
    rows.append(page_row)

    seen: set[str] = set()
    for anchor in page.css("a"):
        text = safe_text(getattr(anchor, "text", ""))
        href = safe_text(anchor.attrib.get("href", ""))
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        url = urljoin(seed.url, href)
        if not relevant_link(seed, url, text):
            continue
        key = url.split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        artifact_type = infer_artifact_type(url, text)
        row = make_base_row(seed, url, text, artifact_type, "discovered")
        row["source_page_title"] = title
        if not no_download and should_download(url, artifact_type):
            row = download_url(row)
        rows.append(row)
    return rows


def fetch_ckan_seed(seed: SourceSeed, no_download: bool) -> list[dict[str, str]]:
    request = Request(seed.url, headers=REQUEST_HEADERS)
    rows: list[dict[str, str]] = []
    package_row = make_base_row(seed, seed.url, "CKAN package metadata", "json", "fetch_failed")
    try:
        with urlopen(request, timeout=45) as response:
            body = response.read()
            payload = json.loads(body.decode("utf-8"))
            package_row.update(
                {
                    "status": "downloaded",
                    "http_status": str(response.status),
                    "content_type": safe_text(response.headers.get("content-type", "")),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "bytes": str(len(body)),
                    "captured_at": now_iso(),
                }
            )
            target = local_path_for(package_row, ".json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            package_row["local_path"] = str(target.relative_to(PROJECT_DIR))
    except Exception as exc:
        package_row["note"] = f"{seed.note} | {type(exc).__name__}: {exc}".strip(" |")
        rows.append(package_row)
        return rows

    rows.append(package_row)
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    package_title = safe_text(result.get("title") or result.get("name") or "")
    for resource in result.get("resources", []) or []:
        resource_url = safe_text(resource.get("url", ""))
        if not resource_url:
            continue
        link_text = safe_text(resource.get("name") or resource.get("description") or resource_url)
        artifact_type = safe_text(resource.get("format", "")).lower() or infer_artifact_type(resource_url, link_text)
        row = make_base_row(seed, resource_url, link_text, artifact_type, "discovered")
        row["source_page_title"] = package_title
        if not no_download:
            row = download_url(row)
        rows.append(row)
    return rows


def fetch_direct_artifact_seed(seed: SourceSeed, no_download: bool) -> list[dict[str, str]]:
    artifact_type = infer_artifact_type(seed.url, seed.source_name)
    row = make_base_row(seed, seed.url, seed.source_name, artifact_type, "discovered")
    if not no_download and should_download(seed.url, artifact_type):
        row = download_url(row)
    return [row]


def fetch_direct_reference_seed(seed: SourceSeed) -> list[dict[str, str]]:
    row = make_base_row(seed, seed.url, seed.source_name, "html_source_page", "reference_confirmed")
    row["note"] = seed.note
    row["captured_at"] = now_iso()
    return [row]


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def summarize(rows: list[dict[str, str]]) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = sources.setdefault(
            row["source_id"],
            {
                "source_id": row["source_id"],
                "country_or_region": row["country_or_region"],
                "data_role": row["data_role"],
                "rows": 0,
                "downloaded": 0,
                "fetch_failed": 0,
                "download_failed": 0,
                "years": set(),
                "artifact_types": set(),
            },
        )
        item["rows"] += 1
        if row["status"] == "downloaded":
            item["downloaded"] += 1
        if row["status"] == "fetch_failed":
            item["fetch_failed"] += 1
        if row["status"] == "download_failed":
            item["download_failed"] += 1
        if row.get("year"):
            item["years"].add(row["year"])
        if row.get("artifact_type"):
            item["artifact_types"].add(row["artifact_type"])
    for item in sources.values():
        item["years"] = sorted(item["years"])
        item["artifact_types"] = sorted(item["artifact_types"])
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "inventory_path": str(INVENTORY_PATH),
        "raw_dir": str(RAW_DIR),
        "source_count": len(sources),
        "total_rows": len(rows),
        "downloaded_artifacts": sum(1 for row in rows if row["status"] == "downloaded"),
        "download_failures": sum(1 for row in rows if row["status"] == "download_failed"),
        "fetch_failures": sum(1 for row in rows if row["status"] == "fetch_failed"),
        "sources": sorted(sources.values(), key=lambda item: item["source_id"]),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Discover country-level medical aesthetics statistics/proxy sources.")
    parser.add_argument("--no-download", action="store_true", help="Only inventory pages and links; do not download artifacts.")
    parser.add_argument("--clean", action="store_true", help="Clear this script's raw output directory before downloading.")
    args = parser.parse_args()

    if args.clean and RAW_DIR.exists():
        resolved_raw = RAW_DIR.resolve()
        resolved_parent = (PROJECT_DIR / "data" / "commercial_sources").resolve()
        if resolved_parent not in resolved_raw.parents:
            raise SystemExit(f"Refusing to clean unexpected path: {resolved_raw}")
        shutil.rmtree(resolved_raw)

    fetcher = Fetcher()
    rows: list[dict[str, str]] = []
    for seed in SOURCE_SEEDS:
        if seed.mode == "ckan_package":
            rows.extend(fetch_ckan_seed(seed, args.no_download))
        elif seed.mode == "direct_artifact":
            rows.extend(fetch_direct_artifact_seed(seed, args.no_download))
        elif seed.mode == "direct_reference":
            rows.extend(fetch_direct_reference_seed(seed))
        else:
            rows.extend(fetch_html_seed(fetcher, seed, args.no_download))

    rows.sort(key=lambda item: (item["country_or_region"], item["source_id"], item["year"], item["artifact_type"], item["discovered_url"]))
    write_csv(rows, INVENTORY_PATH)
    summary = summarize(rows)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
