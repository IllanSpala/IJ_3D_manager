import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from core.database import db
from core.state import app_state
from core.widgets import ModernCard, SearchableComboBox
from core.utils import ACCENT_COLOR, BORDER_COLOR

# ─── Tooltip popup ────────────────────────────────────────────────────────────
class _Tooltip(ctk.CTkToplevel):
    def __init__(self, master, text):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color="#1e1e2e")
        lbl = ctk.CTkLabel(self, text=text, wraplength=280, justify="left",
                           font=ctk.CTkFont(size=12), text_color="#cdd6f4",
                           fg_color="#1e1e2e", corner_radius=8)
        lbl.pack(padx=12, pady=10)
        self.withdraw()

    def show_near(self, widget):
        x = widget.winfo_rootx() + widget.winfo_width() + 6
        y = widget.winfo_rooty()
        self.geometry(f"+{x}+{y}")
        self.deiconify()

    def hide(self):
        self.withdraw()


def _make_info_btn(parent, tooltip_text):
    """Return a small ❓ button that shows a tooltip on hover."""
    tip = _Tooltip(parent.winfo_toplevel(), tooltip_text)

    btn = ctk.CTkButton(parent, text="?", width=22, height=22,
                        corner_radius=11, fg_color="#2d2d44",
                        hover_color="#3d3d5c", text_color="#89b4fa",
                        font=ctk.CTkFont(size=11, weight="bold"))
    btn.bind("<Enter>", lambda e: tip.show_near(btn))
    btn.bind("<Leave>", lambda e: tip.hide())
    return btn


