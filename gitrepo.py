import subprocess
import os
import shutil
import tkinter as tk
from tkinter import messagebox as mb

class GitRepo:

    @staticmethod
    def _handle_checkout_overwrite_error(err_msg, retry_cmd, branch, current_branch):
        # Gestisce l'errore 'would be overwritten by checkout' chiedendo all'utente se vuole annullare le modifiche
        # e riprovare. Se accetta, esegue git restore sui file coinvolti e riprova il comando di checkout.
        # retry_cmd: funzione che esegue il comando di checkout (senza argomenti)
        # branch: branch di destinazione
        # current_branch: branch corrente
        root = tk._default_root
        if root is None:
            root = tk.Tk()
            root.withdraw()
        res = mb.askyesno("Modifiche locali rilevate", "Sono presenti modifiche locali che impediscono il cambio branch.\n\nVuoi annullare le modifiche (git restore) e riprovare?")
        if res:
            # Estrai i file che causano l'errore dal messaggio di errore
            files = []
            lines = err_msg.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith('error: Your local changes to the following files would be overwritten by checkout:'):
                    for file_line in lines[i+1:]:
                        file_line = file_line.strip()
                        if not file_line or file_line.startswith('Please commit your changes'):
                            break
                        files.append(file_line)
            if files:
                try:
                    subprocess.check_output(['git', 'restore', '--'] + files, stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    # Riprova il checkout
                    try:
                        output2 = retry_cmd()
                        GitRepo.unpark_untracked_files(branch)
                        return True, output2.strip() if isinstance(output2, str) else output2
                    except subprocess.CalledProcessError as e2:
                        GitRepo.unpark_untracked_files(current_branch)
                        return False, e2.output.strip() if hasattr(e2, 'output') and e2.output else str(e2)
                except subprocess.CalledProcessError as e_restore:
                    return False, f"Errore durante git restore: {e_restore.output.strip() if hasattr(e_restore, 'output') and e_restore.output else str(e_restore)}"
            else:
                return False, "Impossibile determinare i file da ripristinare dall'errore."
        else:
            return False, "Operazione annullata dall'utente."
    @staticmethod
    def park_untracked_files(branch):
        # Sposta i file non tracciati in una cartella nascosta .git-untracked/<branch>.
        repo_root = os.path.abspath(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).strip())
        untracked_dir = os.path.join(repo_root, '.git-untracked', branch)
        os.makedirs(untracked_dir, exist_ok=True)
        # Trova i file non tracciati
        status = subprocess.check_output(['git', 'status', '--porcelain'], text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        untracked_files = [line[3:] for line in status.splitlines() if line.startswith('?? ')]
        moved = []
        for f in untracked_files:
            abs_f = os.path.join(repo_root, f)
            if os.path.isfile(abs_f):
                dest = os.path.join(untracked_dir, os.path.basename(f))
                shutil.move(abs_f, dest)
                moved.append(f)
            elif os.path.isdir(abs_f):
                dest = os.path.join(untracked_dir, os.path.basename(f))
                shutil.move(abs_f, dest)
                moved.append(f)
        return moved

    @staticmethod
    def unpark_untracked_files(branch):
        # Ripristina i file non tracciati dalla cartella .git-untracked/<branch> nella working directory.
        repo_root = os.path.abspath(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).strip())
        untracked_dir = os.path.join(repo_root, '.git-untracked', branch)
        if not os.path.isdir(untracked_dir):
            return []
        restored = []
        for name in os.listdir(untracked_dir):
            src = os.path.join(untracked_dir, name)
            dest = os.path.join(repo_root, name)
            shutil.move(src, dest)
            restored.append(name)
        # Rimuovi la cartella se vuota
        try:
            os.rmdir(untracked_dir)
        except OSError:
            pass
        return restored
    
    @staticmethod
    def run_gh_command(args, input_text=None, hide_console=True):
        # Esegue un comando gh (GitHub CLI) con gestione della console su Windows.
        # Restituisce (returncode, stdout, stderr)
        kwargs = {'capture_output': True,'text': True}
        if input_text is not None:
            kwargs['input'] = input_text
        if hide_console and os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs['startupinfo'] = startupinfo
        try:
            # Se il comando è 'auth login', esegui prima il logout
            if len(args) >= 2 and args[0] == 'auth' and args[1] == 'login':
                username = None
                if '--user' in args:
                    idx = args.index('--user')
                    if idx + 1 < len(args):
                        username = args[idx + 1]
                GitRepo.logout_github_user(username if username else GitRepo.get_github_user())
            result = subprocess.run(['gh'] + args, **kwargs)
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return 127, '', 'GitHub CLI non trovato'
        except Exception as e:
            return 1, '', str(e)

    @staticmethod
    def logout_github_user(current_user):
        # Esegue il logout da GitHub CLI con vari tentativi.
        # Restituisce (success, messaggio)
        error_messages = []
        # Primo tentativo: logout con utente specifico
        code, out, err = GitRepo.run_gh_command(['auth', 'logout', '--hostname', 'github.com', '--user', current_user], input_text='y\n')
        if code == 0:
            return True, out.strip() or 'Logout eseguito con successo.'
        error_messages.append(f"Logout con utente: {err or out}")
        # Secondo tentativo: logout generico
        code, out, err = GitRepo.run_gh_command(['auth', 'logout', '--hostname', 'github.com'], input_text='y\n')
        if code == 0:
            return True, out.strip() or 'Logout eseguito con successo.'
        error_messages.append(f"Logout generico: {err or out}")
        # Terzo tentativo: logout forzato
        code, out, err = GitRepo.run_gh_command(['auth', 'logout', '--hostname', 'github.com', '--force'])
        if code == 0:
            return True, out.strip() or 'Logout eseguito con successo.'
        error_messages.append(f"Logout forzato: {err or out}")
        return False, '\n'.join(error_messages)
    
    @staticmethod
    def get_status_short_branch():
        # Restituisce l'output di 'git status --short --branch'
        try:
            output = subprocess.check_output(['git', 'status', '--short', '--branch'], text=True, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return True, output.strip()
        except subprocess.CalledProcessError as e:
            return False, e.output.strip() if hasattr(e, 'output') and e.output else str(e)
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_status_porcelain():
        # Restituisce l'output di 'git status --porcelain'
        try:
            output = subprocess.check_output(['git', 'status', '--porcelain'], text=True, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return True, output.strip()
        except subprocess.CalledProcessError as e:
            return False, e.output.strip() if hasattr(e, 'output') and e.output else str(e)
        except Exception as e:
            return False, str(e)
        
    @staticmethod
    def delete_local_branch(branch):
        # Elimina un branch locale e restituisce direttamente l'output di git.
        try:
            output = subprocess.check_output(['git', 'branch', '-D', branch], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return True, output.strip()
        except subprocess.CalledProcessError as e:
            return False, e.output.strip() if hasattr(e, 'output') and e.output else str(e)
        
    @staticmethod
    def create_and_checkout(branch):
        # Crea un nuovo branch locale e fa il checkout su di esso, mostra output git.
        try:
            remote_branches = GitRepo.get_remote_branches()
            if branch in remote_branches:
                output = subprocess.check_output(['git', 'checkout', '-b', branch, f'origin/{branch}'], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                return True, output.strip()
            else:
                output = subprocess.check_output(['git', 'checkout', '-b', branch], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                return True, output.strip()
        except subprocess.CalledProcessError as e:
            return False, e.output.strip() if hasattr(e, 'output') and e.output else str(e)
        
    @staticmethod
    def is_valid_repo():
        try:
            startupinfo = None
            if hasattr(subprocess, 'STARTF_USESHOWWINDOW'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            subprocess.check_output(['git', 'rev-parse', '--is-inside-work-tree'], stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), startupinfo=startupinfo)
            return True
        except Exception:
            return False

    @staticmethod
    def init_repository():
        # Inizializza una nuova repository git nella directory corrente.
        try:
            output = subprocess.check_output(['git', 'init'], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return True, output.strip() or "Repository inizializzata con successo."
        except subprocess.CalledProcessError as e:
            return False, e.output.strip() if hasattr(e, 'output') and e.output else str(e)
        except Exception as e:
            return False, str(e)

    @staticmethod
    def create_initial_commit():
        # Crea un commit vuoto per inizializzare la repository con un primo commit.
        try:
            output = subprocess.check_output(['git', 'commit', '--allow-empty', '-m', 'Initial commit'], 
                                           stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return True, output.strip() or "Commit iniziale creato con successo."
        except subprocess.CalledProcessError as e:
            return False, e.output.strip() if hasattr(e, 'output') and e.output else str(e)
        except Exception as e:
            return False, str(e)

    @staticmethod
    def has_commits():
        try:
            startupinfo = None
            if hasattr(subprocess, 'STARTF_USESHOWWINDOW'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), startupinfo=startupinfo)
            return True
        except subprocess.CalledProcessError:
            return False
        except Exception:
            return False

    @staticmethod
    def get_current_branch():
        if not GitRepo.has_commits():
            return "(nessun commit)"
        try:
            startupinfo = None
            if hasattr(subprocess, 'STARTF_USESHOWWINDOW'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), startupinfo=startupinfo).strip()
        except Exception:
            return "(nessun branch)"

    @staticmethod
    def get_current_origin():
        if not GitRepo.has_commits():
            return "(nessun link remoto)"
        try:
            startupinfo = None
            if hasattr(subprocess, 'STARTF_USESHOWWINDOW'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            return subprocess.check_output(['git', 'remote', 'get-url', 'origin'], text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), startupinfo=startupinfo).strip()
        except Exception:
            return "(nessun link remoto)"

    @staticmethod
    def fetch():
        try:
            startupinfo = None
            if hasattr(subprocess, 'STARTF_USESHOWWINDOW'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            output = subprocess.check_output(['git', 'fetch'], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), startupinfo=startupinfo)
            return True, output.strip()
        except subprocess.CalledProcessError as e:
            return False, e.output.strip() if hasattr(e, 'output') and e.output else str(e)

    @staticmethod
    def pull(branch):
        try:
            output = subprocess.check_output(['git', 'pull', 'origin', branch], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return True, output.strip()
        except subprocess.CalledProcessError as e:
            # Mostra solo errore e suggerisce di abilitare il force pull
            root = tk._default_root
            if root is None:
                root = tk.Tk()
                root.withdraw()
            mb.showerror("Errore pull", f"Si è verificato un errore durante il pull:\n\n{e.output.strip() if hasattr(e, 'output') and e.output else str(e)}\n\nPer risolvere, abilita l'opzione Force Pull.")
            return False, e.output.strip() if hasattr(e, 'output') and e.output else str(e)

    @staticmethod
    def pull_force(branch):
        # Chiede sempre la riclonazione, senza tentare fetch o reset
        root = tk._default_root
        if root is None:
            root = tk.Tk()
            root.withdraw()
        res = mb.askyesno("Riclonazione repository", "Vuoi cancellare e riclonare la repository da remoto?\n\nATTENZIONE: Tutte le modifiche locali e file non tracciati andranno perse.")
        if res:
            ok, msg = GitRepo.offer_cancel_or_clone()
            return ok, msg
        else:
            return False, "Operazione annullata dall'utente."

    @staticmethod
    def push(files, branch, commit_msg, force=False, on_too_many_files=None):
        try:
            output = ""
            repo_root = os.path.abspath(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).strip())

            def do_global_push():
                nonlocal output
                output += subprocess.check_output(['git', 'add', '-A'], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) or ""
                # Non controllare lo status prima - lascia che git commit gestisca il caso
                output += subprocess.check_output(['git', 'commit', '-m', commit_msg], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                return True, None
            if not files or len(files) == 0:
                ok, msg = do_global_push()
                if not ok:
                    return False, msg
            else:
                # Espandi file e cartelle ricorsivamente
                files_to_add = []
                def add_files_recursively(path):
                    abs_path = os.path.abspath(path)
                    if os.path.isfile(abs_path):
                        git_path = os.path.relpath(abs_path, repo_root).replace('\\', '/')
                        files_to_add.append(git_path)
                    elif os.path.isdir(abs_path):
                        for root, _, filenames in os.walk(abs_path):
                            for filename in filenames:
                                file_abs = os.path.join(root, filename)
                                git_path = os.path.relpath(file_abs, repo_root).replace('\\', '/')
                                files_to_add.append(git_path)
                for f in files:
                    add_files_recursively(f)
                # Rimuovi duplicati mantenendo l'ordine
                files_to_add = list(dict.fromkeys(files_to_add))
                if not files_to_add:
                    return False, "Nessun file selezionato da committare."
                try:
                    # Prima resetta i file selezionati dallo staging (così git add è sempre "fresco")
                    subprocess.check_output(['git', 'reset', 'HEAD', '--'] + files_to_add, stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    # Esegui git add solo sui file selezionati
                    output += subprocess.check_output(['git', 'add', '--'] + files_to_add, stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) or ""
                    # Controlla se almeno uno dei file selezionati è staged
                    diff_files = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '--'] + files_to_add, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    if not diff_files.strip():
                        return False, "Nessuna modifica da committare nei file selezionati."
                    # Committa solo se almeno un file selezionato è staged
                    output += subprocess.check_output(['git', 'commit', '-m', commit_msg], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                except (subprocess.CalledProcessError, OSError) as e:
                    err_msg = str(e)
                    # Cerca errori di "troppi file" o "estensione troppo lunga"
                    if any(x in err_msg.lower() for x in ["file name too long", "arg list too long", "estensione troppo lunga", "argument list too long"]):
                        if on_too_many_files and callable(on_too_many_files):
                            user_confirm = on_too_many_files()
                            if user_confirm:
                                ok, msg = do_global_push()
                                if not ok:
                                    return False, msg
                            else:
                                return False, "Push annullato dall'utente (troppi file selezionati)."
                        else:
                            # Callback visuale di default
                            root = None
                            try:
                                root = tk._default_root
                                if root is None:
                                    root = tk.Tk()
                                    root.withdraw()
                                user_confirm = mb.askyesno("Push globale", "Hai selezionato troppi file/cartelle per il push selettivo.\n\nVuoi eseguire un commit e push di TUTTE le modifiche nella repository?\n\nQuesta azione includerà TUTTI i file modificati, aggiunti o cancellati.")
                            except Exception:
                                user_confirm = False
                            finally:
                                if root is not None and not root.winfo_viewable():
                                    root.destroy()
                            if user_confirm:
                                ok, msg = do_global_push()
                                if not ok:
                                    return False, msg
                            else:
                                return False, "Push annullato dall'utente (troppi file selezionati)."
                    else:
                        return False, err_msg

            # Push con o senza force
            push_cmd = ['git', 'push', 'origin', branch]
            if force:
                push_cmd.insert(2, '--force')
            output += subprocess.check_output(push_cmd, stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return True, output.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.output.strip() if hasattr(e, 'output') and e.output else str(e)
            # Rileva errore "repository not found"
            if any(x in error_msg.lower() for x in ["repository not found", "404", "not found"]):
                return False, f"REPO_NOT_FOUND:{error_msg}"
            return False, error_msg

    @staticmethod
    def get_remote_branches():
        try:
            remote_branches = subprocess.check_output(['git', 'branch', '-r'], text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return [b.strip().replace('origin/', '') for b in remote_branches.splitlines() if '->' not in b]
        except Exception:
            return []

    @staticmethod
    def get_local_branches():
        try:
            local_branches = subprocess.check_output(['git', 'branch'], text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return [b.strip().replace("* ", "") for b in local_branches.splitlines()]
        except Exception:
            return []

    @staticmethod
    def checkout(branch):
        # Parcheggia i file non tracciati prima del checkout, ripristina quelli del nuovo branch dopo
        current_branch = GitRepo.get_current_branch()
        GitRepo.park_untracked_files(current_branch)
        try:
            output = subprocess.check_output(['git', 'checkout', branch], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            GitRepo.unpark_untracked_files(branch)
            return True, output.strip()
        except subprocess.CalledProcessError as e:
            GitRepo.unpark_untracked_files(current_branch)
            err_msg = e.output.strip() if hasattr(e, 'output') and e.output else str(e)
            if 'would be overwritten by checkout' in err_msg:
                return GitRepo._handle_checkout_overwrite_error(
                    err_msg,
                    lambda: subprocess.check_output(['git', 'checkout', branch], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)),
                    branch,
                    current_branch
                )
            return False, err_msg

    @staticmethod
    def checkout_new(branch):
        # Parcheggia i file non tracciati prima del checkout, ripristina quelli del nuovo branch dopo
        current_branch = GitRepo.get_current_branch()
        GitRepo.park_untracked_files(current_branch)
        try:
            output = subprocess.check_output(['git', 'checkout', '-b', branch, f'origin/{branch}'], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            GitRepo.unpark_untracked_files(branch)
            return True, output.strip()
        except subprocess.CalledProcessError as e:
            GitRepo.unpark_untracked_files(current_branch)
            err_msg = e.output.strip() if hasattr(e, 'output') and e.output else str(e)
            if 'would be overwritten by checkout' in err_msg:
                return GitRepo._handle_checkout_overwrite_error(
                    err_msg,
                    lambda: subprocess.check_output(['git', 'checkout', '-b', branch, f'origin/{branch}'], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)),
                    branch,
                    current_branch
                )
            return False, err_msg

    @staticmethod
    def create_and_checkout_from_branch(new_branch, origin_branch):
        # Parcheggia i file non tracciati prima del checkout, ripristina quelli del nuovo branch dopo
        current_branch = GitRepo.get_current_branch()
        GitRepo.park_untracked_files(current_branch)
        try:
            output = subprocess.check_output(['git', 'checkout', '-b', new_branch, origin_branch], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            GitRepo.unpark_untracked_files(new_branch)
            return True, output.strip()
        except subprocess.CalledProcessError as e:
            GitRepo.unpark_untracked_files(current_branch)
            err_msg = e.output.strip() if hasattr(e, 'output') and e.output else str(e)
            if 'would be overwritten by checkout' in err_msg:
                return GitRepo._handle_checkout_overwrite_error(
                    err_msg,
                    lambda: subprocess.check_output(['git', 'checkout', '-b', new_branch, origin_branch], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)),
                    new_branch,
                    current_branch
                )
            return False, err_msg

    @staticmethod
    def get_github_user():
        # Restituisce l'utente GitHub autenticato tramite GitHub CLI
        try:
            startupinfo = None
            if hasattr(subprocess, 'STARTF_USESHOWWINDOW'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
            output = subprocess.check_output(['gh', 'auth', 'status'], stderr=subprocess.STDOUT, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), startupinfo=startupinfo)
            
            # Estrae il nome utente dall'output
            for line in output.split('\n'):
                line = line.strip()
                # Cerca la riga "Logged in to github.com account USERNAME"
                if 'Logged in to github.com account' in line:
                    # Estrae la parte dopo "account " e prima di " (keyring)"
                    parts = line.split('account ')
                    if len(parts) > 1:
                        username_part = parts[1]
                        # Rimuove " (keyring)" se presente
                        if ' (' in username_part:
                            username = username_part.split(' (')[0]
                        else:
                            username = username_part.split(' ')[0]
                        return username.strip()
            
            return "(non autenticato)"
        except subprocess.CalledProcessError:
            return "(non autenticato)"
        except FileNotFoundError:
            return "(GitHub CLI non installato)"
        except Exception:
            return "(errore)"

    @staticmethod
    def parse_github_url(url):
        # Estrae account remoto e nome repository da un URL GitHub.
        # Supporta formati:
        # - https://github.com/user/repo.git
        # - https://github.com/user/repo
        # - git@github.com:user/repo.git
        # - git@github.com:user/repo
        # Ritorna (account, repo_name) o (None, None) se il parsing fallisce
        if not url or url.startswith('('):
            return None, None
        try:
            # Gestisci formato HTTPS
            if url.startswith('https://'):
                # Rimuovi il protocollo e il dominio
                parts = url.replace('https://github.com/', '').split('/')
                if len(parts) >= 2:
                    account = parts[0]
                    repo_name = parts[1].replace('.git', '')
                    return account, repo_name
            # Gestisci formato SSH
            elif url.startswith('git@github.com:'):
                # Rimuovi il prefisso SSH
                parts = url.replace('git@github.com:', '').split('/')
                if len(parts) >= 2:
                    account = parts[0]
                    repo_name = parts[1].replace('.git', '')
                    return account, repo_name
        except Exception:
            pass
        return None, None

    @staticmethod
    def build_github_url(account, repo_name):
        # Costruisce un URL GitHub HTTPS dal nome dell'account e del repository.
        return f"https://github.com/{account}/{repo_name}.git"

    @staticmethod
    def set_remote_url(account, repo_name):
        # Imposta il remote origin con l'URL costruito da account e repo_name.
        # Se il remote non esiste, lo crea; se esiste, lo aggiorna.
        try:
            url = GitRepo.build_github_url(account, repo_name)
            try:
                # Prova prima ad aggiornare il remote esistente
                _ = subprocess.check_output(
                    ['git', 'remote', 'set-url', 'origin', url],
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                )
                return True, f"Remote impostato a: {url}"
            except subprocess.CalledProcessError as e:
                # Se il remote non esiste, crealo
                err_msg = e.output.strip() if hasattr(e, 'output') and e.output else str(e)
                if "no such remote" in err_msg.lower():
                    try:
                        _ = subprocess.check_output(
                            ['git', 'remote', 'add', 'origin', url],
                            stderr=subprocess.STDOUT,
                            text=True,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                        )
                        return True, f"Remote creato a: {url}"
                    except subprocess.CalledProcessError as e_add:
                        err_add = e_add.output.strip() if hasattr(e_add, 'output') and e_add.output else str(e_add)
                        return False, err_add
                else:
                    return False, err_msg
        except subprocess.CalledProcessError as e:
            return False, e.output.strip() if hasattr(e, 'output') and e.output else str(e)
        except Exception as e:
            return False, str(e)

    @staticmethod
    def create_remote_repository(repo_name, account=None):
        # Crea una repository su GitHub tramite GitHub CLI.
        # Se account è fornito, crea nell'organizzazione, altrimenti nel profilo utente.
        try:
            # Costruisci il comando gh repo create
            if account:
                repo_full_name = f"{account}/{repo_name}"
            else:
                repo_full_name = repo_name
            
            # Comando semplicissimo - solo creare la repo senza toccare il remote locale
            cmd = ['gh', 'repo', 'create', repo_full_name, '--public']
            
            _ = subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            
            # Dopo la creazione, fai il push manualmente usando il remote già configurato
            push_cmd = ['git', 'push', '-u', 'origin', 'HEAD']
            _ = subprocess.check_output(
                push_cmd,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            
            return True, f"Repository '{repo_full_name}' creata con successo su GitHub!"
        except subprocess.CalledProcessError as e:
            err_msg = e.output.strip() if hasattr(e, 'output') and e.output else str(e)
            return False, err_msg
        except FileNotFoundError:
            return False, "GitHub CLI non trovato. Assicurati che 'gh' sia installato e nel PATH."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def clone(url):
        # Clona una repository da un URL GitHub
        # Restituisce (success, percorso_repo_o_errore)
        try:
            # Estrai il nome della repo dall'URL per usarlo come cartella di destinazione
            repo_name = url.rstrip('/').split('/')[-1].replace('.git', '')
            # Clona nella directory corrente
            clone_cmd = ['git', 'clone', url, repo_name]
            output = subprocess.check_output(
                clone_cmd,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            # Restituisci il percorso assoluto della repo clonata
            cloned_path = os.path.abspath(repo_name)
            return True, cloned_path
        except subprocess.CalledProcessError as e:
            err_msg = e.output.strip() if hasattr(e, 'output') and e.output else str(e)
            return False, err_msg
        except Exception as e:
            return False, str(e)

    @staticmethod
    def reset_last_commit():
        # Annulla l'ultimo commit, mantenendo i cambiamenti nel working directory.
        try:
            _ = subprocess.check_output(
                ['git', 'reset', '--soft', 'HEAD~1'],
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            return True, ""
        except subprocess.CalledProcessError as e:
            err_msg = e.output.strip() if hasattr(e, 'output') and e.output else str(e)
            return False, err_msg
        except Exception as e:
            return False, str(e)