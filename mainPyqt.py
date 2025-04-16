import sys
import os
import tempfile
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                             QPlainTextEdit, QTextEdit, QToolBar, QAction, QMessageBox,
                             QSplitter, QPushButton)
from PyQt5.QtGui import QFont, QTextCursor, QColor, QTextCharFormat, QSyntaxHighlighter
from PyQt5.QtCore import Qt, QProcess, QTimer, QRegExp

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
        layout = QVBoxLayout()
        splitter = QSplitter(Qt.Vertical)
        
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Courier", 12))
        self.highlighter = PythonHighlighter(self.editor.document())
        
        self.console = ConsoleWidget()
        self.console.setFont(QFont("Courier", 12))
        
        splitter.addWidget(self.editor)
        splitter.addWidget(self.console)
        splitter.setSizes([600, 200])
        layout.addWidget(splitter)
        self.setLayout(layout)

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

    def _create_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        toolbar.addAction("New", self.new_tab)
        toolbar.addAction("Run", self.run_code)
        toolbar.addAction("Stop", self.stop_code)
        toolbar.addAction("Clear Console", self.clear_console)

    def _create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction("New", self.new_tab)
        file_menu.addAction("Exit", self.close)
        
        run_menu = menubar.addMenu("&Run")
        run_menu.addAction("Run", self.run_code)
        run_menu.addAction("Stop", self.stop_code)

    def new_tab(self):
        tab = CodeTab(self.temp_dir)
        index = self.tabs.addTab(tab, "Untitled")
        self.tabs.setCurrentIndex(index)

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