# ─── Bidirectional scrollable frame ──────────────────────────────────────────
class _BidirScrollFrame(ctk.CTkFrame):
    """Frame with both horizontal and vertical scrollbars via tk.Canvas."""

    def __init__(self, parent, height=320, canvas_bg="#181818", **kw):
        super().__init__(parent, fg_color="transparent", **kw)

        self._canvas = tk.Canvas(
            self, bg=canvas_bg, highlightthickness=0, height=height, bd=0
        )
        self._v_scroll = ctk.CTkScrollbar(
            self, orientation="vertical", command=self._canvas.yview
        )
        self._h_scroll = ctk.CTkScrollbar(
            self, orientation="horizontal", command=self._canvas.xview
        )
        self._canvas.configure(
            yscrollcommand=self._v_scroll.set,
            xscrollcommand=self._h_scroll.set,
        )

        self._h_scroll.pack(side="bottom", fill="x")
        self._v_scroll.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self.inner = ctk.CTkFrame(self._canvas, fg_color="transparent")
        self._win_id = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_cfg)
        self._canvas.bind("<Configure>", self._on_canvas_cfg)

        # Mouse-wheel bindings (Linux Button-4/5 + Windows/Mac delta)
        for w in (self._canvas, self.inner):
            w.bind("<MouseWheel>", self._on_wheel)
            w.bind("<Button-4>", lambda e: self._canvas.yview_scroll(-1, "units"))
            w.bind("<Button-5>", lambda e: self._canvas.yview_scroll(1, "units"))

    def _on_inner_cfg(self, _e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_cfg(self, e):
        min_w = self.inner.winfo_reqwidth()
        self._canvas.itemconfig(self._win_id, width=max(e.width, min_w))

    def _on_wheel(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")


# ─── Editable row widget ──────────────────────────────────────────────────────
class _EditableRow(ctk.CTkFrame):
    """Label + value display + ✏ edit inline + 💾 save button."""
    def __init__(self, parent, label, tooltip, var, save_key, on_saved=None, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self.grid_columnconfigure(1, weight=1)
        self.var = var
        self.save_key = save_key
        self.on_saved = on_saved
        self._editing = False

        lbl_frame = ctk.CTkFrame(self, fg_color="transparent")
        lbl_frame.grid(row=0, column=0, sticky="e", padx=(0, 8))
        ctk.CTkLabel(lbl_frame, text=label, anchor="e").pack(side="left")
        _make_info_btn(lbl_frame, tooltip).pack(side="left", padx=(4, 0))

        self.entry = ctk.CTkEntry(self, textvariable=self.var, width=120,
                                  fg_color="#1a1a2e", border_color="#333",
                                  state="disabled")
        self.entry.grid(row=0, column=1, sticky="ew", padx=4)

        self.btn_edit = ctk.CTkButton(self, text="✏", width=28, height=28,
                                      fg_color="#2d2d44", hover_color="#3d3d5c",
                                      command=self._start_edit)
        self.btn_edit.grid(row=0, column=2, padx=(4, 2))

        self.btn_save = ctk.CTkButton(self, text="💾", width=28, height=28,
                                      fg_color="#2b7a4b", hover_color="#1d5c36",
                                      command=self._do_save)
        self.btn_save.grid(row=0, column=3, padx=(2, 0))
        self.btn_save.grid_remove()

    def _start_edit(self):
        self._editing = True
        self.entry.configure(state="normal", fg_color="#252540", border_color=ACCENT_COLOR)
        self.entry.focus()
        self.btn_edit.grid_remove()
        self.btn_save.grid()

    def _do_save(self):
        self._editing = False
        val = self.var.get()
        self.entry.configure(state="disabled", fg_color="#1a1a2e", border_color="#333")
        self.btn_save.grid_remove()
        self.btn_edit.grid()
        try:
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE configuracoes SET {} = ? WHERE id = 1".format(self.save_key),
                    (val,)
                )
                conn.commit()
        except Exception:
            pass
        if self.on_saved:
            self.on_saved(val)


# ─── Manual filament row ─────────────────────────────────────────────────────
class _FilRow(ctk.CTkFrame):
    """
    One filament line: ComboBox (filamentos ativos) | preco_kg (auto) | purga_g | modelo_g | [x]
    filamentos_dict: {"Marca Material (Cor)": {"id": int, "preco_kg": float}}
    """
    def __init__(self, parent, on_remove, filamentos_dict: dict, **kw):
        super().__init__(parent, fg_color="#1e1e30", corner_radius=8, **kw)
        self.grid_columnconfigure((0,1,2,3), weight=1)

        self._filamentos_dict = filamentos_dict
        self.preco_var  = ctk.StringVar(value="")
        self.purga_var  = ctk.StringVar(value="0")
        self.modelo_var = ctk.StringVar(value="0")

        labels = ["Filamento", "R$/kg (auto)", "Purga (g)", "Modelo (g)"]
        for col, txt in enumerate(labels):
            ctk.CTkLabel(self, text=txt, font=ctk.CTkFont(size=10),
                         text_color="#666").grid(row=0, column=col, padx=4, pady=(6,0), sticky="w")

        # Col 0: ComboBox com filamentos ativos
        fil_names = list(filamentos_dict.keys()) if filamentos_dict else ["Nenhum filamento ativo"]
        self.fil_combo = ctk.CTkComboBox(
            self, values=fil_names, width=160, height=28,
            font=ctk.CTkFont(size=12),
            command=self._on_filamento_selected
        )
        self.fil_combo.grid(row=1, column=0, padx=4, pady=(0,6), sticky="ew")
        if fil_names:
            self.fil_combo.set(fil_names[0])
            self._on_filamento_selected(fil_names[0])

        # Col 1: preco_kg (preenchido automaticamente, editável se necessário)
        ctk.CTkEntry(self, textvariable=self.preco_var,
                     width=80, height=28, font=ctk.CTkFont(size=12)).grid(
            row=1, column=1, padx=4, pady=(0,6), sticky="ew")

        # Col 2 e 3: purga e modelo
        for col, var in [(2, self.purga_var), (3, self.modelo_var)]:
            ctk.CTkEntry(self, textvariable=var,
                         width=80, height=28, font=ctk.CTkFont(size=12)).grid(
                row=1, column=col, padx=4, pady=(0,6), sticky="ew")

        ctk.CTkButton(self, text="✕", width=26, height=26, fg_color="#4a1a1a",
                      hover_color="#6b2a2a", command=on_remove).grid(
            row=0, column=4, rowspan=2, padx=(4,6))

    def _on_filamento_selected(self, name):
        """Preenche o R$/kg automaticamente ao escolher um filamento."""
        info = self._filamentos_dict.get(name)
        if info:
            self.preco_var.set(f"{info['preco_kg']:.2f}")

    def get_data(self):
        try:
            preco  = float(self.preco_var.get().replace(",",".") or "0")
            purga  = float(self.purga_var.get().replace(",",".") or "0")
            modelo = float(self.modelo_var.get().replace(",",".") or "0")
        except ValueError:
            return None
        return {"label": self.fil_combo.get() or "Filamento",
                "preco_kg": preco, "purga_g": purga, "modelo_g": modelo}


class _TesteManualPanel(ctk.CTkFrame):
    """Expandable panel that holds manual filament rows for ad-hoc cost testing."""
    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color="#16162a", corner_radius=12, **kw)
        self._rows: list[_FilRow] = []
        self._filamentos_dict: dict = {}
        self._load_filamentos()

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10,6))
        ctk.CTkLabel(hdr, text="🧪 Materiais Avulsos",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#a6e3a1").pack(side="left")
        ctk.CTkButton(hdr, text="+ Adicionar Filamento", width=150, height=28,
                      fg_color="#2b4a2b", hover_color="#3a6a3a",
                      font=ctk.CTkFont(size=12),
                      command=self._add_row).pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", height=180)
        self.scroll.pack(fill="x", padx=8, pady=(0,10))
        self.scroll.grid_columnconfigure(0, weight=1)
        self._add_row()

    def _load_filamentos(self):
        """Carrega filamentos ativos (não arquivados) do banco de dados."""
        from core.database import db
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT id, marca, material, cor, preco_rolo, peso_inicial "
                "FROM filamentos WHERE status != 'Arquivado' ORDER BY marca, material, cor"
            ).fetchall()
        self._filamentos_dict = {}
        for fid, marca, material, cor, preco_rolo, peso_ini in rows:
            nome = f"{marca} {material} ({cor})"
            preco_kg = (preco_rolo or 0.0) / (peso_ini or 1.0)
            self._filamentos_dict[nome] = {"id": fid, "preco_kg": preco_kg}

    def _add_row(self):
        row = _FilRow(self.scroll, on_remove=lambda: None,
                      filamentos_dict=self._filamentos_dict)
        idx = len(self._rows)
        self._rows.append(row)
        row.grid(row=idx, column=0, sticky="ew", pady=4, padx=4)
        # Fix remove lambda after row has a real reference
        for child in row.winfo_children():
            if isinstance(child, ctk.CTkButton) and child.cget("text") == "✕":
                child.configure(command=lambda r=row: self._remove(r))

    def _remove(self, row):
        if row in self._rows:
            self._rows.remove(row)
            row.destroy()
            for i, r in enumerate(self._rows):
                r.grid(row=i, column=0, sticky="ew", pady=4, padx=4)

    def get_materials(self):
        result = []
        for r in self._rows:
            d = r.get_data()
            if d:
                result.append(d)
        return result


