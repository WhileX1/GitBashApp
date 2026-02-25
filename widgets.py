import os
import tkinter as tk
from tkinter import filedialog
from helpers import (MouseWheelHelper, set_placeholder, clear_placeholder, 
                     count_selected_files, update_counter_var)
from config import BOLD_FONT, DEFAULT_FONT
from helpers import show_warning

class FileSelectionWindow:
    def _on_paste(self, event, var, entry):
        # Intercetta il testo incollato e verifica se è un percorso valido
        try:
            pasted = self.win.clipboard_get()
        except Exception:
            return "break"
        # Considera valido solo se esiste come file o cartella, oppure se rispetta uno stile di path
        import re
        is_path = os.path.exists(pasted) or re.match(r'^[a-zA-Z]:\\|^/|^\\\\', pasted)
        if not is_path:
            from helpers import show_warning
            show_warning("Attenzione", "Il testo incollato non sembra un percorso valido e verrà ignorato.")
            return "break"
        # Se valido, lascia che l'evento prosegua normalmente
        return None
    def __init__(self, parent, files, num_var, on_files_saved, app_ref=None):
        self.parent = parent
        self.files = files
        self.num_var = num_var
        self.on_files_saved = on_files_saved
        self._app_ref = app_ref  # riferimento all'app principale
        self.placeholder = "Nessun path inserito"
        self.placeholder_fg = "#888"
        self.normal_fg = "#000"
        self.selected_count_var = tk.StringVar()
        self.file_entries = []
        self._row_widgets = []  # Per tracciare i widget delle righe
        self.win = tk.Toplevel(parent)
        self.win.title("Seleziona file da aggiungere")
        self.win.geometry("460x340")
        self.win.resizable(False, False)
        self.win.focus()
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.on_cancel)
        # Se la finestra viene distrutta in modo anomalo, azzera il riferimento nell'app
        if self._app_ref is not None:
            self.win.bind("<Destroy>", lambda e: self._on_destroy())
        # --- Nuovo layout: frame principale con due sezioni verticali ---
        self.main_frame = tk.Frame(self.win)
        self.main_frame.pack(fill="both", expand=True)
        # Sezione superiore: scrollabile, stile branch
        self.sugg_container = tk.Frame(self.main_frame, relief="groove", borderwidth=2)
        self.sugg_container.pack(fill="both", expand=True, padx=10, pady=(10,0))
        self.canvas = tk.Canvas(self.sugg_container, borderwidth=0, highlightthickness=0, height=180, bg="#f8f8f8")
        self.canvas.pack(side="left", fill="both", expand=True, padx=0, pady=0)
        self.vscroll = tk.Scrollbar(self.sugg_container, orient="vertical", command=self.canvas.yview, width=18)
        self.vscroll.pack(side="right", fill="y", padx=0, pady=0)
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.files_frame = tk.Frame(self.canvas, bg="#f8f8f8")
        self.files_frame_id = self.canvas.create_window((0, 0), window=self.files_frame, anchor="nw")

        def on_canvas_configure(event):
            canvas_width = event.width
            self.canvas.itemconfig(self.files_frame_id, width=canvas_width)
        self.canvas.bind('<Configure>', on_canvas_configure)

        def update_scrollregion(event=None):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.files_frame.bind("<Configure>", update_scrollregion)
        # --- Mouse wheel scroll: ora usa la funzione helper centralizzata ---
        get_count = lambda: self.num_var.get()
        self._bind_mousewheel, self._unbind_mousewheel = MouseWheelHelper.setup(self.canvas, self.win, get_count, 9)
        if self.num_var.get() >= 9:
            self._bind_mousewheel()
        self.win.protocol("WM_DELETE_WINDOW", lambda: (self.on_cancel(), self._unbind_mousewheel()))
        self.win.bind("<Destroy>", lambda e: self._unbind_mousewheel())
        # Sezione inferiore: frame pulsanti sempre visibile
        self.close_frame = tk.Frame(self.main_frame)
        self.close_frame.pack(fill="x", pady=(8,16), padx=(24,24), side="bottom")
        self.close_frame.columnconfigure(0, weight=0)
        self.close_frame.columnconfigure(1, weight=1)
        self.close_frame.columnconfigure(2, weight=0)
        btn_annulla = tk.Button(self.close_frame, text="Annulla", command=self.on_cancel, font=("Segoe UI", 10, "bold"))
        btn_annulla.grid(row=0, column=0, padx=4)
        counter_container = tk.Frame(self.close_frame)
        counter_container.grid(row=0, column=1)
        btn_minus = tk.Button(counter_container, text="-", width=2, font=("Segoe UI", 10, "bold"), command=lambda: self.num_var.set(max(1, self.num_var.get()-1)))
        btn_minus.pack(side="left", padx=(0,2))
        tk.Label(counter_container, textvariable=self.selected_count_var, font=("Segoe UI", 10, "bold"), fg="#555", width=6, anchor="center").pack(side="left", padx=(0,2))
        btn_plus = tk.Button(counter_container, text="+", width=2, font=("Segoe UI", 10, "bold"), command=lambda: self.num_var.set(self.num_var.get()+1))
        btn_plus.pack(side="left")
        btn_salva = tk.Button(self.close_frame, text="Salva", command=self.on_save, font=("Segoe UI", 10, "bold"))
        btn_salva.grid(row=0, column=2, padx=4)
        self.num_var.trace_add('write', lambda *a: self.update_ui())
        self.update_ui()
        # Modalità dialog: sempre in primo piano ma non blocca la main window
        self.win.transient(self.parent)
        # self.win.grab_set()  # RIMOSSO: la main window resta interattiva

    # Usa i metodi statici centralizzati di GitGuiApp per i placeholder

    def _make_row(self, idx, var):
        # Crea una riga con pulsante e entry, e la aggiunge a files_frame.
        row_frame = tk.Frame(self.files_frame)
        row_frame.pack(fill="x", padx=1, pady=2)
        btn = tk.Button(row_frame, text=f"File {idx+1}", font=("Segoe UI", 10, "bold"))
        btn.pack(side="left", padx=(0, 4))
        entry_width = 24 if self.num_var.get() > 7 else 38
        entry = tk.Entry(row_frame, textvariable=var, font=("Segoe UI", 10, "bold"), fg=self.placeholder_fg, width=entry_width)
        entry.pack(side="left", fill="x", expand=True, padx=(0,4), ipadx=2)
        btn.config(command=lambda idx=idx, var=var, ent=entry: self.select_file(idx, var, ent))
        entry.bind("<FocusIn>", lambda e, var=var, ent=entry: clear_placeholder(var, ent, self.placeholder, self.normal_fg))
        entry.bind("<FocusOut>", lambda e, var=var, ent=entry: set_placeholder(var, ent, self.placeholder, self.placeholder_fg))
        var.trace_add('write', lambda *a: self.update_selected_count())
        # Always scroll to end when value changes
        def scroll_to_end(*_):
            entry.after(1, lambda: entry.xview_moveto(1.0))
        var.trace_add('write', scroll_to_end)
        # Gestione incolla: intercetta ctrl+v e paste
        entry.bind("<Control-v>", lambda e, v=var, ent=entry: self._on_paste(e, v, ent))
        entry.bind("<Control-V>", lambda e, v=var, ent=entry: self._on_paste(e, v, ent))
        entry.bind("<<Paste>>", lambda e, v=var, ent=entry: self._on_paste(e, v, ent))
        self._row_widgets.append((row_frame, btn, entry))
        return row_frame, btn, entry

    def select_file(self, idx, var, ent):
        # Nascondi la finestra principale e la finestra di selezione prima di aprire la dialog
        self.parent.withdraw()
        self.win.withdraw()
        self.win.attributes("-topmost", False)
        # Permetti solo selezione multipla di file (NO cartelle)
        file_paths = filedialog.askopenfilenames(title=f"Seleziona uno o più file per la posizione {idx+1}")
        self.win.deiconify()
        self.win.attributes("-topmost", True)
        self.parent.deiconify()
        if not file_paths:
            var.set(self.placeholder)
            ent.config(fg=self.placeholder_fg)
            self.files[idx] = None
            return
        n_files = len(file_paths)
        # Selezionati più file del contatore? Aggiorna il contatore e la lista
        if idx + n_files > self.num_var.get():
            self.num_var.set(idx + n_files)
            # Espandi la lista file_entries e files se necessario (update_ui lo farà)
        # Se sono stati selezionati più file, li inserisce a partire da idx
        for i, fpath in enumerate(file_paths):
            if idx + i >= len(self.files):
                self.files.append(None)
            path = os.path.normpath(fpath)
            self.files[idx + i] = path
            # Aggiorna anche la variabile associata all'entry
            if idx + i < len(self.file_entries):
                self.file_entries[idx + i].set(path)
                # Scroll to end after setting value
                entry_widget = self._row_widgets[idx + i][2]
                entry_widget.after(1, lambda ent=entry_widget: ent.xview_moveto(1.0))
        # Aggiorna il colore dell'entry corrente
        if file_paths:
            ent.config(fg=self.normal_fg)
            ent.after(1, lambda: ent.xview_moveto(1.0))

    def get_selected_count(self):
        # Usa la funzione helper centralizzata
        return count_selected_files([var.get() for var in self.file_entries], self.placeholder)

    def update_selected_count(self):
        update_counter_var(self.selected_count_var, self.get_selected_count, self.num_var)

    def on_cancel(self):
        # Reset contatore e svuota selezione file
        self.num_var.set(1)
        self.files.clear()
        for var in self.file_entries:
            var.set("")
        self.win.destroy()
        self.parent.deiconify()
        self.parent.focus_force()
        # Azzeramento riferimento finestra nell'app principale
        if self._app_ref is not None:
            self._app_ref._file_selection_window = None

    def on_save(self):
        # Check for empty fields before saving
        empty_found = False
        for idx, var in enumerate(self.file_entries):
            val = var.get().strip()
            if not val or val == self.placeholder:
                empty_found = True
                break
        if empty_found:
            # Show warning that auto-closes after 1 second
            import threading
            from helpers import show_warning
            def close_warning():
                # Find and destroy the warning window after 1s
                for w in self.win.winfo_children():
                    if isinstance(w, tk.Toplevel) and 'warning' in str(w).lower():
                        w.destroy()
            def show_and_close():
                show_warning("Attenzione", "Tutti i campi devono essere compilati.")
                self.win.after(1000, lambda: [w.destroy() for w in self.win.winfo_children() if isinstance(w, tk.Toplevel) and 'warning' in str(w).lower()])
            self.win.after(10, show_and_close)
            return
        for idx, var in enumerate(self.file_entries):
            val = var.get().strip()
            if val and val != self.placeholder:
                self.files[idx] = val
            else:
                self.files[idx] = None
        self.win.destroy()
        self.parent.deiconify()
        self.parent.focus_force()
        # Azzeramento riferimento finestra nell'app principale
        if self._app_ref is not None:
            self._app_ref._file_selection_window = None
        if self.on_files_saved:
            self.on_files_saved()

    def update_ui(self):
        # Prevent update if window or frame is destroyed
        if not hasattr(self, 'win') or not hasattr(self, 'files_frame'):
            return
        try:
            if not self.win.winfo_exists() or not self.files_frame.winfo_exists():
                return
        except Exception:
            return
        num = int(self.num_var.get())
        prev_values = [var.get() for var in self.file_entries] if self.file_entries else []
        # Rimuovi righe in eccesso e widget associati
        while len(self.file_entries) > num:
            idx = len(self.file_entries) - 1
            try:
                if hasattr(self, '_row_widgets') and idx < len(self._row_widgets):
                    row_frame, btn, entry = self._row_widgets[idx]
                    row_frame.destroy()
                    self._row_widgets.pop()
            except Exception:
                pass
            self.file_entries.pop()
        # Aggiungi righe mancanti tramite funzione privata
        while len(self.file_entries) < num:
            var = tk.StringVar()
            self.file_entries.append(var)
            self._make_row(len(self.file_entries)-1, var)
        # Aggiorna valori
        for i in range(num):
            if i < len(prev_values):
                self.file_entries[i].set(prev_values[i])
            elif i < len(self.files) and self.files[i]:
                self.file_entries[i].set(self.files[i])
            elif not self.file_entries[i].get():
                self.file_entries[i].set("")
            # Always scroll to end after setting value
            if hasattr(self, '_row_widgets') and i < len(self._row_widgets):
                entry_widget = self._row_widgets[i][2]
                entry_widget.after(1, lambda ent=entry_widget: ent.xview_moveto(1.0))
        if len(self.files) < num:
            self.files.extend([None]*(num-len(self.files)))
        elif len(self.files) > num:
            del self.files[num:]
        # Imposta il placeholder se il campo è vuoto e aggiorna il colore
        try:
            for i in range(num):
                if hasattr(self, '_row_widgets') and i < len(self._row_widgets):
                    entry_widget = self._row_widgets[i][2]
                    val = self.file_entries[i].get()
                    if not val or val == self.placeholder:
                        # Usa il placeholder senza GitGuiApp
                        entry_widget.config(fg=self.placeholder_fg)
                        self.file_entries[i].set(self.placeholder)
                    else:
                        entry_widget.config(fg=self.normal_fg)
        except Exception:
            pass
        self.selected_count_var.set(f"{self.get_selected_count()}/{num}")
        # Aggiorna larghezza canvas solo se necessario
        if self.canvas is not None and self.files_frame_id is not None:
            if self.files_frame is not None:
                try:
                    # update_idletasks solo se necessario
                    if num > 8:
                        self.files_frame.update_idletasks()
                        self.win.update_idletasks()
                    canvas_width = self.canvas.winfo_width() or 340
                    self.canvas.itemconfig(self.files_frame_id, width=canvas_width)
                except tk.TclError:
                    pass
        # Gestione dinamica dei binding della rotella
        if hasattr(self, '_bind_mousewheel') and hasattr(self, '_unbind_mousewheel'):
            if num >= 9:
                self._bind_mousewheel()
            else:
                self._unbind_mousewheel()


