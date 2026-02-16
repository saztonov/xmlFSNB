"""
ФСНБ XML to RAG-Friendly Markdown Converter
PyQt6 GUI application.
"""

import sys
import io
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QModelIndex
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTableView, QFileDialog,
    QMessageBox, QHeaderView, QAbstractItemView,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QAbstractTableModel


# ─── Data Classes ─────────────────────────────────────────────────────────────


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


# ─── XML Parser Worker ───────────────────────────────────────────────────────


class XmlParserWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(object, list)
    error = pyqtSignal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        try:
            raw = open(self.file_path, "rb").read()
            if raw.startswith(b"\xef\xbb\xbf"):
                raw = raw[3:]

            # Pass 1: count resources for progress
            total_resources = raw.count(b"<Resource ")
            if total_resources == 0:
                total_resources = 1

            # Pass 2: iterparse
            metadata = CatalogMetadata("", "")
            records: list[ResourceRecord] = []
            hierarchy_stack: list[tuple[str, str, str]] = []
            current_category_type = ""
            parsed_count = 0

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

                        price_elem = elem.find(".//Price")
                        cost = price_elem.get("Cost", "") if price_elem is not None else ""
                        opt_cost = price_elem.get("OptCost", "") if price_elem is not None else ""

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
                                code=elem.get("Code", ""),
                                name=elem.get("Name", ""),
                                measure_unit=elem.get("MeasureUnit", ""),
                                cost=cost,
                                opt_cost=opt_cost,
                            )
                        )
                        parsed_count += 1
                        if parsed_count % 500 == 0:
                            self.progress.emit(int(parsed_count / total_resources * 100))
                        elem.clear()

                    elif elem.tag == "Section":
                        if hierarchy_stack:
                            hierarchy_stack.pop()
                        elem.clear()

            self.progress.emit(100)
            self.finished.emit(metadata, records)

        except Exception as e:
            self.error.emit(f"Ошибка при разборе XML: {e}")


# ─── Markdown Export Worker ───────────────────────────────────────────────────


class MarkdownExporterWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, metadata: CatalogMetadata, records: list[ResourceRecord],
                 output_path: str, parent=None):
        super().__init__(parent)
        self.metadata = metadata
        self.records = records
        self.output_path = output_path

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

            lines.append("")

            with open(self.output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            self.progress.emit(100)
            self.finished.emit(self.output_path)

        except Exception as e:
            self.error.emit(f"Ошибка при экспорте: {e}")


# ─── Table Model ──────────────────────────────────────────────────────────────


class ResourceTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Код", "code"),
        ("Категория", "category_type"),
        ("Книга", "book_name"),
        ("Наименование", "name"),
        ("Ед. изм.", "measure_unit"),
        ("Стоимость", "cost"),
        ("Опт. стоимость", "opt_cost"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: list[ResourceRecord] = []

    def set_records(self, records: list[ResourceRecord]):
        self.beginResetModel()
        self._records = records
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._records)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            record = self._records[index.row()]
            attr = self.COLUMNS[index.column()][1]
            return getattr(record, attr)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() >= 5:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section][0]
        return None


# ─── Main Window ──────────────────────────────────────────────────────────────


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ФСНБ — Конвертер XML в Markdown")

        self._metadata: CatalogMetadata | None = None
        self._records: list[ResourceRecord] = []
        self._parser_worker: XmlParserWorker | None = None
        self._export_worker: MarkdownExporterWorker | None = None

        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Toolbar
        toolbar = QHBoxLayout()
        self.load_btn = QPushButton("Загрузить XML...")
        self.export_btn = QPushButton("Экспорт в Markdown...")
        self.export_btn.setEnabled(False)
        toolbar.addWidget(self.load_btn)
        toolbar.addWidget(self.export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Status
        self.status_label = QLabel("Готово. Выберите XML файл для загрузки.")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Table
        self.model = ResourceTableModel()
        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(False)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table_view)

        # Signals
        self.load_btn.clicked.connect(self._on_load_clicked)
        self.export_btn.clicked.connect(self._on_export_clicked)

    # ── Load XML ──────────────────────────────────────────────────────────

    def _on_load_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите XML файл", "", "XML файлы (*.xml);;Все файлы (*)"
        )
        if not path:
            return

        self.load_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Загрузка и разбор XML...")

        self._parser_worker = XmlParserWorker(path)
        self._parser_worker.progress.connect(self._on_parse_progress)
        self._parser_worker.finished.connect(self._on_parse_finished)
        self._parser_worker.error.connect(self._on_parse_error)
        self._parser_worker.start()

    def _on_parse_progress(self, value: int):
        self.progress_bar.setValue(value)

    def _on_parse_finished(self, metadata: CatalogMetadata, records: list[ResourceRecord]):
        self._metadata = metadata
        self._records = records
        self.model.set_records(records)

        # Resize columns to content (limit to first 100 rows for speed)
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.progress_bar.setVisible(False)
        self.load_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.status_label.setText(
            f"Загружено {len(records):,} ресурсов. "
            f"Акт: {metadata.approving_act_number} от {metadata.approving_act_date}"
        )

    def _on_parse_error(self, msg: str):
        self.progress_bar.setVisible(False)
        self.load_btn.setEnabled(True)
        self.status_label.setText("Ошибка загрузки.")
        QMessageBox.critical(self, "Ошибка", msg)

    # ── Export Markdown ───────────────────────────────────────────────────

    def _on_export_clicked(self):
        if not self._records or not self._metadata:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить Markdown", "", "Markdown (*.md);;Все файлы (*)"
        )
        if not path:
            return

        self.load_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Экспорт в Markdown...")

        self._export_worker = MarkdownExporterWorker(
            self._metadata, self._records, path
        )
        self._export_worker.progress.connect(self._on_export_progress)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_export_error)
        self._export_worker.start()

    def _on_export_progress(self, value: int):
        self.progress_bar.setValue(value)

    def _on_export_finished(self, path: str):
        self.progress_bar.setVisible(False)
        self.load_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.status_label.setText(f"Экспорт завершён: {path}")
        QMessageBox.information(self, "Готово", f"Файл сохранён:\n{path}")

    def _on_export_error(self, msg: str):
        self.progress_bar.setVisible(False)
        self.load_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.status_label.setText("Ошибка экспорта.")
        QMessageBox.critical(self, "Ошибка", msg)


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.resize(1200, 700)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