# ─── Analytical results section ───────────────────────────────────────────────
class _AnalyticalResultsPanel(ctk.CTkFrame):
    """
    Displays a transparent breakdown of the cost formula:
    each material line → unit cost → subtotal, then add-ons, then totals.
    """

    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color="#181818", corner_radius=15, **kw)
        self._rows: list[ctk.CTkFrame] = []

        ctk.CTkLabel(self, text="Extrato Analítico de Custo",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(24, 4))
        ctk.CTkLabel(self, text="Fórmula: (Σ Materiais + Operação + Embalagem) × (1 + Lucro%) ÷ (1 − Taxa%)",
                     font=ctk.CTkFont(size=11), text_color="gray",
                     wraplength=420).pack(pady=(0, 16))

        self._table_scroll = _BidirScrollFrame(self, height=320, canvas_bg="#181818")
        self._table_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        self.table_frame = self._table_scroll.inner
        self.table_frame.grid_columnconfigure(0, weight=3, minsize=200)
        self.table_frame.grid_columnconfigure(1, weight=1, minsize=100)
        self.table_frame.grid_columnconfigure(2, weight=1, minsize=120)
        self.table_frame.grid_columnconfigure(3, weight=1, minsize=100)

        # Table header
        def hdr(col, text, anchor="e"):
            ctk.CTkLabel(self.table_frame, text=text,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="#555").grid(row=0, column=col, sticky=anchor+"ew", padx=6, pady=(0, 4))

        hdr(0, "Item / Material", anchor="w")
        hdr(1, "Qtd / Tempo")
        hdr(2, "Custo Unit.")
        hdr(3, "Subtotal")
        ctk.CTkFrame(self.table_frame, height=1, fg_color="#333").grid(
            row=1, column=0, columnspan=4, sticky="ew", pady=2)

        # Separator above totals (will be repositioned dynamically)
        self._sep = ctk.CTkFrame(self.table_frame, height=1, fg_color=BORDER_COLOR)
        self._total_row_widgets: list = []

        # Fixed bottom labels
        sep2 = ctk.CTkFrame(self, height=1, fg_color=BORDER_COLOR)
        sep2.pack(fill="x", padx=20, pady=(0, 6))

        self.lbl_taxa  = ctk.CTkLabel(self, text="Taxa da Plataforma (0%): R$ 0,00",
                                      font=ctk.CTkFont(size=13), text_color="#d97706")
        self.lbl_taxa.pack(pady=4)

        self.lbl_venda = ctk.CTkLabel(self, text="Preço de Venda: R$ 0,00",
                                      font=ctk.CTkFont(size=26, weight="bold"),
                                      text_color="#2b7a4b")
        self.lbl_venda.pack(pady=(4, 24))

    def _clear_dynamic_rows(self):
        for w in self._rows:
            w.destroy()
        self._rows = []
        for w in self._total_row_widgets:
            w.destroy()
        self._total_row_widgets = []
        self._sep.grid_forget()

    def _add_row(self, grid_row: int, item: str, qty: str, unit: str, sub: str,
                 sub_color: str = "#ccc", item_color: str = "#aaa"):
        def cell(col, text, color, anchor="e"):
            lbl = ctk.CTkLabel(self.table_frame, text=text,
                               font=ctk.CTkFont(size=12), text_color=color,
                               anchor=anchor)
            lbl.grid(row=grid_row, column=col, sticky=anchor+"ew", padx=6, pady=1)
            self._rows.append(lbl)

        cell(0, item,  item_color, anchor="w")
        cell(1, qty,   "#888")
        cell(2, unit,  "#888")
        cell(3, sub,   sub_color)

    def render(self, breakdown: dict):
        """
        breakdown = {
            "materials": [
                {"label": str, "qty_g": float, "price_per_kg": float, "subtotal": float},
                ...
            ],
            "energia": {"horas": float, "custo_hora": float, "subtotal": float},
            "embalagem": float,
            "custo_total": float,
            "lucro_pct": float,
            "preco_com_lucro": float,
            "plataforma": str,
            "taxa_pct": float,
            "valor_taxa": float,
            "preco_final": float,
        }
        """
        self._clear_dynamic_rows()
        r = 2  # start after header + separator

        materials = breakdown.get("materials", [])
        if materials:
            for m in materials:
                qty_txt  = f"{m['qty_g']:.1f} g"
                unit_txt = f"R$ {m['price_per_kg']:.2f}/kg"
                sub_txt  = f"R$ {m['subtotal']:.2f}"
                self._add_row(r, f"  {m['label']}", qty_txt, unit_txt, sub_txt,
                              sub_color=ACCENT_COLOR)
                r += 1
        else:
            self._add_row(r, "  (sem materiais vinculados)", "—", "—", "R$ 0,00",
                          item_color="#555")
            r += 1

        # Operacional
        en = breakdown["energia"]
        _tot_min = round(en['horas'] * 60)
        _h, _m   = divmod(_tot_min, 60)
        time_str = f"{_h}h {_m}min" if _m else f"{_h}h"
        self._add_row(r, "  ⚡ Custo Operacional",
                      time_str,
                      f"R$ {en['custo_hora']:.2f}/h",
                      f"R$ {en['subtotal']:.2f}",
                      sub_color="#d97706")
        r += 1

        # Embalagem
        emb = breakdown["embalagem"]
        self._add_row(r, "  📦 Embalagem", "—", "—", f"R$ {emb:.2f}",
                      sub_color="#7a7a9a")
        r += 1

        # Separator before totals
        self._sep.grid(row=r, column=0, columnspan=4, sticky="ew", pady=4)
        r += 1

        # Custo Total (sessão inteira)
        def total_lbl(grid_row, text, color, size=13, weight="bold"):
            lbl = ctk.CTkLabel(self.table_frame, text=text,
                               font=ctk.CTkFont(size=size, weight=weight),
                               text_color=color)
            lbl.grid(row=grid_row, column=0, columnspan=4, sticky="e", padx=6, pady=1)
            self._total_row_widgets.append(lbl)

        unit_count     = breakdown.get("unit_count", 1)
        custo_unitario = breakdown.get("custo_unitario", breakdown["custo_total"])


        if unit_count > 1:
            total_lbl(r, f"Custo Total da Sessão ({unit_count} peças): R$ {breakdown['custo_total']:.2f}",
                      "#888", size=12, weight="normal")
            r += 1
            total_lbl(r, f"÷ {unit_count} peças = Custo Unit.: R$ {custo_unitario:.2f}",
                      "#d64545", size=14)
        else:
            total_lbl(r, f"Custo Total: R$ {breakdown['custo_total']:.2f}", "#d64545", size=14)
        r += 1
        total_lbl(r,     f"+ Margem de Lucro ({breakdown['lucro_pct']:.0f}%): R$ "
                         f"{breakdown['preco_com_lucro'] - custo_unitario:.2f}",
                  "#a0a0c0", size=12, weight="normal")
        r += 1

        # Update bottom fixed labels
        plat  = breakdown['plataforma']
        pct   = breakdown['taxa_pct'] * 100
        self.lbl_taxa.configure(
            text=f"Taxa da Plataforma ({plat} {pct:.0f}%): R$ {breakdown['valor_taxa']:.2f}"
        )
        unit_suffix = f" /unidade" if unit_count > 1 else ""
        self.lbl_venda.configure(
            text=f"Preço de Venda: R$ {breakdown['preco_final']:.2f}{unit_suffix}"
        )


        # ── Engenharia Reversa: Margem Real ──────────────────────────────────
        margem = breakdown.get("margem_real")
        pe     = breakdown.get("preco_estimado")
        if margem is not None and pe is not None:
            cor = "#10b981" if margem >= 0 else "#d64545"
            sinal = "+" if margem >= 0 else ""
            lbl = ctk.CTkLabel(
                self,
                text=(
                    f"🔍 Preço R$ {pe:.2f} → "
                    f"Margem Real: {sinal}{margem:.1f}%"
                ),
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=cor,
            )
            lbl.pack(pady=(0, 16))
            self._total_row_widgets.append(lbl)
        else:
            # Garante padding inferior consistente quando campo vazio
            pad = ctk.CTkLabel(self, text="", height=16)
            pad.pack()
            self._total_row_widgets.append(pad)


