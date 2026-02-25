import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

REQUIRED_MODULES = [
    "tkinter",
    "pywin32",
    "psutil"
]


class InstallerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Installazione dipendenze")
        # Stile coerente con la finestra "seleziona file":
        self.root.geometry("420x220")
        self.root.resizable(False, False)
        self.root.configure(bg="#f8f8f8")
        self.cancelled = False
        self.thread = None

        # Main frame
        self.main_frame = tk.Frame(root, bg="#f8f8f8")
        self.main_frame.pack(fill="both", expand=True)

        # Log area (non scrollabile, solo poche righe)
        self.log = tk.Text(self.main_frame, height=5, width=54, state='disabled', bg="#f8f8f8", font=("Segoe UI", 10), wrap="word")
        self.log.pack(pady=(18, 5), padx=16, fill="x")

        # Progress bar
        self.progress = ttk.Progressbar(self.main_frame, orient="horizontal", length=350, mode="determinate")
        self.progress.pack(pady=10)

        # Button frame
        self.btn_frame = tk.Frame(self.main_frame, bg="#f8f8f8")
        self.btn_frame.pack(pady=10)
        btn_opts = dict(font=("Segoe UI", 10, "bold"), width=12, height=1)
        self.cancel_btn = tk.Button(self.btn_frame, text="Annulla", command=self.cancel_install, state='disabled', **btn_opts)
        self.cancel_btn.pack(side=tk.LEFT, padx=8)
        self.start_btn = tk.Button(self.btn_frame, text="Installa", command=self.start_install, **btn_opts)
        self.start_btn.pack(side=tk.LEFT, padx=8)
        # Pulsante OK, inizialmente nascosto
        self.ok_btn = tk.Button(self.btn_frame, text="OK", command=self.root.destroy, **btn_opts)
        self.ok_btn.pack_forget()

        # Frame per domanda download CLI (inizialmente nascosto)
        self.cli_question_frame = tk.Frame(self.main_frame, bg="#f8f8f8")
        self.cli_question_frame.pack_forget()
        cli_label = tk.Label(self.cli_question_frame, text="Scaricare GitHub CLI?", font=("Segoe UI", 10, "bold"), bg="#f8f8f8")
        cli_label.pack(side="left", padx=(0, 10))
        self.cli_close_btn = tk.Button(self.cli_question_frame, text="Chiudi", font=("Segoe UI", 10, "bold"), command=self.root.destroy)
        self.cli_close_btn.pack(side="left", padx=6)
        self.cli_download_btn = tk.Button(self.cli_question_frame, text="Scarica", font=("Segoe UI", 10, "bold"), fg="#0057b7", cursor="hand2", command=self.open_gh_cli_url)
        self.cli_download_btn.pack(side="left", padx=6)


        # Stato per la richiesta collegamento
        self.ask_shortcut = False
        # Pulsanti per la scelta collegamento (inizialmente nascosti)
        self.shortcut_btn_frame = tk.Frame(self.main_frame, bg="#f8f8f8")
        self.shortcut_question_label = tk.Label(self.shortcut_btn_frame, text="Creare collegamento?", font=("Segoe UI", 10, "bold"), bg="#f8f8f8")
        self.change_folder_btn = tk.Button(self.shortcut_btn_frame, text="Cambia cartella", command=self.change_shortcut_folder, font=("Segoe UI", 10, "bold"))
        self.confirm_shortcut_btn = tk.Button(self.shortcut_btn_frame, text="Conferma", command=self.confirm_shortcut, font=("Segoe UI", 10, "bold"))
        # NON pack qui: saranno packati solo quando serve

        # Percorso di default per il collegamento
        self.shortcut_folder = os.path.join(os.path.expanduser("~"), "Desktop")

        self.log_message("Pronto per l'installazione.")

    def log_message(self, msg):
        self.log.config(state='normal')
        self.log.insert(tk.END, msg + '\n')
        self.log.see(tk.END)
        self.log.config(state='disabled')
        # Gestione pulsanti in base allo stato
        if msg == "Pronto per l'installazione.":
            self.show_default_buttons()
        elif msg.startswith("Creare collegamento?"):
            self.show_shortcut_buttons()
        elif msg.startswith("Installazione completata"):
            self.show_cli_question()

    def show_default_buttons(self):
        # Mostra Installa e Annulla, nasconde gli altri
        self.shortcut_btn_frame.pack_forget()
        self.ok_btn.pack_forget()
        self.start_btn.pack(side=tk.LEFT, padx=8)
        self.cancel_btn.pack(side=tk.LEFT, padx=8)

    def show_shortcut_buttons(self):
        # Nasconde tutti i pulsanti della btn_frame
        self.start_btn.pack_forget()
        self.cancel_btn.pack_forget()
        self.ok_btn.pack_forget()
        self.btn_frame.pack_forget()  # Nasconde il frame dei pulsanti principali
        # Mostra label domanda e i due pulsanti sulla stessa riga
        for widget in self.shortcut_btn_frame.winfo_children():
            widget.pack_forget()
        self.shortcut_question_label.pack(side="left", padx=(0, 10))
        self.change_folder_btn.pack(side="left", padx=8)
        self.confirm_shortcut_btn.pack(side="left", padx=8)
        self.shortcut_btn_frame.pack(pady=10)

    def show_ok_button(self):
        # (Non più usato: ora si mostra la domanda CLI)
        self.shortcut_btn_frame.pack_forget()
        self.start_btn.pack_forget()
        self.cancel_btn.pack_forget()
        self.ok_btn.pack_forget()

    def show_cli_question(self):
        # Nasconde tutti i pulsanti e mostra la domanda CLI
        self.shortcut_btn_frame.pack_forget()
        self.btn_frame.pack_forget()
        self.ok_btn.pack_forget()
        # Riposiziona i pulsanti: Chiudi a sinistra, Scarica a destra
        for widget in self.cli_question_frame.winfo_children():
            widget.pack_forget()
        self.cli_question_frame.pack_forget()
        cli_label = self.cli_question_frame.winfo_children()[0]
        self.cli_close_btn.pack_forget()
        self.cli_download_btn.pack_forget()
        cli_label.pack(side="left", padx=(0, 10))
        self.cli_close_btn.pack(side="left", padx=6)
        self.cli_download_btn.pack(side="right", padx=6)
        self.cli_question_frame.pack(pady=10)

    def change_shortcut_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(initialdir=self.shortcut_folder, title="Seleziona cartella per il collegamento")
        if folder:
            self.shortcut_folder = folder
            # Aggiorna solo il log senza cambiare i pulsanti
            self.log.config(state='normal')
            self.log.insert(tk.END, f"Percorso: {self.shortcut_folder}\n")
            self.log.see(tk.END)
            self.log.config(state='disabled')

    def confirm_shortcut(self):
        # Crea il collegamento diretto a main.py con icona personalizzata
        self.log_message("Creazione collegamento sul desktop...")
        try:
            # Percorso del file launcher.py nella stessa cartella dell'installer
            base_dir = os.path.dirname(os.path.abspath(__file__))
            target_py = os.path.join(base_dir, "launcher.py")
            if not os.path.exists(target_py):
                raise FileNotFoundError(f"launcher.py non trovato in {base_dir}")
            pythonw = get_pythonw_path()
            shortcut_path = os.path.join(self.shortcut_folder, "GitBashApp.lnk")
            icon_path = os.path.join(base_dir, "icona.ico")
            if not os.path.exists(icon_path):
                icon_path = None  # fallback: nessuna icona
            # Collegamento diretto a pythonw.exe con argomento il file launcher.py
            create_shortcut((pythonw, f'"{target_py}"'), shortcut_path, icon_path=icon_path, description="Avvia Git Bash Automatico senza console")
            self.log_message(f"Collegamento creato: {shortcut_path}")
            # Mostra la domanda CLI invece del pulsante OK
            self.shortcut_btn_frame.pack_forget()
            self.btn_frame.pack_forget()
            self.ok_btn.pack_forget()
            self.cli_question_frame.pack(pady=10)
        except Exception as e:
            self.log_message(f"Errore creazione collegamento: {e}")
            self.shortcut_btn_frame.pack_forget()
            self.show_default_buttons()

    def start_install(self):
        self.cancelled = False
        self.progress['value'] = 0
        self.start_btn.config(state='disabled')
        self.cancel_btn.config(state='normal')
        self.log.config(state='normal')
        self.log.delete(1.0, tk.END)
        self.log.config(state='disabled')
        self.log_message("Installazione in corso...")
        self.thread = threading.Thread(target=self.install_missing_modules)
        self.thread.start()

    def ask_shortcut_question(self):
        # Mostra la domanda collegamento nel log con il path selezionato
        self.log_message(f"Percorso: {self.shortcut_folder}")
        self.show_shortcut_buttons()

    def cancel_install(self):
        self.cancelled = True
        self.log_message("Installazione annullata.")
        self.cancel_btn.config(state='disabled')

    def install_missing_modules(self):
        # Moduli di sistema che non si installano con pip
        system_modules = ["tkinter"]
        # Moduli pip da installare (tutti tranne tkinter)
        pip_modules = [m for m in REQUIRED_MODULES if m not in system_modules]
        total = len(system_modules) + len(pip_modules)
        installed = 0

        # Controlla moduli di sistema
        for mod in system_modules:
            if self.cancelled:
                self.log_message("Installazione annullata dall'utente.")
                return
            try:
                __import__(mod)
                self.log_message(f"{mod} già presente.")
            except ImportError:
                self.log_message(f"Errore: {mod} non trovato. Installa Python standard da python.org.")
                return
            installed += 1
            self.progress['value'] = (installed / total) * 100
            self.root.update_idletasks()

        # Installa o aggiorna i moduli pip
        for mod in pip_modules:
            if self.cancelled:
                self.log_message("Installazione annullata dall'utente.")
                return
            try:
                __import__(mod)
                self.log_message(f"{mod} già installato. Aggiornamento...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", mod])
                    self.log_message(f"{mod} aggiornato con successo.")
                except Exception as e:
                    self.log_message(f"Errore aggiornando {mod}: {e}")
                    return
            except ImportError:
                self.log_message(f"{mod} non trovato. Installazione in corso...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", mod])
                    self.log_message(f"{mod} installato ex-novo con successo.")
                except Exception as e:
                    self.log_message(f"Errore installando {mod}: {e}")
                    return
            installed += 1
            self.progress['value'] = (installed / total) * 100
            self.root.update_idletasks()

        # Al termine, mostra la domanda collegamento invece di OK
        self.ask_shortcut_question()

    def open_gh_cli_url(self):
        import webbrowser
        webbrowser.open_new("https://github.com/cli/cli/releases/latest")
        # Dopo il click, chiudi l'installer
        self.root.after(500, self.root.destroy)

