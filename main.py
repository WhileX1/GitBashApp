import tkinter as tk
from tkinter import filedialog, messagebox as mb
from gitrepo import GitRepo, subprocess
from widgets import FileSelectionWindow
from config import *
import time
import os
import threading
from helpers import *

class GitGuiApp(tk.Tk):
    def _update_progress(self, win, count):
        # Aggiorna la progress bar se la finestra è presente e il metodo esiste.
        if win and hasattr(win, 'update_progress'):
            win.update_progress(count)

    def _safe_show_error(self, title, msg):
        # Mostra un errore in modo thread-safe.
        try:
            self.after(0, lambda: show_error(title, msg))
        except Exception:
            show_error(title, msg)

    def _safe_show_info(self, title, msg):
        # Mostra una info in modo thread-safe.
        try:
            self.after(0, lambda: show_info(title, msg))
        except Exception:
            show_info(title, msg)

    def reset_content_area(self):
        # Centralized removal of dynamic widgets from main_container except dir_label and button_frame.
        self.clear_dynamic_widgets(self.main_container, static_widgets=[self.dir_label, self.button_frame])
        # Ricrea content_frame se necessario.
        if not hasattr(self, 'content_frame') or not self.content_frame.winfo_exists():
            self.content_frame = tk.Frame(self.main_container)
            self.content_frame.pack(fill="both", expand=True)
        else:
            self.clear_dynamic_widgets(self.content_frame)

    @staticmethod
    def clear_dynamic_widgets(container, static_widgets=None):
        # Distrugge tutti i widget figli di container eccetto quelli in static_widgets.
        if static_widgets is None:
            static_widgets = []
        for widget in list(container.winfo_children()):
            if widget not in static_widgets:
                try:
                    widget.destroy()
                except Exception:
                    pass

    def validate_branch(self, branch):
        # Controlla se il branch è valido. Non mostra più warning personalizzati, lascia a git l'errore.
        return branch in self.branch_info

    def get_valid_files(self, files):
        # Restituisce solo i file validi e interni alla repo. 
        # Se viene selezionata una cartella, espande tutti i file e sottocartelle.
        # Ora normalizza anche i path tra virgolette ("C:\path\file.txt" o 'C:/path/file.txt')
        if not files:
            return []
        def strip_quotes(path):
            if isinstance(path, str) and len(path) > 1:
                if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
                    return path[1:-1]
            return path
        try:
            repo_root = None
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            try:
                repo_root = subprocess.check_output(
                    ['git', 'rev-parse', '--show-toplevel'],
                    text=True,
                    startupinfo=startupinfo
                ).strip()
            except Exception:
                repo_root = os.getcwd()
            # Normalizza repo_root per confronto robusto
            repo_root_norm = os.path.normcase(os.path.normpath(repo_root))
            valid = []
            for f in files:
                if f and isinstance(f, str) and f.strip():
                    f_stripped = strip_quotes(f.strip())
                    abs_f = os.path.abspath(f_stripped)
                    abs_f_norm = os.path.normcase(os.path.normpath(abs_f))
                    if os.path.isdir(abs_f):
                        for root, dirs, filelist in os.walk(abs_f):
                            for file in filelist:
                                file_path = os.path.join(root, file)
                                file_path_norm = os.path.normcase(os.path.normpath(file_path))
                                if repo_root_norm and file_path_norm.startswith(repo_root_norm):
                                    valid.append(file_path)
                    else:
                        if repo_root_norm and abs_f_norm.startswith(repo_root_norm):
                            valid.append(abs_f)
            return valid
        except Exception:
            return []

    def validate_commit_message(self, msg):
        # Controlla se il messaggio di commit è valido. Lascia a git la gestione degli errori.
        return bool(msg)

    # --- Caching ottimizzato per ridurre chiamate frequenti ---
    _cache_timeout = CACHE_TIMEOUT
    _cached_branch = CACHE_DEFAULTS['branch']
    _cached_origin = CACHE_DEFAULTS['origin']
    _cached_github_user = CACHE_DEFAULTS['github_user']
    _cached_is_repo = CACHE_DEFAULTS['is_repo']
    _cache_time = CACHE_DEFAULTS['cache_time']
    _github_user_needs_update = CACHE_DEFAULTS['github_user_needs_update']  # Flag per aggiornamento utente GitHub
    _branches_fetched_on_startup = CACHE_DEFAULTS['branches_fetched_on_startup']  # Flag per evitare fetch multipli
    _login_in_progress = CACHE_DEFAULTS['login_in_progress']  # Flag per indicare login in corso
    
    # set_placeholder e clear_placeholder ora sono in helpers.py
    def __init__(self):
        super().__init__()
        last_dir = load_last_dir()
        if last_dir:
            try:
                os.chdir(last_dir)
            except Exception:
                pass
        self.title(APP_TITLE)
        self.geometry(APP_GEOMETRY)
        self.resizable(False, False)
        # Variabili persistenti per schermata push
        self._push_files = []
        self._push_num_var = tk.IntVar(value=1)
        self._push_remote_var = tk.StringVar()
        self._push_commit_msg = ""
        # Finestra selezione file (per evitare doppioni)
        self._file_selection_window = None
        # Mappa branch -> tipo (remoto, locale, entrambi)
        self._branch_info = {}
        # Nome suggerito per nuovo branch (quando si reindirizza da checkout)
        self._suggested_new_branch = None
        # Persistent layout
        self.main_container = tk.Frame(self)
        self.main_container.pack(fill="both", expand=True, padx=MAIN_PAD, pady=PAD_Y_MAIN_CONTAINER)
        self.dir_label = tk.Label(self.main_container, text="", font=BOLD_FONT, justify="left", anchor="w")
        self.dir_label.pack(pady=PAD_Y_DIR_LABEL, fill="x")
        self.button_frame = None
        self.content_frame = tk.Frame(self.main_container)
        self.content_frame.pack(fill="both", expand=True)
        # Aggiorna i branch solo una volta all'avvio per rimuovere quelli eliminati dal remoto
        self._update_branch_info(prune=True)
        self._branches_fetched_on_startup = True
        self.create_buttons()
        self.update_dir_label()
        self.check_repo()

    @property
    def file_selection_window(self):
        return self._file_selection_window

    @file_selection_window.setter
    def file_selection_window(self, value):
        self._file_selection_window = value

    @property
    def branch_info(self):
        return self._branch_info

    @branch_info.setter
    def branch_info(self, value):
        self._branch_info = value

    def _clear_content_frame_widgets(self):
        # Usa la funzione centralizzata
        self.reset_content_area()

    def _init_main_ui(self):
        # Usa la funzione centralizzata per pulire e ricreare l'area dinamica
        self.reset_content_area()
        if not self.button_frame or not self.button_frame.winfo_exists():
            self.create_buttons()
        self.update_dir_label()
        self.check_repo()

    def _update_branch_info(self, prune=False):
        # Recupera branch locali e remoti e costruisce la mappa branch -> tipo
        try:
            if prune:
                try:
                    kwargs = get_subprocess_kwargs()
                    # Su Windows, nasconde la finestra della console per il comando subprocess
                    if os.name == 'nt':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        kwargs['startupinfo'] = startupinfo
                    subprocess.check_output(['git', 'fetch', '--prune'], text=True, **kwargs)
                except Exception:
                    pass
            local = set(GitRepo.get_local_branches())
            remote = set(GitRepo.get_remote_branches())
            all_branches = local | remote
            info = {}
            for b in all_branches:
                if b in local and b in remote:
                    info[b] = "(locale/remoto)"
                elif b in local:
                    info[b] = "(locale)"
                elif b in remote:
                    info[b] = "(remoto)"
            self._branch_info = info
        except Exception:
            self._branch_info = {}

    def create_buttons(self):
        button_frame = tk.Frame(self.main_container)
        button_frame.pack(side="bottom", fill="x")
        btn_opts = dict(width=20, height=2, font=BOLD_FONT)
        row1 = tk.Frame(button_frame)
        row1.pack(fill="x", pady=PAD_Y_MENU_ROW)
        self.btn_pull = tk.Button(row1, text="Pull", command=self.do_pull, **btn_opts)
        self.btn_pull.pack(side="left", expand=True, fill="x", pady=PAD_Y_MENU_BTN, padx=BUTTON_PAD_INNER)
        self.btn_push = tk.Button(row1, text="Push", command=self.do_push, **btn_opts)
        self.btn_push.pack(side="left", expand=True, fill="x", pady=PAD_Y_MENU_BTN, padx=BUTTON_PAD_INNER)
        row2 = tk.Frame(button_frame)
        row2.pack(fill="x", pady=PAD_Y_MENU_ROW)
        self.btn_branch = tk.Button(row2, text="Cambia Branch", command=self.do_branch, **btn_opts)
        self.btn_branch.pack(side="left", expand=True, fill="x", pady=PAD_Y_MENU_BTN, padx=BUTTON_PAD_INNER)
        self.btn_dir = tk.Button(row2, text="Cambia Directory", command=self.change_directory, **btn_opts)
        self.btn_dir.pack(side="left", expand=True, fill="x", pady=PAD_Y_MENU_BTN, padx=BUTTON_PAD_INNER)
        # Nuova riga per il pulsante account
        row3 = tk.Frame(button_frame)
        row3.pack(fill="x", pady=PAD_Y_MENU_ROW)
        self.btn_account = tk.Button(row3, text="Cambia Account", command=self.do_account, **btn_opts)
        self.btn_account.pack(side="left", expand=True, fill="x", pady=PAD_Y_MENU_BTN, padx=BUTTON_PAD_INNER)
        # Pulsante Cambia Link
        self.btn_link = tk.Button(row3, text="Cambia Link", command=self.do_link, **btn_opts)
        self.btn_link.pack(side="left", expand=True, fill="x", pady=PAD_Y_MENU_BTN, padx=BUTTON_PAD_INNER)
        # Nuova riga per Clone Repository
        row4 = tk.Frame(button_frame)
        row4.pack(fill="x", pady=PAD_Y_MENU_ROW)
        self.btn_clone = tk.Button(row4, text="Clone Repository", command=self.do_clone, **btn_opts)
        self.btn_clone.pack(side="left", expand=True, fill="x", pady=PAD_Y_MENU_BTN, padx=BUTTON_PAD_INNER)
        # Pulsante disabilitato per mantenere lo stile
        tk.Button(row4, state="disabled", **btn_opts).pack(side="left", expand=True, fill="x", pady=PAD_Y_MENU_BTN, padx=BUTTON_PAD_INNER)
        self.button_frame = button_frame

    def update_dir_label(self, force_refresh=False):
        now = time.time()
        cache_expired = (now - self._cache_time > self._cache_timeout)
        
        # Aggiorna branch e origin solo se necessario
        if force_refresh or cache_expired or self._cached_branch is None or self._cached_origin is None:
            self._cached_branch = GitRepo.get_current_branch()
            self._cached_origin = GitRepo.get_current_origin()
            self._cache_time = now
        
        # Aggiorna utente GitHub solo se richiesto esplicitamente
        if self._github_user_needs_update or self._cached_github_user is None:
            self._cached_github_user = GitRepo.get_github_user()
            self._github_user_needs_update = False
        
        branch = self._cached_branch
        origin = self._cached_origin
        github_user = self._cached_github_user
        cwd = os.getcwd()
        self.dir_label.config(text=f"📁 Directory: {cwd}\n ➥ Branch: {branch}\n🔍 Link: {origin}\n 👤 GitHub: {github_user}")

    def invalidate_cache(self):
        # Invalida la cache per branch e origin (non per utente GitHub)
        self._cached_branch = None
        self._cached_origin = None
        self._cached_is_repo = None
        self._cache_time = 0

    def invalidate_github_user_cache(self):
        # Invalida solo la cache dell'utente GitHub
        self._cached_github_user = None
        self._github_user_needs_update = True

    @staticmethod
    def is_valid_branch(branch, branches):
        return branch in branches

    def check_repo(self, force_refresh=False):
        now = time.time()
        if force_refresh or (self._cached_is_repo is None) or (now - self._cache_time > self._cache_timeout):
            self._cached_is_repo = GitRepo.is_valid_repo()
            self._cache_time = now
        if not self._cached_is_repo:
            # Chiedi all'utente se vuole inizializzare una nuova repository
            response = mb.askyesno("Repository non trovata", 
                                   "La directory corrente non è una repository git valida.\n\nVuoi inizializzarla come repository git?")
            if response:
                # Tenta di inizializzare la repository
                ok, msg = GitRepo.init_repository()
                if ok:
                    # Crea un commit vuoto per inizializzare la repository
                    ok_commit, msg_commit = GitRepo.create_initial_commit()
                    if not ok_commit:
                        show_error("Errore commit", f"Repository inizializzata ma errore nel commit:\n{msg_commit}")
                    # Se l'inizializzazione ha successo, aggiorna il flag e abilita i bottoni
                    self._cached_is_repo = True
                    self.invalidate_cache()
                    self.invalidate_github_user_cache()
                    self.update_dir_label(force_refresh=True)
                    self._update_branch_info(prune=False)
                    show_info("Repository inizializzata", msg)
                    self.btn_pull.config(state="normal")
                    self.btn_push.config(state="normal")
                    self.btn_branch.config(state="normal")
                else:
                    # Se fallisce, mostra errore e disabilita i bottoni
                    show_error("Errore", f"Impossibile inizializzare la repository:\n{msg}")
                    self.btn_pull.config(state="disabled")
                    self.btn_push.config(state="disabled")
                    self.btn_branch.config(state="disabled")
            else:
                # Utente ha rifiutato l'inizializzazione
                self.btn_pull.config(state="disabled")
                self.btn_push.config(state="disabled")
                self.btn_branch.config(state="disabled")
        else:
            self.btn_pull.config(state="normal")
            self.btn_push.config(state="normal")
            self.btn_branch.config(state="normal")

    def do_pull(self):
        # Non aggiornare la lista branch all'apertura della sezione Pull
        self._show_branch_section(
            title="Seleziona o filtra il branch da cui fare Pull:",
            action_btn_text="Esegui Pull",
            action_callback=self._do_pull_action,
            extra_widgets=lambda bottom_frame, entry_var, action_callback: self._common_extra_widgets(
                bottom_frame=bottom_frame,
                entry_var=entry_var,
                action_callback=action_callback,
                action_text="Esegui Pull",
                show_force=True
            ),
            show_delete_branch=False
        )
    def _do_pull_action(self, branch, force_var=None):
        if not self.validate_branch(branch):
            return
        force = force_var.get() if force_var is not None else False
        if force:
            ok, msg = GitRepo.pull_force(branch)
        else:
            ok, msg = GitRepo.pull(branch)
        if ok:
            self.invalidate_cache()
            self.update_dir_label(force_refresh=True)
            if msg and "already up to date" in msg.lower():
                show_info("Pull Output", "Branch locale allineato con il branch remoto.")
            else:
                show_info("Pull Output", msg)
        else:
            show_error("Errore Pull", msg)


    def do_push(self):
        self.clear_content_frame()
        self.button_frame.pack_forget()
        self._build_push_ui()

    def _build_push_ui(self):
        branch_row = tk.Frame(self.main_container)
        branch_row.pack(pady=PAD_Y_SECTION, anchor="center", fill="x")
        tk.Label(branch_row, text="Branch remoto:", font=BOLD_FONT, anchor="w").grid(row=0, column=0, padx=(0, PAD_X_BUTTON), sticky="w")
        remote_var = self._push_remote_var
        current_branch = self._cached_branch if self._cached_branch else GitRepo.get_current_branch()
        remote_var.set(current_branch)
        remote_entry = tk.Entry(branch_row, textvariable=remote_var, font=BOLD_FONT, width=ENTRY_WIDTH_SHORT, state="readonly")
        remote_entry.grid(row=0, column=1)
        files = self._push_files
        num_var = self._push_num_var

        def get_selected_count():
            return count_selected_files(files)
        file_counter_var = tk.StringVar()

        def update_file_counter(*args):
            update_counter_var(file_counter_var, get_selected_count, num_var)
        update_file_counter()
        num_var.trace_add("write", update_file_counter)

        def after_files_saved():
            update_file_counter()
        btn_select_file = tk.Button(
            branch_row,
            text="Seleziona File",
            command=lambda: self.ensure_file_selection_window(files, num_var, after_files_saved),
            font=BOLD_FONT
        )
        btn_select_file.grid(row=0, column=2, padx=(PAD_Y_SECTION,0))
        tk.Label(branch_row, textvariable=file_counter_var, font=BOLD_FONT, width=6, anchor="center"
                 ).grid(row=0, column=3, padx=(PAD_X_BUTTON,0))

        def periodic_update():
            update_file_counter()
            self.after(200, periodic_update)
        periodic_update()

        tk.Label(self.main_container, text="Messaggio di commit:", font=BOLD_FONT).pack(pady=PAD_Y_DEFAULT)
        commit_text = tk.Text(self.main_container, height=TEXT_HEIGHT_COMMIT, width=TEXT_WIDTH_COMMIT, font=BOLD_FONT)
        commit_text.pack(pady=PAD_Y_DEFAULT)
        if self._push_commit_msg:
            commit_text.delete("1.0", "end")
            commit_text.insert("1.0", self._push_commit_msg)
        bottom_frame = tk.Frame(self.main_container)
        bottom_frame.pack(side="bottom", fill="x", pady=PAD_Y_BUTTON)
        force_var = tk.BooleanVar(value=False)

        def on_back():
            self._push_commit_msg = commit_text.get("1.0", "end").strip()
            self.show_menu()

        tk.Button(bottom_frame, text="Indietro", command=on_back, font=BOLD_FONT).pack(side="left", padx=PAD_X_DEFAULT)
        force_chk = tk.Checkbutton(
            bottom_frame, 
            text="Force Push", 
            variable=force_var,
            font=BOLD_FONT,
            fg=COLOR_ERROR
        )
        force_chk.pack(side="left", expand=True, padx=PAD_X_DEFAULT)
        tk.Button(bottom_frame, text="Esegui Push", 
                  command=lambda: self._on_push_confirm(files, remote_var, commit_text, force_var), 
                  font=BOLD_FONT).pack(side="right", padx=PAD_X_DEFAULT)

    def _on_push_confirm(self, files, remote_var, commit_text, force_var):
        # DRY: usa sempre la stessa logica di espansione file/cartelle con barra avanzamento
        selected_files = self.get_valid_files(files)
        if selected_files is None:
            selected_files = []
        expanded_files, _ = self._expand_dirs_with_progress(selected_files, self)
        files_arg = expanded_files if expanded_files else None
        current_branch = self._cached_branch if self._cached_branch else GitRepo.get_current_branch()
        branch_name = current_branch
        msg = commit_text.get("1.0", "end").strip() if commit_text else ""
        if not self.validate_commit_message(msg):
            self._safe_show_error("Errore", "Il messaggio di commit non può essere vuoto.")
            return

        # Conferma solo se l'utente non ha selezionato alcun file (selezione vuota)
        if not selected_files or len(selected_files) == 0:
            res = mb.askyesno(
                "Conferma push globale",
                "Non hai selezionato alcun file o cartella.\n\n"
                "Vuoi davvero eseguire un commit e push di TUTTE le modifiche nella repository?\n\n"
                "Questa azione includerà TUTTI i file modificati, aggiunti o cancellati."
            )
            if not res:
                return

        def threaded_push():
            try:
                # Use only correct commit command via GitRepo.push
                ok, push_msg = GitRepo.push(files_arg, branch_name, msg, force=force_var.get() if force_var else False)
                def show_push_result():
                    self.invalidate_cache()
                    if ok:
                        self._safe_show_info("Successo", f"Push eseguito con successo al branch {branch_name}")
                    else:
                        # Rileva se la repository non existe
                        if push_msg and push_msg.startswith("REPO_NOT_FOUND:"):
                            # Estrae il messaggio originale
                            original_msg = push_msg.replace("REPO_NOT_FOUND:", "", 1)
                            # Chiedi all'utente se vuole creare la repository
                            try:
                                result = mb.askyesno(
                                    "Repository non trovata",
                                    f"La repository remota non esiste.\n\n{original_msg}\n\nVuoi crearla su GitHub?"
                                )
                                if result:
                                    # Estrai account e repo name dal remote origin
                                    current_origin = GitRepo.get_current_origin()
                                    account, repo_name = GitRepo.parse_github_url(current_origin)
                                    if account and repo_name:
                                        create_ok, create_msg = GitRepo.create_remote_repository(repo_name, account)
                                        if create_ok:
                                            self._safe_show_info("Successo", create_msg)
                                            self.show_menu()
                                        else:
                                            # Se la creazione fallisce, annulla il commit per evitare blocchi futuri
                                            reset_ok, reset_msg = GitRepo.reset_last_commit()
                                            if reset_ok:
                                                self._safe_show_error("Errore creazione repository", f"{create_msg}\n\n{reset_msg}\n\nPer favore, effettua il login a GitHub e riprova.")
                                            else:
                                                self._safe_show_error("Errore creazione repository", f"{create_msg}\n\nErrore durante il reset del commit: {reset_msg}")
                                    else:
                                        self._safe_show_error("Errore", "Impossibile estrarre i dati della repository dal remote configurato.")
                                else:
                                    # Utente ha detto no - annulla il commit silenziosamente
                                    _ = GitRepo.reset_last_commit()
                            except Exception as e:
                                self._safe_show_error("Errore", f"Errore durante la creazione della repository: {e}")
                        elif push_msg and ("up to date" in push_msg.lower() or "everything up-to-date" in push_msg.lower()):
                            self._safe_show_info("Push", f"Nessuna modifica da pushare: il branch locale è già aggiornato con il remoto.")
                        elif push_msg and "failed to push some refs" in push_msg.lower():
                            # Errore classico: il remote è avanti. Suggerisci pull prima di push
                            self._safe_show_error("Errore Push", f"Il repository remoto contiene modifiche che non hai localmente.\n\nSoluzione: esegui PULL prima di fare PUSH di nuovo.\n\n{push_msg}")
                        else:
                            self._safe_show_error("Errore Push", push_msg)
                    self.update_dir_label(force_refresh=True)
                self.after(0, show_push_result)
            except Exception as e:
                self._safe_show_error("Errore", f"Errore durante il push:\n{e}")
        threading.Thread(target=threaded_push, daemon=True).start()

    def _expand_dirs_with_progress(self, paths, parent_win):
        # Espansione semplice senza barra di avanzamento
        all_files = []
        all_dirs = set()
        for p in paths:
            if os.path.isdir(p):
                all_dirs.add(p)
                for root, dirs, files in os.walk(p):
                    all_dirs.add(root)
                    for file in files:
                        fpath = os.path.join(root, file)
                        all_files.append(fpath)
            else:
                all_files.append(p)
        return all_files, list(all_dirs)


    def _threaded_expand_and_push(self, selected_files, branch_name, msg, force, current_branch):

        try:
            expanded_files, _ = self._expand_dirs_with_progress(selected_files, self)

            kwargs = get_subprocess_kwargs()
            # Trova la root della repo git
            def find_git_root(path):
                path = os.path.abspath(path)
                while True:
                    if os.path.isdir(os.path.join(path, ".git")):
                        return path
                    parent = os.path.dirname(path)
                    if parent == path:
                        return None
                    path = parent

            repo_root = None
            for p in selected_files:
                repo_root = find_git_root(p)
                if repo_root:
                    break
            if not repo_root:
                repo_root = os.getcwd()

            # Sempre aggiungi TUTTI i cambiamenti (inclusi deletions) prima del commit/push
            try:
                # Su Windows, nasconde la finestra della console per il comando subprocess
                # come già fatto in altri punti del codice
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    kwargs['startupinfo'] = startupinfo
                # Esegui il comando git add -A senza mostrare la console
                subprocess.check_output(["git", "add", "-A"], text=True, cwd=repo_root, **kwargs)
            except Exception as add_exc:
                self.after(0, lambda: show_error("Errore git add", f"Errore durante 'git add -A':\n{add_exc}"))
                return

            # Se non ci sono cambiamenti da committare, GitRepo.push gestirà il messaggio
            ok, push_msg = GitRepo.push(None, branch_name, msg, force=force)

            def show_push_result():
                self.invalidate_cache()
                if ok:
                    if branch_name != current_branch:
                        show_info("Successo", f"Push eseguito con successo sul branch remoto '{branch_name}' (diverso dal branch attivo '{current_branch}').")
                    else:
                        show_info("Successo", f"Push eseguito con successo al branch {branch_name}")
                else:
                    if push_msg and ("up to date" in push_msg.lower() or "everything up-to-date" in push_msg.lower()):
                        show_info("Push", f"Nessuna modifica da pushare: il branch locale è già aggiornato con il remoto.")
                    elif push_msg and "failed to push some refs" in push_msg.lower():
                        # Errore classico: il remote è avanti. Suggerisci pull prima di push
                        show_error("Errore Push", f"Il repository remoto contiene modifiche che non hai localmente.\n\nSoluzione: esegui PULL prima di fare PUSH di nuovo.\n\n{push_msg}")
                    else:
                        show_error("Errore Push", push_msg)
                self.update_dir_label(force_refresh=True)
            self.after(0, show_push_result)
        except Exception as e:
            self.after(0, lambda e=e: show_error("Errore", f"Errore durante l'espansione file:\n{e}"))

        # RIMOSSO: codice legacy non più usato dopo refactoring do_push

    def ensure_file_selection_window(self, files, num_var, after_files_saved):
        # Gestione DRY della finestra di selezione file: solleva se già esiste, crea se non esiste o è stata chiusa.
        win = self.file_selection_window
        if win is not None:
            try:
                if not win.win.winfo_exists():
                    self.file_selection_window = None
            except Exception:
                self.file_selection_window = None
        if self.file_selection_window is not None:
            try:
                self.file_selection_window.win.lift()
                self.file_selection_window.win.focus_force()
            except Exception:
                self.file_selection_window = None
            return
        self.file_selection_window = FileSelectionWindow(self, files, num_var, after_files_saved, app_ref=self)
        # Nessun codice UI qui: solo gestione della finestra di selezione file

    def do_branch(self):
        # Non aggiornare la lista branch all'apertura della sezione Branch
        self._show_branch_section(
            title="Seleziona o filtra il branch:",
            action_btn_text="Cambia Branch",
            action_callback=self._do_checkout_action,
            extra_widgets=lambda bottom_frame, entry_var, action_callback: self._common_extra_widgets(
                bottom_frame=bottom_frame,
                entry_var=entry_var,
                action_callback=action_callback,
                action_text="Cambia Branch",
                show_force=False
            ),
            show_delete_branch=True
        )

    def _do_checkout_action(self, branch, _force_var=None):
        # Se il branch non esiste, reindirizza alla sezione "Crea Branch"
        if branch not in self.branch_info:
            res = mb.askyesno(
                "Branch non trovato",
                f"Il branch '{branch}' non esiste.\n\nVuoi andare alla sezione 'Crea Branch' per crearlo?"
            )
            if res:
                # Salva il nome del branch per pre-compilarlo nella sezione crea
                self._suggested_new_branch = branch
                self._show_create_branch_section()
            return
        ok, msg = GitRepo.checkout(branch)
        if ok:
            self.invalidate_cache()
            self.update_dir_label(force_refresh=True)
            self.check_repo(force_refresh=True)
            show_info("Cambio branch", msg)
        else:
            show_error("Errore cambio branch", msg)

    def _common_extra_widgets(self, bottom_frame, entry_var, action_callback, action_text, show_force=False):
        # Crea solo widget extra (es. force checkbox), NON pulsanti di azione.
        # Ritorna la funzione di conferma da collegare all'evento <Return>.
        force_var = tk.BooleanVar(value=False) if show_force else None
        if show_force:
            force_chk = tk.Checkbutton(
                bottom_frame, text="Force Pull", variable=force_var,
                font=BOLD_FONT, anchor="center", fg=COLOR_ERROR
            )
            force_chk.pack(side="left", expand=True, padx=PAD_X_DEFAULT)
        def on_confirm():
            branch = entry_var.get().strip()
            if show_force:
                action_callback(branch, force_var)
            else:
                action_callback(branch)
        return on_confirm

    def _show_branch_section(self, title, action_btn_text, action_callback, extra_widgets, show_delete_branch=False):
        # Centralized UI for branch selection (used by Pull and Branch)
        self.clear_content_frame()
        self.button_frame.pack_forget()
        tk.Label(self.main_container, text=title, font=BOLD_FONT).pack(pady=PAD_Y_DEFAULT)
        all_branches = list(self.branch_info.keys())
        filtered_branches = list(all_branches)
        entry_var = tk.StringVar()
        entry = tk.Entry(self.main_container, textvariable=entry_var, font=BOLD_FONT)
        entry.pack(pady=PAD_Y_DEFAULT, padx=PAD_X_DEFAULT, fill="x")
        get_count = lambda: len(filtered_branches)
        sugg_container, canvas, btn_frame, update_mousewheel = create_scrollable_list(self.main_container, height=CANVAS_HEIGHT, threshold=SCROLL_THRESHOLD, item_count_func=get_count, parent_win=self)
        sugg_container.pack(pady=PAD_Y_SUGG_CONTAINER, padx=PAD_X_SUGG_CONTAINER, fill="x")

        def on_suggestion_click(branch):
            entry_var.set(branch)
            entry.focus()
            entry.icursor(tk.END)
            entry.selection_range(0, tk.END)

        def update_buttons(*args):
            for widget in btn_frame.winfo_children():
                widget.destroy()
            filtro = entry_var.get().lower()
            nonlocal filtered_branches
            filtered_branches = [b for b in all_branches if filtro in b.lower()]
            found = False
            for branch in filtered_branches:
                label = branch
                if branch in self.branch_info:
                    label += f" {self.branch_info[branch]}"
                b = tk.Button(btn_frame, text=label, width=BUTTON_WIDTH_DEFAULT, anchor="w", font=BOLD_FONT,
                              command=lambda br=branch: on_suggestion_click(br))
                b.pack(pady=BUTTON_PAD_Y_SUGG, fill="x")
                found = True
            if not found:
                tk.Label(btn_frame, text="Nessun branch trovato.", font=BOLD_FONT).pack(pady=BUTTON_PAD_Y_SUGG)
            update_mousewheel()
        entry_var.trace_add("write", update_buttons)
        update_buttons()

        bottom_frame = tk.Frame(self.main_container)
        bottom_frame.pack(side="bottom", fill="x", pady=PAD_Y_BUTTON)

        # --- Pulsante Elimina branch ---
        def on_delete_branch():
            branch = entry_var.get().strip()
            if not branch:
                show_error("Errore", "Nessun branch selezionato.")
                return
            # Solo branch locale
            local_branches = GitRepo.get_local_branches()
            if branch not in local_branches:
                show_error("Errore", f"Il branch '{branch}' non esiste tra i branch locali.")
                return
            if branch == GitRepo.get_current_branch():
                show_error("Errore", "Non puoi eliminare il branch attualmente attivo.")
                return
            res = mb.askyesno("Conferma eliminazione", f"Vuoi eliminare il branch locale '{branch}'?\nQuesta azione non è reversibile.")
            if not res:
                return
            ok, msg = GitRepo.delete_local_branch(branch)
            if ok:
                self.invalidate_cache()
                # Non fare prune qui, solo aggiorna la lista branch senza fetch
                self._update_branch_info(prune=False)
                self.update_dir_label(force_refresh=True)
                show_info("Branch eliminato", msg)
                entry_var.set("")
                update_buttons()
                # Aggiorna la sezione branch dopo eliminazione
                self._show_branch_section(title="Seleziona o filtra il branch:", action_btn_text="Cambia Branch", action_callback=self._do_checkout_action, extra_widgets=lambda bottom_frame, entry_var, action_callback: self._common_extra_widgets(bottom_frame=bottom_frame, entry_var=entry_var, action_callback=action_callback, action_text="Cambia branch", show_force=False), show_delete_branch=True)
            else:
                show_error("Errore eliminazione branch", msg)

        # --- Pulsanti azione branch: Indietro | Cambia branch | (opzionale) Elimina branch ---
        for widget in bottom_frame.winfo_children():
            widget.destroy()

        # Indietro
        btn_back = tk.Button(bottom_frame, text="Indietro", command=self.show_menu, font=BOLD_FONT)
        btn_back.pack(side="left", padx=PAD_X_DEFAULT)

        # Cambia branch
        def on_confirm():
            branch = entry_var.get().strip()
            action_callback(branch)
        btn_change = tk.Button(bottom_frame, text=action_btn_text, command=on_confirm, font=BOLD_FONT)
        btn_change.pack(side="right", padx=PAD_X_DEFAULT)

        # Elimina branch SOLO se richiesto
        if show_delete_branch:
            btn_delete = tk.Button(bottom_frame, text="Elimina Branch", command=on_delete_branch, font=BOLD_FONT, fg=COLOR_ERROR)
            btn_delete.pack(side="right", padx=PAD_X_DEFAULT)
            # Crea branch - nuovo pulsante
            btn_create = tk.Button(bottom_frame, text="Crea Branch", command=self._show_create_branch_section, font=BOLD_FONT)
            btn_create.pack(side="right", padx=PAD_X_DEFAULT)

        # Setup extra widgets (e.g., force checkbox for pull) SOLO se non sono già presenti
        # (Evita duplicazione: extra_widgets non deve aggiungere altri pulsanti azione)
        # Se extra_widgets aggiunge solo widget "extra" (es. force), va bene:
        on_confirm_extra = extra_widgets(bottom_frame, entry_var, action_callback)
        # Se extra_widgets restituisce una funzione di conferma, usala per <Return>
        entry.bind("<Return>", lambda event: (on_confirm_extra() if on_confirm_extra else on_confirm()))
        entry.focus()
        if self.main_container.winfo_toplevel() is not self:
            self.main_container.winfo_toplevel().resizable(False, False)

        # Centralized cleanup: destroy scrollable widgets and unbind mousewheel on section change
        def cleanup():
            try:
                update_mousewheel()  # ensure unbinding if needed
            except Exception:
                pass
            try:
                sugg_container.destroy()
            except Exception:
                pass
            try:
                bottom_frame.destroy()
            except Exception:
                pass
        self._current_section_cleanup = cleanup

    def clear_content_frame(self):
        # Centralized cleanup for scrollable/mousewheel widgets
        if hasattr(self, '_current_section_cleanup') and self._current_section_cleanup:
            try:
                self._current_section_cleanup()
            except Exception:
                pass
            self._current_section_cleanup = None
        # Usa la funzione centralizzata per pulire l'area dinamica
        self.reset_content_area()

    def show_menu(self):
        # Mostra la schermata principale senza distruggere main_container
        self.clear_content_frame()
        # Assicurati che i pulsanti siano visibili
        if self.button_frame and not self.button_frame.winfo_ismapped():
            self.button_frame.pack(side="bottom", fill="x")
        self._init_main_ui()
        # Porta la finestra principale in primo piano e forza il focus
        def bring_to_front():
            try:
                self.deiconify()
                self.lift()
                self.focus_force()
            except Exception:
                pass
        self.after_idle(bring_to_front)

    # open_files_window rimane come unico punto di gestione della finestra file
    def open_files_window(self, files, num_var, update_counter):
        # Gestione unificata della finestra di selezione file
        def on_files_saved():
            if update_counter:
                update_counter()

        # Chiudi la finestra precedente se esiste
        if self.file_selection_window is not None:
            try:
                if self.file_selection_window.win.winfo_exists():
                    self.file_selection_window.win.destroy()
            except Exception:
                pass
            self.file_selection_window = None

        self.file_selection_window = FileSelectionWindow(self, files, num_var, on_files_saved, app_ref=self)

    # _build_files_frame eliminata: la gestione della selezione file è ora centralizzata in FileSelectionWindow

    def change_directory(self):
        new_dir = filedialog.askdirectory(title="Seleziona nuova directory di lavoro")
        if new_dir:
            try:
                os.chdir(new_dir)
                save_last_dir(new_dir)
                # Invalida TUTTA la cache dopo cambio directory
                self.invalidate_cache()
                self.invalidate_github_user_cache()  # Potrebbe cambiare anche l'utente GitHub
                self.update_dir_label(force_refresh=True)
                self.check_repo(force_refresh=True)
                show_info("Cambio directory", f"Directory cambiata in:\n{os.getcwd()}")
                # Aggiorna la lista branch (anche remoti) dopo cambio directory
                self._update_branch_info(prune=True)
            except Exception as e:
                show_error("Errore", f"Impossibile cambiare directory:\n{e}")

    def do_account(self):
        # Mostra la schermata di gestione account con pulsanti Login e Logout
        self.clear_content_frame()
        self.button_frame.pack_forget()
        
        # Titolo della sezione
        tk.Label(self.main_container, text="Gestione Account GitHub:", font=BOLD_FONT).pack(pady=PAD_Y_SECTION)

        # Frame centrale per i pulsanti principali (stesso stile del menu)
        action_frame = tk.Frame(self.main_container)
        action_frame.pack(expand=True, fill="both", pady=PAD_Y_SECTION)

        # Usa lo stesso stile del menu principale
        BUTTON_PAD_INNER = 8
        btn_opts = dict(width=20, height=2, font=BOLD_FONT)

        # Frame per la riga dei pulsanti (stesso stile di row1, row2 del menu)
        button_row = tk.Frame(action_frame)
        button_row.pack(fill="x", pady=0)

        # Pulsante LOGIN (senza colore)
        self.btn_login = tk.Button(button_row, text="Login", command=self._do_login, **btn_opts)
        self.btn_login.pack(side="left", expand=True, fill="x", pady=PAD_Y_ACCOUNT_BTN, padx=BUTTON_PAD_INNER)

        # Pulsante LOGOUT (senza colore)
        self.btn_logout = tk.Button(button_row, text="Logout", command=self._do_logout, **btn_opts)
        self.btn_logout.pack(side="left", expand=True, fill="x", pady=PAD_Y_ACCOUNT_BTN, padx=BUTTON_PAD_INNER)

        # Frame per il pulsante indietro
        bottom_frame = tk.Frame(self.main_container)
        bottom_frame.pack(side="bottom", fill="x", pady=PAD_Y_BUTTON)

        tk.Button(bottom_frame, text="Indietro", command=self.show_menu, font=BOLD_FONT).pack(side="left", padx=PAD_X_ACCOUNT_BTN)

    def _do_login(self):
        # Esegue il login a GitHub in modalità non bloccante
        try:
            # Controlla se c'è già un login in corso
            if self._login_in_progress:
                show_info("Login in corso", "C'è già un processo di login in corso. Attendi che si completi.")
                return
            
            # Informa l'utente che si aprirà una console
            result = mb.askyesno("Login GitHub", "Si aprirà una finestra del terminale per completare il login.\nL'app rimarrà utilizzabile durante il processo.\n\nVuoi continuare?")
            if not result:
                return
            
            # Avvia il login in un thread separato
            self._login_in_progress = True
            self._update_login_button_state()
            
            def login_thread():
                try:
                    # Usa GitHub CLI per il login - MOSTRA la console per l'interazione
                    result = subprocess.run(
                        ['gh', 'auth', 'login'],
                        capture_output=False,
                        text=True
                        # Rimuovo CREATE_NO_WINDOW per permettere l'interazione
                    )
                    
                    # Pianifica l'aggiornamento dell'UI nel thread principale
                    def update_ui():
                        self._login_in_progress = False
                        self._update_login_button_state()
                        
                        if result.returncode == 0:
                            # Aggiorna SOLO l'utente GitHub dopo il login
                            self.invalidate_github_user_cache()
                            self.update_dir_label()
                            show_info("Login", "Login a GitHub eseguito con successo!")
                        else:
                            show_error("Errore Login", "Errore durante il login. Assicurati di avere GitHub CLI installato.")
                    
                    # Esegue l'aggiornamento UI nel thread principale
                    self.after(0, update_ui)
                    
                except FileNotFoundError:
                    def show_error_ui():
                        self._login_in_progress = False
                        self._update_login_button_state()
                        show_error("GitHub CLI non trovato", 
                                  "GitHub CLI non è installato o non è nel PATH.\n"
                                  "Scaricalo da: https://cli.github.com/")
                    self.after(0, show_error_ui)
                    
                except Exception as e:
                    def show_error_ui():
                        self._login_in_progress = False
                        self._update_login_button_state()
                        show_error("Errore", f"Errore durante il login: {str(e)}")
                    self.after(0, show_error_ui)
            
            # Avvia il thread del login
            thread = threading.Thread(target=login_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            self._login_in_progress = False
            self._update_login_button_state()
            show_error("Errore", f"Errore durante l'avvio del login: {str(e)}")

    def _update_login_button_state(self):
        # Aggiorna lo stato del pulsante login in base al processo in corso
        if hasattr(self, 'btn_login') and self.btn_login.winfo_exists():
            if self._login_in_progress:
                self.btn_login.config(text="Login in corso...", state="disabled")
            else:
                self.btn_login.config(text="Login", state="normal")

    def _do_logout(self):
        # Esegue il logout da GitHub
        try:
            # Conferma logout
            result = mb.askyesno("Conferma Logout", "Sei sicuro di voler effettuare il logout da GitHub?")
            if not result:
                return
            # Ottieni l'utente corrente
            current_user = GitRepo.get_github_user()
            if current_user == "(non autenticato)" or current_user == "(GitHub CLI non installato)" or current_user == "(errore)":
                show_info("Logout", "Non sei attualmente autenticato su GitHub.")
                return
            # Esegui il logout tramite funzione centralizzata in gitrepo.py
            logout_success, msg = GitRepo.logout_github_user(current_user)
            if logout_success:
                self.invalidate_github_user_cache()
                self.update_dir_label()
                show_info("Logout", "Logout da GitHub eseguito con successo!")
            else:
                show_error("Errore Logout", f"Tutti i tentativi di logout sono falliti:\n" + msg)
        except FileNotFoundError:
            show_error("GitHub CLI non trovato", "GitHub CLI non è installato o non è nel PATH.")
        except Exception as e:
            show_error("Errore", f"Errore durante il logout: {str(e)}")

    def _show_create_branch_section(self):
        # Mostra la sezione per creare un nuovo branch con due campi: origine e nuovo
        self.clear_content_frame()
        self.button_frame.pack_forget()

        # Frame per i campi di inserimento
        fields_frame = tk.Frame(self.main_container)
        fields_frame.pack(pady=PAD_Y_DEFAULT, padx=PAD_X_DEFAULT, fill="x")

        # Prima riga - Titoli
        titles_frame = tk.Frame(fields_frame)
        titles_frame.pack(fill="x", pady=(0, PAD_Y_DEFAULT))

        tk.Label(titles_frame, text="Branch di origine", font=BOLD_FONT).pack(side="left", expand=True, anchor="center")
        tk.Label(titles_frame, text="Branch nuovo", font=BOLD_FONT).pack(side="right", expand=True, anchor="center")

        # Seconda riga - Campi di inserimento
        inputs_frame = tk.Frame(fields_frame)
        inputs_frame.pack(fill="x")
        # Campo branch di origine
        origin_var = tk.StringVar()
        origin_entry = tk.Entry(inputs_frame, textvariable=origin_var, font=BOLD_FONT, width=ENTRY_WIDTH_SHORT)
        origin_entry.pack(side="left", expand=True, fill="x", padx=(0, PAD_X_DEFAULT))
        # Campo branch nuovo
        new_var = tk.StringVar()
        new_entry = tk.Entry(inputs_frame, textvariable=new_var, font=BOLD_FONT, width=ENTRY_WIDTH_SHORT)
        new_entry.pack(side="right", expand=True, fill="x", padx=(PAD_X_DEFAULT, 0))

        # Pre-compila il nuovo branch se è stato suggerito da checkout
        if hasattr(self, '_suggested_new_branch') and self._suggested_new_branch:
            new_var.set(self._suggested_new_branch)
            self._suggested_new_branch = None  # Reset dopo l'uso
        
        # Lista scrollabile dei branch esistenti con filtro
        all_branches = list(self.branch_info.keys())
        filtered_branches = list(all_branches)  # iniziale
        get_count = lambda: len(filtered_branches)
        sugg_container, canvas, btn_frame, update_mousewheel = create_scrollable_list(self.main_container,height=CANVAS_HEIGHT,threshold=SCROLL_THRESHOLD,item_count_func=get_count,parent_win=self)
        sugg_container.pack(pady=PAD_Y_SUGG_CONTAINER, padx=PAD_X_SUGG_CONTAINER, fill="x")

        def on_branch_click(branch):
            origin_var.set(branch)
            new_entry.focus()

        def update_branch_buttons(*args):
            # Pulisci i bottoni precedenti
            for widget in btn_frame.winfo_children():
                widget.destroy()
            filtro = origin_var.get().lower()
            nonlocal filtered_branches
            filtered_branches = [b for b in all_branches if filtro in b.lower()]
            found = False
            for branch in filtered_branches:
                label = branch
                if branch in self.branch_info:
                    label += f" {self.branch_info[branch]}"
                b = tk.Button(btn_frame, text=label, width=BUTTON_WIDTH_DEFAULT, anchor="w", font=BOLD_FONT, command=lambda br=branch: on_branch_click(br))
                b.pack(pady=BUTTON_PAD_Y_SUGG, fill="x")
                found = True
            if not found:
                tk.Label(btn_frame, text="Nessun branch trovato.", font=BOLD_FONT).pack(pady=BUTTON_PAD_Y_SUGG)
            update_mousewheel()

        origin_var.trace_add('write', update_branch_buttons)
        update_branch_buttons()
        
        # Frame pulsanti in basso
        bottom_frame = tk.Frame(self.main_container)
        bottom_frame.pack(side="bottom", fill="x", pady=PAD_Y_BUTTON)

        # Pulsante Indietro
        btn_back = tk.Button(bottom_frame, text="Indietro", command=self.do_branch, font=BOLD_FONT)
        btn_back.pack(side="left", padx=PAD_X_DEFAULT)

        # Pulsante Crea
        def on_create():
            origin_branch = origin_var.get().strip()
            new_branch = new_var.get().strip()

            if not origin_branch:
                show_error("Errore", "Inserisci il branch di origine.")
                return
            if not new_branch:
                show_error("Errore", "Inserisci il nome del nuovo branch.")
                return
            if new_branch in self.branch_info:
                show_error("Errore", f"Il branch '{new_branch}' esiste già.")
                return

            # Usa la nuova funzione per creare il branch da quello di origine
            ok, msg = GitRepo.create_and_checkout_from_branch(new_branch, origin_branch)

            if ok:
                self.invalidate_cache()
                self._update_branch_info(prune=False)
                self.update_dir_label(force_refresh=True)
                self.check_repo(force_refresh=True)
                show_info("Branch creato", f"Branch '{new_branch}' creato con successo da '{origin_branch}'.")
                self.do_branch()  # Torna alla sezione branch
            else:
                show_error("Errore creazione branch", msg)

        btn_create = tk.Button(bottom_frame, text="Crea", command=on_create, font=BOLD_FONT)
        btn_create.pack(side="right", padx=PAD_X_DEFAULT)

        # Focus sul primo campo
        origin_entry.focus()

    def do_clone(self):
        # Mostra la sezione per clonare una repository
        self._show_clone_section()

    def _show_clone_section(self):
        # Mostra la sezione per clonare una repository da GitHub
        self.clear_content_frame()
        self.button_frame.pack_forget()
        # Titolo della sezione
        tk.Label(self.main_container, text="Clona Repository GitHub:", font=BOLD_FONT).pack(pady=PAD_Y_SECTION)
        # Frame per i campi di inserimento (centrato verticalmente)
        fields_frame = tk.Frame(self.main_container)
        fields_frame.pack(pady=PAD_Y_DEFAULT, padx=PAD_X_DEFAULT, fill="both", expand=True, anchor="center")
        # Prima riga - Titoli
        titles_frame = tk.Frame(fields_frame)
        titles_frame.pack(fill="x", pady=(0, PAD_Y_DEFAULT))
        tk.Label(titles_frame, text="Account Remoto", font=BOLD_FONT).pack(side="left", expand=True, anchor="center")
        tk.Label(titles_frame, text="Nome Repository", font=BOLD_FONT).pack(side="right", expand=True, anchor="center")
        # Seconda riga - Campi di inserimento
        inputs_frame = tk.Frame(fields_frame)
        inputs_frame.pack(fill="x")
        # Campo account remoto - pre-compila con utente GitHub autenticato
        account_var = tk.StringVar()
        github_user = self._cached_github_user
        if github_user and not github_user.startswith('('):
            account_var.set(github_user)
        account_entry = tk.Entry(inputs_frame, textvariable=account_var, font=BOLD_FONT, width=ENTRY_WIDTH_SHORT)
        account_entry.pack(side="left", expand=True, fill="x", padx=(0, PAD_X_DEFAULT))
        # Campo nome repository
        repo_var = tk.StringVar()
        repo_entry = tk.Entry(inputs_frame, textvariable=repo_var, font=BOLD_FONT, width=ENTRY_WIDTH_SHORT)
        repo_entry.pack(side="right", expand=True, fill="x", padx=(PAD_X_DEFAULT, 0))
        # Frame pulsanti in basso
        bottom_frame = tk.Frame(self.main_container)
        bottom_frame.pack(side="bottom", fill="x", pady=PAD_Y_BUTTON)
        # Pulsante Indietro
        btn_back = tk.Button(bottom_frame, text="Indietro", command=self.show_menu, font=BOLD_FONT)
        btn_back.pack(side="left", padx=PAD_X_DEFAULT)

        # Pulsante Clona
        def on_clone():
            account_text = account_var.get().strip()
            repo_text = repo_var.get().strip()
            if not account_text or not repo_text:
                show_error("Errore", "Account remoto e nome repository non possono essere vuoti.")
                return
            
            clone_url = GitRepo.build_github_url(account_text, repo_text)
            ok, msg = GitRepo.clone(clone_url)
            if ok:
                show_info("Successo", f"Repository clonata con successo in:\n{msg}")
                self.show_menu()
            else:
                show_error("Errore durante il clone", msg)
        btn_clone = tk.Button(bottom_frame, text="Clona", command=on_clone, font=BOLD_FONT)
        btn_clone.pack(side="right", padx=PAD_X_DEFAULT)
        # Focus sul primo campo
        account_entry.focus()

    def do_link(self):
        # Mostra la sezione per modificare il link remoto
        self._show_link_section()

    def _show_link_section(self):
        # Mostra la sezione per modificare Account Remoto e Nome Repository
        self.clear_content_frame()
        self.button_frame.pack_forget()
        # Titolo della sezione
        tk.Label(self.main_container, text="Modifica Link Repository:", font=BOLD_FONT).pack(pady=PAD_Y_SECTION)
        # Frame per i campi di inserimento (centrato verticalmente)
        fields_frame = tk.Frame(self.main_container)
        fields_frame.pack(pady=PAD_Y_DEFAULT, padx=PAD_X_DEFAULT, fill="both", expand=True, anchor="center")
        # Prima riga - Titoli
        titles_frame = tk.Frame(fields_frame)
        titles_frame.pack(fill="x", pady=(0, PAD_Y_DEFAULT))
        tk.Label(titles_frame, text="Account Remoto", font=BOLD_FONT).pack(side="left", expand=True, anchor="center")
        tk.Label(titles_frame, text="Nome Repository", font=BOLD_FONT).pack(side="right", expand=True, anchor="center")
        # Seconda riga - Campi di inserimento
        inputs_frame = tk.Frame(fields_frame)
        inputs_frame.pack(fill="x")
        # Pre-compila con i dati attuali se disponibili, altrimenti con default
        current_origin = GitRepo.get_current_origin()
        account, repo_name = GitRepo.parse_github_url(current_origin)
        # Se il link è vuoto o non valido, usa i default
        if not account:
            # Usa la cache dell'utente GitHub per evitare lag
            account = self._cached_github_user
            # Rimuovi "(non autenticato)" o altri prefissi tra parentesi dal nome utente
            if account and account.startswith('('):
                account = None
        
        if not repo_name:
            repo_name = os.path.basename(os.getcwd())
        
        # Campo account remoto
        account_var = tk.StringVar()
        if account:
            account_var.set(account)
        account_entry = tk.Entry(inputs_frame, textvariable=account_var, font=BOLD_FONT, width=ENTRY_WIDTH_SHORT)
        account_entry.pack(side="left", expand=True, fill="x", padx=(0, PAD_X_DEFAULT))
        # Campo nome repository
        repo_var = tk.StringVar()
        if repo_name:
            repo_var.set(repo_name)
        repo_entry = tk.Entry(inputs_frame, textvariable=repo_var, font=BOLD_FONT, width=ENTRY_WIDTH_SHORT)
        repo_entry.pack(side="right", expand=True, fill="x", padx=(PAD_X_DEFAULT, 0))
        # Frame pulsanti in basso
        bottom_frame = tk.Frame(self.main_container)
        bottom_frame.pack(side="bottom", fill="x", pady=PAD_Y_BUTTON)
        # Pulsante Indietro
        btn_back = tk.Button(bottom_frame, text="Indietro", command=self.show_menu, font=BOLD_FONT)
        btn_back.pack(side="left", padx=PAD_X_DEFAULT)

        # Pulsante Salva
        def on_save():
            account_text = account_var.get().strip()
            repo_text = repo_var.get().strip()
            if not account_text or not repo_text:
                show_error("Errore", "Account remoto e nome repository non possono essere vuoti.")
                return
            
            ok, msg = GitRepo.set_remote_url(account_text, repo_text)
            if ok:
                self.invalidate_cache()
                self.update_dir_label(force_refresh=True)
                show_info("Successo", msg)
                self.show_menu()
            else:
                show_error("Errore durante l'impostazione del remote", msg)
        
        btn_save = tk.Button(bottom_frame, text="Salva", command=on_save, font=BOLD_FONT)
        btn_save.pack(side="right", padx=PAD_X_DEFAULT)
        
        # Focus sul primo campo
        account_entry.focus()

## L'avvio dell'applicazione è stato spostato in launcher.py