import tkinter as tk
from tkinter import ttk
import tempfile
import shutil
import os
import subprocess
import threading
import atexit
import sys

class ConsoleFrame(ttk.Frame):
    def __init__(self, parent, temp_dir):
        super().__init__(parent)
        self.temp_dir = temp_dir
        self.pty = None
        self.console = None
        self.create_widgets()
        self.start_console()

    def create_widgets(self):
        self.console = tk.Text(self, wrap='char', state='disabled', 
                              bg='black', fg='white', insertbackground='white')
        self.console.pack(fill='both', expand=True)
        self.console.bind('<Key>', self.on_key)

    def start_console(self):
        try:
            import winpty
            self.pty = winpty.PTY(80, 25)
            
            # Запуск процесса через PTY
            self.process = subprocess.Popen(
                ['python', '-i', '-q'],
                stdin=subprocess.PIPE,
                stdout=self.pty.fd,
                stderr=self.pty.fd,
                text=True,
                bufsize=1,
                cwd=self.temp_dir
            )
            
            # Запуск потока для чтения вывода
            threading.Thread(target=self.read_output, daemon=True).start()
            
        except Exception as e:
            self.console.configure(state='normal')
            self.console.insert('end', f"Error: {str(e)}\n")
            self.console.configure(state='disabled')

    def read_output(self):
        while True:
            try:
                # Чтение данных через winpty
                data = self.pty.read()
                if data:
                    self.console.configure(state='normal')
                    self.console.insert('end', data)
                    self.console.see('end')
                    self.console.configure(state='disabled')
            except Exception:
                break

    def on_key(self, event):
        if self.pty and self.process.poll() is None:
            key = event.char
            if key:
                # Запись ввода в процесс
                self.pty.write(key)

    def cleanup(self):
        if self.process:
            self.process.terminate()
            self.process.wait()

class PyIDE:
    def __init__(self, root):
        self.root = root
        self.temp_dir = tempfile.mkdtemp()
        self.tabs = []
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True)
        self.create_menu()
        self.create_controls()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
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
        run_btn = ttk.Button(controls_frame, text="Restart Console", command=self.restart_console)
        run_btn.pack(side='left')
        new_tab_btn = ttk.Button(controls_frame, text="New Tab", command=self.new_tab)
        new_tab_btn.pack(side='left')

    def new_tab(self):
        tab = ConsoleFrame(self.notebook, self.temp_dir)
        self.notebook.add(tab, text=f"Console {len(self.tabs)+1}")
        self.tabs.append(tab)

    def restart_console(self):
        current_index = self.notebook.index(self.notebook.select())
        if current_index >= 0:
            self.tabs[current_index].cleanup()
            self.tabs[current_index].start_console()

    def cleanup(self):
        for tab in self.tabs:
            tab.cleanup()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def on_closing(self):
        self.cleanup()
        self.root.destroy()

if __name__ == "__main__":
    if sys.platform != 'win32':
        print("Эта версия работает только на Windows")
        sys.exit(1)
        
    root = tk.Tk()
    root.title("Python ABC IDE with Real Console")
    ide = PyIDE(root)
    ide.new_tab()
    root.mainloop()