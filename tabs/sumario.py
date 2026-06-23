"""
tabs/sumario.py
───────────────
Sumário Financeiro — balanço detalhado por linha (não mais agrupado por mês).

Fontes de dados
---------------
  Receitas:
    • hist_impressoes  (status='Sucesso', preco_venda, data_impressao)
    • pedidos_v2       (valor_cobrado, data_entrega  ← data da entrega ou hoje)

  Gastos:
    • ferramentas_insumos  (ultimo_valor, data_registro ← hoje se nulo)
    • filamentos           (preco_rolo,  data_registro  ← hoje se nulo)
                           inclui Arquivados (ex: preto esgotado)

Colunas da tabela
-----------------
  Data (DD/MM/AAAA) | Descrição | Tipo | Valor (R$) | Resultado acum. | ✕
"""

import datetime
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox

from core.database import db
from core.db_worker import db_worker
from core.utils import ACCENT_COLOR, BORDER_COLOR, APP_BG_COLOR

_GREEN  = "#2b7a4b"
_RED    = "#d64545"
_BLUE   = "#89b4fa"
_YELLOW = "#e6c300"
_HEADER = "#1a1a2e"
_ODD    = "#1c1c2e"
_EVN    = "#181826"

TODAY = datetime.date.today().isoformat()   # "YYYY-MM-DD"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date(raw: str | None) -> str:
    """
    Accepts: YYYY-MM-DD, YYYY-MM, DD/MM/YYYY, or None.
    Returns: YYYY-MM-DD (padded with -01 for month-only) or TODAY as fallback.
    """
    if not raw:
        return TODAY
    raw = raw.strip()
    # Already full ISO
    if len(raw) == 10 and raw[4] == "-":
        return raw
    # Month-only ISO
    if len(raw) == 7 and raw[4] == "-":
        return raw + "-01"
    # DD/MM/YYYY
    if len(raw) == 10 and raw[2] == "/":
        try:
            d, m, y = raw.split("/")
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        except Exception:
            pass
    return TODAY


def _display_date(iso: str) -> str:
    """YYYY-MM-DD → DD/MM/YYYY"""
    try:
        d = datetime.datetime.strptime(iso[:10], "%Y-%m-%d")
        return d.strftime("%d/%m/%Y")
    except Exception:
        return iso


