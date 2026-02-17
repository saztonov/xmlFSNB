"""QThread workers for parsing FSNB XML files."""

import io
from xml.etree import ElementTree as ET

from PyQt6.QtCore import QThread, pyqtSignal

from app.models import (
    CatalogMetadata, ResourceRecord,
    GesnMetadata, GesnWorkResource, GesnWorkRecord,
)


# ─── XML Parser Worker (ФСБЦ) ──────────────────────────────────────────────


class XmlParserWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(object, list, int, int)
    error = pyqtSignal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        try:
            raw = open(self.file_path, "rb").read()
            if raw.startswith(b"\xef\xbb\xbf"):
                raw = raw[3:]

            total_resources = raw.count(b"<Resource ")
            if total_resources == 0:
                total_resources = 1

            metadata = CatalogMetadata("", "")
            records: list[ResourceRecord] = []
            hierarchy_stack: list[tuple[str, str, str]] = []
            current_category_type = ""
            parsed_count = 0
            error_count = 0

            for event, elem in ET.iterparse(io.BytesIO(raw), events=("start", "end")):
                if event == "start":
                    if elem.tag == "ResourceCategory":
                        current_category_type = elem.get("Type", "")
                    elif elem.tag == "Section":
                        hierarchy_stack.append(
                            (elem.get("Type", ""), elem.get("Code", ""), elem.get("Name", ""))
                        )

                elif event == "end":
                    if elem.tag == "ApprovingActNumber":
                        metadata.approving_act_number = elem.text or ""
                    elif elem.tag == "ApprovingActDate":
                        metadata.approving_act_date = elem.text or ""
                    elif elem.tag == "Resource":
                        parsed_count += 1
                        if parsed_count % 500 == 0:
                            self.progress.emit(int(parsed_count / total_resources * 100))

                        code = elem.get("Code", "")
                        name = elem.get("Name", "")
                        measure_unit = elem.get("MeasureUnit", "")
                        price_elem = elem.find(".//Price")

                        if not code or not name or price_elem is None:
                            error_count += 1
                            elem.clear()
                            continue

                        cost = price_elem.get("Cost", "")
                        opt_cost = price_elem.get("OptCost", "")

                        book = ("", "", "")
                        part = ("", "", "")
                        section = ("", "", "")
                        group = ("", "", "")
                        for item in hierarchy_stack:
                            if item[0] == "Книга":
                                book = item
                            elif item[0] == "Часть":
                                part = item
                            elif item[0] == "Раздел":
                                section = item
                            elif item[0] == "Группа":
                                group = item

                        records.append(
                            ResourceRecord(
                                category_type=current_category_type,
                                book_code=book[1],
                                book_name=book[2],
                                part_code=part[1],
                                part_name=part[2],
                                section_code=section[1],
                                section_name=section[2],
                                group_code=group[1],
                                group_name=group[2],
                                code=code,
                                name=name,
                                measure_unit=measure_unit,
                                cost=cost,
                                opt_cost=opt_cost,
                            )
                        )
                        elem.clear()

                    elif elem.tag == "Section":
                        if hierarchy_stack:
                            hierarchy_stack.pop()
                        elem.clear()

            self.progress.emit(100)
            self.finished.emit(metadata, records, total_resources, error_count)

        except Exception as e:
            self.error.emit(f"Ошибка при разборе XML: {e}")


# ─── XML Parser Worker (ГЭСН) ──────────────────────────────────────────────


class GesnXmlParserWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(object, list, int, int)
    error = pyqtSignal(str)

    SECTION_TYPE_MAP = {
        "Сборник": "sbornik",
        "Отдел": "otdel",
        "Раздел": "razdel",
        "Подраздел": "podrazdel",
        "Таблица": "table",
    }

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        try:
            raw = open(self.file_path, "rb").read()
            if raw.startswith(b"\xef\xbb\xbf"):
                raw = raw[3:]

            total_works = raw.count(b"<Work ")
            if total_works == 0:
                total_works = 1

            metadata = GesnMetadata()
            records: list[GesnWorkRecord] = []
            section_stack: list[tuple[str, str, str]] = []
            current_name_group_begin = ""
            parsed_count = 0
            error_count = 0

            for event, elem in ET.iterparse(io.BytesIO(raw), events=("start", "end")):
                if event == "start":
                    if elem.tag == "base":
                        metadata.price_level = elem.get("PriceLevel", "")
                        metadata.base_name = elem.get("BaseName", "")
                    elif elem.tag == "ResourceCategory":
                        metadata.category_type = elem.get("Type", "")
                        metadata.code_prefix = elem.get("CodePrefix", "")
                    elif elem.tag == "Section":
                        section_stack.append(
                            (elem.get("Type", ""), elem.get("Code", ""), elem.get("Name", ""))
                        )
                    elif elem.tag == "NameGroup":
                        current_name_group_begin = elem.get("BeginName", "")

                elif event == "end":
                    if elem.tag == "Decree":
                        metadata.decree_name = elem.get("Name", "")

                    elif elem.tag == "Work":
                        parsed_count += 1
                        if parsed_count % 200 == 0:
                            self.progress.emit(int(parsed_count / total_works * 100))

                        try:
                            code = elem.get("Code", "")
                            end_name = elem.get("EndName", "")
                            measure_unit = elem.get("MeasureUnit", "")

                            content_items: list[str] = []
                            content_el = elem.find("Content")
                            if content_el is not None:
                                for item_el in content_el.findall("Item"):
                                    text = item_el.get("Text", "")
                                    if text:
                                        content_items.append(text)

                            resources: list[GesnWorkResource] = []
                            resources_el = elem.find("Resources")
                            if resources_el is not None:
                                for res_el in resources_el.findall("Resource"):
                                    resources.append(GesnWorkResource(
                                        code=res_el.get("Code", ""),
                                        end_name=res_el.get("EndName", ""),
                                        quantity=res_el.get("Quantity", ""),
                                        measure_unit=res_el.get("MeasureUnit", ""),
                                    ))

                            nr, sp = "", ""
                            nrsp_el = elem.find("NrSp")
                            if nrsp_el is not None:
                                reason = nrsp_el.find("ReasonItem")
                                if reason is not None:
                                    nr = reason.get("Nr", "")
                                    sp = reason.get("Sp", "")

                            hierarchy = {
                                "sbornik": ("", ""), "otdel": ("", ""),
                                "razdel": ("", ""), "podrazdel": ("", ""),
                                "table": ("", ""),
                            }
                            for s_type, s_code, s_name in section_stack:
                                key = self.SECTION_TYPE_MAP.get(s_type)
                                if key:
                                    hierarchy[key] = (s_code, s_name)

                            full_name = current_name_group_begin
                            if end_name:
                                full_name = f"{full_name} {end_name}".strip()

                            records.append(GesnWorkRecord(
                                sbornik_code=hierarchy["sbornik"][0],
                                sbornik_name=hierarchy["sbornik"][1],
                                otdel_code=hierarchy["otdel"][0],
                                otdel_name=hierarchy["otdel"][1],
                                razdel_code=hierarchy["razdel"][0],
                                razdel_name=hierarchy["razdel"][1],
                                podrazdel_code=hierarchy["podrazdel"][0],
                                podrazdel_name=hierarchy["podrazdel"][1],
                                table_code=hierarchy["table"][0],
                                table_name=hierarchy["table"][1],
                                name_group_begin=current_name_group_begin,
                                code=code,
                                end_name=end_name,
                                measure_unit=measure_unit,
                                full_name=full_name,
                                content_items=content_items,
                                resources=resources,
                                nr=nr,
                                sp=sp,
                            ))
                        except Exception:
                            error_count += 1

                        elem.clear()

                    elif elem.tag == "NameGroup":
                        current_name_group_begin = ""

                    elif elem.tag == "Section":
                        if section_stack:
                            section_stack.pop()
                        elem.clear()

            self.progress.emit(100)
            self.finished.emit(metadata, records, parsed_count, error_count)

        except Exception as e:
            self.error.emit(f"Ошибка при разборе ГЭСН XML: {e}")
