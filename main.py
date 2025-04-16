import tkinter as tk
from tkinter import ttk, filedialog
from tkinter.scrolledtext import ScrolledText
import tempfile
import shutil
import os
import subprocess
import threading
from queue import Queue, Empty
import atexit

class CodeTab:
    def __init__(self, notebook, temp_dir):
        self.frame = ttk.Frame(notebook)
        self.notebook = notebook
        self.text = ScrolledText(self.frame, wrap='word')
        self.console = ScrolledText(self.frame, wrap='word', state='disabled')
        self.temp_dir = temp_dir
        self.temp_file = tempfile.NamedTemporaryFile(mode='w+', dir=self.temp_dir, delete=False, suffix='.py')
        self.temp_file_path = self.temp_file.name
        self.temp_file.close()
        self.process = None
        self.queue = Queue()
        self.setup_layout()

    def setup_layout(self):
        self.text.pack(fill='both', expand=True)
        self.console.pack(fill='both', expand=True)

    def run_code(self):
        with open(self.temp_file_path, 'w') as f:
            f.write(self.text.get('1.0', 'end-1c'))
        self.process = subprocess.Popen(['python', self.temp_file_path], 
                                       stdout=subprocess.PIPE, 
                                       stderr=subprocess.PIPE,
                                       text=True)
        stdout_thread = threading.Thread(target=self.read_output, args=(self.process.stdout,))
        stderr_thread = threading.Thread(target=self.read_output, args=(self.process.stderr,))
        stdout_thread.start()
        stderr_thread.start()
        self.update_console()

    def read_output(self, stream):
        for line in iter(stream.readline, ''):
            self.queue.put(line)
        stream.close()

    def update_console(self):
        try:
            while True:
                line = self.queue.get_nowait()
                self.console.configure(state='normal')
                self.console.insert('end', line)
                self.console.see('end')
                self.console.configure(state='disabled')
        except Empty:
            pass
        self.frame.after(100, self.update_console)

    def cleanup(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
        if os.path.exists(self.temp_file_path):
            os.remove(self.temp_file_path)

class PyIDE:
    def __init__(self, root):
        self.root = root
        self.temp_dir = tempfile.mkdtemp()
        self.tabs = []
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True)
        self.create_menu()
        self.create_controls()
        atexit.register(self.cleanup)

    def create_menu(self):
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New Tab", command=self.new_tab)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)

    def create_controls(self):
        controls_frame = ttk.Frame(self.root)
        controls_frame.pack(fill='x')
        run_btn = ttk.Button(controls_frame, text="Run", command=self.run_current)
        run_btn.pack(side='left')
        new_tab_btn = ttk.Button(controls_frame, text="New Tab", command=self.new_tab)
        new_tab_btn.pack(side='left')

    def new_tab(self):
        tab = CodeTab(self.notebook, self.temp_dir)
        self.notebook.add(tab.frame, text=f"Tab {len(self.tabs)+1}")
        self.tabs.append(tab)

    def run_current(self):
        current_index = self.notebook.index(self.notebook.select())
        if current_index >= 0:
            self.tabs[current_index].run_code()

    def cleanup(self):
        for tab in self.tabs:
            tab.cleanup()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Python IDE")
    ide = PyIDE(root)
    ide.new_tab()
    root.mainloop()