class RequestGithubLoginOrAccountDialog:
    # Dialogo unico che mostra prima la scelta tra Login e URL, poi il form di input URL
    def __init__(self, parent, on_login_callback, on_manual_url_callback):
        self.parent = parent
        self.on_login_callback = on_login_callback
        self.on_manual_url_callback = on_manual_url_callback
        self.show_warning = show_warning
        self.BOLD_FONT = BOLD_FONT
        self.DEFAULT_FONT = DEFAULT_FONT
        # Crea la finestra di dialogo
        self.dialog_win = tk.Toplevel(parent)
        self.dialog_win.title("Autentica GitHub")
        self.dialog_win.geometry("420x200")
        self.dialog_win.resizable(False, False)
        self.dialog_win.attributes("-topmost", True)
        self.dialog_win.focus()
        self.dialog_win.lift()
        # Container principale per contenuto dinamico
        self.content_frame = tk.Frame(self.dialog_win)
        self.content_frame.pack(fill="both", expand=True)
        # Mostra la prima schermata (scelta tra Login e URL)
        self.show_auth_choice()
    
    def clear_content(self):
        # Pulisce il contenuto del frame principale
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def show_auth_choice(self):
        # Mostra la schermata di scelta tra Login e URL manuale
        self.clear_content()
        
        # Titolo
        tk.Label(self.content_frame, text="Autentica GitHub", font=self.BOLD_FONT).pack(pady=10)
        # Messaggio
        msg_text = "Scegli il metodo di autenticazione:"
        tk.Label(self.content_frame, text=msg_text, font=self.DEFAULT_FONT).pack(pady=5)
        # Frame per i pulsanti in due colonne
        btn_frame_main = tk.Frame(self.content_frame)
        btn_frame_main.pack(expand=True, pady=10, padx=15)
        # Colonna sinistra: Login con GitHub CLI
        left_frame = tk.Frame(btn_frame_main)
        left_frame.pack(side="left", padx=5, expand=True, fill="both")
        tk.Button(left_frame, text="Login GitHub CLI", command=self.on_login, 
                  font=self.BOLD_FONT, width=18, height=2).pack()
        # Colonna destra: URL manuale
        right_frame = tk.Frame(btn_frame_main)
        right_frame.pack(side="right", padx=5, expand=True, fill="both")
        tk.Button(right_frame, text="Inserisci URL", command=self.show_url_input, 
                  font=self.BOLD_FONT, width=18, height=2).pack()
        # Frame per il pulsante Annulla
        btn_frame = tk.Frame(self.content_frame)
        btn_frame.pack(side="bottom", fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Annulla", command=self.on_cancel, font=self.BOLD_FONT).pack(padx=5)
    
    def show_url_input(self):
        # Mostra la schermata di input dell'URL della repository
        self.clear_content()
        # Titolo
        tk.Label(self.content_frame, text="Collega Repository Remota", font=self.BOLD_FONT).pack(pady=10)
        # Messaggio
        msg_text = "Inserisci l'URL della repository remota su GitHub:"
        tk.Label(self.content_frame, text=msg_text, font=self.DEFAULT_FONT).pack(pady=5)
        # Campo input
        self.url_var = tk.StringVar()
        url_entry = tk.Entry(self.content_frame, textvariable=self.url_var, font=self.BOLD_FONT, width=50)
        url_entry.pack(pady=10, padx=10)
        url_entry.focus()
        # Placeholder hint
        tk.Label(self.content_frame, text="Es: https://github.com/username/repository.git", font=self.DEFAULT_FONT, fg="gray").pack()
        # Pulsanti
        btn_frame = tk.Frame(self.content_frame)
        btn_frame.pack(side="bottom", fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Indietro", command=self.show_auth_choice, font=self.BOLD_FONT).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Collega", command=self.on_confirm_url, font=self.BOLD_FONT).pack(side="right", padx=5)
        # Binding per il tasto Enter
        url_entry.bind("<Return>", lambda e: self.on_confirm_url())
    
    def on_login(self):
        self.dialog_win.destroy()
        self.on_login_callback()
    
    def on_confirm_url(self):
        repo_url = self.url_var.get().strip()
        if not repo_url:
            self.show_warning("Avviso", "Inserisci un URL valido.")
            return
        if not repo_url.startswith("https://") and not repo_url.startswith("git@"):
            self.show_warning("Avviso", "L'URL deve iniziare con 'https://' o 'git@'.")
            return
        self.dialog_win.destroy()
        self.on_manual_url_callback(repo_url)
    
    def on_cancel(self):
        self.dialog_win.destroy()
