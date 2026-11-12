
import os
import re
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ============================================================
# VELORA PC - Windows Edition
# ============================================================

APP_NAME = "VELORA"

BG = "#09090d"
PANEL = "#111118"
PANEL2 = "#191923"
BORDER = "#292936"
FG = "#eeeeF5"
MUTED = "#888897"
PURPLE = "#9b7cff"
PURPLE_DARK = "#7052d4"
GREEN = "#8de0b0"
RED = "#ff8195"

KEYWORDS = set("""
and break do else elseif end false for function if in local nil
not or repeat return then true until while goto
""".split())

BUILTINS = set("""
assert collectgarbage dofile error getmetatable ipairs load
loadfile next pairs pcall print rawequal rawget rawlen rawset
select setmetatable tonumber tostring type xpcall coroutine
debug io math os package string table utf8
""".split())

PATTERNS = [
    ("comment", re.compile(r"--.*$")),
    ("string", re.compile(
        r"""("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')"""
    )),
    ("number", re.compile(r"\b\d+(?:\.\d+)?\b")),
    ("function", re.compile(r"\b[A-Za-z_]\w*(?=\s*\()")),
    ("keyword", re.compile(
        r"\b(?:" + "|".join(map(re.escape, KEYWORDS)) + r")\b"
    )),
    ("builtin", re.compile(
        r"\b(?:" + "|".join(map(re.escape, BUILTINS)) + r")\b"
    )),
]


class EditorTab:

    def __init__(self, notebook, content="", path=None):

        self.path = path
        self.frame = ttk.Frame(notebook)

        self.text = tk.Text(
            self.frame,
            bg=BG,
            fg=FG,
            insertbackground=PURPLE,
            selectbackground="#40345f",
            selectforeground="#ffffff",
            font=("Cascadia Code", 10),
            undo=True,
            maxundo=-1,
            wrap="none",
            padx=16,
            pady=14,
            relief="flat",
            borderwidth=0
        )

        self.scroll_y = ttk.Scrollbar(
            self.frame,
            orient="vertical",
            command=self.text.yview
        )

        self.scroll_x = ttk.Scrollbar(
            self.frame,
            orient="horizontal",
            command=self.text.xview
        )

        self.text.configure(
            yscrollcommand=self.scroll_y.set,
            xscrollcommand=self.scroll_x.set
        )

        self.text.grid(row=0, column=0, sticky="nsew")
        self.scroll_y.grid(row=0, column=1, sticky="ns")
        self.scroll_x.grid(row=1, column=0, sticky="ew")

        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)

        colors = {
            "keyword": "#c4a7ff",
            "builtin": "#85c9ff",
            "string": "#a8dba8",
            "comment": "#777787",
            "number": "#f2bd83",
            "function": "#80d8d0"
        }

        for tag, color in colors.items():
            self.text.tag_configure(tag, foreground=color)

        self.text.insert("1.0", content)

        self.highlight_job = None
        self.text.bind("<KeyRelease>", self.schedule_highlighting)

        self.highlight_all()

    def schedule_highlighting(self, event=None):

        if self.highlight_job:
            self.text.after_cancel(self.highlight_job)

        self.highlight_job = self.text.after(
            180,
            self.highlight_current_line
        )

    def highlight_current_line(self):

        self.highlight_job = None

        line = int(self.text.index("insert").split(".")[0])

        self.highlight_line(line)

    def highlight_line(self, number):

        start = f"{number}.0"
        end = f"{number}.end"

        for tag in (
            "keyword",
            "builtin",
            "string",
            "comment",
            "number",
            "function"
        ):
            self.text.tag_remove(tag, start, end)

        content = self.text.get(start, end)

        for tag, pattern in PATTERNS:

            for match in pattern.finditer(content):

                self.text.tag_add(
                    tag,
                    f"{number}.{match.start()}",
                    f"{number}.{match.end()}"
                )

    def highlight_all(self):

        self.highlight_line_number = 1

        self.highlight_total = int(
            self.text.index("end-1c").split(".")[0]
        )

        self.highlight_chunk()

    def highlight_chunk(self):

        stop = min(
            self.highlight_line_number + 150,
            self.highlight_total + 1
        )

        for number in range(self.highlight_line_number, stop):

            self.highlight_line(number)

        self.highlight_line_number = stop

        if self.highlight_line_number <= self.highlight_total:

            self.text.after(1, self.highlight_chunk)

    def get_content(self):

        return self.text.get("1.0", "end-1c")


