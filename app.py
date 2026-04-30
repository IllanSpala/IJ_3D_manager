import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import sqlite3
import datetime
import os
import shutil
import time
import zipfile
import webbrowser
from pathlib import Path
from PIL import Image

ctk.set_appearance_mode("dark")

# ==========================================
# PORTABILITY: ANCHOR ALL PATHS TO SCRIPT
# ==========================================
BASE_DIR   = Path(__file__).parent.resolve()
MEDIA_DIR  = BASE_DIR / "src_media"
INVOICE_DIR = MEDIA_DIR / "invoices"
DB_PATH    = BASE_DIR / "print_manager_v2.db"

APP_BG_COLOR  = "#141414"
CARD_BG_COLOR = "#212121"
BORDER_COLOR  = "#333333"
ACCENT_COLOR  = "#00a2ff"
APP_ICON_PATH = str(BASE_DIR / "app_icon.png")


# ==========================================
# MEDIA HELPERS
# ==========================================

def _ensure_media_dirs():
    """Create src_media and src_media/invoices if they don't exist."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    INVOICE_DIR.mkdir(parents=True, exist_ok=True)


def copy_to_media(src_path: str, subfolder: str = "") -> str:
    """
    Copy a file into src_media (or a subfolder of it).
    Returns the filename only (not the full path).
    Raises on copy failure.
    """
    dest_dir = MEDIA_DIR / subfolder if subfolder else MEDIA_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    src = Path(src_path)
    filename = src.name

    # Avoid silent overwrites: append timestamp if name conflicts.
    dest = dest_dir / filename
    if dest.exists():
        filename = f"{src.stem}_{int(time.time())}{src.suffix}"
        dest = dest_dir / filename

    try:
        shutil.copy2(src, dest)
    except OSError as exc:
        raise RuntimeError(f"Falha ao copiar arquivo: {exc}") from exc

    return filename


def resolve_media_path(stored_value: str, subfolder: str = "") -> str | None:
    """
    Turn a stored DB value (filename or legacy absolute path) into a
    concrete filesystem path suitable for Pillow / CTkImage.
    Returns None when stored_value is empty.
    """
    if not stored_value:
        return None
    # Legacy records stored the full absolute path — honour them as-is.
    if os.path.isabs(stored_value):
        return stored_value
    # Modern records store the filename only.
    if subfolder:
        return str(MEDIA_DIR / subfolder / stored_value)
    return str(MEDIA_DIR / stored_value)


def load_and_resize_image(path: str | None, size=(150, 150)):
    """Open *path* with Pillow and return a CTkImage, or None on failure."""
    try:
        if path and os.path.exists(path):
            img = Image.open(path)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            return ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
    except Exception:
        pass
    return None


def open_url(url: str):
    if url:
        webbrowser.open(url)


# ==========================================
# DATABASE INITIALISATION
# ==========================================

def init_db():
    _ensure_media_dirs()

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # ── configuracoes ──────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS configuracoes
                 (id INTEGER PRIMARY KEY, printer_name TEXT)''')
    if c.execute("SELECT COUNT(*) FROM configuracoes").fetchone()[0] == 0:
        c.execute("INSERT INTO configuracoes (id, printer_name) VALUES (1, 'BAMBU LAB A1')")

    # ── filamentos ─────────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS filamentos
                 (id INTEGER PRIMARY KEY,
                  marca TEXT, material TEXT, cor TEXT,
                  peso_inicial REAL, peso_atual REAL,
                  caminho_foto TEXT, link_compra TEXT,
                  preco_rolo REAL DEFAULT 0.0,
                  caminho_nota_fiscal TEXT)''')
    # Migrations for tables that may have been created by older versions.
    for col, definition in [
        ("link_compra",         "TEXT"),
        ("preco_rolo",          "REAL DEFAULT 0.0"),
        ("caminho_nota_fiscal", "TEXT"),
    ]:
        try:
            c.execute(f"ALTER TABLE filamentos ADD COLUMN {col} {definition}")
        except sqlite3.OperationalError:
            pass  # Column already exists.

    # ── historico_impressao (telemetria de filamento) ──────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS historico_impressao
                 (id INTEGER PRIMARY KEY,
                  filamento_id INTEGER NOT NULL,
                  data_impressao TEXT NOT NULL,
                  peso_peca_g REAL NOT NULL DEFAULT 0.0,
                  peso_desperdicio_g REAL NOT NULL DEFAULT 0.0,
                  status TEXT NOT NULL DEFAULT 'Sucesso',
                  observacao TEXT,
                  FOREIGN KEY(filamento_id) REFERENCES filamentos(id) ON DELETE CASCADE)''')

    # ── acervo ─────────────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS acervo
                 (id INTEGER PRIMARY KEY,
                  nome_peca TEXT, caminho_foto TEXT,
                  arquivo_3d TEXT, pos_processamento TEXT,
                  data_registro TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS acervo_filamentos
                 (acervo_id INTEGER, filamento_id INTEGER, peso_gasto REAL,
                  FOREIGN KEY(acervo_id) REFERENCES acervo(id),
                  FOREIGN KEY(filamento_id) REFERENCES filamentos(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS acervo_impressoes
                 (id INTEGER PRIMARY KEY, acervo_id INTEGER, data_impressao TEXT,
                  FOREIGN KEY(acervo_id) REFERENCES acervo(id))''')

    # ── manutencao ─────────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS manutencao
                 (id INTEGER PRIMARY KEY,
                  tarefa TEXT, guia_instrucao TEXT,
                  intervalo_dias INTEGER, ultima_execucao TEXT,
                  link_tutorial TEXT)''')

    # ── ferramentas / insumos ──────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS ferramentas_insumos
                 (id INTEGER PRIMARY KEY,
                  nome TEXT, categoria TEXT, quantidade_status TEXT,
                  caminho_foto TEXT, link_compra TEXT,
                  ultimo_valor REAL)''')

    # ── pedidos ────────────────────────────────────────────────────────────────
    try:
        c.execute("SELECT 1 FROM pedidos_itens LIMIT 1")
    except sqlite3.OperationalError:
        c.execute('''CREATE TABLE IF NOT EXISTS pedidos_v2
                     (id INTEGER PRIMARY KEY,
                      nome_cliente TEXT, data_entrega TEXT,
                      valor_cobrado REAL, status TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS pedidos_itens
                     (pedido_id INTEGER, acervo_id INTEGER,
                      FOREIGN KEY(pedido_id) REFERENCES pedidos_v2(id),
                      FOREIGN KEY(acervo_id) REFERENCES acervo(id))''')
        # Migrate legacy `pedidos` table if it exists.
        try:
            old = c.execute(
                "SELECT id, acervo_id, nome_cliente, data_entrega, valor_cobrado, status FROM pedidos"
            ).fetchall()
            for p in old:
                c.execute(
                    "INSERT INTO pedidos_v2 (id, nome_cliente, data_entrega, valor_cobrado, status) VALUES (?,?,?,?,?)",
                    (p[0], p[2], p[3], p[4], p[5]),
                )
                c.execute(
                    "INSERT INTO pedidos_itens (pedido_id, acervo_id) VALUES (?,?)",
                    (p[0], p[1]),
                )
            c.execute("DROP TABLE pedidos")
        except sqlite3.OperationalError:
            pass

    # ── seed manutencao ────────────────────────────────────────────────────────
    if c.execute("SELECT COUNT(*) FROM manutencao").fetchone()[0] == 0:
        hoje = datetime.date.today().isoformat()
        tarefas = [
            ("Lubrificar eixo Y",       "Limpe os trilhos com pano e álcool isopropílico. Aplique graxa.", 30, hoje, "https://wiki.bambulab.com/en/a1/maintenance/lubricate-y-axis"),
            ("Lubrificar eixo Z",       "Limpe os fusos. Aplique graxa nos fusos e mova o eixo Z.", 30, hoje,       "https://wiki.bambulab.com/en/a1/maintenance/lubricate-z-axis"),
            ("Limpar bico (Nozzle)",    "Aqueça a 250°C, use escova de latão para remover resíduos.", 7, hoje,      "https://wiki.bambulab.com/en/a1/maintenance/hotend-maintenance"),
            ("Limpar Engrenagens AMS",  "Pressione botões para remover PTFE, sopre ou use pincel.", 30, hoje,       "https://wiki.bambulab.com/en/ams-lite/maintenance/cleaning-ams-lite"),
            ("Tensionar Correias",      "Afrouxe parafusos X/Y, mova cabeçote/cama. Reaperte.", 30, hoje,          "https://wiki.bambulab.com/en/a1/maintenance/belt-tensioning"),
            ("Limpar PEI (Mesa)",       "Use detergente e água morna. Não use dedos na superfície.", 7, hoje,      "https://wiki.bambulab.com/en/general/textured-pei-plate-cleaning"),
        ]
        c.executemany(
            "INSERT INTO manutencao (tarefa, guia_instrucao, intervalo_dias, ultima_execucao, link_tutorial) VALUES (?,?,?,?,?)",
            tarefas,
        )

    conn.commit()
    conn.close()


# ==========================================
# FILAMENT TELEMETRY (Bambu Lab A1 logic)
# ==========================================

def registrar_impressao(filamento_id: int, peso_peca_g: float,
                         peso_desperdicio_g: float, status: str,
                         observacao: str = "") -> None:
    """
    Insert a row into historico_impressao and debit the consumed filament
    from filamentos.peso_atual.

    On failure (print failed mid-job), the operator may log just the waste:
        peso_peca_g=0, peso_desperdicio_g=<extruded_so_far>, status='Falha'
    """
    total_g = peso_peca_g + peso_desperdicio_g
    total_kg = total_g / 1000.0

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    try:
        c.execute(
            """INSERT INTO historico_impressao
               (filamento_id, data_impressao, peso_peca_g, peso_desperdicio_g, status, observacao)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (filamento_id, datetime.datetime.now().isoformat(),
             peso_peca_g, peso_desperdicio_g, status, observacao),
        )
        # Clamp at 0 — can never go negative.
        c.execute(
            "UPDATE filamentos SET peso_atual = MAX(0.0, peso_atual - ?) WHERE id = ?",
            (total_kg, filamento_id),
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise exc
    finally:
        conn.close()


# ==========================================
# SHARED WIDGET
# ==========================================

class ModernCard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        bc = kwargs.pop("border_color", BORDER_COLOR)
        bw = kwargs.pop("border_width", 1)
        super().__init__(
            master, fg_color=CARD_BG_COLOR, corner_radius=12,
            border_width=bw, border_color=bc, **kwargs,
        )


# ==========================================
# TAB – FILAMENTOS
# ==========================================

class TabFilamentos(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(side="top", fill="x", padx=20, pady=(10, 0))

        self.form_card = ModernCard(top, border_width=0)
        self.form_card.pack(side="top", fill="x", pady=(0, 20))

        self.alert_frame = ctk.CTkFrame(top, fg_color="transparent")
        self.alert_frame.pack(side="top", fill="x")

        self.form_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(
            self.form_card, text="Cadastrar Novo Filamento",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=4, pady=(5, 0))

        def lbl_entry(parent_frame, row, col, label, var, placeholder=""):
            f = ctk.CTkFrame(parent_frame, fg_color="transparent")
            f.grid(row=row, column=col, padx=10, sticky="ew")
            ctk.CTkLabel(f, text=label, text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
            ctk.CTkEntry(f, textvariable=var, height=25, placeholder_text=placeholder).pack(fill="x")

        self.marca_var    = ctk.StringVar()
        self.material_var = ctk.StringVar()
        self.cor_var      = ctk.StringVar()
        self.peso_var     = ctk.StringVar(value="1.0")
        self.preco_var    = ctk.StringVar()
        self.link_var     = ctk.StringVar()

        lbl_entry(self.form_card, 1, 0, "Marca",    self.marca_var)
        lbl_entry(self.form_card, 1, 1, "Material", self.material_var)
        lbl_entry(self.form_card, 1, 2, "Cor",      self.cor_var)
        lbl_entry(self.form_card, 1, 3, "Peso (KG)", self.peso_var)
        lbl_entry(self.form_card, 2, 0, "Valor ($)", self.preco_var)
        lbl_entry(self.form_card, 2, 1, "Link",      self.link_var)

        self._new_foto_filename = None
        f5 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f5.grid(row=2, column=2, padx=10, sticky="ew")
        ctk.CTkLabel(f5, text="Foto", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.btn_foto = ctk.CTkButton(f5, text="Buscar", height=25, fg_color="#333", hover_color="#444", command=self._select_photo)
        self.btn_foto.pack(fill="x")

        f6 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f6.grid(row=2, column=3, padx=10, sticky="ew")
        ctk.CTkLabel(f6, text="", font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkButton(f6, text="Salvar", height=25, font=ctk.CTkFont(weight="bold"),
                      command=self._save_filamento, fg_color=ACCENT_COLOR).pack(fill="x")

        ctk.CTkFrame(self.form_card, height=10, fg_color="transparent").grid(row=3, column=0)

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(5, 20))

        self._load()

    # ── photo selection ────────────────────────────────────────────────────────

    def _select_photo(self):
        path = filedialog.askopenfilename(filetypes=[("Imagens", "*.jpg *.jpeg *.png")])
        if not path:
            return
        try:
            self._new_foto_filename = copy_to_media(path)
            self.btn_foto.configure(text="Anexada ✓", fg_color="#2b7a4b")
        except RuntimeError as exc:
            messagebox.showerror("Erro de cópia", str(exc))

    # ── save new filament ──────────────────────────────────────────────────────

    def _save_filamento(self):
        m, mat, c_val = self.marca_var.get(), self.material_var.get(), self.cor_var.get()
        try:
            p = float(self.peso_var.get().replace(",", "."))
        except ValueError:
            return messagebox.showerror("Erro", "Peso deve ser numérico.")
        if not all([m, mat, c_val]):
            return messagebox.showerror("Erro", "Preencha marca, material e cor.")

        preco = 0.0
        if self.preco_var.get():
            try:
                preco = float(self.preco_var.get().replace(",", "."))
            except ValueError:
                return messagebox.showerror("Erro", "Preço deve ser numérico.")

        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            """INSERT INTO filamentos
               (marca, material, cor, peso_inicial, peso_atual,
                caminho_foto, link_compra, preco_rolo)
               VALUES (?,?,?,?,?,?,?,?)""",
            (m, mat, c_val, p, p, self._new_foto_filename, self.link_var.get(), preco),
        )
        conn.commit(); conn.close()

        for var in (self.marca_var, self.material_var, self.cor_var,
                    self.link_var, self.preco_var):
            var.set("")
        self.peso_var.set("1.0")
        self._new_foto_filename = None
        self.btn_foto.configure(text="Buscar", fg_color="#333")
        self._load()

    # ── attach invoice ─────────────────────────────────────────────────────────

    def _attach_invoice(self, filamento_id: int):
        path = filedialog.askopenfilename(
            title="Selecionar Nota Fiscal / Comprovante",
            filetypes=[("Documentos", "*.jpg *.jpeg *.png *.pdf")],
        )
        if not path:
            return
        try:
            filename = copy_to_media(path, subfolder="invoices")
        except RuntimeError as exc:
            return messagebox.showerror("Erro de cópia", str(exc))

        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "UPDATE filamentos SET caminho_nota_fiscal=? WHERE id=?",
            (filename, filamento_id),
        )
        conn.commit(); conn.close()
        messagebox.showinfo("Sucesso", f"Nota fiscal '{filename}' vinculada ao filamento.")
        self._load()

    # ── open stored invoice ────────────────────────────────────────────────────

    def _open_invoice(self, filename: str):
        full = resolve_media_path(filename, subfolder="invoices")
        if full and os.path.exists(full):
            open_url(f"file://{full}")
        else:
            messagebox.showerror("Arquivo não encontrado", f"Não foi possível localizar:\n{full}")

    # ── telemetry dialog ───────────────────────────────────────────────────────

    def _open_telemetry_dialog(self, filamento_id: int, label: str):
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Registrar Impressão — {label}")
        dlg.geometry("420x420")
        dlg.after(100, dlg.grab_set)

        ctk.CTkLabel(dlg, text="Registrar Uso de Filamento",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(dlg, text="Informe os valores do fatiador (Bambu Studio)",
                     text_color="gray", font=ctk.CTkFont(size=11)).pack()

        ctk.CTkLabel(dlg, text="Peso da Peça (gramas)", font=ctk.CTkFont(weight="bold")).pack(pady=(18, 2))
        peso_peca_var = ctk.StringVar(value="0")
        ctk.CTkEntry(dlg, textvariable=peso_peca_var).pack()

        ctk.CTkLabel(dlg, text="Peso Desperdiçado — purga / suporte (gramas)",
                     font=ctk.CTkFont(weight="bold")).pack(pady=(12, 2))
        peso_waste_var = ctk.StringVar(value="0")
        ctk.CTkEntry(dlg, textvariable=peso_waste_var).pack()

        ctk.CTkLabel(dlg, text="Status da Impressão", font=ctk.CTkFont(weight="bold")).pack(pady=(12, 2))
        status_var = ctk.StringVar(value="Sucesso")
        ctk.CTkOptionMenu(dlg, variable=status_var, values=["Sucesso", "Falha"]).pack()

        ctk.CTkLabel(dlg, text="Observação (opcional)", font=ctk.CTkFont(weight="bold")).pack(pady=(12, 2))
        obs_var = ctk.StringVar()
        ctk.CTkEntry(dlg, textvariable=obs_var, placeholder_text="Ex: Falha na camada 40").pack()

        def _save():
            try:
                pp = float(peso_peca_var.get().replace(",", "."))
                pw = float(peso_waste_var.get().replace(",", "."))
            except ValueError:
                return messagebox.showerror("Erro", "Pesos devem ser numéricos (gramas).")
            if pp < 0 or pw < 0:
                return messagebox.showerror("Erro", "Pesos não podem ser negativos.")
            try:
                registrar_impressao(filamento_id, pp, pw, status_var.get(), obs_var.get())
            except Exception as exc:
                return messagebox.showerror("Erro de banco de dados", str(exc))
            dlg.destroy()
            self._load()

        ctk.CTkButton(dlg, text="Confirmar Registro", fg_color=ACCENT_COLOR,
                      font=ctk.CTkFont(weight="bold"), command=_save).pack(pady=24)

    # ── history dialog ─────────────────────────────────────────────────────────

    def _open_history_dialog(self, filamento_id: int, label: str):
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Histórico — {label}")
        dlg.geometry("600x400")
        dlg.after(100, dlg.grab_set)

        ctk.CTkLabel(dlg, text=f"Histórico de Impressões: {label}",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(
            """SELECT data_impressao, peso_peca_g, peso_desperdicio_g, status, observacao
               FROM historico_impressao WHERE filamento_id=?
               ORDER BY id DESC""",
            (filamento_id,),
        ).fetchall()
        conn.close()

        if not rows:
            ctk.CTkLabel(scroll, text="Nenhum registro encontrado.", text_color="gray").pack(pady=20)
            return

        for (data, peca, waste, status, obs) in rows:
            color = "#2b7a4b" if status == "Sucesso" else "#d64545"
            f = ctk.CTkFrame(scroll, fg_color="#2a2a2a", corner_radius=8)
            f.pack(fill="x", pady=3)
            ctk.CTkLabel(f, text=f"  {data[:16]}  |  Peça: {peca:.1f}g  |  Desperdício: {waste:.1f}g",
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=5, pady=6)
            ctk.CTkLabel(f, text=f"  {status}  ", fg_color=color, corner_radius=4,
                         text_color="white", font=ctk.CTkFont(size=11, weight="bold")).pack(side="right", padx=8, pady=6)
            if obs:
                ctk.CTkLabel(f, text=f"  ↳ {obs}", text_color="gray",
                             font=ctk.CTkFont(size=11)).pack(anchor="w", padx=5)

    # ── edit dialog ────────────────────────────────────────────────────────────

    def _edit_item(self, row):
        fid, marca, cor, preco = row[0], row[1], row[3], row[8]
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Editar {marca} {cor}")
        dlg.geometry("360x220")
        dlg.after(100, dlg.grab_set)

        ctk.CTkLabel(dlg, text="Somar Peso Extra (KG)", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 3))
        add_peso = ctk.StringVar(value="0.0")
        ctk.CTkEntry(dlg, textvariable=add_peso).pack()

        ctk.CTkLabel(dlg, text="Atualizar Preço do Rolo ($)", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 3))
        novo_preco = ctk.StringVar(value=str(preco or 0.0))
        ctk.CTkEntry(dlg, textvariable=novo_preco).pack()

        def _save():
            try:
                p_add = float(add_peso.get().replace(",", "."))
                pr    = float(novo_preco.get().replace(",", "."))
            except ValueError:
                return messagebox.showerror("Erro", "Valores numéricos inválidos.")
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute(
                "UPDATE filamentos SET peso_inicial=peso_inicial+?, peso_atual=peso_atual+?, preco_rolo=? WHERE id=?",
                (p_add, p_add, pr, fid),
            )
            conn.commit(); conn.close()
            dlg.destroy(); self._load()

        ctk.CTkButton(dlg, text="Salvar", fg_color=ACCENT_COLOR, command=_save).pack(pady=20)

    def _delete_item(self, fid: int):
        if messagebox.askyesno("Confirmar", "Remover este filamento? O histórico de impressões também será apagado."):
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("DELETE FROM historico_impressao WHERE filamento_id=?", (fid,))
            conn.execute("DELETE FROM filamentos WHERE id=?", (fid,))
            conn.commit(); conn.close()
            self._load()

    # ── render list ────────────────────────────────────────────────────────────

    def _load(self):
        for w in self.list_frame.winfo_children(): w.destroy()
        for w in self.alert_frame.winfo_children(): w.destroy()

        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(
            """SELECT id, marca, material, cor, peso_inicial, peso_atual,
                      caminho_foto, link_compra, preco_rolo, caminho_nota_fiscal
               FROM filamentos ORDER BY id DESC"""
        ).fetchall()
        conn.close()

        self.list_frame.images = []
        self.list_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        col = 0; r_idx = 0

        for row in rows:
            fid = row[0]
            marca, material, cor = row[1], row[2], row[3]
            peso_ini, peso_atual = row[4], row[5]
            foto_stored, link, preco_rolo, nf_stored = row[6], row[7], row[8], row[9]

            # Low-stock alert banner
            if peso_atual < peso_ini * 0.2:
                af = ctk.CTkFrame(self.alert_frame, fg_color="#4a1515", corner_radius=8)
                af.pack(fill="x", pady=2)
                ctk.CTkLabel(
                    af, text=f"ALERTA: {marca} {material} ({cor}) no fim!",
                    text_color="white", font=ctk.CTkFont(weight="bold", size=11),
                ).pack(side="left", padx=10, pady=2)
                if link:
                    ctk.CTkButton(af, text="Comprar", fg_color="#d64545", height=20,
                                  command=lambda u=link: open_url(u)).pack(side="right", padx=10, pady=2)

            card = ModernCard(self.list_frame)
            card.grid(row=r_idx, column=col, sticky="nsew", padx=5, pady=5)

            # ── action row ────────────────────────────────────────────────────
            top_bar = ctk.CTkFrame(card, fg_color="transparent")
            top_bar.pack(fill="x", padx=5, pady=2)

            ctk.CTkButton(top_bar, text="✕", width=22, height=22,
                          fg_color="transparent", text_color="#d64545",
                          command=lambda i=fid: self._delete_item(i)).pack(side="right")
            ctk.CTkButton(top_bar, text="✎", width=22, height=22,
                          fg_color="transparent", text_color="#ccc",
                          command=lambda r=row: self._edit_item(r)).pack(side="right")

            # Invoice button
            nf_label = "NF ✓" if nf_stored else "NF"
            nf_color  = "#2b7a4b" if nf_stored else "#444"
            if nf_stored:
                ctk.CTkButton(
                    top_bar, text=nf_label, width=38, height=22,
                    fg_color=nf_color, hover_color="#1d5c36",
                    command=lambda fn=nf_stored: self._open_invoice(fn),
                ).pack(side="left", padx=(0, 2))
            else:
                ctk.CTkButton(
                    top_bar, text="NF", width=38, height=22,
                    fg_color=nf_color, hover_color="#555",
                    command=lambda i=fid: self._attach_invoice(i),
                ).pack(side="left", padx=(0, 2))

            if link:
                ctk.CTkButton(top_bar, text="Link", width=36, height=22,
                              fg_color="transparent", text_color=ACCENT_COLOR,
                              command=lambda u=link: open_url(u)).pack(side="left")

            # ── image ─────────────────────────────────────────────────────────
            full_foto = resolve_media_path(foto_stored)
            img_ctk = load_and_resize_image(full_foto, size=(80, 80))
            if img_ctk:
                self.list_frame.images.append(img_ctk)
                ctk.CTkLabel(card, text="", image=img_ctk).pack(pady=2)
            else:
                ph = ctk.CTkFrame(card, width=80, height=80, corner_radius=5, fg_color="#333")
                ph.pack(pady=2)
                ctk.CTkLabel(ph, text="S/ Img").place(relx=0.5, rely=0.5, anchor="center")

            ctk.CTkLabel(card, text=f"{marca} {material}",
                         font=ctk.CTkFont(weight="bold", size=14)).pack()
            ctk.CTkLabel(card, text=cor, text_color="gray", font=ctk.CTkFont(size=11)).pack()

            preco_rolo = preco_rolo or 0.0
            if preco_rolo > 0:
                ctk.CTkLabel(card, text=f"R$ {preco_rolo:.2f}",
                             text_color="#aaa", font=ctk.CTkFont(size=11)).pack()

            prog = peso_atual / peso_ini if peso_ini > 0 else 0
            pb = ctk.CTkProgressBar(card, width=120, height=5,
                                    progress_color=ACCENT_COLOR if prog > 0.2 else "#d64545")
            pb.pack(pady=5)
            pb.set(max(0.0, min(1.0, prog)))
            ctk.CTkLabel(card, text=f"{peso_atual:.2f} kg restante",
                         font=ctk.CTkFont(size=11)).pack(pady=(0, 3))

            # Telemetry buttons
            btn_row = ctk.CTkFrame(card, fg_color="transparent")
            btn_row.pack(fill="x", padx=8, pady=(0, 8))
            lbl = f"{marca} {cor}"
            ctk.CTkButton(
                btn_row, text="📊 Registrar Impressão", height=22,
                fg_color="#1d303b", hover_color="#2a4560", font=ctk.CTkFont(size=11),
                command=lambda i=fid, l=lbl: self._open_telemetry_dialog(i, l),
            ).pack(side="left", fill="x", expand=True, padx=(0, 2))
            ctk.CTkButton(
                btn_row, text="📋", width=28, height=22,
                fg_color="#2a2a2a", hover_color="#3a3a3a",
                command=lambda i=fid, l=lbl: self._open_history_dialog(i, l),
            ).pack(side="right")

            col += 1
            if col > 3:
                col = 0; r_idx += 1


# ==========================================
# TAB – ACERVO
# ==========================================

class TabAcervo(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(side="top", fill="x", padx=20, pady=(10, 0))

        self.form_card = ModernCard(top)
        self.form_card.pack(side="top", fill="x", pady=(0, 20))
        self.form_card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(self.form_card, text="Registrar Peça no Acervo",
                     font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=2, pady=(15, 10))

        self.nome_var = ctk.StringVar()
        f1 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f1.grid(row=1, column=0, padx=15, pady=5, sticky="ew")
        ctk.CTkLabel(f1, text="Nome da Peça", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f1, textvariable=self.nome_var, placeholder_text="Ex: Suporte Fone").pack(fill="x")

        self.pos_var = ctk.StringVar()
        f4 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f4.grid(row=1, column=1, padx=15, pady=5, sticky="ew")
        ctk.CTkLabel(f4, text="Processos de Acabamento (Opcional)", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f4, textvariable=self.pos_var, placeholder_text="Ex: Lixamento, Pintura").pack(fill="x")

        files_frame = ctk.CTkFrame(self.form_card, fg_color="transparent")
        files_frame.grid(row=2, column=0, columnspan=2, padx=15, pady=10, sticky="ew")
        files_frame.grid_columnconfigure((0, 1), weight=1)

        self._new_foto_filename = None
        self._arquivo_3d_path   = None

        self.btn_foto = ctk.CTkButton(files_frame, text="Foto da Peça Pronta",
                                      fg_color="#333", hover_color="#444", command=self._select_photo)
        self.btn_foto.grid(row=0, column=0, padx=5, sticky="ew")

        self.btn_3d = ctk.CTkButton(files_frame, text="Anexar Arquivo 3D (STL/3MF)",
                                    fg_color="#333", hover_color="#444", command=self._select_3d)
        self.btn_3d.grid(row=0, column=1, padx=5, sticky="ew")

        self.filamentos_selecionados = []
        self.fil_frame = ctk.CTkFrame(self.form_card, fg_color=APP_BG_COLOR,
                                      corner_radius=10, border_width=1, border_color=BORDER_COLOR)
        self.fil_frame.grid(row=3, column=0, columnspan=2, padx=15, pady=10, sticky="nsew")
        ctk.CTkLabel(self.fil_frame, text="Filamentos Utilizados", text_color="gray").pack(pady=5)

        self.f_list_ui = ctk.CTkFrame(self.fil_frame, fg_color="transparent")
        self.f_list_ui.pack(fill="x", padx=10, pady=5)

        add_row = ctk.CTkFrame(self.fil_frame, fg_color="transparent")
        add_row.pack(fill="x", padx=10, pady=5)

        self.filamentos_dict = self._get_filamentos()
        self.f_combo = ctk.CTkComboBox(
            add_row, values=list(self.filamentos_dict.keys()) if self.filamentos_dict else ["Nenhum"],
        )
        self.f_combo.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(add_row, text="Adicionar Filamento", width=150,
                      fg_color="#333", command=self._add_filamento_ui).pack(side="right")

        ctk.CTkButton(self.form_card, text="Salvar Peça Completa", height=40,
                      font=ctk.CTkFont(weight="bold"), fg_color=ACCENT_COLOR,
                      command=self._save_peca).grid(row=4, column=0, columnspan=2,
                                                    padx=15, pady=(15, 15), sticky="ew")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 20))

        self._load()

    def _get_filamentos(self):
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("SELECT id, marca, material, cor FROM filamentos").fetchall()
        conn.close()
        return {f"{r[1]} {r[2]} ({r[3]})": r[0] for r in rows}

    def _select_photo(self):
        path = filedialog.askopenfilename(filetypes=[("Imagens", "*.jpg *.jpeg *.png")])
        if not path:
            return
        try:
            self._new_foto_filename = copy_to_media(path)
            self.btn_foto.configure(text="Foto Anexada ✓", fg_color="#2b7a4b")
        except RuntimeError as exc:
            messagebox.showerror("Erro de cópia", str(exc))

    def _select_3d(self):
        path = filedialog.askopenfilename(filetypes=[("3D Files", "*.3mf *.stl *.obj")])
        if path:
            self._arquivo_3d_path = path
            self.btn_3d.configure(text=f"3D: {os.path.basename(path)}", fg_color="#2b7a4b")

    def _add_filamento_ui(self):
        f_name = self.f_combo.get()
        if f_name not in self.filamentos_dict:
            return
        f_id = self.filamentos_dict[f_name]
        row_ui = ctk.CTkFrame(self.f_list_ui, fg_color="#333", corner_radius=5)
        row_ui.pack(fill="x", pady=2)
        ctk.CTkLabel(row_ui, text=f_name).pack(side="left", padx=10)
        ctk.CTkButton(row_ui, text="✕", width=30, fg_color="#d64545", hover_color="#8b0000",
                      command=lambda r=row_ui: self._remove_f_ui(r)).pack(side="right", padx=5)
        p_var = ctk.StringVar()
        ctk.CTkEntry(row_ui, textvariable=p_var, placeholder_text="Gasto (g) ex: 120",
                     width=150).pack(side="right", padx=10)
        self.filamentos_selecionados.append({"id": f_id, "ui": row_ui, "peso_var": p_var})

    def _remove_f_ui(self, row_ui):
        row_ui.destroy()
        self.filamentos_selecionados = [i for i in self.filamentos_selecionados if i["ui"] != row_ui]

    def _save_peca(self):
        nome = self.nome_var.get()
        if not nome:
            return messagebox.showerror("Erro", "Nome da peça é obrigatório.")
        if not self.filamentos_selecionados:
            return messagebox.showerror("Erro", "Adicione pelo menos um filamento.")

        pesos = []
        for item in self.filamentos_selecionados:
            try:
                p_g  = float(item["peso_var"].get().replace(",", "."))
                pesos.append((item["id"], p_g / 1000.0))
            except ValueError:
                return messagebox.showerror("Erro", "Pesos dos filamentos devem ser numéricos (gramas).")

        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        # Check sufficiency
        for f_id, p_kg in pesos:
            atual = c.execute("SELECT peso_atual FROM filamentos WHERE id=?", (f_id,)).fetchone()[0]
            if atual < p_kg:
                if not messagebox.askyesno("Aviso", "Filamento insuficiente. Salvar mesmo assim?"):
                    conn.close(); return

        c.execute(
            "INSERT INTO acervo (nome_peca, caminho_foto, arquivo_3d, pos_processamento, data_registro) VALUES (?,?,?,?,?)",
            (nome, self._new_foto_filename, self._arquivo_3d_path,
             self.pos_var.get(), datetime.date.today().isoformat()),
        )
        acervo_id = c.lastrowid
        agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO acervo_impressoes (acervo_id, data_impressao) VALUES (?,?)", (acervo_id, agora))

        for f_id, p_kg in pesos:
            c.execute("INSERT INTO acervo_filamentos (acervo_id, filamento_id, peso_gasto) VALUES (?,?,?)",
                      (acervo_id, f_id, p_kg))
            atual = c.execute("SELECT peso_atual FROM filamentos WHERE id=?", (f_id,)).fetchone()[0]
            c.execute("UPDATE filamentos SET peso_atual=? WHERE id=?", (max(0, atual - p_kg), f_id))

        conn.commit(); conn.close()

        self.nome_var.set(""); self.pos_var.set("")
        self._new_foto_filename = None; self._arquivo_3d_path = None
        self.btn_foto.configure(text="Foto da Peça Pronta", fg_color="#333")
        self.btn_3d.configure(text="Anexar Arquivo 3D (STL/3MF)", fg_color="#333")
        for item in self.filamentos_selecionados: item["ui"].destroy()
        self.filamentos_selecionados = []
        self._load()

    def _delete_item(self, aid: int):
        if messagebox.askyesno("Confirmar", "Remover esta peça?"):
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("DELETE FROM acervo_impressoes WHERE acervo_id=?", (aid,))
            conn.execute("DELETE FROM acervo_filamentos WHERE acervo_id=?", (aid,))
            conn.execute("DELETE FROM acervo WHERE id=?", (aid,))
            conn.commit(); conn.close()
            self._load()

    def _add_impressao(self, acervo_id: int):
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        fils = c.execute("SELECT filamento_id, peso_gasto FROM acervo_filamentos WHERE acervo_id=?",
                         (acervo_id,)).fetchall()
        for f_id, p_kg in fils:
            atual = c.execute("SELECT peso_atual FROM filamentos WHERE id=?", (f_id,)).fetchone()[0]
            if atual < p_kg:
                if not messagebox.askyesno("Aviso", "Filamento insuficiente. Registrar mesmo assim?"):
                    conn.close(); return
            c.execute("UPDATE filamentos SET peso_atual=? WHERE id=?", (max(0, atual - p_kg), f_id))
        agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO acervo_impressoes (acervo_id, data_impressao) VALUES (?,?)", (acervo_id, agora))
        conn.commit(); conn.close()
        self._load()

    def _remove_impressao(self, acervo_id: int):
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        ult = c.execute("SELECT id FROM acervo_impressoes WHERE acervo_id=? ORDER BY id DESC LIMIT 1",
                        (acervo_id,)).fetchone()
        if not ult:
            conn.close(); return
        if not messagebox.askyesno("Confirmar", "Remover última impressão e devolver filamento?"):
            conn.close(); return
        fils = c.execute("SELECT filamento_id, peso_gasto FROM acervo_filamentos WHERE acervo_id=?",
                         (acervo_id,)).fetchall()
        for f_id, p_kg in fils:
            atual = c.execute("SELECT peso_atual FROM filamentos WHERE id=?", (f_id,)).fetchone()[0]
            c.execute("UPDATE filamentos SET peso_atual=? WHERE id=?", (atual + p_kg, f_id))
        c.execute("DELETE FROM acervo_impressoes WHERE id=?", (ult[0],))
        conn.commit(); conn.close()
        self._load()

    def _load(self):
        for w in self.list_frame.winfo_children(): w.destroy()
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(
            "SELECT id, nome_peca, pos_processamento, caminho_foto, data_registro, arquivo_3d FROM acervo ORDER BY id DESC"
        ).fetchall()
        self.list_frame.images = []

        for r in rows:
            card = ModernCard(self.list_frame)
            card.pack(fill="x", padx=10, pady=5)

            top_bar = ctk.CTkFrame(card, fg_color="transparent")
            top_bar.pack(fill="x", padx=5)

            ctk.CTkButton(top_bar, text="✕", width=30, height=20, fg_color="transparent",
                          text_color="#d64545", command=lambda i=r[0]: self._delete_item(i)).pack(side="right")
            count = conn.execute("SELECT COUNT(*) FROM acervo_impressoes WHERE acervo_id=?", (r[0],)).fetchone()[0]
            ctk.CTkButton(top_bar, text="+1", width=40, height=20, fg_color="#2b7a4b",
                          command=lambda i=r[0]: self._add_impressao(i)).pack(side="left", padx=(0, 5))
            ctk.CTkLabel(top_bar, text=f"Total Impressões: {count}",
                         font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
            if count > 0:
                ctk.CTkButton(top_bar, text="-1", width=40, height=20, fg_color="#d64545",
                              command=lambda i=r[0]: self._remove_impressao(i)).pack(side="left")

            body = ctk.CTkFrame(card, fg_color="transparent")
            body.pack(fill="x", expand=True)

            full_foto = resolve_media_path(r[3])
            img_ctk = load_and_resize_image(full_foto, size=(80, 80))
            if img_ctk:
                self.list_frame.images.append(img_ctk)
                ctk.CTkLabel(body, text="", image=img_ctk).pack(side="left", padx=15, pady=(0, 10))
            else:
                ph = ctk.CTkFrame(body, width=80, height=80, corner_radius=5, fg_color="#333")
                ph.pack(side="left", padx=15, pady=(0, 10))

            info = ctk.CTkFrame(body, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(info, text=r[1], font=ctk.CTkFont(weight="bold", size=18)).pack(anchor="w")

            fils = conn.execute(
                """SELECT f.marca, f.cor, af.peso_gasto FROM acervo_filamentos af
                   JOIN filamentos f ON af.filamento_id = f.id WHERE af.acervo_id=?""",
                (r[0],),
            ).fetchall()
            fils_txt = " + ".join(f"{f[0]} {f[1]} ({f[2]*1000:.0f}g)" for f in fils) or "Nenhum"
            ctk.CTkLabel(info, text=f"Materiais: {fils_txt}", text_color="#aaa").pack(anchor="w")
            ctk.CTkLabel(info, text=f"Pós: {r[2] or 'Nenhum'}", text_color="gray").pack(anchor="w")

            last = conn.execute(
                "SELECT data_impressao FROM acervo_impressoes WHERE acervo_id=? ORDER BY id DESC LIMIT 1", (r[0],)
            ).fetchone()
            if last:
                ctk.CTkLabel(info, text=f"Última impressão: {last[0]}", text_color="#aaa").pack(anchor="w")
            if r[5]:
                ctk.CTkLabel(info, text=f"Arquivo 3D: {os.path.basename(r[5])}",
                             text_color=ACCENT_COLOR).pack(anchor="w")

        conn.close()


# ==========================================
# TAB – ALMOXARIFADO
# ==========================================

class TabAlmoxarifado(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(side="top", fill="x", padx=20, pady=(10, 0))

        form = ModernCard(top)
        form.pack(side="top", fill="x", pady=(0, 20))
        ctk.CTkLabel(form, text="Novo Item de Almoxarifado",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 15))

        self.nome_var   = ctk.StringVar()
        self.cat_var    = ctk.StringVar(value="Ferramenta")
        self.status_var = ctk.StringVar(value="Em estoque")
        self.link_var   = ctk.StringVar()
        self.preco_var  = ctk.StringVar()
        self._new_foto_filename = None

        row1 = ctk.CTkFrame(form, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=5)
        row1.grid_columnconfigure((0, 1, 2), weight=1)

        def lrow(parent, col, label, widget_fn):
            f = ctk.CTkFrame(parent, fg_color="transparent"); f.grid(row=0, column=col, sticky="ew", padx=5)
            ctk.CTkLabel(f, text=label, text_color="gray").pack(anchor="w")
            widget_fn(f)

        lrow(row1, 0, "Nome do Item",
             lambda f: ctk.CTkEntry(f, textvariable=self.nome_var, placeholder_text="Ex: Lixa d'água 400").pack(fill="x"))
        lrow(row1, 1, "Categoria",
             lambda f: ctk.CTkOptionMenu(f, variable=self.cat_var, values=["Ferramenta","Insumo","Peça Reposição"]).pack(fill="x"))
        lrow(row1, 2, "Situação",
             lambda f: ctk.CTkOptionMenu(f, variable=self.status_var, values=["Em estoque","Comprar","Falta"]).pack(fill="x"))

        row2 = ctk.CTkFrame(form, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=5)
        row2.grid_columnconfigure((0, 1, 2), weight=1)

        lrow(row2, 0, "Link de Compra",
             lambda f: ctk.CTkEntry(f, textvariable=self.link_var).pack(fill="x"))
        lrow(row2, 1, "Último Valor ($)",
             lambda f: ctk.CTkEntry(f, textvariable=self.preco_var, placeholder_text="25.50").pack(fill="x"))

        f6 = ctk.CTkFrame(row2, fg_color="transparent"); f6.grid(row=0, column=2, sticky="ew", padx=5)
        ctk.CTkLabel(f6, text="Foto (Opcional)", text_color="gray").pack(anchor="w")
        self.btn_foto = ctk.CTkButton(f6, text="Selecionar", fg_color="#333", hover_color="#444", command=self._select_photo)
        self.btn_foto.pack(fill="x")

        ctk.CTkButton(form, text="Salvar Item", height=40,
                      font=ctk.CTkFont(weight="bold"), fg_color=ACCENT_COLOR,
                      command=self._save).pack(fill="x", padx=25, pady=(15, 20))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 20))

        panel = ModernCard(scroll)
        panel.pack(fill="both", expand=True, pady=(0, 20))
        ctk.CTkLabel(panel, text="Inventário Geral",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 10))

        self.list_items = ctk.CTkFrame(panel, fg_color="transparent")
        self.list_items.pack(fill="both", expand=True, padx=10, pady=10)

        self._load()

    def _select_photo(self):
        path = filedialog.askopenfilename()
        if not path:
            return
        try:
            self._new_foto_filename = copy_to_media(path)
            self.btn_foto.configure(text="Anexado ✓", fg_color="#2b7a4b")
        except RuntimeError as exc:
            messagebox.showerror("Erro de cópia", str(exc))

    def _save(self):
        nome = self.nome_var.get()
        if not nome:
            return messagebox.showerror("Erro", "Nome é obrigatório.")
        preco = 0.0
        if self.preco_var.get():
            try:
                preco = float(self.preco_var.get().replace(",", "."))
            except ValueError:
                return messagebox.showerror("Erro", "Preço deve ser numérico.")
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO ferramentas_insumos (nome, categoria, quantidade_status, caminho_foto, link_compra, ultimo_valor) VALUES (?,?,?,?,?,?)",
            (nome, self.cat_var.get(), self.status_var.get(), self._new_foto_filename, self.link_var.get(), preco),
        )
        conn.commit(); conn.close()
        self.nome_var.set(""); self.link_var.set(""); self.preco_var.set("")
        self._new_foto_filename = None
        self.btn_foto.configure(text="Selecionar", fg_color="#333")
        self._load()

    def _delete(self, iid: int):
        if messagebox.askyesno("Confirmar", "Remover este item?"):
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("DELETE FROM ferramentas_insumos WHERE id=?", (iid,))
            conn.commit(); conn.close()
            self._load()

    def _load(self):
        for w in self.list_items.winfo_children(): w.destroy()
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(
            "SELECT id, nome, categoria, quantidade_status, caminho_foto, link_compra, ultimo_valor FROM ferramentas_insumos ORDER BY categoria, nome"
        ).fetchall()
        conn.close()
        self.list_items.images = []

        for r in rows:
            danger = r[3] in ("Comprar", "Falta")
            f = ctk.CTkFrame(self.list_items, fg_color="#333", corner_radius=8)
            f.pack(fill="x", pady=4)

            ctk.CTkButton(f, text="✕", width=30, height=25, fg_color="transparent",
                          text_color="#d64545", command=lambda i=r[0]: self._delete(i)).pack(side="right", padx=5)

            full_foto = resolve_media_path(r[4])
            img_ctk = load_and_resize_image(full_foto, size=(40, 40))
            if img_ctk:
                self.list_items.images.append(img_ctk)
                ctk.CTkLabel(f, text="", image=img_ctk).pack(side="left", padx=(10, 5), pady=5)
            else:
                ctk.CTkFrame(f, width=40, height=40, fg_color="#222").pack(side="left", padx=(10, 5), pady=5)

            info = ctk.CTkFrame(f, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(info, text=r[1], font=ctk.CTkFont(weight="bold")).pack(anchor="w")
            badge = ctk.CTkFrame(info, fg_color="#8b0000" if danger else "#444", corner_radius=5)
            badge.pack(anchor="w", pady=(2, 0))
            ctk.CTkLabel(badge, text=f" {r[2]} | {r[3]} ", text_color="white",
                         font=ctk.CTkFont(size=10)).pack()

            if r[6] and r[6] > 0:
                ctk.CTkLabel(f, text=f"R$ {r[6]:.2f}", text_color="#ccc").pack(side="right", padx=10)
            if r[5]:
                ctk.CTkButton(f, text="Comprar", width=80, height=25, border_width=1,
                              border_color=ACCENT_COLOR, fg_color="transparent",
                              text_color=ACCENT_COLOR, hover_color="#1d303b",
                              command=lambda l=r[5]: open_url(l)).pack(side="right", padx=10)


# ==========================================
# TAB – MANUTENÇÃO
# ==========================================

class TabManutencao(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="Rotinas de Manutenção",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 20))
        self._load()

    def _mark_done(self, tid: int):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("UPDATE manutencao SET ultima_execucao=? WHERE id=?",
                     (datetime.date.today().isoformat(), tid))
        conn.commit(); conn.close()
        self._load()

    def _load(self):
        for w in self.scroll.winfo_children(): w.destroy()
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("SELECT id, tarefa, guia_instrucao, intervalo_dias, ultima_execucao, link_tutorial FROM manutencao").fetchall()
        conn.close()

        hoje = datetime.date.today()
        for row in rows:
            t_id, tarefa, guia, inv, ult, link = row
            try: data_ult = datetime.date.fromisoformat(ult)
            except Exception: data_ult = hoje
            dias = (hoje - data_ult).days
            atrasado = dias >= inv

            card = ModernCard(self.scroll, border_color="#d64545" if atrasado else BORDER_COLOR,
                              border_width=2 if atrasado else 1)
            card.pack(fill="x", pady=8)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=15, pady=(15, 5))
            ctk.CTkLabel(top, text=tarefa, font=ctk.CTkFont(weight="bold", size=16),
                         text_color="#d64545" if atrasado else "white").pack(side="left")
            ctk.CTkLabel(top, text=f"Última: {ult} ({dias} dias atrás)",
                         text_color="gray").pack(side="left", padx=10)
            ctk.CTkButton(top, text="Feito Hoje", width=100, fg_color="#2b7a4b", hover_color="#1d5c36",
                          command=lambda t=t_id: self._mark_done(t)).pack(side="right")

            mid = ctk.CTkFrame(card, fg_color="transparent")
            mid.pack(fill="x", padx=15, pady=(5, 15))
            ctk.CTkLabel(mid, text=guia, wraplength=700, justify="left",
                         text_color="#ccc").pack(side="left", fill="x", expand=True)
            if link:
                ctk.CTkButton(mid, text="Ver Tutorial", fg_color="transparent",
                              border_width=1, border_color=BORDER_COLOR, width=100,
                              hover_color="#333", command=lambda l=link: open_url(l)).pack(side="right", padx=(10, 0))