def get_pythonw_path():
    # Trova pythonw.exe nella stessa cartella di python.exe
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, 'pythonw.exe')
    if os.path.exists(pythonw):
        return pythonw
    # Fallback: cerca in PATH
    for p in os.environ["PATH"].split(os.pathsep):
        candidate = os.path.join(p, 'pythonw.exe')
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(
        "pythonw.exe non trovato.\n\nPer favore reinstalla Python usando l'installer ufficiale da https://www.python.org/downloads/ e assicurati di selezionare l'opzione 'Add Python to PATH'.\n\npythonw.exe è necessario per eseguire l'applicazione senza console su Windows.")

def create_vbs_launcher(target_py, vbs_path):
    pythonw = get_pythonw_path()
    pythonw = os.path.abspath(pythonw)
    target_py = os.path.abspath(target_py)
    vbs_code = f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run """{pythonw}"" ""{target_py}""", 0, False\n'
    with open(vbs_path, 'w', encoding='utf-8') as f:
        f.write(vbs_code)

def create_shortcut(target, shortcut_path, icon_path=None, description=None):
    try:
        import pythoncom
        from win32com.client import Dispatch
    except ImportError:
        print("Installazione automatica di pywin32...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pywin32'])
        # Esegui lo script di post-installazione di pywin32
        try:
            import site
            pywin32_postinstall = os.path.join(site.getsitepackages()[0], 'pywin32_postinstall.py')
            subprocess.check_call([sys.executable, pywin32_postinstall, '-install'])
        except Exception as e:
            print(f"Errore post-installazione pywin32: {e}")
        import pythoncom
        from win32com.client import Dispatch
    shell_obj = Dispatch('WScript.Shell')
    shortcut = shell_obj.CreateShortcut(shortcut_path)
    if isinstance(target, tuple):
        exe_path, args = target
    else:
        exe_path, args = target, ''
    shortcut.TargetPath = exe_path
    shortcut.Arguments = args
    shortcut.WorkingDirectory = os.path.dirname(exe_path)
    # Gestione robusta dell'icona: controlla che il file esista e sia un .ico valido
    if icon_path:
        icon_path = os.path.abspath(icon_path)
        if os.path.exists(icon_path) and icon_path.lower().endswith('.ico'):
            try:
                shortcut.IconLocation = icon_path
            except Exception as e:
                print(f"Icona non impostata: {e}")
        else:
            print(f"Icona non trovata o non valida: {icon_path}")
    if description:
        shortcut.Description = description
    shortcut.save()
    print(f"Collegamento creato in: {os.path.abspath(shortcut_path)}")


def main():
    root = tk.Tk()
    app = InstallerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
