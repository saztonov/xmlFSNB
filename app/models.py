"""Data classes for FSNB catalog records."""

from dataclasses import dataclass, field


# ─── Data Classes (ФСБЦ) ────────────────────────────────────────────────────


@dataclass
class CatalogMetadata:
    approving_act_number: str
    approving_act_date: str


@dataclass
class ResourceRecord:
    category_type: str
    book_code: str
    book_name: str
    part_code: str
    part_name: str
    section_code: str
    section_name: str
    group_code: str
    group_name: str
    code: str
    name: str
    measure_unit: str
    cost: str
    opt_cost: str


# ─── Data Classes (ГЭСН) ────────────────────────────────────────────────────


@dataclass
class GesnMetadata:
    price_level: str = ""
    base_name: str = ""
    decree_name: str = ""
    category_type: str = ""
    code_prefix: str = ""


@dataclass
class GesnWorkResource:
    code: str = ""
    end_name: str = ""
    quantity: str = ""
    measure_unit: str = ""


@dataclass
class GesnWorkRecord:
    sbornik_code: str = ""
    sbornik_name: str = ""
    otdel_code: str = ""
    otdel_name: str = ""
    razdel_code: str = ""
    razdel_name: str = ""
    podrazdel_code: str = ""
    podrazdel_name: str = ""
    table_code: str = ""
    table_name: str = ""
    name_group_begin: str = ""
    code: str = ""
    end_name: str = ""
    measure_unit: str = ""
    full_name: str = ""
    content_items: list[str] = field(default_factory=list)
    resources: list[GesnWorkResource] = field(default_factory=list)
    nr: str = ""
    sp: str = ""
