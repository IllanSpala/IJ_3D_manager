import datetime
import re
import customtkinter as ctk
from tkinter import messagebox
from core.state import app_state
from core.widgets import InlineEdit, ModernCard
from core.utils import ACCENT_COLOR

def _migrate_old_pedidos():
    """Migra de forma robusta e dinâmica os dados da tabela antiga 'pedidos' para 'pedidos_v2'."""
    try:
        from core.database import db
        with db.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM pedidos_v2").fetchone()[0]
            if count == 0:
                table_exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pedidos'").fetchone()
                if table_exists:
                    old_cursor = conn.execute("SELECT * FROM pedidos")
                    old_pedidos = old_cursor.fetchall()
                    cols = [desc[0] for desc in old_cursor.description]
                    
                    c = conn.cursor()
                    for p in old_pedidos:
                        row = dict(zip(cols, p))
                        old_id = row.get('id')
                        nome = row.get('nome_cliente', 'Cliente Desconhecido')
                        data = row.get('data_entrega', '')
                        valor = row.get('valor_cobrado', row.get('valor', 0.0)) 
                        status = row.get('status', 'A Fazer')
                        
                        c.execute('''INSERT INTO pedidos_v2 
                                     (id, nome_cliente, data_entrega, valor_cobrado, status, plataforma_venda) 
                                     VALUES (?, ?, ?, ?, ?, 'Direto')''',
                                  (old_id, nome, data, valor, status))
                        
                        if 'acervo_id' in row and row.get('acervo_id') is not None:
                            c.execute("INSERT INTO pedidos_itens (pedido_id, acervo_id, tipo) VALUES (?, ?, 'acervo')", (old_id, row['acervo_id']))
                        elif 'peca' in row and row.get('peca'):
                            c.execute("INSERT INTO pedidos_itens (pedido_id, tipo, nome_avulso, custo_est, nota) VALUES (?, 'avulso', ?, 0, '')", (old_id, row['peca']))
                    conn.commit()
    except Exception as e:
        print(f"Erro na migração de pedidos: {e}")


