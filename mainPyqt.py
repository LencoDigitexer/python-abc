import sys
import os
import tempfile
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                             QPlainTextEdit, QTextEdit, QToolBar, QAction, QMessageBox,
                             QSplitter, QPushButton, QFileDialog, QStatusBar, QLabel, QHBoxLayout)
from PyQt5.QtGui import (QFont, QTextCursor, QColor, QTextCharFormat, QSyntaxHighlighter,
                         QPainter, QTextFormat)
from PyQt5.QtCore import Qt, QProcess, QTimer, QRegExp, QRect, QSize


class LineNumberWidget(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.editor.blockCountChanged.connect(self.update_width)
        self.editor.updateRequest.connect(self.update_area)
        self.update_width()

    def update_width(self):
        width = self.fontMetrics().width(str(self.editor.blockCount())) + 10
        self.setFixedWidth(width)
        self.update()

    def update_area(self, rect, dy):
        if dy:
            self.scroll(0, dy)
        else:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), Qt.lightGray)
        block = self.editor.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
        bottom = top + self.editor.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(0, round(top), 
                                 self.width(), self.fontMetrics().height(),
                                 Qt.AlignRight, str(block_number + 1))
            block = block.next()
            top = bottom
            bottom = top + self.editor.blockBoundingRect(block).height()
            block_number += 1

class ConsoleWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.setReadOnly(False)
        self.prompt = "" # вывод приглашения в консоль
        self.append(self.prompt)
        self.history = []
        self.current_line = ""
        self.history_index = 0

    def set_process(self, process):
        self.process = process

    def keyPressEvent(self, event):
        if self.process and self.process.state() == QProcess.Running:
            cursor = self.textCursor()
            if event.key() == Qt.Key_Backspace:
                if cursor.positionInBlock() > len(self.prompt):
                    super().keyPressEvent(event)
            elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
                line = cursor.block().text()[len(self.prompt):]
                self.process.write(f"{line}\n".encode())
                self.history.append(line)
                self.history_index = len(self.history)
                self.append(self.prompt)
            elif event.key() == Qt.Key_Up:
                if self.history_index > 0:
                    self.history_index -= 1
                    self._replace_line(self.history[self.history_index])
            elif event.key() == Qt.Key_Down:
                if self.history_index < len(self.history)-1:
                    self.history_index +=1
                    self._replace_line(self.history[self.history_index])
                else:
                    self._replace_line("")
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def _replace_line(self, text):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, len(self.prompt))
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.setTextCursor(cursor)

    def append_output(self, text):
        self.moveCursor(QTextCursor.End)
        self.insertPlainText(text)
        self.moveCursor(QTextCursor.End)

    def clear_console(self):
        self.clear()
        self.append(self.prompt)

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.styles = {
            'keyword': self._format(Qt.blue, bold=True),
            'string': self._format(Qt.darkGreen),
            'comment': self._format(Qt.darkGray),
            'number': self._format(Qt.darkMagenta),
            'function': self._format(Qt.darkCyan)
        }
        self.rules = []
        self._build_rules()

    def _format(self, color, bold=False):
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        if bold:
            fmt.setFontWeight(QFont.Bold)
        return fmt

    def _build_rules(self):
        keywords = ['and', 'as', 'assert', 'break', 'class', 'continue', 'def', 'del',
                    'elif', 'else', 'except', 'False', 'finally', 'for', 'from', 'global',
                    'if', 'import', 'in', 'is', 'lambda', 'None', 'nonlocal', 'not', 'or',
                    'pass', 'raise', 'return', 'True', 'try', 'while', 'with', 'yield']
        self.rules += [(rf'\b{kw}\b', self.styles['keyword']) for kw in keywords]
        self.rules += [(r'".*?"', self.styles['string']),
                       (r"'.*?'", self.styles['string']),
                       (r'#.*', self.styles['comment']),
                       (r'\b\d+\b', self.styles['number']),
                       (r'\b[A-Za-z0-9_]+(?=\()', self.styles['function'])]

    def highlightBlock(self, text):
        for pattern, format in self.rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