class VeloraApp:

    def __init__(self, root):

        self.root = root

        self.root.title("VELORA")
        self.root.geometry("1160x740")
        self.root.minsize(820, 540)
        self.root.configure(bg=BG)

        self.tabs = {}
        self.tab_counter = 0

        self.process = None
        self.process_thread = None

        self.configure_styles()
        self.build_interface()

        self.new_tab()

        self.log("VELORA workspace initialized.", "success")

        self.log(
            "Standalone Lua workspace ready.",
            "info"
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close_application
        )

    # --------------------------------------------------------
    # INTERFACE
    # --------------------------------------------------------

    def configure_styles(self):

        style = ttk.Style()

        style.theme_use("clam")

        style.configure(
            "TFrame",
            background=BG
        )

        style.configure(
            "TNotebook",
            background=BG,
            borderwidth=0,
            tabmargins=0
        )

        style.configure(
            "TNotebook.Tab",
            background=PANEL,
            foreground=MUTED,
            padding=(15, 9),
            borderwidth=0
        )

        style.map(
            "TNotebook.Tab",
            background=[("selected", PANEL2)],
            foreground=[("selected", FG)]
        )

        style.configure(
            "TScrollbar",
            background=PANEL,
            troughcolor=BG,
            bordercolor=BG,
            arrowcolor=MUTED
        )

    def make_button(self, parent, label, command, accent=False):

        button = tk.Button(
            parent,
            text=label,
            command=command,
            bg=PURPLE_DARK if accent else PANEL2,
            fg="#ffffff" if accent else FG,
            activebackground=PURPLE,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=13,
            pady=7,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2"
        )

        return button

    def build_interface(self):

        header = tk.Frame(
            self.root,
            bg=PANEL,
            height=58,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        header.pack(fill="x")
        header.pack_propagate(False)

        logo = tk.Frame(header, bg=PANEL)
        logo.pack(side="left", padx=20)

        tk.Label(
            logo,
            text="V",
            bg=PANEL,
            fg=PURPLE,
            font=("Segoe UI", 20, "bold")
        ).pack(side="left")

        tk.Label(
            logo,
            text="ELORA",
            bg=PANEL,
            fg=FG,
            font=("Segoe UI", 15, "bold")
        ).pack(side="left")

        tk.Label(
            header,
            text="SCRIPT WORKSPACE",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8, "bold")
        ).pack(side="left", padx=18)

        actions = tk.Frame(header, bg=PANEL)
        actions.pack(side="right", padx=12)

        buttons = [
            ("New", self.new_tab, False),
            ("Open", self.open_file, False),
            ("Save", self.save_file, False),
            ("Run Lua", self.run_script, True),
            ("Stop", self.stop_script, False)
        ]

        for label, command, accent in buttons:

            self.make_button(
                actions,
                label,
                command,
                accent
            ).pack(side="left", padx=3)

        # Editor

        editor_container = tk.Frame(self.root, bg=BG)

        editor_container.pack(
            fill="both",
            expand=True,
            padx=14,
            pady=(14, 8)
        )

        self.notebook = ttk.Notebook(editor_container)

        self.notebook.pack(
            fill="both",
            expand=True
        )

        # Console

        console_box = tk.Frame(
            self.root,
            bg=PANEL,
            height=150,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        console_box.pack(
            fill="x",
            padx=14,
            pady=(0, 10)
        )

        console_box.pack_propagate(False)

        tk.Label(
            console_box,
            text="  OUTPUT CONSOLE",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", pady=(7, 2))

        self.console = tk.Text(
            console_box,
            bg="#0c0c12",
            fg="#c9c9d5",
            font=("Cascadia Code", 9),
            relief="flat",
            height=5,
            state="disabled",
            padx=10,
            pady=6,
            wrap="word"
        )

        self.console.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=(0, 1)
        )

        self.console.tag_configure(
            "error",
            foreground=RED
        )

        self.console.tag_configure(
            "success",
            foreground=GREEN
        )

        self.console.tag_configure(
            "info",
            foreground=PURPLE
        )

        # Status bar

        footer = tk.Frame(
            self.root,
            bg=PANEL,
            height=30
        )

        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self.status = tk.Label(
            footer,
            text="READY · LOCAL LUA WORKSPACE",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8, "bold")
        )

        self.status.pack(side="left", padx=14)

        runtime_color = GREEN if self.find_lua() else "#e9c77d"

        self.runtime_label = tk.Label(
            footer,
            text=self.runtime_text(),
            bg=PANEL,
            fg=runtime_color,
            font=("Segoe UI", 8)
        )

        self.runtime_label.pack(side="right", padx=14)

    # --------------------------------------------------------
    # RUNTIME
    # --------------------------------------------------------

    def find_lua(self):

        return (
            shutil.which("lua")
            or shutil.which("luajit")
        )

    def runtime_text(self):

        if self.find_lua():

            return "LUA RUNTIME DETECTED"

        return "LUA RUNTIME NOT FOUND"

    # --------------------------------------------------------
    # TABS
    # --------------------------------------------------------

    def current_tab(self):

        selected = self.notebook.select()

        return self.tabs.get(selected)

    def new_tab(self, content="", path=None):

        self.tab_counter += 1

        tab = EditorTab(
            self.notebook,
            content,
            path
        )

        self.tabs[str(tab.frame)] = tab

        name = (
            os.path.basename(path)
            if path
            else f"untitled-{self.tab_counter}.lua"
        )

        self.notebook.add(
            tab.frame,
            text=name
        )

        self.notebook.select(tab.frame)

        self.update_status("NEW SCRIPT")

    # --------------------------------------------------------
    # FILE MANAGEMENT
    # --------------------------------------------------------

    def open_file(self):

        path = filedialog.askopenfilename(
            filetypes=[
                ("Lua/Luau scripts", "*.lua *.luau"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if not path:
            return

        try:

            with open(
                path,
                "r",
                encoding="utf-8-sig",
                errors="replace"
            ) as file:

                content = file.read()

            self.new_tab(content, path)

            size = os.path.getsize(path)

            self.log(
                f"Opened {os.path.basename(path)} · {size:,} bytes",
                "success"
            )

        except Exception as error:

            messagebox.showerror(
                "VELORA",
                str(error)
            )

    def save_file(self):

        tab = self.current_tab()

        if not tab:
            return

        path = tab.path

        if not path:

            path = filedialog.asksaveasfilename(
                defaultextension=".lua",
                filetypes=[
                    ("Lua scripts", "*.lua"),
                    ("Luau scripts", "*.luau"),
                    ("All files", "*.*")
                ]
            )

        if not path:
            return

        try:

            content = tab.get_content()

            with open(
                path,
                "w",
                encoding="utf-8",
                newline="\n"
            ) as file:

                file.write(content)

            tab.path = path

            self.notebook.tab(
                tab.frame,
                text=os.path.basename(path)
            )

            self.log(
                f"Saved {len(content):,} characters.",
                "success"
            )

            self.update_status("SAVED")

        except Exception as error:

            messagebox.showerror(
                "VELORA",
                str(error)
            )

    # --------------------------------------------------------
    # EXECUTION
    # --------------------------------------------------------

    def run_script(self):

        tab = self.current_tab()

        if not tab:
            return

        lua = self.find_lua()

        if not lua:

            self.log(
                "Lua runtime not found. Install Lua and add 'lua' to PATH.",
                "error"
            )

            return

        source = tab.get_content()

        if not source.strip():

            self.log(
                "The current editor is empty.",
                "error"
            )

            return

        self.stop_script()

        fd, path = tempfile.mkstemp(
            suffix=".lua",
            prefix="velora_"
        )

        os.close(fd)

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(source)

        self.update_status("RUNNING")

        self.log(
            "Executing locally...",
            "info"
        )

        def worker():

            try:

                process = subprocess.Popen(
                    [lua, path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )

                self.process = process

                output, errors = process.communicate()

                code = process.returncode

                if output:

                    self.root.after(
                        0,
                        lambda: self.log(output.rstrip(), "success")
                    )

                if errors:

                    self.root.after(
                        0,
                        lambda: self.log(errors.rstrip(), "error")
                    )

                self.root.after(
                    0,
                    lambda: self.log(
                        f"Finished · exit code {code}",
                        "success" if code == 0 else "error"
                    )
                )

            except Exception as error:

                self.root.after(
                    0,
                    lambda: self.log(str(error), "error")
                )

            finally:

                try:
                    os.remove(path)
                except OSError:
                    pass

                self.root.after(
                    0,
                    lambda: self.update_status("READY")
                )

        self.process_thread = threading.Thread(
            target=worker,
            daemon=True
        )

        self.process_thread.start()

    def stop_script(self):

        if self.process and self.process.poll() is None:

            self.process.terminate()

            self.log(
                "Stop requested.",
                "info"
            )

        self.update_status("READY")

    # --------------------------------------------------------
    # CONSOLE / STATUS
    # --------------------------------------------------------

    def log(self, message, tag=None):

        if not message:
            return

        self.console.configure(state="normal")

        self.console.insert(
            "end",
            message + "\n",
            tag or ()
        )

        self.console.see("end")

        self.console.configure(state="disabled")

    def update_status(self, message):

        self.status.configure(
            text=f"{message} · LOCAL LUA WORKSPACE"
        )

    # --------------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------------

    def close_application(self):

        self.stop_script()

        self.root.destroy()


if __name__ == "__main__":

    root = tk.Tk()

    application = VeloraApp(root)

    root.mainloop()
