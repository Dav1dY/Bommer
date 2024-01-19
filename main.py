import sqlite3
from PyQt6.QtCore import Qt, QModelIndex, QVariant
from PyQt6 import QtWidgets, uic
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QAbstractItemView, QStyledItemDelegate, QComboBox, QTableView, QPushButton
import sys
from functools import partial
from enum import Enum
from typing import Optional


class ComboBoxDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, choices=None):
        super().__init__(parent)
        self.choices = choices if choices else []

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItems(self.choices)
        return editor


class PartPageState(Enum):
    UNSELECTED = 1
    SELECTED = 2
    EDIT = 3
    NEW = 4


class PartStateMachine:
    def __init__(self):
        self.state = PartPageState.UNSELECTED

    def select_row(self):
        if self.state == PartPageState.UNSELECTED:
            self.state = PartPageState.SELECTED

    def click_edit(self):
        if self.state == PartPageState.SELECTED:
            self.state = PartPageState.EDIT

    def click_cancel(self):
        if self.state == PartPageState.EDIT:
            self.state = PartPageState.SELECTED
        else:
            self.state = PartPageState.UNSELECTED

    def click_remove(self):
        if self.state == PartPageState.SELECTED:
            self.state = PartPageState.UNSELECTED

    def click_new(self):
        if self.state == PartPageState.UNSELECTED or self.state == PartPageState.SELECTED:
            self.state = PartPageState.NEW

    def click_save(self):
        if self.state == PartPageState.EDIT or self.state == PartPageState.NEW:
            self.state = PartPageState.SELECTED


class ModuleTableModel(QStandardItemModel):
    def flags(self, index):
        if index.column() == self.columnCount()-1:
            return super().flags(index) | Qt.ItemFlag.ItemIsEditable
        else:
            return super().flags(index) & ~Qt.ItemFlag.ItemIsEditable


class MainWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        uic.loadUi('main_window.ui', self)

        self.db = PartsDatabase()

        self.Main_stackedWidget.currentChanged.connect(self.on_mainStack_changed)
        self.back2mainPage_Button_1.clicked.connect(partial(self.stackedWidget_jump, self.Main_stackedWidget, 0))
        self.back2mainPage_Button_2.clicked.connect(partial(self.stackedWidget_jump, self.Main_stackedWidget, 0))
        self.back2mainPage_Button_3.clicked.connect(partial(self.stackedWidget_jump, self.Main_stackedWidget, 0))
        self.jump2partPage_Button.clicked.connect(partial(self.stackedWidget_jump, self.Main_stackedWidget, 1))
        self.jump2modulePage_Button.clicked.connect(partial(self.stackedWidget_jump, self.Main_stackedWidget, 2))
        self.jump2stationPage_Button.clicked.connect(partial(self.stackedWidget_jump, self.Main_stackedWidget, 3))

        # part
        self.part_tableView.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.part_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.part_tableView.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.part_tableView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.part_statemachine: Optional[PartStateMachine] = None
        self.search_part_pushButton.clicked.connect(self.partPage_searchPart)
        self.edit_part_pushButton.clicked.connect(self.partPage_edit)
        self.edit_part_pushButton.setEnabled(False)
        self.new_part_pushButton.clicked.connect(self.partPage_new)
        self.new_part_pushButton.setEnabled(True)
        self.part_cancalEdit_pushButton.clicked.connect(self.partPage_cancel_edit)
        self.part_cancalEdit_pushButton.setEnabled(False)
        self.part_savechange_pushButton.clicked.connect(self.partPage_save_edit)
        self.part_savechange_pushButton.setEnabled(False)
        self.remove_part_pushButton.clicked.connect(self.partPage_remove_part)
        self.remove_part_pushButton.setEnabled(False)
        part_choices = [self.part_category_comboBox.itemText(combo_index) for combo_index in range(self.part_category_comboBox.count())]
        self.part_cate_combo_delegate = ComboBoxDelegate(choices=part_choices)
        self.part_stan_combo_delegate = ComboBoxDelegate(choices=["標準件", "非標準件"])
        self.part_tableView.setItemDelegateForColumn(1, self.part_stan_combo_delegate)
        self.part_tableView.setItemDelegateForColumn(6, self.part_cate_combo_delegate)
        self.part_editing_row = None
        self.original_data = []

        # moduleP1
        self.module_search_tableView.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.module_search_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.module_search_tableView.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.module_search_tableView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.module_belong_combo_delegate = ComboBoxDelegate(choices=["Conveyor", "Robot", "Modbus"])
        self.module_search_tableView.setItemDelegateForColumn(2, self.module_belong_combo_delegate)
        self.module_search_pushButton.clicked.connect(self.modulePage_searchModule)
        self.module_view_pushButton.clicked.connect(self.module_view)
        self.module_newModule_pushButton.clicked.connect(self.create_new_module)
        self.module_saveModule_pushButton.clicked.connect(self.save_new_module)
        self.module_cancelModule_pushButton.clicked.connect(self.cancel_new_module)
        self.module_removeModule_pushButton.clicked.connect(self.remove_module)
        self.module_view_pushButton.setEnabled(False)
        self.module_removeModule_pushButton.setEnabled(False)
        self.module_saveModule_pushButton.setEnabled(False)
        self.module_cancelModule_pushButton.setEnabled(False)
        self.selected_module_id = None
        self.selected_module_name = None
        self.selected_module_belonging = None

        # module P2
        self.module_content_tableView.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        # self.module_content_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.module_content_tableView.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.module_content_tableView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.module_searchPart_tableView.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.module_searchPart_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.module_searchPart_tableView.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.module_searchPart_tableView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.module_removePart_pushButton.setEnabled(False)
        self.module_addPart_pushButton.setEnabled(False)
        self.module_removePart_pushButton.clicked.connect(self.module_removePart)
        self.module_save_pushButton.clicked.connect(self.module_save_module)
        self.module_searchPart_pushButton.clicked.connect(self.module_search_part)
        self.module_addPart_pushButton.clicked.connect(self.module_add_part)
        self.module_return_pushButton.clicked.connect(self.module_page_return)

        # station p1
        self.station_search_tableView.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.station_search_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.station_search_tableView.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.station_search_tableView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.station_search_pushButton.clicked.connect(self.stationPage_searchStation)
        self.view_station_pushButton.clicked.connect(self.station_view)
        self.station_newStation_pushButton.clicked.connect(self.create_new_station)
        self.station_saveStation_pushButton.clicked.connect(self.save_new_station)
        self.station_cancelStation_pushButton.clicked.connect(self.cancel_new_station)
        self.station_removeStation_pushButton.clicked.connect(self.remove_station)
        self.view_station_pushButton.setEnabled(False)
        self.station_removeStation_pushButton.setEnabled(False)
        self.station_saveStation_pushButton.setEnabled(False)
        self.station_cancelStation_pushButton.setEnabled(False)
        self.selected_station_id = None
        self.selected_station_name = None

        # station p2
        self.station_content_tableView.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        # self.station_content_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.station_content_tableView.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.station_content_tableView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.station_search_module_tableView.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.station_search_module_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.station_search_module_tableView.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.station_search_module_tableView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.station_remove_module_pushButton.setEnabled(False)
        self.station_add_module_pushButton.setEnabled(False)
        self.station_remove_module_pushButton.clicked.connect(self.station_removeModule)
        self.station_save_pushButton.clicked.connect(self.station_save_station)
        self.station_module_search_pushButton.clicked.connect(self.station_search_module)
        self.station_add_module_pushButton.clicked.connect(self.station_add_module)
        self.station_return_pushButton.clicked.connect(self.station_page_return)

        self.exitButton.clicked.connect(self.close)

    def on_mainStack_changed(self, index):
        if index == 1:
            self.part_tableView.setModel(None)
        elif index == 2:
            self.module_stackedWidget.setCurrentIndex(0)
            self.module_search_tableView.setModel(None)
        elif index == 3:
            self.station_stackedWidget.setCurrentIndex(0)
            self.station_search_tableView.setModel(None)

    def stackedWidget_jump(self, widget, page):
        widget.setCurrentIndex(page)

    def partPage_searchPart(self):
        # todo: check if old model still take memory
        fields = ['part_name', 'part_spec', 'part_category']
        fields_all = ['id', '標準件', '名稱', '品牌', '描述', '規格', '類別']
        name = self.part_name_lineEdit.text()
        spec = self.part_spec_lineEdit.text()
        cate = self.part_category_comboBox.currentText()
        if name == '':
            name = None
        if spec == '':
            spec = None
        if cate == '所有':
            cate = None
        values = [name, spec, cate]
        fields_values = list(zip(fields, values))
        results = self.db.search_part(fields_values)
        if not results:
            return
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(fields_all)
        for row in results:
            items = [QStandardItem(str(field)) for field in row]
            model.appendRow(items)
        self.part_tableView.setModel(model)
        self.part_tableView.hideColumn(0)
        selection_model = self.part_tableView.selectionModel()
        selection_model.selectionChanged.connect(lambda: self.update_button(self.part_tableView))
        self.part_statemachine = PartStateMachine()
        self.part_update_buttons(self.part_statemachine.state)

    def partPage_edit(self):
        index = self.part_tableView.currentIndex()

        model = self.part_tableView.model()
        for row in range(model.rowCount()):
            for column in range(model.columnCount()):
                cellIndex = model.index(row, column)
                item = model.itemFromIndex(cellIndex)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

        if index.isValid():
            self.original_data = []
            self.part_editing_row = index.row()
            for column in range(model.columnCount()):
                cellIndex = model.index(self.part_editing_row, column)
                item = model.itemFromIndex(cellIndex)
                self.original_data.append(item.text())
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
            self.part_tableView.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
            self.part_statemachine.click_edit()
            self.part_update_buttons(self.part_statemachine.state)

    def partPage_cancel_edit(self):
        model = self.part_tableView.model()
        if self.part_statemachine.state == PartPageState.EDIT:
            for row in range(model.rowCount()):
                for column in range(model.columnCount()):
                    cellIndex = model.index(row, column)
                    item = model.itemFromIndex(cellIndex)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)

            if self.part_editing_row is not None and self.original_data:
                for column in range(model.columnCount()):
                    cellIndex = model.index(self.part_editing_row, column)
                    item = model.itemFromIndex(cellIndex)
                    item.setText(self.original_data[column])
            self.part_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.part_statemachine.click_cancel()
            self.part_update_buttons(self.part_statemachine.state)
            self.part_editing_row = None
        elif self.part_statemachine.state == PartPageState.NEW:
            model.removeRow(0)
            self.part_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.part_statemachine.click_cancel()
            self.part_update_buttons(self.part_statemachine.state)

    def partPage_save_edit(self):
        model = self.part_tableView.model()
        if self.part_statemachine.state == PartPageState.EDIT:
            if self.part_editing_row is not None:
                cmd = []
                for column in range(0, model.columnCount()):
                    cellIndex = model.index(self.part_editing_row, column)
                    item = model.itemFromIndex(cellIndex)
                    cmd.append(item.text())
                self.db.edit_part(cmd[1], cmd[2], cmd[3], cmd[4], cmd[5], cmd[6], cmd[0])
                self.part_editing_row = None
                self.part_statemachine.click_save()
                self.part_update_buttons(self.part_statemachine.state)
            for row in range(model.rowCount()):
                for column in range(model.columnCount()):
                    cellIndex = model.index(row, column)
                    item = model.itemFromIndex(cellIndex)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
            self.part_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        elif self.part_statemachine.state == PartPageState.NEW:
            if not model.data(model.index(0, 0)):
                if any(model.data(model.index(0, column)) for column in range(model.columnCount())):
                    self.db.store_part(*["" if model.data(model.index(0, i)) is None else model.data(model.index(0, i)) for i in range(1, 7)])
            self.part_statemachine.click_save()
            self.part_update_buttons(self.part_statemachine.state)
            for row in range(model.rowCount()):
                for column in range(model.columnCount()):
                    cellIndex = model.index(row, column)
                    item = model.itemFromIndex(cellIndex)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
            self.part_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def partPage_remove_part(self):
        index = self.part_tableView.currentIndex()
        model = self.part_tableView.model()
        if index.isValid():
            row = index.row()
            item = model.itemFromIndex(model.index(row, 0))
            if self.db.delete_part(item.text()):
                model.removeRow(row)
            self.part_statemachine.click_remove()
            self.part_update_buttons(self.part_statemachine.state)

    def partPage_new(self):
        try:
            if self.part_tableView.model():
                model = self.part_tableView.model()
                model.insertRow(0)
                self.part_tableView.selectRow(0)

                index = self.part_tableView.currentIndex()
                # disable all
                for row in range(model.rowCount()):
                    for column in range(model.columnCount()):
                        cellIndex = model.index(row, column)
                        item = model.itemFromIndex(cellIndex)
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                # enable selected
                if index.isValid():
                    self.part_editing_row = index.row()
                    for column in range(model.columnCount()):
                        cellIndex = model.index(self.part_editing_row, column)
                        item = model.itemFromIndex(cellIndex)
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                    self.part_tableView.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
                    self.part_statemachine.click_new()
                    self.part_update_buttons(self.part_statemachine.state)

            else:
                fields_all = ['id', '標準件', '名稱', '品牌', '描述', '規格', '類別']
                model = QStandardItemModel()
                model.setRowCount(1)
                model.setColumnCount(7)
                for column in range(7):
                    index = model.index(0, column, QModelIndex())
                    model.setData(index, "")
                model.setHorizontalHeaderLabels(fields_all)
                self.part_tableView.setModel(model)
                self.part_tableView.hideColumn(0)
                self.part_tableView.selectRow(0)
                if not self.part_statemachine:
                    self.part_statemachine = PartStateMachine()
                self.part_statemachine.click_new()
                self.part_update_buttons(self.part_statemachine.state)
                for column in range(model.columnCount()):
                    cellIndex = model.index(0, column)
                    item = model.itemFromIndex(cellIndex)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                self.part_tableView.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        except Exception as e:
            print(e)

    def part_update_buttons(self, state):
        if state == PartPageState.UNSELECTED:
            self.set_part_buttons(True, False, False, False, False)
        elif state == PartPageState.SELECTED:
            self.set_part_buttons(True, True, True, False, True)
        elif state == PartPageState.EDIT:
            self.set_part_buttons(False, False, True, True, False)
        elif state == PartPageState.NEW:
            self.set_part_buttons(False, False, True, True, False)

    def set_part_buttons(self, new: bool, edit: bool, cancel: bool, save: bool, remove: bool):
        self.new_part_pushButton.setEnabled(new)
        self.edit_part_pushButton.setEnabled(edit)
        self.part_cancalEdit_pushButton.setEnabled(cancel)
        self.part_savechange_pushButton.setEnabled(save)
        self.remove_part_pushButton.setEnabled(remove)

    def update_button(self, tableview: QTableView):
        if tableview.model() is not None and tableview.selectionModel().hasSelection():
            self.part_statemachine.select_row()
            self.part_update_buttons(self.part_statemachine.state)

    def modulePage_searchModule(self):
        fields = ['module_name', 'module_belonging']
        fields_all = ['id', '名稱', '歸屬']
        name = self.module_name_lineEdit_1.text()
        belong = self.module_belonging_comboBox_1.currentText()
        if name == '':
            name = None
        if belong == 'All':
            belong = None
        values = [name, belong]
        fields_values = list(zip(fields, values))
        results = self.db.search_module(fields_values)
        if not results:
            return
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(fields_all)
        for row in results:
            items = [QStandardItem(str(field)) for field in row]
            model.appendRow(items)
        self.module_search_tableView.setModel(model)
        self.module_search_tableView.hideColumn(0)
        self.module_view_pushButton.setEnabled(False)
        self.module_removeModule_pushButton.setEnabled(False)
        self.module_saveModule_pushButton.setEnabled(False)
        self.module_cancelModule_pushButton.setEnabled(False)
        selection_model = self.module_search_tableView.selectionModel()
        selection_model.selectionChanged.connect(self.module_view_button_update)
        selection_model.selectionChanged.connect(self.module_remove_button_update)

    def module_view(self):
        fields_all = ['id', '標準件', '名稱', '品牌', '描述', '規格', '類別', '數量']
        field = ['part_id']
        row = self.module_search_tableView.selectionModel().currentIndex().row()
        self.selected_module_id = self.module_search_tableView.model().index(row, 0).data()
        if not self.selected_module_id:
            return
        self.selected_module_name = self.module_search_tableView.model().index(row, 1).data()
        self.selected_module_belonging = self.module_search_tableView.model().index(row, 2).data()
        ret_value = self.db.search_module_parts(self.selected_module_id)
        model = ModuleTableModel()
        model.setHorizontalHeaderLabels(fields_all)
        for part_id, part_quantity in ret_value:
            fields_values = list(zip(field, [part_id]))
            results = self.db.search_part(fields_values)
            row_items = [QStandardItem(str(item)) for item in results[0]]
            row_items.append(QStandardItem(str(part_quantity)))
            model.appendRow(row_items)
        self.module_content_tableView.setModel(model)
        self.module_content_tableView.hideColumn(0)
        self.stackedWidget_jump(self.module_stackedWidget, 1)
        self.module_name_lineEdit_2.setText(self.selected_module_name if self.selected_module_name else "")
        self.module_belonging_comboBox_2.setCurrentText(self.selected_module_belonging)
        selection_model = self.module_content_tableView.selectionModel()
        selection_model.selectionChanged.connect(self.module_remove_part_button_update)
        self.module_searchPart_tableView.setModel(None)

    def create_new_module(self):
        try:
            if self.module_search_tableView.model():
                model = self.module_search_tableView.model()
                if model.rowCount() and not model.data(model.index(model.rowCount()-1, 0)):
                    return
                model.insertRow(0)
                self.module_search_tableView.selectRow(0)
                index = self.module_search_tableView.currentIndex()
                # disable all
                for row in range(model.rowCount()):
                    for column in range(model.columnCount()):
                        cellIndex = model.index(row, column)
                        item = model.itemFromIndex(cellIndex)
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                # enable selected
                if index.isValid():
                    editing_row = index.row()
                    for column in range(model.columnCount()):
                        cellIndex = model.index(editing_row, column)
                        item = model.itemFromIndex(cellIndex)
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                    self.module_search_tableView.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
                    self.module_saveModule_pushButton.setEnabled(True)
                    self.module_cancelModule_pushButton.setEnabled(True)
            else:
                fields_all = ['id', '名稱', '歸屬']
                model = QStandardItemModel()
                model.setRowCount(1)
                model.setColumnCount(3)
                for column in range(3):
                    index = model.index(0, column, QModelIndex())
                    model.setData(index, "")
                model.setHorizontalHeaderLabels(fields_all)
                self.module_search_tableView.setModel(model)
                self.module_search_tableView.hideColumn(0)
                self.module_search_tableView.selectRow(0)
                for column in range(model.columnCount()):
                    cellIndex = model.index(0, column)
                    item = model.itemFromIndex(cellIndex)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                self.module_search_tableView.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
                self.module_saveModule_pushButton.setEnabled(True)
                self.module_cancelModule_pushButton.setEnabled(True)
        except Exception as e:
            print(e)

    def cancel_new_module(self):
        if self.module_search_tableView.model() is not None and self.module_search_tableView.selectionModel().hasSelection():
            model = self.module_search_tableView.model()
            row = self.module_search_tableView.selectionModel().currentIndex().row()
            if not self.module_search_tableView.model().index(row, 0).data():
                model.removeRow(row)
                for row in range(model.rowCount()):
                    for column in range(model.columnCount()):
                        cellIndex = model.index(row, column)
                        item = model.itemFromIndex(cellIndex)
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                self.module_search_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                self.module_saveModule_pushButton.setEnabled(False)
                self.module_cancelModule_pushButton.setEnabled(False)

    def remove_module(self):
        model = self.module_search_tableView.model()
        selected_row = self.module_search_tableView.selectionModel().currentIndex().row()
        module_id = model.index(selected_row, 0).data()
        if module_id:
            self.db.delete_module(module_id)
        model.removeRow(selected_row)

    def save_new_module(self):
        model = self.module_search_tableView.model()
        selected_row = self.module_search_tableView.selectionModel().currentIndex().row()
        if not model.index(selected_row, 0).data():
            name = model.index(selected_row, 1).data()
            belonging = model.index(selected_row, 2).data()
            if name and belonging:
                self.db.store_module(name, belonging)
                values = [name, belonging]
                fields = ['module_name', 'module_belonging']
                fields_values = list(zip(fields, values))
                results = self.db.search_module(fields_values)
                index = model.index(selected_row, 0)
                model.setData(index, results[0][0])
                for row in range(model.rowCount()):
                    for column in range(model.columnCount()):
                        cellIndex = model.index(row, column)
                        item = model.itemFromIndex(cellIndex)
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                self.module_search_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                self.module_saveModule_pushButton.setEnabled(False)
                self.module_cancelModule_pushButton.setEnabled(False)
                self.module_view_button_update()

    def module_view_button_update(self):
        if self.module_search_tableView.model() is not None and self.module_search_tableView.selectionModel().hasSelection():
            if self.module_search_tableView.model().index(self.module_search_tableView.selectionModel().currentIndex().row(), 0).data():
                self.module_view_pushButton.setEnabled(True)
            else:
                self.module_view_pushButton.setEnabled(False)
        else:
            self.module_view_pushButton.setEnabled(False)

    def module_remove_button_update(self):
        if self.module_search_tableView.model() is not None and self.module_search_tableView.selectionModel().hasSelection():
            self.module_removeModule_pushButton.setEnabled(True)
        else:
            self.module_removeModule_pushButton.setEnabled(False)

    def module_remove_part_button_update(self):
        if self.module_content_tableView.model() is not None and self.module_content_tableView.selectionModel().hasSelection():
            self.module_removePart_pushButton.setEnabled(True)
        else:
            self.module_removePart_pushButton.setEnabled(False)

    def module_removePart(self):
        row = self.module_content_tableView.selectionModel().currentIndex().row()
        self.module_content_tableView.model().removeRow(row)

    def module_search_part(self):
        try:
            fields = ['part_name', 'part_spec', 'part_category']
            fields_all = ['id', '標準件', '名稱', '品牌', '描述', '規格', '類別']
            name = self.module_part_name_lineEdit.text()
            spec = self.module_part_spec_lineEdit.text()
            cate = self.module_part_category_comboBox.currentText()
            if name == '':
                name = None
            if spec == '':
                spec = None
            if cate == '所有':
                cate = None
            values = [name, spec, cate]
            fields_values = list(zip(fields, values))
            results = self.db.search_part(fields_values)
            if not results:
                return
            model = QStandardItemModel()
            model.setHorizontalHeaderLabels(fields_all)
            for row in results:
                items = [QStandardItem(str(field)) for field in row]
                model.appendRow(items)
            self.module_searchPart_tableView.setModel(model)
            self.module_searchPart_tableView.hideColumn(0)
            selection_model = self.module_searchPart_tableView.selectionModel()
            self.module_addPart_pushButton.setEnabled(False)
            selection_model.selectionChanged.connect(self.module_add_part_button_update)
        except Exception as e:
            print(e)

    def module_add_part(self):
        selected_row = self.module_searchPart_tableView.currentIndex().row()
        source_model = self.module_searchPart_tableView.model()
        target_model = self.module_content_tableView.model()
        row_data = []
        part_id = source_model.index(selected_row, 0).data()
        for row in range(target_model.rowCount()):
            if target_model.index(row, 0).data() == part_id:
                print("same")
                return
        for column in range(source_model.columnCount()):
            index = source_model.index(selected_row, column)
            row_data.append(source_model.data(index))
        target_model.insertRow(target_model.rowCount())
        for column, data in enumerate(row_data):
            index = target_model.index(target_model.rowCount()-1, column)
            target_model.setData(index, data)
        index_last = target_model.index(target_model.rowCount()-1, 7)
        target_model.setData(index_last, 0)

    def module_add_part_button_update(self):
        if self.module_searchPart_tableView.model() is not None and self.module_searchPart_tableView.selectionModel().hasSelection():
            self.module_addPart_pushButton.setEnabled(True)
        else:
            self.module_addPart_pushButton.setEnabled(False)

    def module_save_module(self):
        try:
            parts = []
            model = self.module_content_tableView.model()
            module_name = self.module_name_lineEdit_2.text()
            module_cate = self.module_belonging_comboBox_2.currentText()

            for row in range(model.rowCount()):
                part_id = model.index(row, 0).data()
                quantity = model.index(row, 7).data()
                parts.append({'id': part_id, 'quantity': quantity})

            self.db.edit_module_parts(self.selected_module_id, parts)
            self.db.edit_module(module_name, module_cate, self.selected_module_id)
        except Exception as e:
            print(e)

    def module_page_return(self):
        self.module_search_tableView.setModel(None)
        self.stackedWidget_jump(self.module_stackedWidget, 0)

    # station
    def stationPage_searchStation(self):
        fields = ['station_name']
        fields_all = ['id', '名稱']
        name = self.station_name_lineEdit_1.text()
        if name == '':
            name = None
        values = [name]
        fields_values = list(zip(fields, values))
        results = self.db.search_station(fields_values)
        if not results:
            return
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(fields_all)
        for row in results:
            items = [QStandardItem(str(field)) for field in row]
            model.appendRow(items)
        self.station_search_tableView.setModel(model)
        self.station_search_tableView.hideColumn(0)
        self.view_station_pushButton.setEnabled(False)
        selection_model = self.station_search_tableView.selectionModel()
        selection_model.selectionChanged.connect(self.station_view_button_update)

    def station_view(self):
        try:
            fields_all = ['id', '名稱', '歸屬', '數量']
            field = ['module_id']
            row = self.station_search_tableView.selectionModel().currentIndex().row()
            self.selected_station_id = self.station_search_tableView.model().index(row, 0).data()
            self.selected_station_name = self.station_search_tableView.model().index(row, 1).data()
            ret_value = self.db.search_station_modules(self.selected_station_id)
            model = ModuleTableModel()
            model.setHorizontalHeaderLabels(fields_all)
            for module_id, module_quantity in ret_value:
                fields_values = list(zip(field, [module_id]))
                results = self.db.search_module(fields_values)
                row_items = [QStandardItem(str(item)) for item in results[0]]
                row_items.append(QStandardItem(str(module_quantity)))
                model.appendRow(row_items)
            self.station_content_tableView.setModel(model)
            self.station_content_tableView.hideColumn(0)
            self.stackedWidget_jump(self.station_stackedWidget, 1)
            self.station_name_lineEdit_2.setText(self.selected_station_name if self.selected_station_name else "")
            selection_model = self.station_content_tableView.selectionModel()
            selection_model.selectionChanged.connect(self.station_remove_module_button_update)
            self.station_search_module_tableView.setModel(None)
        except Exception as e:
            print(e)

    def create_new_station(self):
        try:
            if self.station_search_tableView.model():
                model = self.station_search_tableView.model()
                if model.rowCount() and not model.data(model.index(model.rowCount()-1, 0)):
                    return
                model.insertRow(0)
                self.station_search_tableView.selectRow(0)
                index = self.station_search_tableView.currentIndex()
                # disable all
                for row in range(model.rowCount()):
                    for column in range(model.columnCount()):
                        cellIndex = model.index(row, column)
                        item = model.itemFromIndex(cellIndex)
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                # enable selected
                if index.isValid():
                    editing_row = index.row()
                    for column in range(model.columnCount()):
                        cellIndex = model.index(editing_row, column)
                        item = model.itemFromIndex(cellIndex)
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                    self.station_search_tableView.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
                    self.station_saveStation_pushButton.setEnabled(True)
                    self.station_cancelStation_pushButton.setEnabled(True)
            else:
                fields_all = ['id', '名稱']
                model = QStandardItemModel()
                model.setRowCount(1)
                model.setColumnCount(2)
                for column in range(2):
                    index = model.index(0, column, QModelIndex())
                    model.setData(index, "")
                model.setHorizontalHeaderLabels(fields_all)
                self.station_search_tableView.setModel(model)
                self.station_search_tableView.hideColumn(0)
                self.station_search_tableView.selectRow(0)
                for column in range(model.columnCount()):
                    cellIndex = model.index(0, column)
                    item = model.itemFromIndex(cellIndex)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                self.station_search_tableView.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
                self.station_saveStation_pushButton.setEnabled(True)
                self.station_cancelStation_pushButton.setEnabled(True)
        except Exception as e:
            print(e)

    def cancel_new_station(self):
        if self.station_search_tableView.model() is not None and self.station_search_tableView.selectionModel().hasSelection():
            model = self.station_search_tableView.model()
            row = self.station_search_tableView.selectionModel().currentIndex().row()
            if not model.index(row, 0).data():
                model.removeRow(row)
                for row in range(model.rowCount()):
                    for column in range(model.columnCount()):
                        cellIndex = model.index(row, column)
                        item = model.itemFromIndex(cellIndex)
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                self.station_search_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                self.station_saveStation_pushButton.setEnabled(False)
                self.station_cancelStation_pushButton.setEnabled(False)

    def remove_station(self):
        model = self.station_search_tableView.model()
        selected_row = self.station_search_tableView.selectionModel().currentIndex().row()
        station_id = model.index(selected_row, 0).data()
        if station_id:
            self.db.delete_station(station_id)
        model.removeRow(selected_row)

    def save_new_station(self):
        model = self.station_search_tableView.model()
        selected_row = self.station_search_tableView.selectionModel().currentIndex().row()
        if not model.index(selected_row, 0).data():
            name = model.index(selected_row, 1).data()
            if name :
                self.db.store_station(name)
                values = [name]
                fields = ['module_name']
                fields_values = list(zip(fields, values))
                results = self.db.search_station(fields_values)
                index = model.index(selected_row, 0)
                model.setData(index, results[0][0])
                for row in range(model.rowCount()):
                    for column in range(model.columnCount()):
                        cellIndex = model.index(row, column)
                        item = model.itemFromIndex(cellIndex)
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                self.station_search_tableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                self.station_saveStation_pushButton.setEnabled(False)
                self.station_cancelStation_pushButton.setEnabled(False)
                self.station_view_button_update()

    def station_view_button_update(self):
        if self.station_search_tableView.model() is not None and self.station_search_tableView.selectionModel().hasSelection():
            if self.station_search_tableView.model().index(self.station_search_tableView.selectionModel().currentIndex().row(), 0).data():
                self.view_station_pushButton.setEnabled(True)
            else:
                self.view_station_pushButton.setEnabled(False)
        else:
            self.view_station_pushButton.setEnabled(False)

    def station_remove_module_button_update(self):
        if self.station_content_tableView.model() is not None and self.station_content_tableView.selectionModel().hasSelection():
            self.station_remove_module_pushButton.setEnabled(True)
        else:
            self.station_remove_module_pushButton.setEnabled(False)

    def station_removeModule(self):
        row = self.station_content_tableView.selectionModel().currentIndex().row()
        self.station_content_tableView.model().removeRow(row)

    def station_search_module(self):
        try:
            fields = ['module_name', 'module_belonging']
            fields_all = ['id', '名稱', '歸屬']
            name = self.station_module_name_lineEdit.text()
            cate = self.station_module_belonging_comboBox.currentText()
            if name == '':
                name = None
            if cate == '所有':
                cate = None
            values = [name, cate]
            fields_values = list(zip(fields, values))
            results = self.db.search_module(fields_values)
            if not results:
                return
            model = QStandardItemModel()
            model.setHorizontalHeaderLabels(fields_all)
            for row in results:
                items = [QStandardItem(str(field)) for field in row]
                model.appendRow(items)
            self.station_search_module_tableView.setModel(model)
            self.station_search_module_tableView.hideColumn(0)
            selection_model = self.station_search_module_tableView.selectionModel()
            self.station_add_module_pushButton.setEnabled(False)
            selection_model.selectionChanged.connect(self.station_add_module_button_update)
        except Exception as e:
            print(e)

    def station_add_module(self):
        selected_row = self.station_search_module_tableView.currentIndex().row()
        source_model = self.station_search_module_tableView.model()
        target_model = self.station_content_tableView.model()
        row_data = []
        module_id = source_model.index(selected_row, 0).data()
        for row in range(target_model.rowCount()):
            if target_model.index(row, 0).data() == module_id:
                print("same")
                return
        for column in range(source_model.columnCount()):
            index = source_model.index(selected_row, column)
            row_data.append(source_model.data(index))
        target_model.insertRow(target_model.rowCount())
        for column, data in enumerate(row_data):
            index = target_model.index(target_model.rowCount()-1, column)
            target_model.setData(index, data)
        index_last = target_model.index(target_model.rowCount()-1, 3)
        target_model.setData(index_last, 0)

    def station_add_module_button_update(self):
        if self.station_search_module_tableView.model() is not None and self.station_search_module_tableView.selectionModel().hasSelection():
            self.station_add_module_pushButton.setEnabled(True)
        else:
            self.station_add_module_pushButton.setEnabled(False)

    def station_save_station(self):
        try:
            modules = []
            model = self.station_content_tableView.model()
            station_name = self.station_name_lineEdit_2.text()

            for row in range(model.rowCount()):
                module_id = model.index(row, 0).data()
                quantity = model.index(row, 3).data()
                modules.append({'id': module_id, 'quantity': quantity})
            self.db.edit_station_modules(self.selected_station_id, modules)
            self.db.edit_station(station_name, self.selected_station_id)
        except Exception as e:
            print(e)

    def station_page_return(self):
        self.station_search_tableView.setModel(None)
        self.view_station_pushButton.setEnabled(False)
        self.stackedWidget_jump(self.station_stackedWidget, 0)


