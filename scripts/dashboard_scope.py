"""Dashboard display-scope rules.

The source workbook keeps removed or out-of-scope rows for traceability, while
the dashboard database and public snapshot focus on upstream aesthetic product
suppliers: manufacturers, brand owners, technology/material platforms, and
regulated product lines.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


EXPLICIT_ECOSYSTEM_COMPANIES = {
    "54gene",
    "archidemia",
    "fagrongenomics",
    "oeofirenze",
    "skindna",
    "vampirefacial",
}

EXPLICIT_OUT_OF_SCOPE_COMPANIES = {
    "kai",
    "q3medicaldevices",
}

SERVICE_CATEGORY_L1 = {"services", "service"}
SERVICE_CATEGORY_L2_TERMS = (
    "service",
    "training",
    "education",
    "conference",
    "publishing",
)
SERVICE_TECH_TERMS = (
    "medical aesthetics training",
    "online medical education",
    "medical education platform",
    "conference",
    "medical publishing",
    "book of injectable fillers",
    "genetic data",
    "dna analysis",
    "dna genotyping",
    "r&d",
)
SERVICE_CORE_TERMS = (
    "conference",
    "training",
    "workshop",
    "online education",
    "education platform",
    "book of injectable fillers",
)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", clean_text(value).lower())


def field(row: Mapping[str, Any], *names: str) -> str:
    for name in names:
        if name in row and clean_text(row.get(name)):
            return clean_text(row.get(name))
    lowered = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if clean_text(value):
            return clean_text(value)
    return ""


def product_exclusion_reason(row: Mapping[str, Any]) -> str:
    inclusion_status = compact_key(field(row, "Inclusion_Status", "inclusion_status"))
    if inclusion_status == "deleted":
        return "inclusion_status_deleted"
    if inclusion_status == "excluded":
        return "inclusion_status_excluded"

    company_key = compact_key(field(row, "Company", "company"))
    if company_key in EXPLICIT_OUT_OF_SCOPE_COMPANIES:
        return "no_medical_aesthetic_product"
    if company_key in EXPLICIT_ECOSYSTEM_COMPANIES:
        return "ecosystem_company"

    role = compact_key(field(row, "Business_Role", "business_role"))
    if role == "service":
        return "service_business_role"

    category_l1 = compact_key(field(row, "Category_L1", "category_l1"))
    if category_l1 in SERVICE_CATEGORY_L1:
        return "service_category"

    category_l2 = field(row, "Category_L2", "category_l2").lower()
    if any(term in category_l2 for term in SERVICE_CATEGORY_L2_TERMS):
        return "service_subcategory"

    material_path = field(row, "Material_Taxonomy_Path_CN", "material_taxonomy_path_cn").lower()
    if "科研/数据服务" in material_path or "非产品服务" in material_path:
        return "research_data_service"

    tech = field(row, "Tech_Type_Std", "tech_type_std", "Technology", "technology").lower()
    if any(term in tech for term in SERVICE_TECH_TERMS):
        return "service_technology"

    core = field(row, "Core_Product", "core_product", "Brand", "brand").lower()
    if any(term in core for term in SERVICE_CORE_TERMS):
        return "service_product"

    return ""


def company_exclusion_reason(row: Mapping[str, Any]) -> str:
    company_key = compact_key(field(row, "Company", "company"))
    if company_key in EXPLICIT_OUT_OF_SCOPE_COMPANIES:
        return "no_medical_aesthetic_product"
    if company_key in EXPLICIT_ECOSYSTEM_COMPANIES:
        return "ecosystem_company"

    role = compact_key(field(row, "Business_Role", "business_role"))
    if role == "service":
        return "service_business_role"

    primary_track = compact_key(field(row, "Primary_Track", "primary_track"))
    if primary_track in SERVICE_CATEGORY_L1:
        return "service_primary_track"

    return ""
