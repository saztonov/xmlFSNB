"""QAbstractTableModel implementations for table views."""

from PyQt6.QtCore import Qt, QModelIndex, QAbstractTableModel

from app.models import ResourceRecord, GesnWorkRecord


# ─── Table Model (ФСБЦ) ────────────────────────────────────────────────────


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


# ─── Table Model (ГЭСН) ────────────────────────────────────────────────────


class GesnTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Код", "code"),
        ("Наименование", "full_name"),
        ("Ед. изм.", "measure_unit"),
        ("Сборник", "sbornik_name"),
        ("Таблица", "table_code"),
        ("Ресурсов", "_resource_count"),
        ("Нр", "nr"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: list[GesnWorkRecord] = []

    def set_records(self, records: list[GesnWorkRecord]):
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
            if attr == "_resource_count":
                return str(len(record.resources))
            return getattr(record, attr)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() == 5:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section][0]
        return None
