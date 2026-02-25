import sys
import os
import tkinter as tk
import tkinter.messagebox as mb
import subprocess
from config import LAST_DIR_FILE

class MouseWheelHelper:
    @staticmethod
    def setup(canvas, parent_win, item_count_func, threshold):
        helper = MouseWheelHelper(canvas, parent_win, item_count_func, threshold)
        return helper.bind_mousewheel, helper.unbind_mousewheel
    def __init__(self, canvas, parent_win, item_count_func, threshold):
        self.canvas = canvas
        self.parent_win = parent_win
        self.item_count_func = item_count_func
        self.threshold = threshold
        self.mousewheel_bound = False
        self.parent_win.bind("<Destroy>", self._on_destroy)
        self._update_binding()
    def _on_mousewheel(self, event):
        if self.item_count_func() >= self.threshold:
            if hasattr(event, 'delta') and event.delta:
                delta = int(-1 * (event.delta / 120))
                self.canvas.yview_scroll(delta, "units")
            elif hasattr(event, 'num'):
                if event.num == 4:
                    self.canvas.yview_scroll(-3, "units")
                elif event.num == 5:
                    self.canvas.yview_scroll(3, "units")
    def _update_binding(self):
        if self.item_count_func() >= self.threshold:
            self.bind_mousewheel()
        else:
            self.unbind_mousewheel()
    def bind_mousewheel(self):
        if not self.mousewheel_bound:
            self.parent_win.bind_all('<MouseWheel>', self._on_mousewheel)
            self.parent_win.bind_all('<Button-4>', self._on_mousewheel)
            self.parent_win.bind_all('<Button-5>', self._on_mousewheel)
            self.mousewheel_bound = True
    def unbind_mousewheel(self):
        if self.mousewheel_bound:
            self.parent_win.unbind_all('<MouseWheel>')
            self.parent_win.unbind_all('<Button-4>')
            self.parent_win.unbind_all('<Button-5>')
            self.mousewheel_bound = False
    def _on_destroy(self, event=None):
        self.unbind_mousewheel()

def create_scrollable_list(parent, height, threshold, item_count_func, parent_win, **canvas_kwargs):
    container = tk.Frame(parent, relief="groove", borderwidth=2)
    canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0, height=height, **canvas_kwargs)
    canvas.pack(side="left", fill="both", expand=True)
    vscroll = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    vscroll.pack(side="right", fill="y")
    canvas.configure(yscrollcommand=vscroll.set)
    btn_frame = tk.Frame(canvas)
    btn_window = canvas.create_window((0, 0), window=btn_frame, anchor="nw")
    def on_canvas_configure(event):
        canvas.itemconfig(btn_window, width=event.width)
    canvas.bind('<Configure>', on_canvas_configure)
    def update_scrollregion(event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
    btn_frame.bind("<Configure>", update_scrollregion)
    helper = MouseWheelHelper(canvas, parent_win, item_count_func, threshold)
    def update_mousewheel_binding():
        helper._update_binding()
    return container, canvas, btn_frame, update_mousewheel_binding

def save_last_dir(path):
    try:
        with open(LAST_DIR_FILE, "w", encoding="utf-8") as f:
            f.write(path)
    except (OSError, IOError) as e:
        print(f"[save_last_dir] Errore nel salvataggio: {e}")

def load_last_dir():
    try:
        with open(LAST_DIR_FILE, "r", encoding="utf-8") as f:
            d = f.read().strip()
            if d and os.path.isdir(d):
                return d
    except (OSError, IOError) as e:
        print(f"[load_last_dir] Errore nel caricamento: {e}")
    return None

def set_placeholder(var, ent, placeholder, placeholder_fg):
    if not var.get():
        ent.config(fg=placeholder_fg)
        var.set(placeholder)

def clear_placeholder(var, ent, placeholder, normal_fg):
    if var.get() == placeholder:
        var.set("")
        ent.config(fg=normal_fg)

def count_selected_files(files, placeholder=None):
    # Conta i file selezionati validi (non vuoti e diversi dal placeholder).
    if placeholder is None:
        return len([f for f in files if f and f.strip()])
    return len([f for f in files if f and f.strip() and f != placeholder])

def update_counter_var(counter_var, get_count_func, num_var=None):
    # Aggiorna una StringVar counter_var con il valore restituito da get_count_func.
    # Se num_var è fornito, mostra anche il totale (es: 2/5).
    count = get_count_func()
    if num_var is not None:
        counter_var.set(f"{count}/{num_var.get()}")
    else:
        counter_var.set(str(count))

def show_error(title, message):
    mb.showerror(title, message)

def show_warning(title, message):
    mb.showwarning(title, message)

def show_info(title, message):
    mb.showinfo(title, message)

    # Helper universale per subprocess: nasconde sempre la console su Windows
def get_subprocess_kwargs():
    # Restituisce i parametri startupinfo e creationflags per nascondere la console su Windows.
    kwargs = {}
    if sys.platform.startswith("win"):
        if hasattr(subprocess, 'STARTF_USESHOWWINDOW'):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs['startupinfo'] = startupinfo
        if hasattr(subprocess, 'CREATE_NO_WINDOW'):
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    return kwargs