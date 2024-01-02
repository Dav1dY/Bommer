import sqlite3
from PyQt6 import QtWidgets
from PyQt6 import uic


class MainWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        uic.loadUi('main_window.ui', self)

        self.submitButton.clicked.connect(self.goToSubmitPage)
        self.backButton.clicked.connect(self.goToMainPage)
        self.exitButton.clicked.connect(self.close)

    def goToSubmitPage(self):
        currentIndex = self.stackedWidget.currentIndex()
        if currentIndex + 1 < self.stackedWidget.count():
            self.stackedWidget.setCurrentIndex(currentIndex + 1)

    def goToMainPage(self):
        self.stackedWidget.setCurrentIndex(0)


class PartsDatabase:
    def __init__(self):
        self.conn = sqlite3.connect("parts.db")
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS parts (
            part_id INTEGER PRIMARY KEY,
            part_is_standard text,
            part_name text,
            part_vendor text,
            part_description text,
            part_spec text
        ) 
        ''')
        self.conn.commit()

    def store_part(self, part_is_standard, part_name, part_vendor, part_description, part_spec):
        self.cursor.execute('''
           INSERT INTO parts (part_is_standard, part_name, part_vendor, part_description, part_spec) VALUES(?, ?, ?, ?, ?)        
        ''', (part_is_standard, part_name, part_vendor, part_description, part_spec))
        self.conn.commit()

    def search_part(self, field, value):
        self.cursor.execute(f"SELECT * FROM parts WHERE {field} = ?", (value,))
        return self.cursor.fetchall()

    def edit_part(self, part_is_standard, part_name, part_vendor, part_description, part_spec):
        sql = "UPDATE parts SET part_is_standard = ?, part_name = ?, part_vendor = ?, part_description = ?, part_spec = ? WHERE part_od = ?"
        self.cursor.execute(sql, (part_is_standard, part_name, part_vendor, part_description, part_spec))
        self.conn.commit()

    def close(self):
        self.conn.close()


if __name__ == '__main__':
    # import sys
    # app = QtWidgets.QApplication(sys.argv)
    # window = MainWindow()
    # window.show()
    # sys.exit(app.exec())
    db = PartsDatabase()
    db.store_part("標準件", "兩通手動閥", "SMC", "無洩氣，兩通閥，接管孔徑1(P)Φ8/2(A)Φ8", "VHK2-08F-08F")
    ret = db.search_part("part_vendor", "SMC")
    for i in ret:
        print(i)
    db.close()