# ─── Main tab ─────────────────────────────────────────────────────────────────
class TabFinanceiro(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.TAXAS_PLATAFORMA = {
            "Shopee":         0.18,
            "Mercado Livre":  0.15,
            "OLX":            0.10,
            "Direto":         0.0,
        }

        self._ensure_config_cols()
        cfg = self._load_config()

        main = ModernCard(self)
        main.grid(row=0, column=0, padx=40, pady=40, sticky="nsew")
        main.grid_columnconfigure((0, 1), weight=1)
        main.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(main, text="Simulador Financeiro — Extrato Analítico",
                     font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, columnspan=2, pady=30)

        # ── Left panel: inputs ────────────────────────────────────────────
        self._modo_teste = False

        f_in = ctk.CTkScrollableFrame(main, fg_color="transparent")
        f_in.grid(row=1, column=0, padx=30, sticky="nsew")
        f_in.grid_columnconfigure(0, weight=1)

        # Toggle button row (toggle + save-to-acervo)
        toggle_row = ctk.CTkFrame(f_in, fg_color="transparent")
        toggle_row.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        toggle_row.grid_columnconfigure(0, weight=1)

        self.btn_toggle_teste = ctk.CTkButton(
            toggle_row, text="🧪 Testar Peça Avulsa",
            height=34, fg_color="#2a2a4a", hover_color="#3a3a6a",
            font=ctk.CTkFont(size=13),
            command=self._toggle_teste
        )
        self.btn_toggle_teste.grid(row=0, column=0, sticky="ew")

        self.btn_acao_acervo = ctk.CTkButton(
            toggle_row, text="💾  Salvar Peça no Acervo",
            height=34, width=200, fg_color="#2b4a2b", hover_color="#3a6a3a",
            font=ctk.CTkFont(size=12),
            command=self._acao_acervo
        )
        self.btn_acao_acervo.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.btn_acao_acervo.grid_remove()   # oculto até haver contexto

        # Piece selector (normal mode)
        sel_row = ctk.CTkFrame(f_in, fg_color="transparent")
        sel_row.grid(row=1, column=0, sticky="ew", pady=8)
        sel_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(sel_row, text="Selecione a Peça / Kit:").grid(
            row=0, column=0, sticky="e", padx=(0, 8))
        self.acervo_dict = self._get_acervo()
        self.peca_combo = SearchableComboBox(
            sel_row,
            values=list(self.acervo_dict.keys()) if self.acervo_dict else [],
            command=self._on_peca_selected,
            placeholder_text="Buscar peça ou kit..."
        )
        self.peca_combo.grid(row=0, column=1, sticky="ew")
        _make_info_btn(sel_row,
            "Selecione uma peça cadastrada no Acervo ou um Kit.\n"
            "O custo de material será calculado automaticamente\n"
            "com base nos filamentos vinculados e seus preços de rolo."
        ).grid(row=0, column=2, padx=(6, 0))
        self._sel_row_widget = sel_row

        # Manual test panel (hidden initially)
        self._teste_panel = _TesteManualPanel(f_in)
        self._teste_panel.grid(row=1, column=0, sticky="ew", pady=8)
        self._teste_panel.grid_remove()

        # Editable rows
        self.energia_var    = ctk.StringVar(value=cfg.get("calc_custo_hora", "1.50"))
        self.horas_int_var  = ctk.StringVar(value="1")
        self.min_var        = ctk.StringVar(value="0")
        self.lucro_var      = ctk.StringVar(value=cfg.get("calc_lucro_pct", "100"))
        self.embalagem_var = ctk.StringVar(value=cfg.get("calc_embalagem", "0.00"))

        rows_def = [
            (1, "Custo de Operação / Hora (R$):", self.energia_var, "calc_custo_hora",
             "Inclui energia elétrica, desgaste de peças,\n"
             "custo do bico, das correntes, etc.\n\n"
             "Dica: some a conta de luz mensal + manutenção\n"
             "e divida pelas horas que a impressora roda."),

            (3, "Margem de Lucro (%):", self.lucro_var, "calc_lucro_pct",
             "Percentual de lucro que você deseja obter\n"
             "sobre o custo total (material + operação + embalagem).\n\n"
             "100% = você dobra o custo → 50% de margem bruta."),

            (4, "Custo de Embalagem (R$):", self.embalagem_var, "calc_embalagem",
             "Custo fixo de embalagem por envio:\n"
             "caixas, plástico bolha, fita, etiqueta, etc.\n"
             "Salve o valor padrão e ajuste quando necessário."),
        ]

        for r, label, var, key, tip in rows_def:
            grid_r = r + 1  # shift down 1 to make room for toggle btn at row=0
            row_w = _EditableRow(f_in, label, tip, var, key)
            row_w.grid(row=grid_r, column=0, sticky="ew", pady=6)

        # ── Tempo de Impressão: horas (int) + minutos (int) ──────────────
        horas_row = ctk.CTkFrame(f_in, fg_color="transparent")
        horas_row.grid(row=3, column=0, sticky="ew", pady=6)
        horas_row.grid_columnconfigure(1, weight=1)
        lbl_hf = ctk.CTkFrame(horas_row, fg_color="transparent")
        lbl_hf.grid(row=0, column=0, sticky="e", padx=(0, 8))
        ctk.CTkLabel(lbl_hf, text="Tempo de Impressão:", anchor="e").pack(side="left")
        _make_info_btn(lbl_hf,
            "Informe a duração em horas e minutos inteiros.\n"
            "Ex: 6 h + 50 min (≠ 6.5 h).\n"
            "Não precisa salvar — varia por peça."
        ).pack(side="left", padx=(4, 0))
        hm_inner = ctk.CTkFrame(horas_row, fg_color="transparent")
        hm_inner.grid(row=0, column=1, sticky="w", padx=4)
        ctk.CTkEntry(hm_inner, textvariable=self.horas_int_var,
                     width=64, placeholder_text="h").pack(side="left")
        ctk.CTkLabel(hm_inner, text="h", text_color="#888", width=18).pack(side="left")
        ctk.CTkEntry(hm_inner, textvariable=self.min_var,
                     width=64, placeholder_text="min").pack(side="left", padx=(8, 0))
        ctk.CTkLabel(hm_inner, text="min", text_color="#888").pack(side="left", padx=(4, 0))

        # ── Quantidade de Cópias (múltiplos itens na mesma impressão) ─────────
        qtd_row = ctk.CTkFrame(f_in, fg_color="transparent")
        qtd_row.grid(row=7, column=0, sticky="ew", pady=6)
        qtd_row.grid_columnconfigure(1, weight=1)
        lbl_qf = ctk.CTkFrame(qtd_row, fg_color="transparent")
        lbl_qf.grid(row=0, column=0, sticky="e", padx=(0, 8))
        ctk.CTkLabel(lbl_qf, text="Quantidade de Cópias:", anchor="e").pack(side="left")
        _make_info_btn(lbl_qf,
            "Quantas peças idênticas foram impressas "
            "na mesma mesa / sessão?\n\n"
            "Ex: 6 chaveiros → informe 6.\n"
            "O custo individual será calculado dividindo "
            "o custo total por este valor.\n"
            "O Extrato mostrará tanto o custo unitário \n"
            "quanto o preço de venda por peça."
        ).pack(side="left", padx=(4, 0))
        self.qtd_var = ctk.StringVar(value="1")
        ctk.CTkEntry(qtd_row, textvariable=self.qtd_var,
                     width=80, height=32, placeholder_text="1",
                     font=ctk.CTkFont(size=13)).grid(
            row=0, column=1, sticky="w", padx=4)

        # Platform selector
        plat_row = ctk.CTkFrame(f_in, fg_color="transparent")
        plat_row.grid(row=8, column=0, sticky="ew", pady=6)
        plat_row.grid_columnconfigure(1, weight=1)
        lbl_pf = ctk.CTkFrame(plat_row, fg_color="transparent")
        lbl_pf.grid(row=0, column=0, sticky="e", padx=(0, 8))
        ctk.CTkLabel(lbl_pf, text="Modo de Envio / Plataforma:", anchor="e").pack(side="left")
        _make_info_btn(lbl_pf,
            "Taxa cobrada pela plataforma de venda:\n"
            "• Shopee: 18%\n"
            "• Mercado Livre: 15%\n"
            "• OLX: 10%\n"
            "• Direto (WhatsApp / local): 0%\n\n"
            "O preço final já é ajustado para que\n"
            "você receba a margem desejada após a taxa."
        ).pack(side="left", padx=(4, 0))
        self.plataforma_var = ctk.StringVar(value="Direto")
        ctk.CTkOptionMenu(plat_row, variable=self.plataforma_var,
                          values=list(self.TAXAS_PLATAFORMA.keys())).grid(
            row=0, column=1, sticky="ew", padx=4)

        # ── Engenharia Reversa: Preço Estimado de Venda ───────────────────
        rev_row = ctk.CTkFrame(f_in, fg_color="transparent")
        rev_row.grid(row=9, column=0, sticky="ew", pady=6)
        rev_row.grid_columnconfigure(1, weight=1)
        lbl_rv = ctk.CTkFrame(rev_row, fg_color="transparent")
        lbl_rv.grid(row=0, column=0, sticky="e", padx=(0, 8))
        ctk.CTkLabel(lbl_rv, text="Preço Estimado de Venda (R$):", anchor="e").pack(side="left")
        _make_info_btn(lbl_rv,
            "Opcional: informe o preço que você pretende cobrar.\n"
            "A calculadora mostrará qual Margem de Lucro Real\n"
            "você obtém com esse valor, já descontando\n"
            "a taxa da plataforma e todos os custos."
        ).pack(side="left", padx=(4, 0))
        self.preco_estimado_var = ctk.StringVar(value="")
        ctk.CTkEntry(rev_row, textvariable=self.preco_estimado_var,
                     width=120, height=32, placeholder_text="ex: 45.00",
                     font=ctk.CTkFont(size=13)).grid(
            row=0, column=1, sticky="w", padx=4)

        ctk.CTkButton(f_in, text="Calcular Extrato",
                       font=ctk.CTkFont(weight="bold", size=16),
                       height=45, fg_color=ACCENT_COLOR,
                       command=self._calcular).grid(
            row=10, column=0, pady=30, sticky="ew")

        # ── Right panel: analytical results ──────────────────────────────
        self.results_panel = _AnalyticalResultsPanel(main)
        self.results_panel.grid(row=1, column=1, padx=30, sticky="nsew", pady=(0, 30))

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _ensure_config_cols(self):
        cols = [
            ("calc_custo_hora", "TEXT DEFAULT '1.50'"),
            ("calc_lucro_pct",  "TEXT DEFAULT '100'"),
            ("calc_embalagem",  "TEXT DEFAULT '0.00'"),
        ]
        with db.get_connection() as conn:
            for col, defn in cols:
                try:
                    conn.execute(f"ALTER TABLE configuracoes ADD COLUMN {col} {defn}")
                    conn.commit()
                except Exception:
                    pass

    def _load_config(self):
        with db.get_connection() as conn:
            conn.row_factory = __import__("sqlite3").Row
            row = conn.execute("SELECT * FROM configuracoes WHERE id=1").fetchone()
            return dict(row) if row else {}

    def _get_acervo(self):
        with db.get_connection() as conn:
            pecas = conn.execute("SELECT id, nome_peca FROM acervo").fetchall()
            kits  = conn.execute("SELECT id, nome_kit FROM kits_acervo").fetchall() \
                    if self._table_exists(conn, "kits_acervo") else []
        result = {r[1]: ("peca", r[0]) for r in pecas}
        for r in kits:
            result[f"[KIT] {r[1]}"] = ("kit", r[0])
        return result

    def _table_exists(self, conn, name):
        return conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    def _toggle_teste(self):
        self._modo_teste = not self._modo_teste
        if self._modo_teste:
            self._sel_row_widget.grid_remove()
            self._teste_panel.grid()
            self.btn_acao_acervo.configure(
                text="💾  Salvar Peça no Acervo",
                fg_color="#2b4a2b", hover_color="#3a6a3a")
            self.btn_acao_acervo.grid()
            self.btn_toggle_teste.configure(
                text="✖ Voltar ao Acervo",
                fg_color="#4a1a1a", hover_color="#6b2a2a")
        else:
            self._teste_panel.grid_remove()
            self._sel_row_widget.grid()
            self.btn_toggle_teste.configure(
                text="🧪 Testar Peça Avulsa",
                fg_color="#2a2a4a", hover_color="#3a3a6a")
            self._on_peca_selected(self.peca_combo.get())

    def _on_peca_selected(self, val=None):
        """Atualiza o botão de ação conforme a peça selecionada (modo normal)."""
        if not self._modo_teste:
            sel = val or self.peca_combo.get()
            info = self.acervo_dict.get(sel)
            if info and info[0] == "peca":
                self.btn_acao_acervo.configure(
                    text="🔄  Sobrescrever Peça no Acervo",
                    fg_color="#2b4a6b", hover_color="#3a6a9a")
                self.btn_acao_acervo.grid()
            else:
                self.btn_acao_acervo.grid_remove()

    def _acao_acervo(self):
        """Despacha para salvar (modo avulso) ou sobrescrever (modo acervo)."""
        if self._modo_teste:
            self._salvar_acervo()
        else:
            self._atualizar_peca_acervo()

    def _salvar_acervo(self):
        """Persiste os materiais avulsos do teste nas tabelas acervo + acervo_filamentos."""
        from tkinter.simpledialog import askstring
        import datetime

        nome = askstring("Salvar no Acervo", "Nome da Peça:",
                         parent=self.winfo_toplevel())
        if not nome or not nome.strip():
            return

        tempo_h_str = askstring("Tempo de Impressão", "Horas (número inteiro):",
                                parent=self.winfo_toplevel()) or "0"
        tempo_m_str = askstring("Tempo de Impressão", "Minutos (0-59):",
                                parent=self.winfo_toplevel()) or "0"
        try:
            _h = int(tempo_h_str.strip()); _m = int(tempo_m_str.strip())
            if _m < 0 or _m >= 60 or _h < 0: raise ValueError
        except ValueError:
            return messagebox.showerror("Erro", "Tempo inválido.")
        tempo_str = f"{_h:02d}:{_m:02d}"

        custo_str = askstring("Preço de Custo", "Preço de custo (R$):",
                              parent=self.winfo_toplevel()) or "0"
        try:
            preco_custo = float(custo_str.replace(",", "."))
        except ValueError:
            return messagebox.showerror("Erro", "Preço inválido.")

        raw = self._teste_panel.get_materials()
        if not raw:
            return messagebox.showwarning("Aviso", "Adicione pelo menos um filamento antes de salvar.")

        hoje = datetime.date.today().isoformat()
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO acervo (nome_peca, data_registro, tempo_impressao, preco_custo) "
                "VALUES (?, ?, ?, ?)",
                (nome.strip(), hoje, tempo_str, preco_custo)
            )
            acervo_id = c.lastrowid

            for d in raw:
                fil_info = self._teste_panel._filamentos_dict.get(d["label"])
                if not fil_info:
                    continue
                fil_id   = fil_info["id"]
                peso_kg  = (d["purga_g"] + d["modelo_g"]) / 1000.0
                purga_kg = d["purga_g"] / 1000.0
                c.execute(
                    "INSERT INTO acervo_filamentos "
                    "(acervo_id, filamento_id, peso_gasto, peso_desperdicio) "
                    "VALUES (?, ?, ?, ?)",
                    (acervo_id, fil_id, peso_kg, purga_kg)
                )
            conn.commit()

        messagebox.showinfo("Sucesso", f"Peça '{nome.strip()}' salva no Acervo com sucesso!")

    def _atualizar_peca_acervo(self):
        """Atualiza tempo_impressao e preco_custo da peça selecionada com os dados da simulação atual."""
        peca = self.peca_combo.get()
        info = self.acervo_dict.get(peca)
        if not info or info[0] != "peca":
            return messagebox.showwarning("Aviso", "Selecione uma peça do Acervo primeiro.")
        acervo_id = info[1]

        try:
            _h = int(self.horas_int_var.get().strip() or "0")
            _m = int(self.min_var.get().strip() or "0")
        except ValueError:
            return messagebox.showerror("Erro", "Tempo inválido na calculadora.")
        tempo_str = f"{_h:02d}:{_m:02d}"

        # Calcular custo total da simulação atual
        try:
            ch = float(self.energia_var.get().replace(",", "."))
            hrs = _h + _m / 60.0
            embalagem = float(self.embalagem_var.get().replace(",", ".") or "0")
        except ValueError:
            return messagebox.showerror("Erro", "Valores da calculadora inválidos.")

        custo_mat = 0.0
        with db.get_connection() as conn:
            fils = conn.execute(
                "SELECT af.peso_gasto, f.peso_inicial, f.preco_rolo "
                "FROM acervo_filamentos af JOIN filamentos f ON af.filamento_id=f.id "
                "WHERE af.acervo_id=?", (acervo_id,)
            ).fetchall()
        for p_gasto, p_ini, p_rolo in fils:
            if p_ini and p_ini > 0:
                custo_mat += p_gasto * (p_rolo or 0.0) / p_ini
        preco_custo = custo_mat + ch * hrs + embalagem

        if not messagebox.askyesno("Confirmar",
            f"Atualizar '{peca}'?\n"
            f"Tempo: {tempo_str}\n"
            f"Custo: R$ {preco_custo:.2f}"):
            return

        with db.get_connection() as conn:
            conn.execute(
                "UPDATE acervo SET tempo_impressao=?, preco_custo=? WHERE id=?",
                (tempo_str, preco_custo, acervo_id)
            )
            conn.commit()
        messagebox.showinfo("Sucesso", "Peça atualizada com sucesso!")

    def _calcular(self):
        try:
            ch  = float(self.energia_var.get().replace(",", "."))
            _h  = int(self.horas_int_var.get().strip() or "0")
            _m  = int(self.min_var.get().strip() or "0")
            hrs = _h + _m / 60.0
            lucro     = float(self.lucro_var.get().replace(",", "."))
            embalagem = float(self.embalagem_var.get().replace(",", ".") or "0")
            qtd       = max(1, int(self.qtd_var.get().strip() or "1"))
        except ValueError:
            return messagebox.showerror("Erro", "Valores devem ser numéricos.")

        materials = []
        custo_mat = 0.0

        if self._modo_teste:
            # ── Manual test mode ─────────────────────────────────────────
            raw = self._teste_panel.get_materials()
            if not raw:
                return messagebox.showwarning("Aviso", "Adicione pelo menos um filamento.")
            for d in raw:
                total_g   = d["purga_g"] + d["modelo_g"]
                subtotal  = (total_g / 1000.0) * d["preco_kg"]
                custo_mat += subtotal
                label = d["label"]
                materials.append({
                    "label":        label,
                    "qty_g":        total_g,
                    "price_per_kg": d["preco_kg"],
                    "subtotal":     subtotal,
                })
        else:
            # ── Acervo / Kit mode ─────────────────────────────────────────
            peca = self.peca_combo.get()
            if not peca or peca not in self.acervo_dict:
                return
            tipo, oid = self.acervo_dict[peca]

            with db.get_connection() as conn:
                if tipo == "peca":
                    fils = conn.execute(
                        """SELECT af.peso_gasto, f.peso_inicial, f.preco_rolo,
                                  f.marca, f.material, f.cor
                           FROM acervo_filamentos af JOIN filamentos f ON af.filamento_id=f.id
                           WHERE af.acervo_id=?""", (oid,)
                    ).fetchall()
                else:
                    fils = conn.execute(
                        """SELECT af.peso_gasto, f.peso_inicial, f.preco_rolo,
                                  f.marca, f.material, f.cor
                           FROM kit_itens ki
                           JOIN acervo_filamentos af ON af.acervo_id = ki.acervo_id
                           JOIN filamentos f ON af.filamento_id = f.id
                           WHERE ki.kit_id=?""", (oid,)
                    ).fetchall()

            for p_gasto, p_ini, p_rolo, marca, material, cor in fils:
                if p_ini and p_ini > 0:
                    preco_kg  = (p_rolo or 0.0) / p_ini
                    qty_g     = p_gasto * 1000
                    subtotal  = p_gasto * preco_kg
                    custo_mat += subtotal
                    materials.append({
                        "label":        f"{marca} {material} ({cor})",
                        "qty_g":        qty_g,
                        "price_per_kg": preco_kg,
                        "subtotal":     subtotal,
                    })

        custo_op        = ch * hrs
        custo_total     = custo_mat + custo_op + embalagem

        # ── Divisão por quantidade de cópias ─────────────────────────────
        custo_unitario  = custo_total / qtd
        preco_com_lucro = custo_unitario * (1 + lucro / 100)

        plataforma  = self.plataforma_var.get()
        taxa_pct    = self.TAXAS_PLATAFORMA.get(plataforma, 0.0)
        preco_final = preco_com_lucro / (1 - taxa_pct) if taxa_pct > 0 else preco_com_lucro
        valor_taxa  = preco_final * taxa_pct

        # ── Engenharia Reversa: margem real sobre o preço estimado ────────
        margem_real = None
        preco_estimado_str = self.preco_estimado_var.get().strip().replace(",", ".")
        if preco_estimado_str:
            try:
                pe = float(preco_estimado_str)
                if pe > 0 and custo_unitario > 0:
                    receita_liquida = pe * (1 - taxa_pct)   # após desconto da taxa
                    margem_real     = (receita_liquida - custo_unitario) / custo_unitario * 100
            except ValueError:
                pass

        breakdown = {
            "materials":       materials,
            "energia":         {"horas": hrs, "custo_hora": ch, "subtotal": custo_op},
            "embalagem":       embalagem,
            "custo_total":     custo_total,         # custo da sessão inteira
            "custo_unitario":  custo_unitario,       # custo por peça
            "unit_count":      qtd,
            "lucro_pct":       lucro,
            "preco_com_lucro": preco_com_lucro,      # preço com lucro por peça
            "plataforma":      plataforma,
            "taxa_pct":        taxa_pct,
            "valor_taxa":      valor_taxa,
            "preco_final":     preco_final,          # preço final por peça
            "margem_real":     margem_real,          # None → não exibir
            "preco_estimado":  float(preco_estimado_str) if preco_estimado_str else None,
        }
        self.results_panel.render(breakdown)