# ==========================================
# TAB – PEDIDOS (Kanban)
# ==========================================

class TabPedidos(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.form_visible = False

        self.toggle_btn = ctk.CTkButton(self, text="▶ Exibir Formulário de Pedido",
                                        fg_color="transparent", text_color=ACCENT_COLOR,
                                        anchor="w", hover_color="#222", command=self._toggle_form)
        self.toggle_btn.pack(side="top", fill="x", padx=20, pady=0)

        self.form_card = ModernCard(self, border_width=0)

        f1 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f1.pack(fill="x", padx=10, pady=(5, 0))
        f1.grid_columnconfigure((0, 1, 2), weight=1)

        def field(parent, col, label, var):
            fc = ctk.CTkFrame(parent, fg_color="transparent"); fc.grid(row=0, column=col, padx=2, sticky="ew")
            ctk.CTkLabel(fc, text=f"{label}:", font=ctk.CTkFont(size=11)).pack(side="left", padx=2)
            ctk.CTkEntry(fc, textvariable=var, height=25).pack(side="left", fill="x", expand=True, padx=2)

        self.cliente_var = ctk.StringVar()
        self.data_var    = ctk.StringVar()
        self.valor_var   = ctk.StringVar()
        field(f1, 0, "Cliente", self.cliente_var)
        field(f1, 1, "Data Entrega", self.data_var)
        field(f1, 2, "Valor (R$)", self.valor_var)

        f2 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f2.pack(fill="x", padx=10, pady=(5, 5))
        ctk.CTkLabel(f2, text="Peça:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 2))
        self.acervo_dict = self._get_acervo()
        self.peca_combo = ctk.CTkComboBox(
            f2, values=list(self.acervo_dict.keys()) if self.acervo_dict else ["Nenhuma Peça"], height=25,
        )
        self.peca_combo.pack(side="left", fill="x", expand=True, padx=2)
        ctk.CTkButton(f2, text="+ Add", width=50, height=25, fg_color="#333",
                      command=self._add_peca_ui).pack(side="left", padx=5)
        ctk.CTkButton(f2, text="Salvar Pedido", width=110, height=25,
                      font=ctk.CTkFont(weight="bold"), fg_color=ACCENT_COLOR,
                      command=self._criar_pedido).pack(side="right", padx=(10, 4))

        self.pecas_selecionadas = []
        self.pecas_ui_frame = ctk.CTkFrame(self.form_card, fg_color="transparent")
        self.pecas_ui_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.kanban = ctk.CTkFrame(self, fg_color="transparent")
        self.kanban.pack(side="top", fill="both", expand=True, padx=20, pady=(5, 20))
        self.kanban.grid_columnconfigure((0, 1, 2), weight=1)
        self.kanban.grid_rowconfigure(0, weight=1)

        self.col_fazer       = self._make_col(0, "A Fazer")
        self.col_imp         = self._make_col(1, "Imprimindo")
        self.col_encaminhado = self._make_col(2, "Enviado")

        self._load()

    def _toggle_form(self):
        if self.form_visible:
            self.form_card.pack_forget()
            self.toggle_btn.configure(text="▶ Exibir Formulário de Pedido")
        else:
            self.form_card.pack(side="top", fill="x", padx=20, pady=(0, 5), before=self.kanban)
            self.toggle_btn.configure(text="▼ Ocultar Formulário de Pedido")
        self.form_visible = not self.form_visible

    def _make_col(self, col, title):
        f = ctk.CTkFrame(self.kanban, fg_color="#1a1a1a", corner_radius=10, border_width=1, border_color="#333")
        f.grid(row=0, column=col, sticky="nsew", padx=5)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(weight="bold", size=14), pady=5).pack()
        s = ctk.CTkScrollableFrame(f, fg_color="transparent")
        s.pack(fill="both", expand=True)
        return s

    def _get_acervo(self):
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("SELECT id, nome_peca FROM acervo").fetchall()
        conn.close()
        return {r[1]: r[0] for r in rows}

    def _add_peca_ui(self):
        p = self.peca_combo.get()
        if not p or p not in self.acervo_dict: return
        row_ui = ctk.CTkFrame(self.pecas_ui_frame, fg_color="#333", corner_radius=3)
        row_ui.pack(side="left", padx=2)
        ctk.CTkLabel(row_ui, text=p, font=ctk.CTkFont(size=11)).pack(side="left", padx=5)
        ctk.CTkButton(row_ui, text="✕", width=15, height=15, fg_color="transparent",
                      text_color="#d64545", command=lambda r=row_ui: self._rem_peca(r)).pack(side="right")
        self.pecas_selecionadas.append({"id": self.acervo_dict[p], "ui": row_ui})

    def _rem_peca(self, r):
        r.destroy()
        self.pecas_selecionadas = [i for i in self.pecas_selecionadas if i["ui"] != r]

    def _criar_pedido(self):
        if not self.cliente_var.get() or not self.pecas_selecionadas:
            return messagebox.showerror("Erro", "Adicione cliente e pelo menos uma peça.")
        try: v = float(self.valor_var.get().replace(",", ".")) if self.valor_var.get() else 0.0
        except: v = 0.0
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("INSERT INTO pedidos_v2 (nome_cliente, data_entrega, valor_cobrado, status) VALUES (?,?,?,?)",
                  (self.cliente_var.get(), self.data_var.get(), v, "A Fazer"))
        pid = c.lastrowid
        for item in self.pecas_selecionadas:
            c.execute("INSERT INTO pedidos_itens (pedido_id, acervo_id) VALUES (?,?)", (pid, item["id"]))
            item["ui"].destroy()
        conn.commit(); conn.close()
        self.pecas_selecionadas = []
        self.cliente_var.set(""); self.valor_var.set(""); self.data_var.set("")
        self._load()

    def _move(self, pid: int, status: str):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("UPDATE pedidos_v2 SET status=? WHERE id=?", (status, pid))
        conn.commit(); conn.close()
        self._load()

    def _delete(self, pid: int):
        if messagebox.askyesno("Confirmar", "Excluir este pedido?"):
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("DELETE FROM pedidos_itens WHERE pedido_id=?", (pid,))
            conn.execute("DELETE FROM pedidos_v2 WHERE id=?", (pid,))
            conn.commit(); conn.close()
            self._load()

    def _load(self):
        for col in (self.col_fazer, self.col_imp, self.col_encaminhado):
            for w in col.winfo_children(): w.destroy()
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("SELECT id, nome_cliente, data_entrega, valor_cobrado, status FROM pedidos_v2").fetchall()

        for p_id, cliente, data, valor, status in rows:
            parent = self.col_fazer if status == "A Fazer" else self.col_imp if status == "Imprimindo" else self.col_encaminhado
            if status == "Encaminhado":
                card = ModernCard(parent, border_color="#d64545", border_width=2)
                card.configure(fg_color="#3d1818")
            elif status == "Entregue":
                card = ModernCard(parent, border_color="#2b7a4b", border_width=2)
                card.configure(fg_color="#1c3b22")
            else:
                card = ModernCard(parent, border_width=0)
            card.pack(fill="x", padx=5, pady=3)

            ctk.CTkLabel(card, text=f"  {cliente}", font=ctk.CTkFont(weight="bold", size=13)).pack(pady=(3, 0))
            for (nome_p,) in conn.execute(
                "SELECT a.nome_peca FROM pedidos_itens pi JOIN acervo a ON pi.acervo_id=a.id WHERE pi.pedido_id=?",
                (p_id,),
            ).fetchall():
                ctk.CTkLabel(card, text=f"  - {nome_p}", text_color="#ccc", font=ctk.CTkFont(size=11)).pack(anchor="w")

            if data:
                ctk.CTkLabel(card, text=f"  {data}", text_color="gray", font=ctk.CTkFont(size=10)).pack()
            if valor and valor > 0:
                ctk.CTkLabel(card, text=f"R$ {valor:.2f}", text_color=ACCENT_COLOR,
                             font=ctk.CTkFont(size=11)).pack()

            btns = ctk.CTkFrame(card, fg_color="transparent")
            btns.pack(fill="x", pady=2)
            if status in ("Imprimindo", "Encaminhado", "Entregue"):
                prev = {"Imprimindo": "A Fazer", "Encaminhado": "Imprimindo", "Entregue": "Encaminhado"}[status]
                ctk.CTkButton(btns, text="<", width=25, height=20,
                              command=lambda i=p_id, s=prev: self._move(i, s)).pack(side="left", padx=2)
            ctk.CTkButton(btns, text="✕", width=25, height=20, fg_color="#d64545", hover_color="#8b0000",
                          command=lambda i=p_id: self._delete(i)).pack(side="left", expand=True)
            if status in ("A Fazer", "Imprimindo"):
                nxt = "Imprimindo" if status == "A Fazer" else "Encaminhado"
                ctk.CTkButton(btns, text=">", width=25, height=20,
                              command=lambda i=p_id, s=nxt: self._move(i, s)).pack(side="right", padx=2)
            elif status == "Encaminhado":
                ctk.CTkButton(btns, text="✔ Entregue", width=70, height=20, fg_color="#2b7a4b",
                              command=lambda i=p_id: self._move(i, "Entregue")).pack(side="right", padx=2)

        conn.close()


# ==========================================
# TAB – FINANCEIRO
# ==========================================

class TabFinanceiro(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        main = ModernCard(self)
        main.grid(row=0, column=0, padx=40, pady=40, sticky="nsew")
        main.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(main, text="Simulador Financeiro Inteligente",
                     font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, columnspan=2, pady=30)

        f_in = ctk.CTkFrame(main, fg_color="transparent")
        f_in.grid(row=1, column=0, padx=30, sticky="nsew")
        f_in.grid_columnconfigure(1, weight=1)

        def inp(row, label, var):
            ctk.CTkLabel(f_in, text=label).grid(row=row, column=0, padx=10, pady=15, sticky="e")
            ctk.CTkEntry(f_in, textvariable=var).grid(row=row, column=1, padx=10, pady=15, sticky="we")

        self.acervo_dict = self._get_acervo()
        ctk.CTkLabel(f_in, text="Selecione a Peça:").grid(row=0, column=0, padx=10, pady=15, sticky="e")
        self.peca_combo = ctk.CTkComboBox(
            f_in, values=list(self.acervo_dict.keys()) if self.acervo_dict else ["Nenhuma Peça"],
        )
        self.peca_combo.grid(row=0, column=1, padx=10, pady=15, sticky="we")

        self.energia_var = ctk.StringVar(value="1.50")
        self.horas_var   = ctk.StringVar(value="1.0")
        self.lucro_var   = ctk.StringVar(value="100")
        inp(1, "Custo de Operação Fixo / Hora ($):", self.energia_var)
        inp(2, "Tempo Médio (Horas):", self.horas_var)
        inp(3, "Margem de Lucro (%):", self.lucro_var)

        ctk.CTkButton(f_in, text="Calcular Extrato", font=ctk.CTkFont(weight="bold", size=16),
                      height=45, fg_color=ACCENT_COLOR, command=self._calcular).grid(
            row=4, column=0, columnspan=2, pady=30, sticky="we", padx=10,
        )

        res = ctk.CTkFrame(main, fg_color="#181818", corner_radius=15)
        res.grid(row=1, column=1, padx=30, sticky="nsew", pady=(0, 30))
        ctk.CTkLabel(res, text="Extrato de Precificação",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(30, 20))

        self.lbl_material = ctk.CTkLabel(res, text="Custo do Material: R$ 0,00",
                                         font=ctk.CTkFont(size=16), text_color="#aaa")
        self.lbl_material.pack(pady=10)
        self.lbl_energia  = ctk.CTkLabel(res, text="Custo Operacional: R$ 0,00",
                                         font=ctk.CTkFont(size=16), text_color="#aaa")
        self.lbl_energia.pack(pady=10)
        ctk.CTkFrame(res, height=1, fg_color=BORDER_COLOR).pack(fill="x", padx=40, pady=20)
        self.lbl_total = ctk.CTkLabel(res, text="Custo Total: R$ 0,00",
                                      font=ctk.CTkFont(size=20, weight="bold"), text_color="#d64545")
        self.lbl_total.pack(pady=10)
        self.lbl_venda = ctk.CTkLabel(res, text="Preço de Venda: R$ 0,00",
                                      font=ctk.CTkFont(size=28, weight="bold"), text_color="#2b7a4b")
        self.lbl_venda.pack(pady=(20, 10))

    def _get_acervo(self):
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("SELECT id, nome_peca FROM acervo").fetchall()
        conn.close()
        return {r[1]: r[0] for r in rows}

    def _calcular(self):
        peca = self.peca_combo.get()
        if not peca or peca not in self.acervo_dict: return
        try:
            ch    = float(self.energia_var.get().replace(",", "."))
            hrs   = float(self.horas_var.get().replace(",", "."))
            lucro = float(self.lucro_var.get().replace(",", "."))
        except ValueError:
            return messagebox.showerror("Erro", "Valores devem ser numéricos.")

        conn = sqlite3.connect(str(DB_PATH))
        fils = conn.execute(
            """SELECT af.peso_gasto, f.peso_inicial, f.preco_rolo
               FROM acervo_filamentos af JOIN filamentos f ON af.filamento_id=f.id
               WHERE af.acervo_id=?""",
            (self.acervo_dict[peca],),
        ).fetchall()
        conn.close()

        custo_mat = sum(
            p_gasto * ((p_rolo or 0.0) / p_ini)
            for p_gasto, p_ini, p_rolo in fils if p_ini > 0
        )
        custo_op  = ch * hrs
        total     = custo_mat + custo_op
        venda     = total * (1 + lucro / 100)

        self.lbl_material.configure(text=f"Custo do Material: R$ {custo_mat:.2f}")
        self.lbl_energia.configure( text=f"Custo Operacional: R$ {custo_op:.2f}")
        self.lbl_total.configure(   text=f"Custo Total: R$ {total:.2f}")
        self.lbl_venda.configure(   text=f"Preço de Venda: R$ {venda:.2f}")


# ==========================================
# MAIN APP
# ==========================================

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IJ 3D")
        self.geometry("1920x1080")
        
        # Maximize the window cross-platform
        try:
            self.after(100, lambda: self.state('zoomed'))
        except Exception:
            try:
                self.after(100, lambda: self.attributes('-zoomed', True))
            except Exception:
                pass

        self.configure(fg_color=APP_BG_COLOR)

        try:
            if os.path.exists(APP_ICON_PATH):
                icon = tk.PhotoImage(file=APP_ICON_PATH)
                self.wm_iconphoto(True, icon)
        except Exception:
            pass

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.sidebar_expanded = True
        sidebar = ctk.CTkFrame(self, corner_radius=0, fg_color="#111111",
                               border_width=1, border_color=BORDER_COLOR)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(8, weight=1)
        self._sidebar = sidebar

        self._btn_toggle = ctk.CTkButton(
            sidebar, text="≡", width=40, height=40, fg_color="transparent",
            font=ctk.CTkFont(size=20), command=self._toggle_sidebar,
        )
        self._btn_toggle.grid(row=0, column=0, padx=10, pady=(20, 10), sticky="w")

        self._logo = ctk.CTkLabel(sidebar, text="IJ 3D", font=ctk.CTkFont(size=24, weight="bold"))
        self._logo.grid(row=0, column=1, padx=(0, 20), pady=(20, 10), sticky="w")

        conn = sqlite3.connect(str(DB_PATH))
        p_name = conn.execute("SELECT printer_name FROM configuracoes WHERE id=1").fetchone()[0]
        conn.close()

        self._printer_var = ctk.StringVar(value=p_name)
        self._printer_entry = ctk.CTkEntry(
            sidebar, textvariable=self._printer_var, width=150,
            fg_color="transparent", border_width=0,
            font=ctk.CTkFont(size=12, slant="italic"), text_color=ACCENT_COLOR,
        )
        self._printer_entry.grid(row=1, column=1, padx=(0, 20), pady=(0, 30), sticky="w")
        self._printer_entry.bind("<FocusOut>", self._save_printer)
        self._printer_entry.bind("<Return>", self._save_printer)

        self._nav_btns: list[tuple] = []
        nav_items = [
            (2, "⚙",  "Filamentos",    self._show_filamentos),
            (3, "📦",  "Almoxarifado",  self._show_insumos),
            (4, "📚",  "Acervo",        self._show_acervo),
            (5, "📝",  "Pedidos",       self._show_pedidos),
            (6, "💰",  "Calculadora",   self._show_financeiro),
            (7, "🔧",  "Manutenção",    self._show_manutencao),
        ]
        for row, icon, label, cmd in nav_items:
            full = f"{icon}   {label}"
            btn = ctk.CTkButton(sidebar, text=full, width=200, fg_color="transparent",
                                text_color="white", anchor="w", font=ctk.CTkFont(size=15), command=cmd)
            btn.grid(row=row, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
            self._nav_btns.append((btn, full, icon))

        self._btn_export = ctk.CTkButton(
            sidebar, text="💾 Exportar Backup", width=200, fg_color="#2b7a4b", hover_color="#1d5c36", command=self._export_backup, font=ctk.CTkFont(size=14, weight="bold")
        )
        self._btn_export.grid(row=9, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="ew")

        self._btn_import = ctk.CTkButton(
            sidebar, text="📂 Importar Backup", width=200, fg_color="#a83232", hover_color="#7a2424", command=self._import_backup, font=ctk.CTkFont(size=14, weight="bold")
        )
        self._btn_import.grid(row=10, column=0, columnspan=2, padx=10, pady=(0, 5), sticky="ew")

        self._footer = ctk.CTkButton(
            sidebar, text="  github.com/IllanSpala", width=200,
            fg_color="transparent", text_color="gray", hover_color="#222", anchor="w",
            command=lambda: open_url("https://github.com/IllanSpala"),
        )
        self._footer.grid(row=11, column=0, columnspan=2, padx=10, pady=(5, 20), sticky="ew")

        self.main_frame = ctk.CTkFrame(self, fg_color=APP_BG_COLOR, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")

        self._current: ctk.CTkFrame | None = None
        self._show_filamentos()

    def _save_printer(self, _event=None):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("UPDATE configuracoes SET printer_name=? WHERE id=1", (self._printer_var.get(),))
        conn.commit(); conn.close()
        self.focus()

    def _toggle_sidebar(self):
        self.sidebar_expanded = not self.sidebar_expanded
        if self.sidebar_expanded:
            self._sidebar.configure(width=220)
            self._logo.grid(); self._printer_entry.grid()
            self._footer.configure(text="  github.com/IllanSpala", width=200)
            self._btn_export.configure(text="💾 Exportar Backup", width=200)
            self._btn_import.configure(text="📂 Importar Backup", width=200)
            for btn, full, short in self._nav_btns:
                btn.configure(text=full, width=200)
        else:
            self._sidebar.configure(width=50)
            self._logo.grid_remove(); self._printer_entry.grid_remove()
            self._footer.configure(text=" ", width=30)
            self._btn_export.configure(text="💾", width=30)
            self._btn_import.configure(text="📂", width=30)
            for btn, full, short in self._nav_btns:
                btn.configure(text=short, width=30)

    def _swap(self, cls):
        if self._current:
            self._current.destroy()
        self._current = cls(self.main_frame)
        self._current.pack(fill="both", expand=True)

    def _export_backup(self):
        dest = filedialog.asksaveasfilename(
            defaultextension=".zip",
            initialfile=f"IJ3D_Backup_{int(time.time())}.zip",
            filetypes=[("ZIP Archive", "*.zip")],
            title="Salvar Backup",
        )
        if not dest:
            return
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
        src = filedialog.askopenfilename(
            filetypes=[("ZIP Archive", "*.zip")],
            title="Selecionar arquivo de Backup",
        )
        if not src:
            return
        try:
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(BASE_DIR)
            messagebox.showinfo("Sucesso", "Backup importado!\n\nO aplicativo será fechado para recarregar os dados de forma limpa. Por favor, abra-o novamente.")
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Erro", f"Falha ao importar backup:\n{exc}")

    def _show_filamentos(self):  self._swap(TabFilamentos)
    def _show_acervo(self):      self._swap(TabAcervo)
    def _show_pedidos(self):     self._swap(TabPedidos)
    def _show_financeiro(self):  self._swap(TabFinanceiro)
    def _show_manutencao(self):  self._swap(TabManutencao)
    def _show_insumos(self):     self._swap(TabAlmoxarifado)


# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":
    init_db()
    app = App()
    app.mainloop()