class EditarPedidoModal(ctk.CTkToplevel):
    def __init__(self, master, p_id, data):
        super().__init__(master)
        self.title(f"Editar Pedido #{p_id}")
        self.geometry("620x700")
        self.configure(fg_color="#181818")
        self.resizable(False, False)
        self.grab_set()

        self.p_id = p_id
        self.data_origial = data
        self.pecas_novas = []
        self.pecas_removidas_ids = []

        # Variáveis de controle dos campos cadastrais
        self.nome_var = ctk.StringVar(value=data.get('nome_cliente', ''))
        self.data_var = ctk.StringVar(value=data.get('data_entrega', ''))
        val_cobrado = float(data.get('valor_cobrado', 0.0))
        self.valor_var = ctk.StringVar(value=f"{val_cobrado:.2f}")
        self.status_var = ctk.StringVar(value=data.get('status', 'A Fazer'))
        self.plat_var = ctk.StringVar(value=data.get('plataforma_venda', 'Direto'))

        # Estrutura principal com Scroll para conter todos os elementos de forma fluida
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # ─── Seção 1: Dados Cadastrais do Pedido ───
        f_dados = ctk.CTkFrame(self.scroll, fg_color="#1f1f1f", corner_radius=6, border_width=1, border_color="#333")
        f_dados.pack(fill="x", padx=10, pady=5)

        def field(parent, label, var, is_option=False, options=None):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(fill="x", padx=15, pady=6)
            ctk.CTkLabel(f, text=label, text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w")
            if is_option:
                ctk.CTkOptionMenu(f, variable=var, values=options, fg_color="#111", button_color="#333", height=32).pack(fill="x")
            else:
                ctk.CTkEntry(f, textvariable=var, height=32, fg_color="#111", border_color="#444").pack(fill="x")

        field(f_dados, "Nome do Cliente", self.nome_var)
        field(f_dados, "Data de Entrega (YYYY-MM-DD)", self.data_var)
        field(f_dados, "Valor Cobrado (R$)", self.valor_var)
        field(f_dados, "Plataforma", self.plat_var, is_option=True, options=["Shopee", "MercadoLivre", "OLX", "Direto"])
        field(f_dados, "Status", self.status_var, is_option=True, options=["A Fazer", "Imprimindo", "Encaminhado", "Entregue"])

        # ─── Seção 2: Gerenciamento de Itens ───
        ctk.CTkLabel(self.scroll, text="Itens do Pedido", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", padx=15, pady=(15, 5))

        self.f_itens = ctk.CTkFrame(self.scroll, fg_color="#141414", corner_radius=6, border_width=1, border_color="#2a2a2a")
        self.f_itens.pack(fill="x", padx=10, pady=5)

        # Componentes de adição de peças (replicando funcionalidade da TabPedidos)
        f_add = ctk.CTkFrame(self.scroll, fg_color="transparent")
        f_add.pack(fill="x", padx=10, pady=10)
        
        from core.database import db
        with db.get_connection() as conn:
            rows = conn.execute("SELECT id, nome_peca FROM acervo").fetchall()
        self.acervo_dict = {r[1]: r[0] for r in rows}

        self.peca_combo = ctk.CTkComboBox(f_add, values=list(self.acervo_dict.keys()) if self.acervo_dict else ["Acervo Vazio"], height=35, fg_color="#111", border_color="#444")
        self.peca_combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ctk.CTkButton(f_add, text="+ Acervo", height=35, width=85, fg_color="#333", hover_color="#444", command=self._add_peca_acervo).pack(side="left", padx=2)
        ctk.CTkButton(f_add, text="+ Avulsa", height=35, width=85, fg_color="#2b7a4b", hover_color="#1d5c36", font=ctk.CTkFont(weight="bold"), command=self._open_avulsa_modal).pack(side="left", padx=2)

        # Carrega itens existentes no banco de dados
        self._carregar_itens_banco()

        # Botões de ação do Modal (Fixo na parte inferior da janela)
        btn_frame = ctk.CTkFrame(self, fg_color="#1c1c1c", height=60, corner_radius=0)
        btn_frame.pack(side="bottom", fill="x")
        btn_frame.pack_propagate(False)

        ctk.CTkButton(btn_frame, text="Cancelar", height=35, fg_color="transparent", border_width=1, border_color="#444", hover_color="#333", command=self.destroy).pack(side="left", padx=20, pady=12)
        ctk.CTkButton(btn_frame, text="Salvar Alterações", height=35, font=ctk.CTkFont(weight="bold"), fg_color=ACCENT_COLOR, hover_color="#007acc", command=self._save).pack(side="right", padx=20, pady=12)

    def _carregar_itens_banco(self):
        from core.database import db
        with db.get_connection() as conn:
            # Busca itens vinculados ao acervo
            pecas_acervo = conn.execute(
                """SELECT pi.id, a.nome_peca, 'acervo' as tipo
                   FROM pedidos_itens pi
                   JOIN acervo a ON pi.acervo_id=a.id
                   WHERE pi.pedido_id=? AND (pi.tipo='acervo' OR pi.tipo IS NULL)""", (self.p_id,)
            ).fetchall()
            
            # Busca itens cadastrados de forma avulsa
            pecas_avulsas = conn.execute(
                """SELECT id, COALESCE(nome_avulso, nome_custom, 'Peça Avulsa') as nome_peca, 'avulso' as tipo, custo_est
                   FROM pedidos_itens
                   WHERE pedido_id=? AND tipo='avulso'""", (self.p_id,)
            ).fetchall()

        for item in pecas_acervo:
            self._render_item_linha(item['id'], item['nome_peca'], item['tipo'], do_banco=True)
        for item in pecas_avulsas:
            self._render_item_linha(item['id'], item['nome_peca'], item['tipo'], do_banco=True, custo=item['custo_est'])

    def _render_item_linha(self, item_id, nome, tipo, do_banco=False, custo=0.0):
        row = ctk.CTkFrame(self.f_itens, fg_color="#1c1c1c" if do_banco else "#1a2e3a", corner_radius=4, height=32)
        row.pack(fill="x", padx=5, pady=3)
        row.pack_propagate(False)

        prefix = "• " if tipo == "acervo" else "🔧 Avulsa: "
        ctk.CTkLabel(row, text=f"{prefix}{nome}", font=ctk.CTkFont(size=12), text_color="#eee").pack(side="left", padx=10)

        # Botão de remoção (atua de forma lógica dependendo da origem do dado)
        if do_banco:
            cmd = lambda: self._remover_item_banco(item_id, row, custo)
        else:
            cmd = lambda: self._remover_item_novo(item_id, row, custo)

        ctk.CTkButton(row, text="✕", width=22, height=22, corner_radius=4, fg_color="transparent", text_color="#d64545", hover_color="#3d1818", command=cmd).pack(side="right", padx=5, pady=5)

    def _add_peca_acervo(self):
        p = self.peca_combo.get()
        if not p or p not in self.acervo_dict: return
        acervo_id = self.acervo_dict[p]

        custo_peca = 0.0
        from core.database import db
        with db.get_connection() as conn:
            rows = conn.execute("SELECT af.peso_gasto, af.peso_desperdicio, f.preco_rolo, f.peso_inicial FROM acervo_filamentos af JOIN filamentos f ON af.filamento_id = f.id WHERE af.acervo_id=?", (acervo_id,)).fetchall()
            for pg, pd, pr, pi in rows:
                if pi and pi > 0:
                    custo_peca += (pg + pd) * (pr / pi)

        idx = len(self.pecas_novas) + 100000 # Offset para IDs temporários locais
        item_ref = {"tipo": "acervo", "id_local": idx, "acervo_id": acervo_id, "custo": custo_peca}
        self.pecas_novas.append(item_ref)
        
        self._render_item_linha(idx, p, "acervo", do_banco=False, custo=custo_peca)
        self._atualizar_valor_soma(custo_peca)

    def _add_avulsa_callback(self, nome, tempo, custo_total, filamentos):
        idx = len(self.pecas_novas) + 100000
        item_ref = {
            "tipo": "avulso",
            "id_local": idx,
            "nome": nome,
            "tempo": tempo,
            "custo": custo_total,
            "filamentos": filamentos
        }
        self.pecas_novas.append(item_ref)
        self._render_item_linha(idx, nome, "avulso", do_banco=False, custo=custo_total)
        self._atualizar_valor_soma(custo_total)

    def _open_avulsa_modal(self):
        AdicionarAvulsoModal(self, self._add_avulsa_callback)

    def _remover_item_banco(self, item_id, row_ui, custo):
        self.pecas_removidas_ids.append(item_id)
        row_ui.destroy()
        self._atualizar_valor_soma(-custo)

    def _remover_item_novo(self, id_local, row_ui, custo):
        self.pecas_novas = [i for i in self.pecas_novas if i.get("id_local") != id_local]
        row_ui.destroy()
        self._atualizar_valor_soma(-custo)

    def _atualizar_valor_soma(self, valor_diferenca):
        try:
            curr = float(self.valor_var.get().replace(",", "."))
        except ValueError:
            curr = 0.0
        self.valor_var.set(f"{max(0.0, curr + valor_diferenca):.2f}")

    def _save(self):
        try:
            v_formatado = float(self.valor_var.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Erro", "O valor cobrado deve ser numérico.", parent=self)
            return

        from core.database import db
        with db.get_connection() as conn:
            c = conn.cursor()
            
            # 1. Atualiza dados escalares do pedido
            c.execute("""UPDATE pedidos_v2 
                         SET nome_cliente=?, data_entrega=?, valor_cobrado=?, status=?, plataforma_venda=? 
                         WHERE id=?""",
                      (self.nome_var.get(), self.data_var.get(), v_formatado, self.status_var.get(), self.plat_var.get(), self.p_id))
            
            # 2. Processa remoções solicitadas do banco
            for rem_id in self.pecas_removidas_ids:
                c.execute("DELETE FROM pedido_filamentos_avulsos WHERE item_idx=?", (rem_id,))
                c.execute("DELETE FROM pedidos_itens WHERE id=?", (rem_id,))
                
            # 3. Processa inserções de novos itens acoplados
            for item in self.pecas_novas:
                if item["tipo"] == "acervo":
                    c.execute("INSERT INTO pedidos_itens (pedido_id, acervo_id, tipo) VALUES (?,?,?)", 
                              (self.p_id, item["acervo_id"], "acervo"))
                elif item["tipo"] == "avulso":
                    c.execute("INSERT INTO pedidos_itens (pedido_id, tipo, nome_avulso, custo_est, nota) VALUES (?,?,?,?,?)",
                              (self.p_id, "avulso", item["nome"], item["custo"], item.get("tempo", "")))
                    item_idx = c.lastrowid
                    for fil in item["filamentos"]:
                        c.execute("""INSERT INTO pedido_filamentos_avulsos 
                                     (pedido_id, item_idx, filamento_id, peso_modelo_g, peso_purga_g, custo_unit) 
                                     VALUES (?,?,?,?,?,?)""",
                                  (self.p_id, item_idx, fil["fil_id"], fil["peso"], fil["purga"], fil["custo"]))
            conn.commit()

        app_state.load_pedidos()
        self.destroy()


class PedidoCard(ModernCard):
    def __init__(self, master, data, **kwargs):
        self.p_id = data['id']
        self.data = data
        self.status = data.get('status', 'A Fazer')
        
        b_color, f_color = self._get_priority_colors(data.get('data_entrega'), self.status)
        
        super().__init__(master, corner_radius=6, border_width=0, fg_color=f_color, **kwargs)

        self.top_line = ctk.CTkFrame(self, height=3, fg_color=b_color, corner_radius=0)
        self.top_line.pack(fill="x", side="top")

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", padx=10, pady=8)

        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))
        
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", fill="x", expand=True)

        nome_cli = data.get('nome_cliente', '')
        self.cliente_entry = InlineEdit(title_frame, nome_cli, self._make_saver('nome_cliente'), font=ctk.CTkFont(weight="bold", size=13))
        self.cliente_entry.pack(side="left")

        plat = data.get('plataforma_venda', 'Direto')
        if plat and plat != "Direto":
            self.plat_lbl = ctk.CTkLabel(title_frame, text=f" {plat.upper()} ", text_color="#aaa", fg_color="#222", corner_radius=4, font=ctk.CTkFont(size=9, weight="bold"))
            self.plat_lbl.pack(side="left", padx=(6, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        
        # Botão para abrir o novo gerenciador dinâmico de edição
        ctk.CTkButton(actions, text="✏", width=22, height=22, corner_radius=4, 
                      fg_color="transparent", text_color="#aaa", hover_color="#333", font=ctk.CTkFont(size=12),
                      command=self._open_edit_modal).pack(side="left", padx=2)
        ctk.CTkButton(actions, text="✕", width=22, height=22, corner_radius=4, 
                      fg_color="transparent", text_color="#d64545", hover_color="#3d1818", font=ctk.CTkFont(size=12),
                      command=self._delete).pack(side="left")

        pecas = data.get('pecas', [])
        if pecas:
            parts_frame = ctk.CTkFrame(inner, fg_color="transparent")
            parts_frame.pack(fill="x", pady=(0, 6))
            for pc in pecas:
                ctk.CTkLabel(parts_frame, text=f"• {pc.get('nome_peca', '')}", text_color="#bbb", font=ctk.CTkFont(size=11), justify="left").pack(anchor="w", pady=0)

        info_row = ctk.CTkFrame(inner, fg_color="transparent")
        info_row.pack(fill="x", pady=(0, 8))
        
        date_f = ctk.CTkFrame(info_row, fg_color="#222", corner_radius=4)
        date_f.pack(side="left")
        self.data_entry = InlineEdit(date_f, self._format_date(data.get('data_entrega')), self._make_saver('data_entrega'), text_color="#aaa", font=ctk.CTkFont(size=11), width=65)
        self.data_entry.pack(padx=6, pady=2)

        val_f = ctk.CTkFrame(info_row, fg_color="transparent")
        val_f.pack(side="right")
        ctk.CTkLabel(val_f, text="R$ ", text_color="#00a2ff", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        
        val_formatado = f"{float(data.get('valor_cobrado', 0.0)):.2f}"
        self.valor_entry = InlineEdit(val_f, val_formatado, self._make_saver_float('valor_cobrado'), text_color="#00a2ff", font=ctk.CTkFont(size=13, weight="bold"), width=55, is_double=True)
        self.valor_entry.pack(side="left")

        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.pack(fill="x")
        
        btn_font = ctk.CTkFont(size=11, weight="bold")
        if self.status in ("Imprimindo", "Encaminhado", "Entregue"):
            prev = {"Imprimindo": "A Fazer", "Encaminhado": "Imprimindo", "Entregue": "Encaminhado"}[self.status]
            ctk.CTkButton(btns, text="◀ Ant", height=24, fg_color="#2a2a2a", hover_color="#444", text_color="#aaa", font=btn_font, command=lambda s=prev: self._move(s)).pack(side="left", expand=True, fill="x", padx=(0, 2))
            
        if self.status in ("A Fazer", "Imprimindo"):
            nxt = "Imprimindo" if self.status == "A Fazer" else "Encaminhado"
            ctk.CTkButton(btns, text="Próx ▶", height=24, fg_color="#2a2a2a", hover_color="#444", text_color="#aaa", font=btn_font, command=lambda s=nxt: self._move(s)).pack(side="right", expand=True, fill="x", padx=(2, 0))
        elif self.status == "Encaminhado":
            ctk.CTkButton(btns, text="✔ Fim", height=24, fg_color="#2b7a4b", hover_color="#1d5c36", text_color="white", font=btn_font, command=lambda: self._move("Entregue")).pack(side="right", expand=True, fill="x", padx=(2, 0))

    def _open_edit_modal(self):
        EditarPedidoModal(self.winfo_toplevel(), self.p_id, self.data)

    def _format_date(self, d_str):
        if not d_str: return ''
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
        if status == "A Fazer": return "#d64545", "#181414"
        if status == "Imprimindo": return "#d97706", "#1a1612"
        if status in ("Encaminhado", "Entregue"): return "#10b981", "#121815"
        return "#555555", "#161616"

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
            from core.database import db
            with db.get_connection() as conn:
                conn.execute("DELETE FROM pedidos_itens WHERE pedido_id=?", (self.p_id,))
                conn.execute("DELETE FROM pedidos_v2 WHERE id=?", (self.p_id,))
                conn.commit()
            app_state.load_pedidos()

    def update_data(self, data):
        self.data = data
        self.cliente_entry.delete(0, 'end')
        self.cliente_entry.insert(0, data['nome_cliente'])
        self.data_entry.delete(0, 'end')
        self.data_entry.insert(0, self._format_date(data['data_entrega']))
        
        self.valor_entry.delete(0, 'end')
        val_formatado = f"{float(data.get('valor_cobrado', 0.0)):.2f}"
        self.valor_entry.insert(0, val_formatado)

        self.status = data.get('status', 'A Fazer')
        b_color, f_color = self._get_priority_colors(data.get('data_entrega'), self.status)
        self.configure(fg_color=f_color)
        self.top_line.configure(fg_color=b_color)


class TabPedidos(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        _migrate_old_pedidos()
        self.form_visible = False

        self.top_control = ctk.CTkFrame(self, fg_color="transparent")
        self.top_control.pack(side="top", fill="x", padx=20, pady=(15, 5))
        
        self.toggle_btn = ctk.CTkButton(self.top_control, text="+ Adicionar Pedido",
                                        fg_color=ACCENT_COLOR, text_color="white", font=ctk.CTkFont(size=14, weight="bold"),
                                        hover_color="#007acc", command=self._toggle_form)
        self.toggle_btn.pack(side="left")

        self.form_card = ctk.CTkFrame(self, fg_color="#181818", corner_radius=8, border_width=1, border_color="#333")

        f1 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f1.pack(fill="x", padx=15, pady=(15, 5))
        f1.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def field(parent_frame, col, label, var, placeholder=""):
            fc = ctk.CTkFrame(parent_frame, fg_color="transparent")
            fc.grid(row=0, column=col, padx=8, sticky="ew")
            ctk.CTkLabel(fc, text=label, text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w")
            ctk.CTkEntry(fc, textvariable=var, height=35, placeholder_text=placeholder, fg_color="#111", border_color="#444").pack(fill="x", expand=True)

        self.cliente_var = ctk.StringVar()
        self.data_var = ctk.StringVar()
        self.valor_var = ctk.StringVar()
        self.plataforma_var = ctk.StringVar(value="Direto")
        
        field(f1, 0, "Nome do Cliente", self.cliente_var)
        field(f1, 1, "Data (YYYY-MM-DD)", self.data_var, "Ex: 2024-12-25")
        field(f1, 2, "Valor (R$)", self.valor_var, "Ex: 150.00")
        
        fc_plat = ctk.CTkFrame(f1, fg_color="transparent")
        fc_plat.grid(row=0, column=3, padx=8, sticky="ew")
        ctk.CTkLabel(fc_plat, text="Plataforma", text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w")
        ctk.CTkOptionMenu(fc_plat, variable=self.plataforma_var, values=["Shopee", "MercadoLivre", "OLX", "Direto"], height=35, fg_color="#111", button_color="#333").pack(fill="x", expand=True)

        f2 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f2.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(f2, text="Adicionar Peça:", text_color="gray", font=ctk.CTkFont(size=12)).pack(side="left", padx=(8, 5))
        self.acervo_dict = self._get_acervo()
        self.peca_combo = ctk.CTkComboBox(f2, values=list(self.acervo_dict.keys()) if self.acervo_dict else ["Acervo Vazio"], height=35, fg_color="#111", border_color="#444")
        self.peca_combo.pack(side="left", fill="x", expand=True, padx=5)
        
        ctk.CTkButton(f2, text="+ Acervo", height=35, width=90, fg_color="#333", hover_color="#444", command=self._add_peca_ui).pack(side="left", padx=(5, 5))
        ctk.CTkButton(f2, text="+ Avulsa", height=35, width=90, fg_color="#2b7a4b", hover_color="#1d5c36", font=ctk.CTkFont(weight="bold"), command=self._open_avulsa_modal).pack(side="left", padx=5)

        self.pecas_selecionadas = []
        self.pecas_ui_frame = ctk.CTkFrame(self.form_card, fg_color="transparent")
        self.pecas_ui_frame.pack(fill="x", padx=20, pady=(0, 10))

        submit_frame = ctk.CTkFrame(self.form_card, fg_color="transparent")
        submit_frame.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkButton(submit_frame, text="Confirmar Pedido", height=40, font=ctk.CTkFont(weight="bold", size=14), fg_color=ACCENT_COLOR, hover_color="#007acc", command=self._criar_pedido).pack(side="right")

        self.kanban = ctk.CTkFrame(self, fg_color="transparent")
        self.kanban.pack(side="top", fill="both", expand=True, padx=15, pady=10)
        self.kanban.grid_columnconfigure((0, 1, 2), weight=1, uniform="col")
        self.kanban.grid_rowconfigure(0, weight=1)

        self.col_fazer = self._make_col(0, "A Fazer", "#1a1a2e")
        self.col_imp = self._make_col(1, "Imprimindo", "#2e2116")
        self.col_encaminhado = self._make_col(2, "Pronto / Encaminhado", "#162e21")

        self.cards = {}
        app_state.subscribe('pedidos', self._on_state_change)
        app_state.subscribe('acervo', self._update_acervo_combo)
        app_state.load_pedidos()

    def _toggle_form(self):
        if self.form_visible:
            self.form_card.pack_forget()
            self.toggle_btn.configure(text="+ Adicionar Pedido", fg_color=ACCENT_COLOR)
        else:
            self.form_card.pack(side="top", fill="x", padx=20, pady=(0, 10), before=self.kanban)
            self.toggle_btn.configure(text="✕ Cancelar", fg_color="#333")
        self.form_visible = not self.form_visible

    def _make_col(self, col, title, header_color):
        col_frame = ctk.CTkFrame(self.kanban, fg_color="#141414", corner_radius=8, border_width=1, border_color="#222")
        col_frame.grid(row=0, column=col, sticky="nsew", padx=10)
        
        header = ctk.CTkFrame(col_frame, fg_color=header_color, corner_radius=6)
        header.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(weight="bold", size=15), text_color="#eee", pady=10).pack()
        
        s = ctk.CTkScrollableFrame(col_frame, fg_color="transparent")
        s.pack(fill="both", expand=True, padx=2, pady=2)
        return s

    def _get_acervo(self):
        from core.database import db
        with db.get_connection() as conn:
            rows = conn.execute("SELECT id, nome_peca FROM acervo").fetchall()
        return {r[1]: r[0] for r in rows}

    def _update_acervo_combo(self, event=None):
        self.acervo_dict = self._get_acervo()
        self.peca_combo.configure(values=list(self.acervo_dict.keys()) if self.acervo_dict else ["Acervo Vazio"])
        if self.acervo_dict:
            self.peca_combo.set(list(self.acervo_dict.keys())[0])
        else:
            self.peca_combo.set("Acervo Vazio")

    def _add_peca_ui(self):
        p = self.peca_combo.get()
        if not p or p not in self.acervo_dict: return
        acervo_id = self.acervo_dict[p]
        
        row_ui = ctk.CTkFrame(self.pecas_ui_frame, fg_color="#222", corner_radius=6, border_width=1, border_color="#333")
        row_ui.pack(side="left", padx=5, pady=5)
        ctk.CTkLabel(row_ui, text=p, font=ctk.CTkFont(size=12)).pack(side="left", padx=10, pady=6)
        
        custo_peca = 0.0
        from core.database import db
        with db.get_connection() as conn:
            rows = conn.execute("SELECT af.peso_gasto, af.peso_desperdicio, f.preco_rolo, f.peso_inicial FROM acervo_filamentos af JOIN filamentos f ON af.filamento_id = f.id WHERE af.acervo_id=?", (acervo_id,)).fetchall()
            for pg, pd, pr, pi in rows:
                if pi and pi > 0:
                    custo_peca += (pg + pd) * (pr / pi)
                    
        ctk.CTkButton(row_ui, text="✕", width=20, height=20, corner_radius=4, fg_color="transparent", text_color="#d64545", hover_color="#3d1818", command=lambda r=row_ui, c=custo_peca, i=acervo_id: self._rem_peca(r, c, i)).pack(side="right", padx=5)
        self.pecas_selecionadas.append({"tipo": "acervo", "id": acervo_id, "ui": row_ui})
        
        try: v = float(self.valor_var.get().replace(",", ".")) if self.valor_var.get() else 0.0
        except ValueError: v = 0.0
        self.valor_var.set(f"{max(0.0, v + custo_peca):.2f}")

    def _add_avulsa_ui(self, nome, tempo, custo_total, filamentos):
        row_ui = ctk.CTkFrame(self.pecas_ui_frame, fg_color="#1a2e3a", corner_radius=6, border_width=1, border_color="#2a4a5e")
        row_ui.pack(side="left", padx=5, pady=5)
        ctk.CTkLabel(row_ui, text=f"Avulsa: {nome}", font=ctk.CTkFont(size=12)).pack(side="left", padx=10, pady=6)
        
        idx = len(self.pecas_selecionadas)
        ctk.CTkButton(row_ui, text="✕", width=20, height=20, corner_radius=4, fg_color="transparent", text_color="#ff6b6b", hover_color="#3d1a1a", command=lambda r=row_ui, c=custo_total, i=idx: self._rem_peca(r, c, i)).pack(side="right", padx=5)
        
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
            return messagebox.showerror("Erro", "Preencha o nome do cliente e adicione pelo menos uma peça.")
        try: v = float(self.valor_var.get().replace(",", ".")) if self.valor_var.get() else 0.0
        except ValueError: v = 0.0
        
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
        self._toggle_form()
        app_state.load_pedidos()

    def _on_state_change(self, event=None):
        current_data = {p['id']: p for p in app_state.pedidos}
        
        for pid in list(self.cards.keys()):
            if pid not in current_data:
                self.cards[pid].destroy()
                del self.cards[pid]
                
        for pid, data in current_data.items():
            if pid in self.cards:
                card = self.cards[pid]
                if card.status != data.get('status', 'A Fazer'):
                    card.destroy()
                    self._add_card(data)
                else:
                    card.update_data(data)
            else:
                self._add_card(data)

    def _add_card(self, data):
        status = data.get('status', 'A Fazer')
        
        if status == "Imprimindo": parent = self.col_imp
        elif status in ("Encaminhado", "Entregue"): parent = self.col_encaminhado
        else: parent = self.col_fazer
        
        card = PedidoCard(parent, data)
        card.pack(fill="x", padx=6, pady=6)
        self.cards[data['id']] = card


class AdicionarAvulsoModal(ctk.CTkToplevel):
    def __init__(self, master, on_add_callback):
        super().__init__(master)
        self.title("Adicionar Peça Avulsa")
        self.geometry("560x520")
        self.configure(fg_color="#181818")
        self.resizable(False, False)
        self.grab_set()
        
        self.on_add_callback = on_add_callback
        self.filamentos = app_state.get_filamentos_ativos()
        self.fil_rows = []
        
        self.grid_rowconfigure(1, weight=1) 
        self.grid_columnconfigure(0, weight=1)
        
        f_top = ctk.CTkFrame(self, fg_color="transparent")
        f_top.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 5))
        
        ctk.CTkLabel(f_top, text="Nome da Peça Avulsa:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.nome_var = ctk.StringVar()
        ctk.CTkEntry(f_top, textvariable=self.nome_var, width=300, fg_color="#111", border_color="#333").pack(anchor="w", pady=(2, 10))
        
        ctk.CTkLabel(f_top, text="Tempo Estimado (HH:MM) [opcional]:", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.tempo_var = ctk.StringVar()
        ctk.CTkEntry(f_top, textvariable=self.tempo_var, width=150, placeholder_text="02:30", fg_color="#111", border_color="#333").pack(anchor="w", pady=(2, 10))
        
        ctk.CTkLabel(f_top, text="Filamentos (Modelo + Purga):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10, 0))
        
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#111", corner_radius=6, border_width=1, border_color="#222")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(5, 10))
        
        ctk.CTkButton(self.scroll, text="+ Adicionar Filamento", fg_color="#2a2a2a", hover_color="#444", command=self._add_fil_row).pack(anchor="w", pady=(5, 10), padx=5)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=20)
        
        ctk.CTkButton(btn_frame, text="Cancelar", height=35, fg_color="transparent", border_width=1, border_color="#444", hover_color="#333", command=self.destroy).pack(side="left")
        ctk.CTkButton(btn_frame, text="Salvar Peça", height=35, font=ctk.CTkFont(weight="bold"), fg_color=ACCENT_COLOR, hover_color="#007acc", command=self._save).pack(side="right")
        
    def _add_fil_row(self):
        row = ctk.CTkFrame(self.scroll, fg_color="#1e1e1e", corner_radius=6, border_width=1, border_color="#333")
        row.pack(fill="x", pady=4, padx=5)
        
        fil_var = ctk.StringVar()
        opts = [f"{f['marca']} {f['material']} {f['cor']}" for f in self.filamentos]
        opt = ctk.CTkOptionMenu(row, variable=fil_var, values=opts if opts else ["Sem Filamentos"], width=180, fg_color="#111", button_color="#333")
        opt.pack(side="left", padx=8, pady=8)
        
        mod_var = ctk.StringVar(value="0")
        pur_var = ctk.StringVar(value="0")
        
        ctk.CTkLabel(row, text="M(g):", text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 2))
        ctk.CTkEntry(row, textvariable=mod_var, width=55, fg_color="#111", border_color="#444").pack(side="left")
        
        ctk.CTkLabel(row, text="P(g):", text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 2))
        ctk.CTkEntry(row, textvariable=pur_var, width=55, fg_color="#111", border_color="#444").pack(side="left")
        
        def _rem():
            row.destroy()
            self.fil_rows = [r for r in self.fil_rows if r["ui"] != row]
            
        ctk.CTkButton(row, text="✕", width=28, height=28, corner_radius=4, fg_color="transparent", text_color="#d64545", hover_color="#3d1818", command=_rem).pack(side="right", padx=8)
        
        self.fil_rows.append({
            "ui": row,
            "fil_var": fil_var,
            "mod_var": mod_var,
            "pur_var": pur_var
        })
        
    def _save(self):
        nome = self.nome_var.get().strip()
        if not nome:
            messagebox.showerror("Erro", "O Nome da Peça é obrigatório.", parent=self)
            return
            
        custo_total = 0.0
        fils_data = []
        
        for r in self.fil_rows:
            sel = r["fil_var"].get()
            f_id = None
            f_preco_kg = 0.0
            
            for f in self.filamentos:
                if f"{f['marca']} {f['material']} {f['cor']}" == sel:
                    f_id = f["id"]
                    peso_inicial = float(f.get("peso_inicial") or 1.0)
                    if peso_inicial > 0:
                        f_preco_kg = float(f.get("preco_rolo", 0.0)) / peso_inicial
                    break
                    
            try: mod = float(r["mod_var"].get().replace(",", "."))
            except: mod = 0.0
            try: pur = float(r["pur_var"].get().replace(",", "."))
            except: pur = 0.0
            
            custo_item = ((mod + pur) / 1000.0) * f_preco_kg
            custo_total += custo_item
            
            fils_data.append({
                "fil_id": f_id,
                "peso": mod,
                "purga": pur,
                "custo": custo_item
            })
            
        self.on_add_callback(nome, self.tempo_var.get(), custo_total, fils_data)
        self.destroy()