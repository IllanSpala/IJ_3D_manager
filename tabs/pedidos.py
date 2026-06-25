import datetime
import customtkinter as ctk
from tkinter import messagebox
from core.state import app_state
from core.widgets import InlineEdit
from core.utils import ACCENT_COLOR

from core.widgets import InlineEdit, ModernCard

class PedidoCard(ModernCard):
    def __init__(self, master, data, **kwargs):
        self.p_id = data['id']
        self.data = data
        self.status = data['status']
        
        # Priority colors based on date
        b_color, f_color = self._get_priority_colors(data['data_entrega'], self.status)
        
        super().__init__(master, corner_radius=8, border_width=1, border_color=b_color, fg_color=f_color, **kwargs)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=12)
        inner.grid_columnconfigure(0, weight=1)

        # Header: Name and Delete button
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)
        
        nome_cli = data['nome_cliente']
        self.cliente_entry = InlineEdit(header, nome_cli, self._make_saver('nome_cliente'), font=ctk.CTkFont(weight="bold", size=16))
        self.cliente_entry.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(header, text="✕", width=24, height=24, corner_radius=12, 
                      fg_color="transparent", text_color="#d64545", hover_color="#3d1818", 
                      command=self._delete).grid(row=0, column=1, sticky="e")

        # Parts list
        parts_frame = ctk.CTkFrame(inner, fg_color="transparent")
        parts_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        for pc in data.get('pecas', []):
            ctk.CTkLabel(parts_frame, text=f"• {pc['nome_peca']}", text_color="#aaaaaa", font=ctk.CTkFont(size=12), anchor="w", justify="left").pack(anchor="w", padx=5)

        # Date and Value row
        info_row = ctk.CTkFrame(inner, fg_color="transparent")
        info_row.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        info_row.grid_columnconfigure(0, weight=1)
        
        # Date
        date_f = ctk.CTkFrame(info_row, fg_color="transparent")
        date_f.pack(side="left")
        self.data_entry = InlineEdit(date_f, self._format_date(data['data_entrega']), self._make_saver('data_entrega'), text_color="gray", font=ctk.CTkFont(size=12), width=70)
        self.data_entry.pack(side="left")

        # Value
        val_f = ctk.CTkFrame(info_row, fg_color="transparent")
        val_f.pack(side="right")
        ctk.CTkLabel(val_f, text="R$ ", text_color=ACCENT_COLOR, font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        self.valor_entry = InlineEdit(val_f, data['valor_cobrado'], self._make_saver_float('valor_cobrado'), text_color=ACCENT_COLOR, font=ctk.CTkFont(size=14, weight="bold"), width=60, is_double=True)
        self.valor_entry.pack(side="left")
        
        # Platform
        plat = data.get('plataforma_venda', 'Direto')
        if plat:
            ctk.CTkLabel(inner, text=f"[{plat}]", text_color="#777", font=ctk.CTkFont(size=10)).grid(row=3, column=0, sticky="w", pady=(0, 5))

        # Kanban Navigation Buttons
        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.grid(row=4, column=0, sticky="ew")
        
        if self.status in ("Imprimindo", "Encaminhado", "Entregue"):
            prev = {"Imprimindo": "A Fazer", "Encaminhado": "Imprimindo", "Entregue": "Encaminhado"}[self.status]
            ctk.CTkButton(btns, text="<", width=40, height=28, fg_color="#333", hover_color="#444", font=ctk.CTkFont(size=11), command=lambda s=prev: self._move(s)).pack(side="left")
            
        if self.status in ("A Fazer", "Imprimindo"):
            nxt = "Imprimindo" if self.status == "A Fazer" else "Encaminhado"
            ctk.CTkButton(btns, text=">", width=40, height=28, fg_color="#333", hover_color="#444", font=ctk.CTkFont(size=11), command=lambda s=nxt: self._move(s)).pack(side="right")
        elif self.status == "Encaminhado":
            ctk.CTkButton(btns, text="OK", width=40, height=28, fg_color="#2b7a4b", hover_color="#1d5c36", font=ctk.CTkFont(size=11, weight="bold"), command=lambda: self._move("Entregue")).pack(side="right")

    def _format_date(self, d_str):
        if not d_str: return ''
        import re
        m = re.search(r'(\d{2,4})[-/](\d{1,2})[-/](\d{1,2})', d_str)
        if m:
            p = m.groups()
            if len(p[0]) == 4:
                y, mo, d = p[0][2:], p[1], p[2]
            else:
                d, mo, y = p[0], p[1], p[2]
                if len(y) == 4: y = y[2:]
            return f"{int(d):02d}/{int(mo):02d}/{y}"
        return d_str

    def _get_priority_colors(self, data_entrega_str, status):
        if status == "A Fazer": return "#8b0000", "#2c1414"
        if status == "Imprimindo": return "#d97706", "#3a2001"
        if status in ("Encaminhado", "Entregue"): return "#059669", "#012b1e"
        return "#333333", "#1e1e1e"

    def _make_saver(self, field):
        def saver(val):
            app_state.update_pedido(self.p_id, {field: val})
            return True
        return saver

    def _make_saver_float(self, field):
        def saver(val):
            try:
                f_val = float(val.replace(',', '.'))
                app_state.update_pedido(self.p_id, {field: f_val})
                return True
            except ValueError:
                messagebox.showerror("Erro", "Valor numérico inválido.")
                return False
        return saver

    def _move(self, new_status):
        app_state.update_pedido(self.p_id, {'status': new_status})

    def _delete(self):
        if messagebox.askyesno("Confirmar", "Tem certeza que deseja excluir este pedido?"):
            import sqlite3
            from core.database import db
            with db.get_connection() as conn:
                conn.execute("DELETE FROM pedidos_itens WHERE pedido_id=?", (self.p_id,))
                conn.execute("DELETE FROM pedidos_v2 WHERE id=?", (self.p_id,))
                conn.commit()
            app_state.load_pedidos()

    def update_data(self, data):
        self.data = data
        self.cliente_entry.delete(0, 'end'); self.cliente_entry.insert(0, data['nome_cliente'])
        self.data_entry.delete(0, 'end'); self.data_entry.insert(0, self._format_date(data['data_entrega']))
        self.valor_entry.delete(0, 'end'); self.valor_entry.insert(0, str(data['valor_cobrado']))


class TabPedidos(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.form_visible = False

        self.toggle_btn = ctk.CTkButton(self, text="+ Criar Novo Pedido",
                                        fg_color="transparent", text_color=ACCENT_COLOR, font=ctk.CTkFont(size=16, weight="bold"),
                                        anchor="w", hover_color="#222", command=self._toggle_form)
        self.toggle_btn.pack(side="top", fill="x", padx=20, pady=(15, 5))

        self.form_card = ctk.CTkFrame(self, fg_color="#181818", corner_radius=12)

        f1 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f1.pack(fill="x", padx=15, pady=(15, 5))
        f1.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def field(parent_frame, col, label, var, placeholder=""):
            fc = ctk.CTkFrame(parent_frame, fg_color="transparent"); fc.grid(row=0, column=col, padx=8, sticky="ew")
            ctk.CTkLabel(fc, text=label, text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w")
            ctk.CTkEntry(fc, textvariable=var, height=35, placeholder_text=placeholder).pack(fill="x", expand=True)

        self.cliente_var = ctk.StringVar()
        self.data_var = ctk.StringVar()
        self.valor_var = ctk.StringVar()
        self.plataforma_var = ctk.StringVar(value="Direto")
        field(f1, 0, "Nome do Cliente", self.cliente_var)
        field(f1, 1, "Data (YYYY-MM-DD)", self.data_var, "Ex: 2024-12-25")
        field(f1, 2, "Valor (R$)", self.valor_var, "Ex: 150.00")
        
        fc_plat = ctk.CTkFrame(f1, fg_color="transparent"); fc_plat.grid(row=0, column=3, padx=8, sticky="ew")
        ctk.CTkLabel(fc_plat, text="Plataforma", text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w")
        ctk.CTkOptionMenu(fc_plat, variable=self.plataforma_var, values=["Shopee", "MercadoLivre", "OLX", "Direto"], height=35).pack(fill="x", expand=True)

        f2 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f2.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(f2, text="Adicionar Peça do Acervo:", text_color="gray", font=ctk.CTkFont(size=12)).pack(side="left", padx=(8, 5))
        self.acervo_dict = self._get_acervo()
        self.peca_combo = ctk.CTkComboBox(f2, values=list(self.acervo_dict.keys()) if self.acervo_dict else ["Acervo Vazio"], height=35)
        self.peca_combo.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(f2, text="+ Acervo", height=35, width=90, fg_color="#333", hover_color="#444", command=self._add_peca_ui).pack(side="left", padx=(5, 10))
        
        ctk.CTkButton(f2, text="+ Peça Avulsa", height=35, width=120, fg_color="#2b7a4b", hover_color="#1d5c36", font=ctk.CTkFont(weight="bold"), command=self._open_avulsa_modal).pack(side="left", padx=5)

        self.pecas_selecionadas = []
        self.pecas_ui_frame = ctk.CTkFrame(self.form_card, fg_color="transparent")
        self.pecas_ui_frame.pack(fill="x", padx=20, pady=(0, 10))

        submit_frame = ctk.CTkFrame(self.form_card, fg_color="transparent")
        submit_frame.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkButton(submit_frame, text="Confirmar Pedido", height=40, font=ctk.CTkFont(weight="bold", size=14), fg_color=ACCENT_COLOR, command=self._criar_pedido).pack(side="right")

        self.kanban = ctk.CTkFrame(self, fg_color="transparent")
        self.kanban.pack(side="top", fill="both", expand=True, padx=15, pady=10)
        self.kanban.grid_columnconfigure((0, 1, 2), weight=1)
        self.kanban.grid_rowconfigure(0, weight=1)

        self.col_fazer = self._make_col(0, "A Fazer")
        self.col_imp = self._make_col(1, "Imprimindo")
        self.col_encaminhado = self._make_col(2, "Encaminhado / Pronto")

        self.cards = {}
        app_state.subscribe('pedidos', self._on_state_change)
        app_state.load_pedidos()

    def _toggle_form(self):
        if self.form_visible:
            self.form_card.pack_forget()
            self.toggle_btn.configure(text="+ Criar Novo Pedido")
        else:
            self.form_card.pack(side="top", fill="x", padx=20, pady=(0, 10), before=self.kanban)
            self.toggle_btn.configure(text="- Ocultar Formulário")
        self.form_visible = not self.form_visible

    def _make_col(self, col, title):
        col_frame = ctk.CTkFrame(self.kanban, fg_color="#141414", corner_radius=15, border_width=1, border_color="#2a2a2a")
        col_frame.grid(row=0, column=col, sticky="nsew", padx=10)
        
        # Header
        header = ctk.CTkFrame(col_frame, fg_color="#1f1f1f", corner_radius=15)
        header.pack(fill="x", padx=2, pady=2)
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(weight="bold", size=16), text_color="#eee", pady=12).pack()
        
        # Scrollable area for cards
        s = ctk.CTkScrollableFrame(col_frame, fg_color="transparent")
        s.pack(fill="both", expand=True, padx=5, pady=5)
        return s

    def _get_acervo(self):
        import sqlite3
        from core.database import db
        with db.get_connection() as conn:
            rows = conn.execute("SELECT id, nome_peca FROM acervo").fetchall()
        return {r[1]: r[0] for r in rows}

    def _add_peca_ui(self):
        p = self.peca_combo.get()
        if not p or p not in self.acervo_dict: return
        acervo_id = self.acervo_dict[p]
        row_ui = ctk.CTkFrame(self.pecas_ui_frame, fg_color="#2b2b2b", corner_radius=8)
        row_ui.pack(side="left", padx=5, pady=5)
        ctk.CTkLabel(row_ui, text=p, font=ctk.CTkFont(size=13)).pack(side="left", padx=10, pady=5)
        
        custo_peca = 0.0
        import sqlite3
        from core.database import db
        with db.get_connection() as conn:
            rows = conn.execute("SELECT af.peso_gasto, af.peso_desperdicio, f.preco_rolo, f.peso_inicial FROM acervo_filamentos af JOIN filamentos f ON af.filamento_id = f.id WHERE af.acervo_id=?", (acervo_id,)).fetchall()
            for pg, pd, pr, pi in rows:
                if pi and pi > 0:
                    custo_peca += (pg + pd) * (pr / pi)
                    
        ctk.CTkButton(row_ui, text="✕", width=20, height=20, corner_radius=10, fg_color="transparent", text_color="#d64545", hover_color="#444", command=lambda r=row_ui, c=custo_peca, i=acervo_id: self._rem_peca(r, c, i)).pack(side="right", padx=5)
        self.pecas_selecionadas.append({"tipo": "acervo", "id": acervo_id, "ui": row_ui})
        
        try: v = float(self.valor_var.get().replace(",", ".")) if self.valor_var.get() else 0.0
        except ValueError: v = 0.0
        self.valor_var.set(f"{max(0.0, v + custo_peca):.2f}")

    def _add_avulsa_ui(self, nome, tempo, custo_total, filamentos):
        row_ui = ctk.CTkFrame(self.pecas_ui_frame, fg_color="#1e3a5f", corner_radius=8)
        row_ui.pack(side="left", padx=5, pady=5)
        ctk.CTkLabel(row_ui, text=f"Avulsa: {nome}", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=10, pady=5)
        
        idx = len(self.pecas_selecionadas)
        ctk.CTkButton(row_ui, text="✕", width=20, height=20, corner_radius=10, fg_color="transparent", text_color="#ff6b6b", hover_color="#444", command=lambda r=row_ui, c=custo_total, i=idx: self._rem_peca(r, c, i)).pack(side="right", padx=5)
        self.pecas_selecionadas.append({
            "tipo": "avulso", 
            "id": idx,
            "nome": nome, 
            "tempo": tempo, 
            "custo": custo_total, 
            "filamentos": filamentos, 
            "ui": row_ui
        })
        
        try: v = float(self.valor_var.get().replace(",", ".")) if self.valor_var.get() else 0.0
        except ValueError: v = 0.0
        self.valor_var.set(f"{max(0.0, v + custo_total):.2f}")

    def _open_avulsa_modal(self):
        AdicionarAvulsoModal(self.winfo_toplevel(), self._add_avulsa_ui)

    def _rem_peca(self, r, custo, item_id):
        r.destroy()
        self.pecas_selecionadas = [i for i in self.pecas_selecionadas if i["id"] != item_id]
        try: v = float(self.valor_var.get().replace(",", ".")) if self.valor_var.get() else 0.0
        except ValueError: v = 0.0
        self.valor_var.set(f"{max(0.0, v - custo):.2f}")

    def _criar_pedido(self):
        if not self.cliente_var.get() or not self.pecas_selecionadas:
            return messagebox.showerror("Erro", "Por favor, preencha o nome do cliente e adicione pelo menos uma peça.")
        try: v = float(self.valor_var.get().replace(",", ".")) if self.valor_var.get() else 0.0
        except ValueError: v = 0.0
        
        import sqlite3
        from core.database import db
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO pedidos_v2 (nome_cliente, data_entrega, valor_cobrado, status, plataforma_venda) VALUES (?,?,?,?,?)",
                      (self.cliente_var.get(), self.data_var.get(), v, "A Fazer", self.plataforma_var.get()))
            pid = c.lastrowid
            for item in self.pecas_selecionadas:
                if item.get("tipo") == "avulso":
                    c.execute("INSERT INTO pedidos_itens (pedido_id, tipo, nome_avulso, custo_est, nota) VALUES (?,?,?,?,?)",
                              (pid, "avulso", item["nome"], item["custo"], item.get("tempo", "")))
                    item_idx = c.lastrowid
                    for fil in item["filamentos"]:
                        c.execute("INSERT INTO pedido_filamentos_avulsos (pedido_id, item_idx, filamento_id, peso_modelo_g, peso_purga_g, custo_unit) VALUES (?,?,?,?,?,?)",
                                  (pid, item_idx, fil["fil_id"], fil["peso"], fil["purga"], fil["custo"]))
                else:
                    c.execute("INSERT INTO pedidos_itens (pedido_id, acervo_id, tipo) VALUES (?,?,?)", (pid, item["id"], "acervo"))
                item["ui"].destroy()
            conn.commit()
            
        self.pecas_selecionadas = []
        self.cliente_var.set(""); self.valor_var.set(""); self.data_var.set("")
        app_state.load_pedidos()

    def _on_state_change(self, event=None):
        if not event:
            # Full reload
            for w in self.cards.values(): w.destroy()
            self.cards = {}
            for data in app_state.pedidos:
                self._add_card(data)
        else:
            action = event.get('action')
            p_id = event.get('id')
            if action == 'update':
                if p_id in self.cards:
                    self.cards[p_id].destroy()
                    del self.cards[p_id]
                self._add_card(event['data'])

class AdicionarAvulsoModal(ctk.CTkToplevel):
    def __init__(self, master, on_add_callback):
        super().__init__(master)
        self.title("Adicionar Peça Avulsa")
        self.geometry("600x500")
        self.configure(fg_color="#181818")
        self.resizable(False, False)
        self.grab_set()
        
        self.on_add_callback = on_add_callback
        
        self.filamentos = app_state.get_filamentos_ativos()
        self.fil_rows = []
        
        f_top = ctk.CTkFrame(self, fg_color="transparent")
        f_top.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(f_top, text="Nome da Peça:").pack(anchor="w")
        self.nome_var = ctk.StringVar()
        ctk.CTkEntry(f_top, textvariable=self.nome_var, width=300).pack(anchor="w", pady=(0, 10))
        
        ctk.CTkLabel(f_top, text="Tempo Estimado (HH:MM) [opcional]:").pack(anchor="w")
        self.tempo_var = ctk.StringVar()
        ctk.CTkEntry(f_top, textvariable=self.tempo_var, width=150, placeholder_text="02:30").pack(anchor="w", pady=(0, 10))
        
        ctk.CTkLabel(self, text="Filamentos (Modelo + Purga):").pack(anchor="w", padx=20)
        
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#222", height=150)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(5, 10))
        
        ctk.CTkButton(self, text="+ Adicionar Filamento", fg_color="#333", hover_color="#444", command=self._add_fil_row).pack(anchor="w", padx=20, pady=(0, 10))
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(btn_frame, text="Cancelar", fg_color="transparent", hover_color="#333", command=self.destroy).pack(side="left")
        ctk.CTkButton(btn_frame, text="Salvar e Adicionar", fg_color=ACCENT_COLOR, command=self._save).pack(side="right")
        
    def _add_fil_row(self):
        row = ctk.CTkFrame(self.scroll, fg_color="#1a1a1a", corner_radius=6)
        row.pack(fill="x", pady=2)
        
        fil_var = ctk.StringVar()
        opts = [f"{f['marca']} {f['material']} {f['cor']}" for f in self.filamentos]
        opt = ctk.CTkOptionMenu(row, variable=fil_var, values=opts if opts else ["Sem Filamentos"], width=200)
        opt.pack(side="left", padx=5, pady=5)
        
        mod_var = ctk.StringVar(value="0")
        pur_var = ctk.StringVar(value="0")
        
        ctk.CTkLabel(row, text="M(g):", font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 2))
        ctk.CTkEntry(row, textvariable=mod_var, width=50).pack(side="left")
        
        ctk.CTkLabel(row, text="P(g):", font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 2))
        ctk.CTkEntry(row, textvariable=pur_var, width=50).pack(side="left")
        
        def _rem():
            row.destroy()
            self.fil_rows = [r for r in self.fil_rows if r["ui"] != row]
            
        ctk.CTkButton(row, text="X", width=25, fg_color="#d64545", hover_color="#8a2020", command=_rem).pack(side="right", padx=5)
        
        self.fil_rows.append({
            "ui": row,
            "fil_var": fil_var,
            "mod_var": mod_var,
            "pur_var": pur_var
        })
        
    def _save(self):
        nome = self.nome_var.get().strip()
        if not nome:
            messagebox.showerror("Erro", "Nome é obrigatório.", parent=self)
            return
            
        custo_total = 0.0
        fils_data = []
        
        for r in self.fil_rows:
            sel = r["fil_var"].get()
            f_id = None
            f_preco_g = 0.0
            
            for f in self.filamentos:
                if f"{f['marca']} {f['material']} {f['cor']}" == sel:
                    f_id = f["id"]
                    if f.get("peso_inicial") and f["peso_inicial"] > 0:
                        f_preco_g = float(f.get("preco_rolo", 0.0)) / float(f["peso_inicial"])
                    break
                    
            try: mod = float(r["mod_var"].get().replace(",", "."))
            except: mod = 0.0
            try: pur = float(r["pur_var"].get().replace(",", "."))
            except: pur = 0.0
            
            custo_item = (mod + pur) * f_preco_g
            custo_total += custo_item
            
            fils_data.append({
                "fil_id": f_id,
                "peso": mod,
                "purga": pur,
                "custo": custo_item
            })
            
        self.on_add_callback(nome, self.tempo_var.get(), custo_total, fils_data)
        self.destroy()

    def _add_card(self, data):
        status = data['status']
        if status == "A Fazer": parent = self.col_fazer
        elif status == "Imprimindo": parent = self.col_imp
        elif status in ("Encaminhado", "Entregue"): parent = self.col_encaminhado
        else: return
        
        card = PedidoCard(parent, data)
        card.pack(fill="x", padx=5, pady=8)
        self.cards[data['id']] = card
