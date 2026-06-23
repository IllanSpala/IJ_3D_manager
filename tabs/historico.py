import datetime
import os
import shutil
from pathlib import Path
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog

from core.database import db
from core.utils import (
    load_and_resize_image, resolve_media_path, MEDIA_DIR,
    ACCENT_COLOR, APP_BG_COLOR, BORDER_COLOR, CARD_BG_COLOR
)

_GREEN   = "#2b7a4b"
_RED     = "#d64545"
_ORANGE  = "#d97706"
_YELLOW  = "#e6c300"
_BLUE    = "#89b4fa"
_GRAY    = "#666"
_HEADER  = "#1a1a2e"
_ROW_ODD = "#1c1c2e"
_ROW_EVN = "#181826"

_COR_MAP = {
    "preto":      "#111111", "black":      "#111111",
    "branco":     "#f0f0f0", "white":      "#f0f0f0",
    "cinza":      "#888888", "gray":       "#888888", "grey": "#888888",
    "vermelho":   "#d64545", "red":        "#d64545",
    "verde":      "#2b7a4b", "green":      "#2b7a4b",
    "azul":       "#3b82f6", "blue":       "#3b82f6",
    "amarelo":    "#e6c300", "yellow":     "#e6c300",
    "laranja":    "#d97706", "orange":     "#d97706",
    "rosa":       "#f472b6", "pink":       "#f472b6",
    "roxo":       "#9333ea", "purple":     "#9333ea", "violeta": "#9333ea",
    "marrom":     "#92400e", "brown":      "#92400e",
    "bege":       "#d4b896", "beige":      "#d4b896",
    "dourado":    "#d4a017", "gold":       "#d4a017",
    "prata":      "#c0c0c0", "silver":     "#c0c0c0",
    "transparente": "#cccccc44", "natural": "#e8dcc8",
}

def _map_cor_hex(cor: str) -> str:
    """Mapeia string de cor comum para valor hexadecimal."""
    if not cor:
        return "#555"
    chave = cor.strip().lower()
    # Busca direta
    if chave in _COR_MAP:
        return _COR_MAP[chave]
    # Busca por substring
    for k, v in _COR_MAP.items():
        if k in chave:
            return v
    # Se começar com # assume hex direto
    if chave.startswith("#"):
        return cor
    return "#555"

def _migrate_old_history():
    """Migra dados da antiga acervo_impressoes para hist_impressoes na primeira vez."""
    with db.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM hist_impressoes").fetchone()[0]
        if count == 0:
            # Verifica se existem dados antigos
            try:
                old_imps = conn.execute("SELECT id, acervo_id, data_impressao, tempo_impressao, status, preco_venda, observacao FROM acervo_impressoes").fetchall()
            except Exception:
                old_imps = []
                
            for imp in old_imps:
                old_id, acervo_id, data_imp, tempo_imp, status, preco, obs = imp
                if acervo_id:
                    acervo = conn.execute("SELECT nome_peca, config_fatiador, arquivo_3d FROM acervo WHERE id=?", (acervo_id,)).fetchone()
                    if acervo:
                        nome_peca, config_fat, arq_3d = acervo
                    else:
                        nome_peca, config_fat, arq_3d = f"Acervo #{acervo_id}", "", ""
                else:
                    nome_peca, config_fat, arq_3d = "Desconhecido", "", ""
                
                c = conn.cursor()
                c.execute('''INSERT INTO hist_impressoes 
                             (acervo_id, nome_peca, data_impressao, tempo_impressao, status, preco_venda, observacao, config_fatiador, arquivo_3d)
                             VALUES (?,?,?,?,?,?,?,?,?)''', 
                             (acervo_id, nome_peca, data_imp, tempo_imp, status, preco, obs, config_fat, arq_3d))
                new_hist_id = c.lastrowid
                
                if acervo_id:
                    old_fils = conn.execute("SELECT filamento_id, peso_gasto, peso_desperdicio, peso_torre FROM acervo_filamentos WHERE acervo_id=?", (acervo_id,)).fetchall()
                    for fil in old_fils:
                        f_id, p_gasto, p_desp, p_torre = fil
                        # Os pesos antigos estavam em KG, para histórico geral guardamos em gramas.
                        c.execute('''INSERT INTO hist_filamentos
                                     (hist_id, filamento_id, peso_modelo_g, peso_purga_g, peso_torre_g)
                                     VALUES (?,?,?,?,?)''',
                                     (new_hist_id, f_id, (p_gasto or 0)*1000, (p_desp or 0)*1000, (p_torre or 0)*1000))
            conn.commit()