def _fmt(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ─────────────────────────────────────────────────────────────────────────────
# Table widget
# ─────────────────────────────────────────────────────────────────────────────

class _DetailTable(ctk.CTkFrame):
    """
    Scrollable table with one row per financial entry.
    Columns: Data | Descrição | Tipo | Valor (R$) | ✕
    """

    _COLS = [
        ("Data",          100, "center"),
        ("Descrição",     280, "w"),
        ("Tipo",          110, "center"),
        ("Valor (R$)",    130, "e"),
        ("Resultado",     130, "e"),
        ("",               42, "center"),   # delete button
    ]

    def __init__(self, parent, on_delete, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self._on_delete = on_delete
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=_HEADER, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        for ci, (label, minw, anchor) in enumerate(self._COLS):
            hdr.grid_columnconfigure(ci, weight=1 if ci in (1,) else 0, minsize=minw)
            ctk.CTkLabel(
                hdr, text=label,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=_BLUE, anchor=anchor, width=minw,
            ).grid(row=0, column=ci, padx=6, pady=8, sticky="ew")

        sep = ctk.CTkFrame(self, height=2, fg_color=ACCENT_COLOR)
        sep.grid(row=1, column=0, sticky="ew")

        # ── Scrollable body ───────────────────────────────────────────────
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=2, column=0, sticky="nsew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(wrap, bg="#141414", highlightthickness=0)
        self._vs = ctk.CTkScrollbar(wrap, orientation="vertical",
                                    command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vs.set)
        self._vs.grid(row=0, column=1, sticky="ns")
        self._canvas.grid(row=0, column=0, sticky="nsew")

        self._inner = ctk.CTkFrame(self._canvas, fg_color="transparent")
        self._win = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", lambda _: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        for w in (self._canvas, self._inner):
            w.bind("<Button-4>", lambda e: self._canvas.yview_scroll(-1, "units"))
            w.bind("<Button-5>", lambda e: self._canvas.yview_scroll(1,  "units"))

        # ── Footer totals ─────────────────────────────────────────────────
        self._footer = ctk.CTkFrame(self, fg_color="#111122", corner_radius=0,
                                    border_width=1, border_color=BORDER_COLOR)
        self._footer.grid(row=3, column=0, sticky="ew")
        for ci, (_, minw, _a) in enumerate(self._COLS):
            self._footer.grid_columnconfigure(ci, weight=1 if ci == 1 else 0, minsize=minw)

        self._tot_labels: list[ctk.CTkLabel] = []
        anchors = ["center", "w", "center", "e", "e", "center"]
        for ci, (_, minw, _a) in enumerate(self._COLS):
            lbl = ctk.CTkLabel(self._footer, text="—",
                               font=ctk.CTkFont(size=13, weight="bold"),
                               text_color="#ccc", anchor=anchors[ci], width=minw)
            lbl.grid(row=0, column=ci, padx=6, pady=10, sticky="ew")
            self._tot_labels.append(lbl)
        self._tot_labels[0].configure(text="TOTAL")

        self._row_widgets: list = []

    def _on_canvas_resize(self, e):
        mw = self._inner.winfo_reqwidth()
        self._canvas.itemconfig(self._win, width=max(e.width, mw))

    def render(self, rows: list[dict]):
        """
        rows: list of {date_iso, descricao, tipo, valor, sign, source, source_id}
          sign: +1 for receita, -1 for gasto
        Sorted descending by date_iso.
        """
        for w in self._row_widgets:
            try: w.destroy()
            except Exception: pass
        self._row_widgets = []

        t = self._inner
        # configure column widths
        for ci, (_, minw, _a) in enumerate(self._COLS):
            t.grid_columnconfigure(ci, weight=1 if ci == 1 else 0, minsize=minw)

        running = 0.0
        # Compute running total in chronological order, display reversed
        for ri, row in enumerate(rows):
            running += row["valor"] * row["sign"]

        # We'll display newest first; recalculate running descending
        cumul = 0.0
        for ri, row in enumerate(rows):
            cumul += row["valor"] * row["sign"]

        # Re-do accumulation in display order (newest first = reversed)
        running_totals = []
        cum = 0.0
        for row in reversed(rows):
            cum += row["valor"] * row["sign"]
            running_totals.insert(0, cum)

        bg_colors = [_ODD, _EVN]
        for ri, (row, rtot) in enumerate(zip(rows, running_totals)):
            bg = bg_colors[ri % 2]
            sign = row["sign"]
            val  = row["valor"]
            tipo = row["tipo"]
            color_val = _GREEN if sign > 0 else _RED
            color_res = _GREEN if rtot >= 0 else _RED

            cells = []

            # Date
            c = ctk.CTkFrame(t, fg_color=bg, corner_radius=0)
            c.grid(row=ri, column=0, sticky="nsew", padx=1, pady=0)
            ctk.CTkLabel(c, text=_display_date(row["date_iso"]),
                         font=ctk.CTkFont(size=11), text_color="#aaa",
                         anchor="center").pack(padx=6, pady=4)
            cells.append(c)

            # Descrição
            c = ctk.CTkFrame(t, fg_color=bg, corner_radius=0)
            c.grid(row=ri, column=1, sticky="nsew", padx=1, pady=0)
            ctk.CTkLabel(c, text=row["descricao"],
                         font=ctk.CTkFont(size=12), text_color="#ddd",
                         anchor="w").pack(padx=8, pady=4, anchor="w")
            cells.append(c)

            # Tipo badge
            tipo_colors = {
                "Pedido":       ("#1a3a2a", _GREEN),
                "Impressão":    ("#1a2a1a", "#7bc87a"),
                "Almoxarifado": ("#2a1a1a", _RED),
                "Filamento":    ("#1a1a3a", _BLUE),
            }
            tc_bg, tc_fg = tipo_colors.get(tipo, ("#222", "#aaa"))
            c = ctk.CTkFrame(t, fg_color=bg, corner_radius=0)
            c.grid(row=ri, column=2, sticky="nsew", padx=1, pady=0)
            badge = ctk.CTkFrame(c, fg_color=tc_bg, corner_radius=6)
            badge.pack(padx=6, pady=4)
            ctk.CTkLabel(badge, text=tipo, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=tc_fg).pack(padx=8, pady=2)
            cells.append(c)

            # Valor
            c = ctk.CTkFrame(t, fg_color=bg, corner_radius=0)
            c.grid(row=ri, column=3, sticky="nsew", padx=1, pady=0)
            prefix = "+" if sign > 0 else "-"
            ctk.CTkLabel(c, text=f"{prefix} {_fmt(val)}",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=color_val, anchor="e").pack(padx=8, pady=4, anchor="e")
            cells.append(c)

            # Resultado acumulado
            c = ctk.CTkFrame(t, fg_color=bg, corner_radius=0)
            c.grid(row=ri, column=4, sticky="nsew", padx=1, pady=0)
            ctk.CTkLabel(c, text=_fmt(rtot),
                         font=ctk.CTkFont(size=11),
                         text_color=color_res, anchor="e").pack(padx=8, pady=4, anchor="e")
            cells.append(c)

            # Delete button
            c = ctk.CTkFrame(t, fg_color=bg, corner_radius=0)
            c.grid(row=ri, column=5, sticky="nsew", padx=1, pady=0)
            src    = row.get("source")
            src_id = row.get("source_id")
            if src and src_id:
                ctk.CTkButton(
                    c, text="✕", width=28, height=28,
                    fg_color="transparent", text_color="#d64545",
                    hover_color="#3d1818", corner_radius=6,
                    command=lambda s=src, i=src_id: self._on_delete(s, i)
                ).pack(padx=4, pady=4)
            cells.append(c)

            self._row_widgets.extend(cells)

        if not rows:
            empty = ctk.CTkFrame(t, fg_color="transparent")
            empty.grid(row=0, column=0, columnspan=6, pady=40)
            ctk.CTkLabel(empty,
                         text="Nenhum dado financeiro encontrado para o período selecionado.",
                         font=ctk.CTkFont(size=14), text_color="#555").pack()
            self._row_widgets.append(empty)
            self._update_totals(0.0, 0.0)
            return

        total_rec  = sum(r["valor"] for r in rows if r["sign"] > 0)
        total_gast = sum(r["valor"] for r in rows if r["sign"] < 0)
        self._update_totals(total_rec, total_gast)

    def _update_totals(self, receita: float, gastos: float):
        resultado = receita - gastos
        color = _GREEN if resultado >= 0 else _RED
        self._tot_labels[0].configure(text="TOTAL")
        self._tot_labels[1].configure(text="")
        self._tot_labels[2].configure(text="")
        self._tot_labels[3].configure(text=_fmt(receita - gastos), text_color=color)
        self._tot_labels[4].configure(
            text=f"Rec: {_fmt(receita)}  Gas: {_fmt(gastos)}",
            text_color="#aaa"
        )
        self._tot_labels[5].configure(text="")


# ─────────────────────────────────────────────────────────────────────────────
# Main Tab
# ─────────────────────────────────────────────────────────────────────────────

class TabSumario(ctk.CTkFrame):
    """Sumário Financeiro — entrada detalhada com suporte a exclusão de linhas."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header bar ────────────────────────────────────────────────────
        top = ctk.CTkFrame(self, fg_color="#111", corner_radius=0,
                           border_width=1, border_color=BORDER_COLOR)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            top, text="📊  Sumário Financeiro",
            font=ctk.CTkFont(size=20, weight="bold"), text_color="white"
        ).grid(row=0, column=0, padx=20, pady=14, sticky="w")

        ctrl = ctk.CTkFrame(top, fg_color="transparent")
        ctrl.grid(row=0, column=1, sticky="e", padx=12)

        ctk.CTkLabel(ctrl, text="Ano:").pack(side="left", padx=(0, 6))
        self._year_var = ctk.StringVar(value=str(datetime.date.today().year))
        years = [str(y) for y in range(datetime.date.today().year, 2023, -1)] + ["Todos"]
        ctk.CTkOptionMenu(ctrl, variable=self._year_var, values=years,
                          width=100, command=lambda _: self.after(0, self._load)).pack(
            side="left", padx=(0, 10))

        ctk.CTkButton(
            ctrl, text="⟳ Atualizar", width=110,
            fg_color="#2a2a4a", hover_color="#3a3a6a",
            command=self._load
        ).pack(side="left")

        # ── Loading indicator ─────────────────────────────────────────────
        self._loading_lbl = ctk.CTkLabel(
            self, text="⏳ Carregando dados…",
            font=ctk.CTkFont(size=14), text_color="#888"
        )
        self._loading_lbl.grid(row=2, column=0)
        self._loading_lbl.grid_remove()

        # ── Summary cards row ─────────────────────────────────────────────
        cards_row = ctk.CTkFrame(self, fg_color="transparent")
        cards_row.grid(row=1, column=0, sticky="ew", padx=20, pady=(12, 0))
        cards_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def _card(parent, col, title, color):
            f = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=12,
                             border_width=1, border_color=BORDER_COLOR)
            f.grid(row=0, column=col, padx=8, sticky="ew")
            ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=12),
                         text_color="#888").pack(pady=(12, 2))
            val = ctk.CTkLabel(f, text="R$ —",
                               font=ctk.CTkFont(size=20, weight="bold"),
                               text_color=color)
            val.pack(pady=(0, 12))
            return val

        self._card_receita   = _card(cards_row, 0, "Total Receitas",   _GREEN)
        self._card_gastos    = _card(cards_row, 1, "Total Gastos",     _RED)
        self._card_resultado = _card(cards_row, 2, "Resultado Líquido", _BLUE)
        self._card_linhas    = _card(cards_row, 3, "Lançamentos",      "#aaa")

        # ── Detail table ──────────────────────────────────────────────────
        self._table = _DetailTable(self, on_delete=self._delete_entry)
        self._table.grid(row=2, column=0, sticky="nsew", padx=20, pady=(10, 20))

        self.after(0, self._load)

    # ── Data loading ──────────────────────────────────────────────────────

    def _load(self, *_):
        self._loading_lbl.grid()
        year = self._year_var.get()
        db_worker.run_query(
            query_fn=lambda: self._query(year),
            on_done=self._on_data,
            tk_widget=self,
        )

    def _query(self, year: str) -> list[dict]:
        """Runs on background thread. Returns flat list of financial entries."""
        rows: list[dict] = []

        def _matches_year(iso_date: str) -> bool:
            if year == "Todos":
                return True
            return iso_date.startswith(year)

        with db.get_connection() as conn:
            # ── 1. Receitas: impressões bem-sucedidas ─────────────────────
            hist = conn.execute(
                "SELECT id, nome_peca, data_impressao, preco_venda "
                "FROM hist_impressoes "
                "WHERE status='Sucesso' AND preco_venda IS NOT NULL AND preco_venda > 0"
            ).fetchall()
            for h in hist:
                iso = _parse_date(h[1])  # data_impressao
                if not _matches_year(iso):
                    continue
                rows.append({
                    "date_iso":  iso,
                    "descricao": f"Impressão: {h[1] or 'sem nome'}",
                    "tipo":      "Impressão",
                    "valor":     float(h[3] or 0),
                    "sign":      +1,
                    "source":    "hist_impressoes",
                    "source_id": h[0],
                })

            # ── 2. Receitas: pedidos entregues ────────────────────────────
            pedidos = conn.execute(
                "SELECT id, nome_cliente, data_entrega, valor_cobrado FROM pedidos_v2 "
                "WHERE status='Finalizado' AND valor_cobrado IS NOT NULL AND valor_cobrado > 0"
            ).fetchall()
            for p in pedidos:
                iso = _parse_date(p[2])  # data_entrega
                if not _matches_year(iso):
                    continue
                rows.append({
                    "date_iso":  iso,
                    "descricao": f"Pedido: {p[1] or 'cliente'}",
                    "tipo":      "Pedido",
                    "valor":     float(p[3] or 0),
                    "sign":      +1,
                    "source":    "pedidos_v2",
                    "source_id": p[0],
                })

            # ── 3. Gastos: almoxarifado ────────────────────────────────────
            almo = conn.execute(
                "SELECT id, nome, ultimo_valor, data_registro FROM ferramentas_insumos "
                "WHERE ultimo_valor IS NOT NULL AND ultimo_valor > 0"
            ).fetchall()
            for a in almo:
                iso = _parse_date(a[3])   # data_registro → fallback = TODAY
                if not _matches_year(iso):
                    continue
                rows.append({
                    "date_iso":  iso,
                    "descricao": f"Almoxarifado: {a[1]}",
                    "tipo":      "Almoxarifado",
                    "valor":     float(a[2] or 0),
                    "sign":      -1,
                    "source":    "ferramentas_insumos",
                    "source_id": a[0],
                })

            # ── 4. Gastos: filamentos (todos, inclusive Arquivados) ────────
            fils = conn.execute(
                "SELECT id, marca, cor, material, preco_rolo, data_registro, status "
                "FROM filamentos "
                "WHERE preco_rolo IS NOT NULL AND preco_rolo > 0"
            ).fetchall()
            for f in fils:
                iso = _parse_date(f[5])   # data_registro → fallback = TODAY
                if not _matches_year(iso):
                    continue
                status_tag = " [Esgotado]" if f[6] == "Arquivado" else ""
                rows.append({
                    "date_iso":  iso,
                    "descricao": f"Filamento: {f[1]} {f[2]}{status_tag}",
                    "tipo":      "Filamento",
                    "valor":     float(f[4] or 0),
                    "sign":      -1,
                    "source":    "filamentos",
                    "source_id": f[0],
                })

        # Sort newest first
        rows.sort(key=lambda r: r["date_iso"], reverse=True)
        return rows

    def _on_data(self, rows, error):
        self._loading_lbl.grid_remove()
        if error:
            messagebox.showerror("Erro", f"Falha ao carregar sumário:\n{error}")
            return

        total_rec  = sum(r["valor"] for r in rows if r["sign"] > 0)
        total_gast = sum(r["valor"] for r in rows if r["sign"] < 0)
        total_res  = total_rec - total_gast

        self._card_receita.configure(text=_fmt(total_rec))
        self._card_gastos.configure(text=_fmt(total_gast))
        res_color = _GREEN if total_res >= 0 else _RED
        self._card_resultado.configure(text=_fmt(total_res), text_color=res_color)
        self._card_linhas.configure(text=str(len(rows)))

        self._table.render(rows)

    # ── Delete entry ──────────────────────────────────────────────────────

    def _delete_entry(self, source: str, source_id: int):
        """
        source: table name ('hist_impressoes', 'pedidos_v2',
                             'ferramentas_insumos', 'filamentos')
        """
        labels = {
            "hist_impressoes":    "esta impressão do histórico",
            "pedidos_v2":         "este pedido",
            "ferramentas_insumos": "este item de almoxarifado",
            "filamentos":         "este filamento",
        }
        label = labels.get(source, "este registro")

        if not messagebox.askyesno(
            "Confirmar exclusão",
            f"Tem certeza que deseja excluir {label}?\n\n"
            "Esta ação não pode ser desfeita.",
        ):
            return

        try:
            with db.get_connection() as conn:
                if source == "hist_impressoes":
                    conn.execute("DELETE FROM hist_filamentos WHERE hist_id=?", (source_id,))
                    conn.execute("DELETE FROM hist_fotos    WHERE hist_id=?", (source_id,))
                    conn.execute("DELETE FROM hist_impressoes WHERE id=?",    (source_id,))
                elif source == "pedidos_v2":
                    conn.execute("DELETE FROM pedido_filamentos_avulsos WHERE pedido_id=?", (source_id,))
                    conn.execute("DELETE FROM pedidos_itens WHERE pedido_id=?", (source_id,))
                    conn.execute("DELETE FROM pedidos_v2 WHERE id=?",          (source_id,))
                elif source == "ferramentas_insumos":
                    conn.execute("DELETE FROM ferramentas_insumos WHERE id=?", (source_id,))
                elif source == "filamentos":
                    conn.execute("DELETE FROM acervo_filamentos WHERE filamento_id=?", (source_id,))
                    conn.execute("DELETE FROM hist_filamentos WHERE filamento_id=?",   (source_id,))
                    conn.execute("DELETE FROM filamentos WHERE id=?",                  (source_id,))
                conn.commit()
        except Exception as exc:
            messagebox.showerror("Erro", f"Falha ao excluir:\n{exc}")
            return

        self._load()
