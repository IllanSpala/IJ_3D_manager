import os
import sys
import time
import zipfile
from pathlib import Path
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.paths import BUNDLE_DIR
from core.database import db, DB_PATH
from core.utils import open_url, APP_BG_COLOR, BORDER_COLOR, ACCENT_COLOR, BASE_DIR, MEDIA_DIR
from tabs.filamentos import TabFilamentos
from tabs.acervo import TabAcervo
from tabs.almoxarifado import TabAlmoxarifado
from tabs.pedidos import TabPedidos
from tabs.financeiro import TabFinanceiro
from tabs.historico import TabHistorico

ctk.set_appearance_mode("dark")
# Icon is a read-only bundled asset — use BUNDLE_DIR so it resolves
# to _MEIPASS when frozen and to project root when running from source.
APP_ICON_PATH = str(BUNDLE_DIR / "app_icon.png")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IJ 3D - Refactored")

        # ── Resolução adaptativa ──────────────────────────────────────────
        # Lê a resolução REAL do monitor antes de configurar qualquer coisa
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        # Escala global do CustomTkinter baseada na altura da tela
        # 768p → 1.0 | 1080p → 1.1 | 1440p → 1.3 | 4K(2160p) → 1.6
        if sh >= 2000:
            ui_scale = 1.6
        elif sh >= 1400:
            ui_scale = 1.3
        elif sh >= 1000:
            ui_scale = 1.1
        else:
            ui_scale = 1.0
        ctk.set_widget_scaling(ui_scale)
        ctk.set_window_scaling(ui_scale)

        # Janela começa maximizada / adaptada para 4k
        self.geometry("3840x2160+0+0")

        # ── Critical: intercept the close button ──
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        def _try_maximize():
            try:
                self.state('zoomed')          # Windows — único alvo
            except Exception:
                pass
        self.after(100, _try_maximize)

        self.configure(fg_color=APP_BG_COLOR)
        try:
            if os.path.exists(APP_ICON_PATH):
                icon = tk.PhotoImage(file=APP_ICON_PATH)
                self.wm_iconphoto(True, icon)
        except Exception:
            pass

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── Icon-only sidebar (45 px, no expand/collapse) ─────────────────────
        sidebar = ctk.CTkFrame(
            self, corner_radius=0, fg_color="#111111",
            border_width=1, border_color=BORDER_COLOR, width=45
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)          # enforce fixed width
        sidebar.grid_columnconfigure(0, weight=1)
        # spacer row pushes backup buttons to the bottom
        sidebar.grid_rowconfigure(10, weight=1)

        nav_items = [
            (1,  "⚙",  lambda: self._swap(TabFilamentos)),
            (2,  "📦", lambda: self._swap(TabAlmoxarifado)),
            (3,  "📚", lambda: self._swap(TabAcervo)),
            (5,  "📝", lambda: self._swap(TabPedidos)),
            (6,  "🗂", lambda: self._swap(TabHistorico)),
            (7,  "💰", lambda: self._swap(TabFinanceiro)),
        ]
        for row, icon, cmd in nav_items:
            btn = ctk.CTkButton(
                sidebar, text=icon, width=38, height=38,
                fg_color="transparent", text_color="white",
                font=ctk.CTkFont(size=18), command=cmd
            )
            btn.grid(row=row, column=0, padx=3, pady=3, sticky="ew")

        # ── Bottom: minimal backup icons ─────────────────────────────────────
        bottom = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom.grid(row=11, column=0, sticky="sew", pady=(0, 6))
        bottom.grid_columnconfigure(0, weight=1)

        self._btn_export = ctk.CTkButton(
            bottom, text="💾", width=38, height=38,
            fg_color="#2b7a4b", hover_color="#1d5c36",
            font=ctk.CTkFont(size=16),
            command=self._export_backup
        )
        self._btn_export.grid(row=0, column=0, padx=3, pady=2)

        self._btn_import = ctk.CTkButton(
            bottom, text="📂", width=38, height=38,
            fg_color="#a83232", hover_color="#7a2424",
            font=ctk.CTkFont(size=16),
            command=self._import_backup
        )
        self._btn_import.grid(row=1, column=0, padx=3, pady=2)

        self.main_frame = ctk.CTkFrame(self, fg_color=APP_BG_COLOR, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")

        from core.modals import DetalhesModal
        self.modals = {
            'detalhes': DetalhesModal(self)
        }

        self.tab_cache = {}
        self._current = None
        self._swap(TabFilamentos)

    def _save_printer(self, _event=None):
        """No-op kept for compatibility; printer entry removed from compact sidebar."""
        self.focus()

    # _toggle_sidebar removed — sidebar is now permanently compact (icon-only).

    def _swap(self, cls):
        if self._current:
            self._current.pack_forget()
            
        if cls not in self.tab_cache:
            self.tab_cache[cls] = cls(self.main_frame)
            
        self._current = self.tab_cache[cls]
        self._current.pack(fill="both", expand=True)

    def _export_backup(self):
        dest = filedialog.asksaveasfilename(
            defaultextension=".zip",
            initialfile=f"IJ3D_Backup_{int(time.time())}.zip",
            filetypes=[("ZIP Archive", "*.zip")],
            title="Salvar Backup",
        )
        if not dest: return
        try:
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                if DB_PATH.exists():
                    zf.write(DB_PATH, DB_PATH.name)
                if MEDIA_DIR.exists():
                    for root, _, files in os.walk(MEDIA_DIR):
                        for f in files:
                            abs_path = os.path.join(root, f)
                            rel_path = os.path.relpath(abs_path, BASE_DIR)
                            zf.write(abs_path, rel_path)
            messagebox.showinfo("Sucesso", "Backup exportado com sucesso!")
        except Exception as exc:
            messagebox.showerror("Erro", f"Falha ao exportar backup:\n{exc}")

    def _import_backup(self):
        if not messagebox.askyesno("Aviso", "Atenção: Importar um backup irá SOBRESCREVER o banco de dados atual e TODAS as fotos cadastradas. Deseja continuar?"):
            return
        src = filedialog.askopenfilename(filetypes=[("ZIP Archive", "*.zip")], title="Selecionar arquivo de Backup")
        if not src: return
        try:
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(BASE_DIR)
            messagebox.showinfo("Sucesso", "Backup importado!\n\nO aplicativo será fechado para recarregar os dados de forma limpa. Por favor, abra-o novamente.")
            self._on_close()
        except Exception as exc:
            messagebox.showerror("Erro", f"Falha na importação:\n{exc}")

    def _on_close(self):
        """Graceful shutdown: silence state → close SQLite → destroy UI → hard exit."""
        from core.state import app_state

        # 1. Flag shutdown to block any in-flight notify() calls
        app_state._shutting_down = True

        # 2. Silence all state listeners so no callback fires against dead widgets
        for key in app_state.listeners:
            app_state.listeners[key].clear()

        # 3. Close all SQLite connections explicitly to avoid WAL corruption
        try:
            from core.database import db
            # Force a clean checkpoint + close on the shared connection pool
            with db.get_connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass

        # 4. Destroy the Tk window (stops the mainloop)
        try:
            self.destroy()
        except Exception:
            pass

        # 5. Hard exit — orphan Tcl threads can keep the process alive
        #    even after destroy(). os._exit is the only guaranteed kill.
        os._exit(0)

if __name__ == "__main__":
    app = App()
    app.mainloop()