class _BiScroll(ctk.CTkFrame):
    def __init__(self, parent, height=400, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self._canvas = tk.Canvas(self, bg="#141414", highlightthickness=0, height=height, bd=0)
        self._vs = ctk.CTkScrollbar(self, orientation="vertical",   command=self._canvas.yview)
        self._hs = ctk.CTkScrollbar(self, orientation="horizontal",  command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=self._vs.set, xscrollcommand=self._hs.set)
        self._hs.pack(side="bottom", fill="x")
        self._vs.pack(side="right",  fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self.inner = ctk.CTkFrame(self._canvas, fg_color="transparent")
        self._win  = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", self._on_canvas)
        for w in (self._canvas, self.inner):
            w.bind("<MouseWheel>", self._on_wheel)
            w.bind("<Button-4>",   lambda e: self._canvas.yview_scroll(-1, "units"))
            w.bind("<Button-5>",   lambda e: self._canvas.yview_scroll(1,  "units"))

    def _on_canvas(self, e):
        mw = self.inner.winfo_reqwidth()
        self._canvas.itemconfig(self._win, width=max(e.width, mw))

    def _on_wheel(self, e):
        if e.delta != 0:
            self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")


class _FilamentoRow(ctk.CTkFrame):
    def __init__(self, parent, filamentos_db, onDelete, data=None):
        super().__init__(parent, fg_color="#222", corner_radius=6)
        self.filamentos_db = filamentos_db
        self.grid_columnconfigure((0,1,2,3), weight=1)

        self.fil_var = ctk.StringVar()
        opts = ["Customizado"] + [f"{f[1]} {f[2]} ({f[3]})" for f in filamentos_db]
        self.fil_opt = ctk.CTkOptionMenu(self, variable=self.fil_var, values=opts, width=220)
        self.fil_opt.grid(row=0, column=0, padx=5, pady=(8, 0))

        self.modelo_var = ctk.StringVar(value="0.0")
        self.purga_var = ctk.StringVar(value="0.0")
        self.torre_var = ctk.StringVar(value="0.0")

        # Rótulos independentes acima das caixas
        ctk.CTkLabel(self, text="Modelo (g)", font=ctk.CTkFont(size=10),
                     text_color="#888").grid(row=0, column=1, padx=5, pady=(8, 0), sticky="w")
        ctk.CTkLabel(self, text="Purga (g)", font=ctk.CTkFont(size=10),
                     text_color="#888").grid(row=0, column=2, padx=5, pady=(8, 0), sticky="w")
        ctk.CTkLabel(self, text="Torre (g)", font=ctk.CTkFont(size=10),
                     text_color="#888").grid(row=0, column=3, padx=5, pady=(8, 0), sticky="w")

        ctk.CTkEntry(self, textvariable=self.modelo_var, width=75).grid(row=1, column=1, padx=5, pady=(0, 6))
        ctk.CTkEntry(self, textvariable=self.purga_var,  width=75).grid(row=1, column=2, padx=5, pady=(0, 6))
        ctk.CTkEntry(self, textvariable=self.torre_var,  width=75).grid(row=1, column=3, padx=5, pady=(0, 6))

        ctk.CTkButton(self, text="X", width=30, fg_color=_RED, hover_color="#8a2020",
                      command=lambda: onDelete(self)).grid(row=0, column=4, rowspan=2, padx=5)

        if data:
            if data.get('filamento_id'):
                for f in filamentos_db:
                    if f[0] == data['filamento_id']:
                        self.fil_var.set(f"{f[1]} {f[2]} ({f[3]})")
                        break
            else:
                self.fil_var.set("Customizado")
            self.modelo_var.set(str(data.get('peso_modelo_g', 0)))
            self.purga_var.set(str(data.get('peso_purga_g', 0)))
            self.torre_var.set(str(data.get('peso_torre_g', 0)))


    def get_data(self):
        sel = self.fil_var.get()
        fil_id = None
        if sel != "Customizado":
            for f in self.filamentos_db:
                if f"{f[1]} {f[2]} ({f[3]})" == sel:
                    fil_id = f[0]
                    break
        try: mod = float(self.modelo_var.get().replace(',','.'))
        except: mod = 0.0
        try: pur = float(self.purga_var.get().replace(',','.'))
        except: pur = 0.0
        try: tor = float(self.torre_var.get().replace(',','.'))
        except: tor = 0.0
        return {
            'filamento_id': fil_id,
            'peso_modelo_g': mod,
            'peso_purga_g': pur,
            'peso_torre_g': tor
        }


class _DetalhesHistoricoModal(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Detalhes da Impressão")
        self.geometry("820x720")
        self.configure(fg_color=APP_BG_COLOR)
        self.resizable(True, True)
        self.withdraw()
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self._hist_id = None
        self._on_saved = None
        
        self.filamentos_db = []
        self.acervo_db = []
        
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=APP_BG_COLOR)
        self.scroll.pack(fill="both", expand=True, padx=0, pady=0)
        self.scroll.grid_columnconfigure(1, weight=1)

        pad = dict(padx=16, pady=(8, 4))
        
        # 1. Base Info
        f_info = ctk.CTkFrame(self.scroll, fg_color="#1a1a1a", border_width=1, border_color=BORDER_COLOR)
        f_info.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(16, 8))
        f_info.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(f_info, text="Origem (Acervo):").grid(row=0, column=0, sticky="e", **pad)
        self.origem_var = ctk.StringVar()
        self.origem_opt = ctk.CTkOptionMenu(f_info, variable=self.origem_var, command=self._on_origem_change)
        self.origem_opt.grid(row=0, column=1, sticky="ew", **pad)
        
        ctk.CTkLabel(f_info, text="Peça / Modelo:").grid(row=1, column=0, sticky="e", **pad)
        self.peca_var = ctk.StringVar()
        ctk.CTkEntry(f_info, textvariable=self.peca_var).grid(row=1, column=1, sticky="ew", **pad)
        
        ctk.CTkLabel(f_info, text="Data (AAAA-MM-DD):").grid(row=2, column=0, sticky="e", **pad)
        self.data_var = ctk.StringVar()
        ctk.CTkEntry(f_info, textvariable=self.data_var).grid(row=2, column=1, sticky="ew", **pad)
        
        ctk.CTkLabel(f_info, text="Tempo (HH:MM):").grid(row=3, column=0, sticky="e", **pad)
        self.tempo_var = ctk.StringVar()
        ctk.CTkEntry(f_info, textvariable=self.tempo_var, placeholder_text="02:30").grid(row=3, column=1, sticky="ew", **pad)
        
        ctk.CTkLabel(f_info, text="Status:").grid(row=4, column=0, sticky="e", **pad)
        self.status_var = ctk.StringVar()
        ctk.CTkOptionMenu(f_info, variable=self.status_var, values=["Sucesso", "Falha", "Cancelado", "Remake", "Pausado"]).grid(row=4, column=1, sticky="w", **pad)
        
        ctk.CTkLabel(f_info, text="Preço Venda (R$):").grid(row=5, column=0, sticky="e", **pad)
        self.preco_var = ctk.StringVar()
        ctk.CTkEntry(f_info, textvariable=self.preco_var).grid(row=5, column=1, sticky="ew", **pad)
        
        ctk.CTkLabel(f_info, text="Conf. Fatiador:").grid(row=6, column=0, sticky="e", **pad)
        self.conf_var = ctk.StringVar()
        ctk.CTkEntry(f_info, textvariable=self.conf_var).grid(row=6, column=1, sticky="ew", **pad)
        
        ctk.CTkLabel(f_info, text="Arq. 3D:").grid(row=7, column=0, sticky="e", **pad)
        self.arq_var = ctk.StringVar()
        ctk.CTkEntry(f_info, textvariable=self.arq_var).grid(row=7, column=1, sticky="ew", **pad)
        
        ctk.CTkLabel(f_info, text="Observação:").grid(row=8, column=0, sticky="ne", **pad)
        self.obs_txt = ctk.CTkTextbox(f_info, height=60, fg_color="#222")
        self.obs_txt.grid(row=8, column=1, sticky="ew", **pad)
        
        # 2. Filamentos
        fil_frame = ctk.CTkFrame(self.scroll, fg_color="#1a1a1a", border_width=1, border_color=BORDER_COLOR)
        fil_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=8)
        fil_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(fil_frame, text="🧵 Filamentos Utilizados", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=16, pady=10)
        
        self.fil_list_frame = ctk.CTkFrame(fil_frame, fg_color="transparent")
        self.fil_list_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=5)
        self.fil_list_frame.grid_columnconfigure(0, weight=1)
        self.fil_rows = []
        
        ctk.CTkButton(fil_frame, text="+ Adicionar Filamento", command=self._add_fil_row, width=150, fg_color="#2d2d44", hover_color="#3d3d5c").grid(row=2, column=0, padx=16, pady=10, sticky="w")
        
        # 3. Fotos
        foto_frame = ctk.CTkFrame(self.scroll, fg_color="#1a1a1a", border_width=1, border_color=BORDER_COLOR)
        foto_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=8)
        foto_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(foto_frame, text="📷 Fotos da Impressão", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=16, pady=10)
        
        self.foto_gallery = ctk.CTkScrollableFrame(foto_frame, fg_color="transparent", orientation="horizontal", height=130)
        self.foto_gallery.grid(row=1, column=0, sticky="ew", padx=16, pady=5)
        self.foto_rows = []
        
        ctk.CTkButton(foto_frame, text="+ Adicionar Foto", command=self._add_foto, width=150, fg_color="#2d2d44", hover_color="#3d3d5c").grid(row=2, column=0, padx=16, pady=10, sticky="w")
        
        # Save Button
        ctk.CTkButton(self.scroll, text="💾 SALVAR IMPRESSÃO", fg_color=ACCENT_COLOR, hover_color="#007acc", font=ctk.CTkFont(weight="bold", size=14), height=44, command=self._save).grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=(16, 30))
        
    def _on_origem_change(self, val):
        if val == "Customizado": return
        acervo_id = None
        for a in self.acervo_db:
            if f"{a[1]} (#{a[0]})" == val:
                acervo_id = a[0]
                break
        if acervo_id:
            with db.get_connection() as conn:
                a = conn.execute("SELECT nome_peca, config_fatiador, arquivo_3d FROM acervo WHERE id=?", (acervo_id,)).fetchone()
                if a:
                    self.peca_var.set(a[0] or "")
                    self.conf_var.set(a[1] or "")
                    self.arq_var.set(a[2] or "")
                
                if self._hist_id is None:
                    for r in self.fil_rows: r.destroy()
                    self.fil_rows = []
                    fils = conn.execute("SELECT filamento_id, peso_gasto, peso_desperdicio, peso_torre FROM acervo_filamentos WHERE acervo_id=?", (acervo_id,)).fetchall()
                    for f in fils:
                        self._add_fil_row({
                            'filamento_id': f[0],
                            'peso_modelo_g': (f[1] or 0)*1000,
                            'peso_purga_g': (f[2] or 0)*1000,
                            'peso_torre_g': (f[3] or 0)*1000
                        })

    def _add_fil_row(self, data=None):
        r = _FilamentoRow(self.fil_list_frame, self.filamentos_db, self._del_fil_row, data)
        r.grid(row=len(self.fil_rows), column=0, sticky="ew", pady=4)
        self.fil_rows.append(r)
        
    def _del_fil_row(self, row_widget):
        row_widget.destroy()
        if row_widget in self.fil_rows:
            self.fil_rows.remove(row_widget)
            for i, r in enumerate(self.fil_rows):
                r.grid(row=i, column=0, sticky="ew", pady=4)
                
    def _add_foto(self, path=None):
        if not path:
            path = filedialog.askopenfilename(filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp")])
            if not path: return
            
        f = ctk.CTkFrame(self.foto_gallery, fg_color="#222", width=110, height=120)
        f.pack(side="left", padx=5)
        f.pack_propagate(False)
        f._photo_path = path
        
        lbl = ctk.CTkLabel(f, text="")
        lbl.pack(pady=(4,2))
        
        img = load_and_resize_image(resolve_media_path(path), size=(90,70))
        if img:
            lbl.configure(image=img)
            lbl.image = img
            
        def _del():
            f.destroy()
            if f in self.foto_rows: self.foto_rows.remove(f)
            
        ctk.CTkButton(f, text="🗑 Excluir", width=80, height=24, fg_color=_RED, font=ctk.CTkFont(size=10), command=_del).pack(pady=(4,0))
        self.foto_rows.append(f)

    def show(self, hist_id=None, on_saved=None):
        self._hist_id = hist_id
        self._on_saved = on_saved
        
        with db.get_connection() as conn:
            self.filamentos_db = conn.execute("SELECT id, marca, material, cor FROM filamentos WHERE status='Ativo'").fetchall()
            self.acervo_db = conn.execute("SELECT id, nome_peca FROM acervo ORDER BY nome_peca").fetchall()
            
        self.origem_opt.configure(values=["Customizado"] + [f"{a[1]} (#{a[0]})" for a in self.acervo_db])
        
        # Reset default fields
        self.origem_var.set("Customizado")
        self.peca_var.set("")
        self.data_var.set(datetime.datetime.now().strftime("%Y-%m-%d"))
        self.tempo_var.set("")
        self.status_var.set("Sucesso")
        self.preco_var.set("")
        self.conf_var.set("")
        self.arq_var.set("")
        self.obs_txt.delete("1.0", "end")
        for r in self.fil_rows: r.destroy()
        self.fil_rows = []
        for r in self.foto_gallery.winfo_children(): r.destroy()
        self.foto_rows = []
        
        if hist_id:
            with db.get_connection() as conn:
                h = conn.execute("SELECT acervo_id, nome_peca, data_impressao, tempo_impressao, status, preco_venda, observacao, config_fatiador, arquivo_3d FROM hist_impressoes WHERE id=?", (hist_id,)).fetchone()
                if h:
                    if h[0]:
                        for a in self.acervo_db:
                            if a[0] == h[0]:
                                self.origem_var.set(f"{a[1]} (#{a[0]})")
                                break
                    self.peca_var.set(h[1] or "")
                    self.data_var.set(h[2] or "")
                    self.tempo_var.set(h[3] or "")
                    self.status_var.set(h[4] or "Sucesso")
                    self.preco_var.set(str(h[5]) if h[5] is not None else "")
                    self.obs_txt.insert("1.0", h[6] or "")
                    self.conf_var.set(h[7] or "")
                    self.arq_var.set(h[8] or "")
                    
                fils = conn.execute("SELECT filamento_id, peso_modelo_g, peso_purga_g, peso_torre_g FROM hist_filamentos WHERE hist_id=?", (hist_id,)).fetchall()
                for f in fils:
                    self._add_fil_row({'filamento_id': f[0], 'peso_modelo_g': f[1], 'peso_purga_g': f[2], 'peso_torre_g': f[3]})
                    
                fotos = conn.execute("SELECT caminho_foto FROM hist_fotos WHERE hist_id=?", (hist_id,)).fetchall()
                for f in fotos:
                    self._add_foto(f[0])

        self.deiconify()
        self.lift()
        self.focus_force()

    def _save(self):
        acervo_id = None
        origem = self.origem_var.get()
        if origem != "Customizado":
            for a in self.acervo_db:
                if f"{a[1]} (#{a[0]})" == origem:
                    acervo_id = a[0]
                    break
                    
        nome_peca = self.peca_var.get().strip()
        if not nome_peca:
            messagebox.showerror("Erro", "Nome da peça é obrigatório.")
            return
            
        data_imp = self.data_var.get().strip()
        tempo_imp = self.tempo_var.get().strip()
        status = self.status_var.get()
        obs = self.obs_txt.get("1.0", "end-1c").strip()
        conf = self.conf_var.get().strip()
        arq = self.arq_var.get().strip()
        
        try:
            preco_str = self.preco_var.get().strip().replace(',', '.')
            preco = float(preco_str) if preco_str else None
        except ValueError:
            messagebox.showerror("Erro", "Preço deve ser numérico.")
            return

        with db.get_connection() as conn:
            c = conn.cursor()
            if self._hist_id:
                c.execute('''UPDATE hist_impressoes SET acervo_id=?, nome_peca=?, data_impressao=?, tempo_impressao=?, status=?, preco_venda=?, observacao=?, config_fatiador=?, arquivo_3d=? WHERE id=?''',
                          (acervo_id, nome_peca, data_imp, tempo_imp, status, preco, obs, conf, arq, self._hist_id))
            else:
                c.execute('''INSERT INTO hist_impressoes (acervo_id, nome_peca, data_impressao, tempo_impressao, status, preco_venda, observacao, config_fatiador, arquivo_3d) VALUES (?,?,?,?,?,?,?,?,?)''',
                          (acervo_id, nome_peca, data_imp, tempo_imp, status, preco, obs, conf, arq))
                self._hist_id = c.lastrowid
                
            c.execute("DELETE FROM hist_filamentos WHERE hist_id=?", (self._hist_id,))
            for r in self.fil_rows:
                fd = r.get_data()
                c.execute('''INSERT INTO hist_filamentos (hist_id, filamento_id, peso_modelo_g, peso_purga_g, peso_torre_g) VALUES (?,?,?,?,?)''',
                          (self._hist_id, fd['filamento_id'], fd['peso_modelo_g'], fd['peso_purga_g'], fd['peso_torre_g']))
                          
            c.execute("DELETE FROM hist_fotos WHERE hist_id=?", (self._hist_id,))
            for fr in self.foto_rows:
                path = fr._photo_path
                if not path.startswith("media"):
                    # copy to media dir
                    ext = os.path.splitext(path)[1]
                    new_name = f"hist_{int(datetime.datetime.now().timestamp() * 1000)}{ext}"
                    dest_dir = os.path.join(MEDIA_DIR, "hist_fotos")
                    os.makedirs(dest_dir, exist_ok=True)
                    dest = os.path.join(dest_dir, new_name)
                    shutil.copy2(path, dest)
                    path = f"media/hist_fotos/{new_name}"
                c.execute("INSERT INTO hist_fotos (hist_id, caminho_foto) VALUES (?,?)", (self._hist_id, path))
                
            conn.commit()
            
        if self._on_saved: self._on_saved()
        self.withdraw()


def _status_color(status: str) -> str:
    m = {"sucesso": _GREEN, "falha": _RED, "cancelado": _RED, "remake": _YELLOW, "pausado": _ORANGE}
    return m.get((status or "").lower(), "#888")

def _fmt_date(raw: str | None) -> str:
    if not raw:
        return "—"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(raw, fmt).strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            pass
    return raw


class TabHistorico(ctk.CTkFrame):
    _COLS = [
        ("Data / Tempo",      140, "w"),
        ("Peça / Modelo",     200, "w"),
        ("Status",            100, "center"),
        ("Detalhe Filamentos",320, "w"),
        ("Total (g)",          80, "e"),
        ("Preço (R$)",        100, "e"),
        ("Fotos",              60, "center"),
        ("Ações",             150, "center"),
    ]

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        _migrate_old_history()

        self._modal: _DetalhesHistoricoModal | None = None

        top = ctk.CTkFrame(self, fg_color="#111", corner_radius=0, border_width=1, border_color=BORDER_COLOR)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="📋  Histórico Geral de Impressões", font=ctk.CTkFont(size=20, weight="bold"), text_color="white").grid(row=0, column=0, padx=20, pady=14, sticky="w")

        filt = ctk.CTkFrame(top, fg_color="transparent")
        filt.grid(row=0, column=1, sticky="e", padx=12)

        ctk.CTkButton(filt, text="➕ Adicionar Impressão", width=150, fg_color=_GREEN, hover_color="#1d5c36", font=ctk.CTkFont(size=13, weight="bold"), command=self._add_new).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(filt, text="Buscar:").pack(side="left", padx=(0, 6))
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._refresh())
        ctk.CTkEntry(filt, textvariable=self._search_var, width=160, placeholder_text="Peça...").pack(side="left", padx=(0, 8))

        ctk.CTkLabel(filt, text="Status:").pack(side="left", padx=(0, 4))
        self._status_filter = ctk.StringVar(value="Todos")
        self._status_filter.trace_add("write", lambda *_: self._refresh())
        ctk.CTkOptionMenu(filt, variable=self._status_filter, values=["Todos", "Sucesso", "Falha", "Cancelado", "Remake", "Pausado"], width=120).pack(side="left", padx=(0, 12))

        ctk.CTkButton(filt, text="⟳ Atualizar", width=100, fg_color="#2a2a4a", hover_color="#3a3a6a", command=self._refresh).pack(side="left")

        # Altura dinâmica: 75% da altura de tela disponível
        try:
            _sh = self.winfo_screenheight()
        except Exception:
            _sh = 900
        self._scroll = _BiScroll(self, height=max(400, int(_sh * 0.72)))
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        t = self._scroll.inner
        # Pesos de expansão: colunas maiores expandem mais
        _weights = [1, 2, 1, 4, 1, 1, 1, 2]
        for ci, (minw_weight, col) in enumerate(zip(_weights, self._COLS)):
            t.grid_columnconfigure(ci, weight=minw_weight, minsize=col[1])

        for ci, (label, minw, _align) in enumerate(self._COLS):
            hf = ctk.CTkFrame(t, fg_color=_HEADER, corner_radius=0, border_width=0)
            hf.grid(row=0, column=ci, sticky="nsew", padx=1, pady=(0, 1))
            ctk.CTkLabel(hf, text=label, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#89b4fa").pack(padx=8, pady=6)

        sep = ctk.CTkFrame(t, height=2, fg_color=ACCENT_COLOR)
        sep.grid(row=1, column=0, columnspan=len(self._COLS), sticky="ew")

        self._data_rows = []
        self._row_start = 2
        self._refresh()


    def _load_data(self):
        with db.get_connection() as conn:
            rows = conn.execute("SELECT id, nome_peca, data_impressao, tempo_impressao, status, preco_venda, observacao, config_fatiador, arquivo_3d FROM hist_impressoes ORDER BY id DESC").fetchall()
            
            res = []
            for r in rows:
                hid = r[0]
                fils = conn.execute("""SELECT f.marca, f.material, f.cor, hf.peso_modelo_g, hf.peso_purga_g, hf.peso_torre_g 
                                       FROM hist_filamentos hf LEFT JOIN filamentos f ON hf.filamento_id = f.id WHERE hf.hist_id=?""", (hid,)).fetchall()
                fotos_count = conn.execute("SELECT COUNT(*) FROM hist_fotos WHERE hist_id=?", (hid,)).fetchone()[0]
                
                fil_data = []  # lista de dicts com cor_hex, nome e total_g por cor
                total_g_geral = 0
                for f in fils:
                    nome = f"{f[0]} {f[1]} ({f[2]})" if f[0] else "Customizado"
                    cor_str = f[2] or ""
                    mod = f[3] or 0
                    pur = f[4] or 0
                    tor = f[5] or 0
                    total_cor = mod + pur + tor
                    total_g_geral += total_cor
                    fil_data.append({
                        'nome': nome,
                        'cor_hex': _map_cor_hex(cor_str),
                        'total_g': total_cor,
                        'mod': mod, 'pur': pur, 'tor': tor,
                    })
                
                res.append({
                    'id': hid,
                    'nome_peca': r[1] or "—",
                    'data': r[2] or "—",
                    'tempo': r[3] or "",
                    'status': r[4] or "Sucesso",
                    'preco': r[5],
                    'fil_data': fil_data,
                    'total_g': total_g_geral,
                    'fotos': fotos_count > 0
                })
            return res

    def _refresh(self, *_):
        for row_widgets in self._data_rows:
            for w in row_widgets:
                if w and w.winfo_exists(): w.destroy()
        self._data_rows = []

        data = self._load_data()

        search = self._search_var.get().strip().lower()
        sf = self._status_filter.get()
        if search:
            data = [d for d in data if search in d["nome_peca"].lower() or any(search in f['nome'].lower() for f in d['fil_data'])]
        if sf != "Todos":
            data = [d for d in data if d["status"].lower() == sf.lower()]

        t = self._scroll.inner
        for ri, d in enumerate(data):
            gr = self._row_start + ri
            bg = _ROW_ODD if ri % 2 == 0 else _ROW_EVN
            row_refs = []

            def _cell(col, text, color="#ccc", anchor="w"):
                mw = self._COLS[col][1]
                cf = ctk.CTkFrame(t, fg_color=bg, corner_radius=0)
                cf.grid(row=gr, column=col, sticky="nsew", padx=1, pady=0)
                ctk.CTkLabel(cf, text=text, text_color=color, font=ctk.CTkFont(size=11),
                             anchor=anchor, width=mw).pack(padx=6, pady=4,
                             anchor=anchor if anchor != "center" else "center")
                return cf

            # Col 0: Data/Tempo
            cf0 = ctk.CTkFrame(t, fg_color=bg, corner_radius=0)
            cf0.grid(row=gr, column=0, sticky="nsew", padx=1, pady=0)
            ctk.CTkLabel(cf0, text=_fmt_date(d["data"]), text_color="#aaa",
                         font=ctk.CTkFont(size=11), anchor="w",
                         width=self._COLS[0][1]).pack(padx=6, pady=(4, 0), anchor="w")
            if d["tempo"]:
                ctk.CTkLabel(cf0, text=f"⏱ {d['tempo']}", text_color="#7b7b9e",
                             font=ctk.CTkFont(size=10), anchor="w").pack(padx=6, pady=(0, 4), anchor="w")
            row_refs.append(cf0)

            # Col 1: Peça
            row_refs.append(_cell(1, d["nome_peca"], "#fff"))
            # Col 2: Status
            row_refs.append(_cell(2, d["status"], _status_color(d["status"]), anchor="center"))

            # Col 3: Filamentos com swatch + total por cor
            cf3 = ctk.CTkFrame(t, fg_color=bg, corner_radius=0)
            cf3.grid(row=gr, column=3, sticky="nsew", padx=1, pady=2)
            if d["fil_data"]:
                for fd in d["fil_data"]:
                    row_f = ctk.CTkFrame(cf3, fg_color="transparent")
                    row_f.pack(fill="x", padx=4, pady=1)
                    sw = tk.Frame(row_f, width=12, height=12, bg=fd['cor_hex'], relief="flat")
                    sw.pack(side="left", padx=(2, 5))
                    sw.pack_propagate(False)
                    ctk.CTkLabel(row_f,
                                 text=f"{fd['nome']}: {fd['total_g']:.1f}g  (M{fd['mod']:.0f}+P{fd['pur']:.0f}+T{fd['tor']:.0f})",
                                 text_color="#ccc", font=ctk.CTkFont(size=10),
                                 anchor="w").pack(side="left")
            else:
                ctk.CTkLabel(cf3, text="Sem filamentos", text_color="#555",
                             font=ctk.CTkFont(size=10)).pack(padx=6, pady=4)
            row_refs.append(cf3)

            # Col 4: Total
            row_refs.append(_cell(4, f"{d['total_g']:.1f}", _BLUE, anchor="e"))

            # Col 5: Preço
            ptxt = f"R$ {d['preco']:.2f}" if d['preco'] is not None else "—"
            row_refs.append(_cell(5, ptxt, "#a6e3a1" if d['preco'] else "#555", anchor="e"))

            # Col 6: Fotos
            row_refs.append(_cell(6, "📷" if d["fotos"] else "—",
                                  "#fff" if d["fotos"] else "#555", anchor="center"))

            # Col 7: Ações (Detalhes + Editar + Excluir)
            af = ctk.CTkFrame(t, fg_color=bg, corner_radius=0)
            af.grid(row=gr, column=7, sticky="nsew", padx=1, pady=0)
            hid = d["id"]
            ctk.CTkButton(af, text="❓", width=28, height=26,
                          fg_color="#3d4f7a", hover_color="#4d6f9a",
                          font=ctk.CTkFont(size=13),
                          command=lambda item=d: self._show_duvida(item)).pack(side="left", padx=2, pady=4)
            ctk.CTkButton(af, text="Detalhes", width=68, height=26,
                          fg_color="#2d3a5c", hover_color="#3d4f7a",
                          font=ctk.CTkFont(size=11),
                          command=lambda i=hid: self._show_detalhes(i)).pack(side="left", padx=2, pady=4)
            ctk.CTkButton(af, text="✏", width=28, height=26, fg_color="#2d2d44",
                          hover_color="#3d3d5c", font=ctk.CTkFont(size=13),
                          command=lambda i=hid: self._edit(i)).pack(side="left", padx=2, pady=4)
            ctk.CTkButton(af, text="🗑", width=28, height=26, fg_color="#4a2d2d",
                          hover_color="#6e3a3a", font=ctk.CTkFont(size=13),
                          command=lambda i=hid: self._delete(i)).pack(side="left", padx=2, pady=4)
            row_refs.append(af)

            self._data_rows.append(row_refs)

        if not data:
            ef = ctk.CTkFrame(t, fg_color="transparent")
            ef.grid(row=self._row_start, column=0, columnspan=len(self._COLS), sticky="ew", pady=40)
            ctk.CTkLabel(ef, text="Nenhum histórico encontrado.",
                         font=ctk.CTkFont(size=14), text_color="#555").pack()
            self._data_rows.append([ef])

    def _show_duvida(self, d):
        tempo = d['tempo'] if d['tempo'] else 'Não informado'
        msg = f"Tempo Total de Impressão: {tempo}\n\nUso de Filamentos:\n"
        if not d['fil_data']:
            msg += "Nenhum filamento registrado."
        else:
            for fd in d['fil_data']:
                msg += f"- {fd['nome']}: Modelo {fd['mod']}g, Purga {fd['pur']}g, Torre {fd['tor']}g\n"
        messagebox.showinfo("Detalhes de Consumo", msg, parent=self.winfo_toplevel())

    def _show_detalhes(self, hid):
        """Abre um modal de leitura com os dados textuais longos da impressão."""
        with db.get_connection() as conn:
            h = conn.execute(
                "SELECT nome_peca, data_impressao, tempo_impressao, status, "
                "preco_venda, observacao, config_fatiador, arquivo_3d "
                "FROM hist_impressoes WHERE id=?", (hid,)
            ).fetchone()
        if not h:
            return
        win = ctk.CTkToplevel(self.winfo_toplevel())
        win.title("Detalhes da Impressão")
        win.configure(fg_color="#141420")
        win.resizable(True, True)
        win.attributes("-topmost", True)
        win.grab_set()

        # Dimensiona relativo ao monitor principal
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        w = min(620, int(sw * 0.35))
        h_win = min(500, int(sh * 0.55))
        win.geometry(f"{w}x{h_win}+{(sw-w)//2}+{(sh-h_win)//2}")

        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)

        campos = [
            ("Peça / Modelo",    h[0] or "—"),
            ("Data",             h[1] or "—"),
            ("Tempo",            h[2] or "—"),
            ("Status",           h[3] or "—"),
            ("Preço Venda",      f"R$ {h[4]:.2f}" if h[4] is not None else "—"),
            ("Observação",       h[5] or "—"),
            ("Conf. Fatiador",   h[6] or "—"),
            ("Arquivo 3D",       h[7] or "—"),
        ]

        outer = ctk.CTkFrame(win, fg_color="transparent")
        outer.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, bg="#141420", highlightthickness=0)
        vsb = ctk.CTkScrollbar(outer, orientation="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        canvas.grid(row=0, column=0, sticky="nsew")

        inner = ctk.CTkFrame(canvas, fg_color="transparent")
        inner.columnconfigure(1, weight=1)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas(e):
            canvas.itemconfig(win_id, width=e.width)
        inner.bind("<Configure>", _on_inner)
        canvas.bind("<Configure>", _on_canvas)
        for w_ in (canvas, inner):
            w_.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
            w_.bind("<Button-5>", lambda e: canvas.yview_scroll(1,  "units"))

        for i, (lbl, val) in enumerate(campos):
            ctk.CTkLabel(inner, text=f"{lbl}:", text_color="#89b4fa",
                         font=ctk.CTkFont(weight="bold", size=13),
                         anchor="e").grid(row=i, column=0, sticky="ne",
                                          padx=(16, 10), pady=6)
            ctk.CTkLabel(inner, text=val, text_color="#cdd6f4",
                         font=ctk.CTkFont(size=13),
                         wraplength=int(w * 0.58), justify="left",
                         anchor="w").grid(row=i, column=1, sticky="nw",
                                          padx=(0, 16), pady=6)

        ctk.CTkButton(win, text="✖  Fechar", height=36,
                      fg_color="#2d2d44", hover_color="#3d3d60",
                      font=ctk.CTkFont(size=13),
                      command=win.destroy).grid(row=1, column=0,
                                                pady=(0, 14), ipadx=20)

    def _add_new(self):
        if self._modal is None: self._modal = _DetalhesHistoricoModal(self.winfo_toplevel())
        self._modal.show(on_saved=self._refresh)

    def _edit(self, hid):
        if self._modal is None: self._modal = _DetalhesHistoricoModal(self.winfo_toplevel())
        self._modal.show(hist_id=hid, on_saved=self._refresh)

    def _delete(self, hid):
        if messagebox.askyesno("Excluir", "Deseja excluir este registro do histórico?", parent=self.winfo_toplevel()):
            with db.get_connection() as conn:
                conn.execute("DELETE FROM hist_impressoes WHERE id=?", (hid,))
                conn.commit()
            self._refresh()