class CodeTab(QWidget):
    def __init__(self, temp_dir):
        super().__init__()
        self.temp_dir = temp_dir
        self.process = None
        self.file_path = None
        
        layout = QVBoxLayout()
        splitter = QSplitter(Qt.Vertical)
        
        # Редактор кода
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Courier", 12))
        
        # Номера строк
        self.line_number_widget = LineNumberWidget(self.editor)
        
        # Компоновка для редактора и номеров строк
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addWidget(self.line_number_widget)
        hbox.addWidget(self.editor)
        editor_container = QWidget()
        editor_container.setLayout(hbox)
        
        # Подсветка синтаксиса
        self.highlighter = PythonHighlighter(self.editor.document())
        
        # Консоль
        self.console = ConsoleWidget()
        self.console.setFont(QFont("Courier", 12))
        
        # Статусная строка
        self.status_label = QLabel("Ln 1, Col 1")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # Сигналы для обновления статуса
        self.editor.cursorPositionChanged.connect(self.update_status)
        self.editor.textChanged.connect(self.update_line_numbers)
        
        splitter.addWidget(editor_container)
        splitter.addWidget(self.console)
        splitter.setSizes([600, 200])
        
        layout.addWidget(splitter)
        layout.addWidget(self.status_label)
        self.setLayout(layout)
        
    def update_line_numbers(self):
        self.line_number_widget.update()
        self.line_number_widget.update_width()

    def update_status(self):
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber()
        self.status_label.setText(f"Ln {line}, Col {col}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)
        self._init_ui()
        self.new_tab()

    def _init_ui(self):
        self._create_toolbar()
        self._create_menu()
        self.setWindowTitle("Python ABC IDE")
        self.setGeometry(100, 100, 1200, 800)
        self.statusBar().showMessage("Ready") # Статусная строка

    def _create_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        toolbar.addAction("New", self.new_tab)
        toolbar.addAction("Open", self.open_file)
        toolbar.addAction("Save", self.save_file)
        toolbar.addAction("Save As", self.save_as_file)
        toolbar.addAction("Run", self.run_code)
        toolbar.addAction("Stop", self.stop_code)
        toolbar.addAction("Clear Console", self.clear_console)

    def _create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction("New", self.new_tab)
        file_menu.addAction("Open", self.open_file)
        file_menu.addAction("Save", self.save_file)
        file_menu.addAction("Save As", self.save_as_file)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)
        
        run_menu = menubar.addMenu("&Run")
        run_menu.addAction("Run", self.run_code)
        run_menu.addAction("Stop", self.stop_code)

    def new_tab(self):
        tab = CodeTab(self.temp_dir)
        index = self.tabs.addTab(tab, "Untitled")
        self.tabs.setCurrentIndex(index)
        return tab
    
    def current_tab(self):
        return self.tabs.currentWidget()
    
    def save_file(self):
        tab = self.current_tab()
        if not tab:
            return
            
        if tab.file_path:
            try:
                with open(tab.file_path, 'w') as f:
                    f.write(tab.editor.toPlainText())
                self.statusBar().showMessage(f"Saved {tab.file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save file:\n{str(e)}")
        else:
            self.save_as_file()

    def save_as_file(self):
        tab = self.current_tab()
        if not tab:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Python File",
            "",
            "Python Files (*.py);;All Files (*)"
        )
        
        if file_path:
            tab.file_path = file_path
            self.save_file()
            self.tabs.setTabText(self.tabs.currentIndex(), os.path.basename(file_path))

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Python File",
            "",
            "Python Files (*.py);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                tab = self.new_tab()
                tab.editor.setPlainText(content)
                tab.file_path = file_path
                self.tabs.setTabText(self.tabs.currentIndex(), os.path.basename(file_path))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file:\n{str(e)}")

    def close_tab(self, index):
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.close()

    def run_code(self):
        tab = self.tabs.currentWidget()
        if not tab:
            return
            
        code = tab.editor.toPlainText()
        with tempfile.NamedTemporaryFile(suffix='.py', 
                                        dir=self.temp_dir.name, 
                                        delete=False, 
                                        mode='w') as f:
            f.write(code)
            filename = f.name

        process = QProcess(self)
        tab.process = process
        process.setProcessChannelMode(QProcess.MergedChannels)
        
        process.readyReadStandardOutput.connect(
            lambda: tab.console.append_output(
                process.readAllStandardOutput().data().decode()
            )
        )
        
        process.started.connect(lambda: tab.console.set_process(process))
        process.finished.connect(lambda: setattr(tab, 'process', None))
        
        process.start(sys.executable, [filename])
        process.waitForStarted()

    def stop_code(self):
        tab = self.tabs.currentWidget()
        if tab and tab.process:
            tab.process.kill()

    def clear_console(self):
        tab = self.tabs.currentWidget()
        if tab:
            tab.console.clear_console()

    def closeEvent(self, event):
        self.temp_dir.cleanup()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())