class PartsDatabase:
    def __init__(self):
        self.conn = sqlite3.connect("parts.db")
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS parts (
            part_id INTEGER PRIMARY KEY UNIQUE,
            part_is_standard text,
            part_name text,
            part_vendor text,
            part_description text,
            part_spec text,
            part_category text,
            unique (part_name, part_vendor, part_description, part_spec)
        )
        ''')
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            module_id INTEGER PRIMARY KEY,
            module_name text UNIQUE,
            module_belonging text
        )
        ''')
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules_parts (
            module_id INTEGER,
            part_id INTEGER,
            quantity INTEGER,
            FOREIGN KEY(module_id) REFERENCES modules(module_id),
            FOREIGN KEY(part_id) REFERENCES parts(part_id),
            unique (module_id, part_id)
        )
        ''')
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS stations (
            station_id INTEGER PRIMARY KEY,
            station_name text UNIQUE
        )
        ''')
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS stations_modules (
            station_id INTEGER,
            module_id INTEGER,
            quantity INTEGER,
            FOREIGN KEY(station_id) REFERENCES stations(station_id),
            FOREIGN KEY(module_id) REFERENCES modules(module_id),
            unique (station_id, module_id)
        )
        ''')

        self.conn.commit()

    def store_part(self, part_is_standard, part_name, part_vendor, part_description, part_spec, part_category):
        self.cursor.execute('''
           INSERT INTO parts (part_is_standard, part_name, part_vendor, part_description, part_spec, part_category) VALUES(?, ?, ?, ?, ?, ?)
        ''', (part_is_standard, part_name, part_vendor, part_description, part_spec, part_category))
        self.conn.commit()

    def store_from_excel(self):
        self.cursor.execute(f"PRAGMA table_info(parts)")
        table_info = self.cursor.fetchall()

    def store_module(self, module_name, module_belonging):
        self.cursor.execute('''
           INSERT INTO modules (module_name, module_belonging) VALUES(?, ?)
        ''', (module_name, module_belonging))
        self.conn.commit()

    def store_module_parts(self, module_id, part_id, quantity):
        self.cursor.execute('''
           INSERT INTO modules_parts (module_id, part_id, quantity) VALUES(?, ?, ?)
        ''', (module_id, part_id, quantity))
        self.conn.commit()

    def store_station(self, station_name):
        self.cursor.execute('''
           INSERT INTO stations (station_name) VALUES(?)
        ''', (station_name,))
        self.conn.commit()

    def store_station_modules(self, station_id, module_id, quantity):
        self.cursor.execute('''
           INSERT INTO stations_modules (station_id, module_id, quantity) VALUES(?, ?, ?)
        ''', (station_id, module_id, quantity))
        self.conn.commit()

    def delete_part(self, part_id) -> bool:
        query = "DELETE FROM parts WHERE part_id = ?"
        try:
            self.cursor.execute(query, part_id)
            self.conn.commit()
            return True
        except Exception as e:
            print(e)
            return False

    def delete_module(self, module_id):
        self.cursor.execute("DELETE FROM modules_parts WHERE module_id = ?", (module_id,))
        self.cursor.execute("DELETE FROM modules WHERE module_id = ?", (module_id,))
        self.conn.commit()

    def delete_station(self, station_id):
        self.cursor.execute("DELETE FROM stations_modules WHERE station_id = ?", (station_id,))
        self.cursor.execute("DELETE FROM stations WHERE station_id = ?", (station_id,))
        self.conn.commit()

    def search_part(self, fields_values):
        query = "SELECT * FROM parts"
        conditions = []
        values = []
        for field, value in fields_values:
            if value is not None:
                conditions.append(f"{field} LIKE ?")
                values.append(f"%{value}%")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        self.cursor.execute(query, values)
        return self.cursor.fetchall()

    def search_module(self, fields_values):
        query = "SELECT * FROM modules"
        conditions = []
        values = []
        for field, value in fields_values:
            if value is not None:
                conditions.append(f"{field} LIKE ?")
                values.append(f"%{value}%")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        self.cursor.execute(query, values)
        return self.cursor.fetchall()

    def search_module_parts(self, module_id):
        try:
            self.cursor.execute('''
                SELECT part_id, quantity
                FROM modules_parts
                WHERE module_id = ?
            ''', (module_id,))
        except Exception as e:
            print(e)
        return self.cursor.fetchall()

    def search_station(self, fields_values):
        query = "SELECT * FROM stations"
        conditions = []
        values = []
        for field, value in fields_values:
            if value is not None:
                conditions.append(f"{field} LIKE ?")
                values.append(f"%{value}%")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        self.cursor.execute(query, values)
        return self.cursor.fetchall()

    def search_station_modules(self, station_id):
        try:
            self.cursor.execute('''
                SELECT module_id, quantity
                FROM stations_modules
                WHERE station_id = ?
            ''', (station_id,))
        except Exception as e:
            print(e)
        return self.cursor.fetchall()

    def edit_part(self, part_is_standard, part_name, part_vendor, part_description, part_spec, part_category, part_id):
        sql = "UPDATE parts SET part_is_standard = ?, part_name = ?, part_vendor = ?, part_description = ?, part_spec = ?, part_category = ? WHERE part_id = ?"
        self.cursor.execute(sql, (part_is_standard, part_name, part_vendor, part_description, part_spec, part_category, part_id))
        self.conn.commit()

    def edit_module(self, module_name, module_cate, module_id):
        try:
            sql = "UPDATE modules SET module_name = ?, module_belonging = ? WHERE module_id = ?"
            self.cursor.execute(sql, (module_name, module_cate, module_id))
            self.conn.commit()
        except Exception as e:
            print(e)

    def edit_module_parts(self, module_id, parts):
        self.cursor.execute('BEGIN TRANSACTION')
        try:
            self.cursor.execute("DELETE FROM modules_parts WHERE module_id = ?", (module_id,))
            for part in parts:
                self.store_module_parts(module_id, part['id'], part['quantity'])
            self.conn.commit()
        except sqlite3.Error as e:
            self.conn.rollback()

    def edit_station(self, station_name, module_id):
        try:
            sql = "UPDATE stations SET station_name = ? WHERE station_id = ?"
            self.cursor.execute(sql, (station_name, module_id))
            self.conn.commit()
        except Exception as e:
            print(e)

    def edit_station_modules(self, station_id, modules):
        self.cursor.execute('BEGIN TRANSACTION')
        try:
            self.cursor.execute("DELETE FROM stations_modules WHERE station_id = ?", (station_id,))
            for module in modules:
                self.store_station_modules(station_id, module['id'], module['quantity'])
            self.conn.commit()
        except sqlite3.Error as e:
            print(e)
            self.conn.rollback()

    def close(self):
        self.conn.close()


if __name__ == '__main__':
    db = PartsDatabase()
    try:
        db.store_part("標準件", "三通手動閥", "SMC", "無洩氣，兩通閥，接管孔徑1(P)Φ8/2(A)Φ8", "VHK3-08F-08F", "氣動元件")
        db.store_part("標準件", "兩通手動閥", "SMC", "無洩氣，兩通閥，接管孔徑1(P)Φ8/2(A)Φ8", "VHK2-08F-08F", "氣動元件")
        db.store_module("Input_stopper", "Conveyor")
        db.store_module_parts(1, 2, 15)
        db.store_module("input_lifter", "Robot")
        db.store_module_parts(1, 1, 10)
        db.store_station("IO_Port")
        db.store_station_modules(1, 1, 4)
    except Exception as e:
        pass
    ret = db.search_part([("part_vendor", "SMC"), ("part_name", "三通手動閥")])
    for i in ret:
        print(i)
    db.close()
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
