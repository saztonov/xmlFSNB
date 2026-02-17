"""Main application window."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTableView, QFileDialog,
    QMessageBox, QHeaderView, QAbstractItemView, QTabWidget,
)

from app.models import CatalogMetadata, ResourceRecord, GesnMetadata, GesnWorkRecord
from app.workers.parsers import XmlParserWorker, GesnXmlParserWorker
from app.workers.exporters import MarkdownExporterWorker, GesnMarkdownExporterWorker
from app.ui.table_models import ResourceTableModel, GesnTableModel


# ─── Reusable controller for ГЭСН-family tabs ──────────────────────────────


class GesnTabController:
    """Manages state, widgets, and logic for one ГЭСН-family tab.

    Reused for both ГЭСН and ГЭСНм — only the labels differ.
    """

    def __init__(self, tab_label: str, doc_title: str, parent_window: QMainWindow):
        self.tab_label = tab_label
        self.doc_title = doc_title
        self.parent_window = parent_window

        self.metadata: GesnMetadata | None = None
        self.records: list[GesnWorkRecord] = []
        self.total_parsed = 0
        self.parse_errors = 0
        self.parser_worker: GesnXmlParserWorker | None = None
        self.export_worker: GesnMarkdownExporterWorker | None = None

        self.load_btn: QPushButton | None = None
        self.export_btn: QPushButton | None = None
        self.progress_bar: QProgressBar | None = None
        self.status_label: QLabel | None = None
        self.model: GesnTableModel | None = None
        self.table_view: QTableView | None = None

    def build_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        toolbar = QHBoxLayout()
        self.load_btn = QPushButton(f"Загрузить {self.tab_label} XML...")
        self.export_btn = QPushButton("Экспорт в Markdown...")
        self.export_btn.setEnabled(False)
        toolbar.addWidget(self.load_btn)
        toolbar.addWidget(self.export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.status_label = QLabel(f"Готово. Выберите {self.tab_label} XML файл для загрузки.")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.model = GesnTableModel()
        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(False)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table_view)

        self.load_btn.clicked.connect(self._on_load_clicked)
        self.export_btn.clicked.connect(self._on_export_clicked)

        return tab

    # ── Load XML ────────────────────────────────────────────────────────

    def _on_load_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self.parent_window,
            f"Выберите {self.tab_label} XML файл", "",
            "XML файлы (*.xml);;Все файлы (*)",
        )
        if not path:
            return

        self.load_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Загрузка и разбор {self.tab_label} XML...")

        self.parser_worker = GesnXmlParserWorker(path)
        self.parser_worker.progress.connect(self._on_parse_progress)
        self.parser_worker.finished.connect(self._on_parse_finished)
        self.parser_worker.error.connect(self._on_parse_error)
        self.parser_worker.start()

    def _on_parse_progress(self, value: int):
        self.progress_bar.setValue(value)

    def _on_parse_finished(self, metadata: GesnMetadata, records: list[GesnWorkRecord],
                           total_parsed: int, parse_errors: int):
        self.metadata = metadata
        self.records = records
        self.total_parsed = total_parsed
        self.parse_errors = parse_errors
        self.model.set_records(records)

        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.progress_bar.setVisible(False)
        self.load_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        total_res = sum(len(r.resources) for r in records)
        self.status_label.setText(
            f"Загружено {len(records):,} норм (ошибок: {parse_errors:,}). "
            f"Ресурсов: {total_res:,}. "
            f"Категория: {metadata.category_type}"
        )

    def _on_parse_error(self, msg: str):
        self.progress_bar.setVisible(False)
        self.load_btn.setEnabled(True)
        self.status_label.setText("Ошибка загрузки.")
        QMessageBox.critical(self.parent_window, "Ошибка", msg)

    # ── Export Markdown ─────────────────────────────────────────────────

    def _on_export_clicked(self):
        if not self.records or not self.metadata:
            return

        path, _ = QFileDialog.getSaveFileName(
            self.parent_window,
            f"Сохранить {self.tab_label} Markdown", "",
            "Markdown (*.md);;Все файлы (*)",
        )
        if not path:
            return

        self.load_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Экспорт {self.tab_label} в Markdown...")

        self.export_worker = GesnMarkdownExporterWorker(
            self.metadata, self.records, path,
            self.total_parsed, self.parse_errors,
            doc_title=self.doc_title,
        )
        self.export_worker.progress.connect(self._on_export_progress)
        self.export_worker.finished.connect(self._on_export_finished)
        self.export_worker.error.connect(self._on_export_error)
        self.export_worker.start()

    def _on_export_progress(self, value: int):
        self.progress_bar.setValue(value)

    def _on_export_finished(self, path: str):
        self.progress_bar.setVisible(False)
        self.load_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.status_label.setText(f"Экспорт завершён: {path}")

        total_res = sum(len(r.resources) for r in self.records)
        QMessageBox.information(
            self.parent_window, "Готово",
            f"Файл сохранён:\n{path}\n\n"
            f"Записей: {len(self.records):,} | "
            f"Ресурсов: {total_res:,} | "
            f"Ошибок: {self.parse_errors:,}",
        )

    def _on_export_error(self, msg: str):
        self.progress_bar.setVisible(False)
        self.load_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.status_label.setText("Ошибка экспорта.")
        QMessageBox.critical(self.parent_window, "Ошибка", msg)


# ─── Main Window ──────────────────────────────────────────────────────────────


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ФСНБ — Конвертер XML в Markdown")

        # ФСБЦ state
        self._metadata: CatalogMetadata | None = None
        self._records: list[ResourceRecord] = []
        self._total_in_xml = 0
        self._parse_errors = 0
        self._parser_worker: XmlParserWorker | None = None
        self._export_worker: MarkdownExporterWorker | None = None

        # ГЭСН-family tabs
        self._gesn_tab = GesnTabController(
            tab_label="ГЭСН",
            doc_title="ГЭСН: Государственные элементные сметные нормы",
            parent_window=self,
        )
        self._gesnm_tab = GesnTabController(
            tab_label="ГЭСНм",
            doc_title="ГЭСНм: Государственные элементные сметные нормы на монтаж оборудования",
            parent_window=self,
        )

        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        self._init_fsbc_tab()
        self.tab_widget.addTab(self._gesn_tab.build_tab(), "ГЭСН")
        self.tab_widget.addTab(self._gesnm_tab.build_tab(), "ГЭСНм")

    # ── ФСБЦ Tab ─────────────────────────────────────────────────────────

    def _init_fsbc_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        toolbar = QHBoxLayout()
        self.load_btn = QPushButton("Загрузить XML...")
        self.export_btn = QPushButton("Экспорт в Markdown...")
        self.export_btn.setEnabled(False)
        toolbar.addWidget(self.load_btn)
        toolbar.addWidget(self.export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.status_label = QLabel("Готово. Выберите XML файл для загрузки.")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.model = ResourceTableModel()
        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(False)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table_view)

        self.load_btn.clicked.connect(self._on_load_clicked)
        self.export_btn.clicked.connect(self._on_export_clicked)

        self.tab_widget.addTab(tab, "ФСБЦ")

    # ── ФСБЦ: Load XML ──────────────────────────────────────────────────

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

    def _on_parse_finished(self, metadata: CatalogMetadata, records: list[ResourceRecord],
                           total_in_xml: int, parse_errors: int):
        self._metadata = metadata
        self._records = records
        self._total_in_xml = total_in_xml
        self._parse_errors = parse_errors
        self.model.set_records(records)

        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.progress_bar.setVisible(False)
        self.load_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        status = (
            f"Прочитано в XML: {total_in_xml:,} | "
            f"Загружено: {len(records):,} | "
            f"Ошибок: {parse_errors:,} | "
            f"Акт: {metadata.approving_act_number} от {metadata.approving_act_date}"
        )
        self.status_label.setText(status)

    def _on_parse_error(self, msg: str):
        self.progress_bar.setVisible(False)
        self.load_btn.setEnabled(True)
        self.status_label.setText("Ошибка загрузки.")
        QMessageBox.critical(self, "Ошибка", msg)

    # ── ФСБЦ: Export Markdown ────────────────────────────────────────────

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
            self._metadata, self._records, path,
            self._total_in_xml, self._parse_errors,
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
