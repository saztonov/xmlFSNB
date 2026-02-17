"""QThread workers for exporting parsed data to Markdown."""

from PyQt6.QtCore import QThread, pyqtSignal

from app.models import CatalogMetadata, ResourceRecord, GesnMetadata, GesnWorkRecord


# ─── Markdown Export Worker (ФСБЦ) ─────────────────────────────────────────


class MarkdownExporterWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, metadata: CatalogMetadata, records: list[ResourceRecord],
                 output_path: str, total_in_xml: int, parse_errors: int,
                 parent=None):
        super().__init__(parent)
        self.metadata = metadata
        self.records = records
        self.output_path = output_path
        self.total_in_xml = total_in_xml
        self.parse_errors = parse_errors

    def run(self):
        try:
            lines: list[str] = []
            lines.append("# Федеральный сборник базовых цен на материалы и оборудование")
            lines.append("")
            lines.append(f"**Утверждающий акт:** {self.metadata.approving_act_number}  ")
            lines.append(f"**Дата утверждения:** {self.metadata.approving_act_date}")
            lines.append("")
            lines.append("---")
            lines.append("")

            current_cat = None
            current_book = None
            current_part = None
            current_section = None
            current_group = None
            total = len(self.records)

            for i, r in enumerate(self.records):
                if r.category_type != current_cat:
                    current_cat = r.category_type
                    lines.append(f"# {r.category_type}")
                    lines.append("")
                    current_book = current_part = current_section = current_group = None

                if r.book_code != current_book:
                    current_book = r.book_code
                    lines.append(f"## {r.book_code}. {r.book_name}")
                    lines.append("")
                    current_part = current_section = current_group = None

                if r.part_code != current_part:
                    current_part = r.part_code
                    lines.append(f"### {r.part_code}. {r.part_name}")
                    lines.append("")
                    current_section = current_group = None

                if r.section_code != current_section:
                    current_section = r.section_code
                    lines.append(f"#### {r.section_code}. {r.section_name}")
                    lines.append("")
                    current_group = None

                if r.group_code != current_group:
                    current_group = r.group_code
                    lines.append(f"##### {r.group_code}. {r.group_name}")
                    lines.append("")
                    lines.append("| Код | Наименование | Ед. изм. | Стоимость | Опт. стоимость |")
                    lines.append("|-----|-------------|----------|-----------|----------------|")

                safe_name = r.name.replace("|", r"\|")
                lines.append(
                    f"| {r.code} | {safe_name} | {r.measure_unit} | {r.cost} | {r.opt_cost} |"
                )

                if i % 1000 == 0:
                    self.progress.emit(int(i / total * 100))

            cat_counts: dict[str, int] = {}
            book_codes: set[str] = set()
            group_codes: set[str] = set()
            for r in self.records:
                cat_counts[r.category_type] = cat_counts.get(r.category_type, 0) + 1
                book_codes.add(r.book_code)
                group_codes.add(r.group_code)

            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("# Сводная информация по конвертации")
            lines.append("")
            lines.append(f"- **Прочитано ресурсов в XML:** {self.total_in_xml}")
            lines.append(f"- **Создано записей в документе:** {len(self.records)}")
            lines.append(f"- **Пропущено (ошибки):** {self.parse_errors}")
            lines.append(f"- **Книг (разделов верхнего уровня):** {len(book_codes)}")
            lines.append(f"- **Групп ресурсов:** {len(group_codes)}")
            lines.append("")
            lines.append("**По категориям:**")
            lines.append("")
            lines.append("| Категория | Кол-во ресурсов |")
            lines.append("|-----------|-----------------|")
            for cat_name, count in cat_counts.items():
                lines.append(f"| {cat_name} | {count} |")
            lines.append("")

            with open(self.output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            self.progress.emit(100)
            self.finished.emit(self.output_path)

        except Exception as e:
            self.error.emit(f"Ошибка при экспорте: {e}")


# ─── Markdown Export Worker (ГЭСН) ─────────────────────────────────────────


class GesnMarkdownExporterWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, metadata: GesnMetadata, records: list[GesnWorkRecord],
                 output_path: str, total_parsed: int, parse_errors: int,
                 doc_title: str = "ГЭСН: Государственные элементные сметные нормы",
                 parent=None):
        super().__init__(parent)
        self.metadata = metadata
        self.records = records
        self.output_path = output_path
        self.total_parsed = total_parsed
        self.parse_errors = parse_errors
        self.doc_title = doc_title

    def _escape(self, text: str) -> str:
        return text.replace("|", r"\|")

    def _build_breadcrumb(self, w: GesnWorkRecord) -> str:
        parts: list[str] = []
        if w.sbornik_code:
            parts.append(f'Сборник {w.sbornik_code} "{w.sbornik_name}"')
        if w.otdel_code:
            parts.append(f'Отдел {w.otdel_code} "{w.otdel_name}"')
        if w.razdel_code:
            parts.append(f'Раздел {w.razdel_code} "{w.razdel_name}"')
        if w.podrazdel_code:
            parts.append(f'Подраздел {w.podrazdel_code} "{w.podrazdel_name}"')
        if w.table_code:
            parts.append(f'Таблица {w.table_code}')
        return " > ".join(parts)

    def run(self):
        try:
            total = len(self.records)
            total_resources = 0
            total_content_items = 0

            with open(self.output_path, "w", encoding="utf-8") as f:
                f.write(f"# {self.doc_title}\n\n")
                f.write(f"**База:** {self.metadata.base_name}  \n")
                f.write(f"**Ценовой уровень:** {self.metadata.price_level}  \n")
                f.write(f"**Основание:** {self.metadata.decree_name}  \n")
                f.write(f"**Категория:** {self.metadata.category_type}\n\n")
                f.write("---\n\n")

                for i, w in enumerate(self.records):
                    total_resources += len(w.resources)
                    total_content_items += len(w.content_items)

                    safe_name = self._escape(w.full_name)
                    breadcrumb = self._escape(self._build_breadcrumb(w))

                    f.write(f"## ГЭСН {w.code} — {safe_name}\n\n")
                    f.write(f"**Код нормы:** {w.code}  \n")
                    f.write(f"**Единица измерения:** {w.measure_unit}  \n")
                    f.write(f"**Расположение:** {breadcrumb}  \n")
                    if w.nr or w.sp:
                        f.write(f"**Нр:** {w.nr} | **Сп:** {w.sp}\n")
                    f.write("\n")

                    if w.content_items:
                        f.write("### Состав работ\n\n")
                        for item_text in w.content_items:
                            f.write(f"- {self._escape(item_text)}\n")
                        f.write("\n")

                    if w.resources:
                        f.write("### Ресурсы\n\n")
                        f.write("| Код ресурса | Наименование | Ед. изм. | Количество |\n")
                        f.write("|---|---|---|---|\n")
                        for res in w.resources:
                            safe_end = self._escape(res.end_name)
                            f.write(
                                f"| {res.code} | {safe_end} "
                                f"| {res.measure_unit} | {res.quantity} |\n"
                            )
                        f.write("\n")

                    f.write("---\n\n")

                    if i % 500 == 0:
                        self.progress.emit(int(i / total * 100))

                f.write("# Сводная информация по конвертации\n\n")
                f.write("| Параметр | Значение |\n")
                f.write("|---|---|\n")
                f.write(f"| Всего обработано элементов Work в XML | {self.total_parsed:,} |\n")
                f.write(f"| Успешно создано записей в Markdown | {len(self.records):,} |\n")
                f.write(f"| Пропущено с ошибками | {self.parse_errors:,} |\n")
                f.write(f"| Общее количество ресурсов | {total_resources:,} |\n")
                f.write(f"| Общее количество пунктов состава работ | {total_content_items:,} |\n")
                f.write("")

            self.progress.emit(100)
            self.finished.emit(self.output_path)

        except Exception as e:
            self.error.emit(f"Ошибка при экспорте ГЭСН: {e}")
