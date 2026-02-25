import os
import sys
import atexit
import ctypes
from tkinter import messagebox as mb
from main import GitGuiApp

def is_pid_running(pid):
    try:
        if pid <= 0:
            return False
        if os.name == 'nt':
            PROCESS_QUERY_INFORMATION = 0x0400
            process = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, 0, pid)
            if process != 0:
                ctypes.windll.kernel32.CloseHandle(process)
                return True
            else:
                return False
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False

def check_gui_visible(app):
    app.update_idletasks()
    app.update()
    return app.winfo_exists() and (app.state() != 'withdrawn')

if __name__ == "__main__":
    lockfile = os.path.join(os.getenv('TEMP') or '.', 'gitbash_auto.lock')
    # Kill any previous process of this app (if running)
    if os.path.exists(lockfile):
        try:
            with open(lockfile, 'r') as f:
                pid_str = f.read().strip()
                pid = int(pid_str) if pid_str.isdigit() else None
        except Exception:
            pid = None
        if pid and pid != os.getpid():
            try:
                if os.name == 'nt':
                    PROCESS_TERMINATE = 0x0001
                    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, 0, pid)
                    if handle:
                        ctypes.windll.kernel32.TerminateProcess(handle, -1)
                        ctypes.windll.kernel32.CloseHandle(handle)
                else:
                    os.kill(pid, 9)
            except Exception:
                pass
        try:
            os.remove(lockfile)
        except Exception:
            pass
    with open(lockfile, 'w') as f:
        f.write(str(os.getpid()))

    def remove_lock():
        try:
            if os.path.exists(lockfile):
                os.remove(lockfile)
        except Exception:
            pass
    atexit.register(remove_lock)

    try:
        # Controllo ambiente Tkinter
        try:
            import tkinter
            root = tkinter.Tk()
            root.withdraw()
            root.update()
            root.destroy()
        except Exception as tkerr:
            try:
                mb.showerror("Errore ambiente Tkinter", f"Tkinter non funziona correttamente:\n{tkerr}")
            except Exception:
                pass
            remove_lock()
            sys.exit(1)
        app = GitGuiApp()
        if not check_gui_visible(app):
            try:
                mb.showerror("Errore GUI", "La finestra principale non è visibile.\nControlla che non ci siano errori di Tkinter o di ambiente.")
            except Exception:
                pass
            remove_lock()
            sys.exit(1)
        app.mainloop()
    except Exception as e:
        try:
            mb.showerror("Errore avvio app", f"Errore durante l'avvio dell'app:\n{e}")
        except Exception:
            pass
        raise
    finally:
        remove_lock()