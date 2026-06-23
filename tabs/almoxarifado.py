import customtkinter as ctk
from tkinter import messagebox, filedialog
from core.state import app_state
from core.widgets import ModernCard, InlineEdit, HorizontalInventoryCard
from core.utils import load_and_resize_image, resolve_media_path, copy_to_media, open_url, ACCENT_COLOR

class AlmoxarifadoCard(HorizontalInventoryCard):
    def __init__(self, master, data, **kwargs):
        is_esgotado = data.get('quantidade_status') == 'Esgotado'
        danger = data['quantidade_status'] in ("Comprar", "Falta")
        super().__init__(master, data, fg_color="#333", corner_radius=8, **kwargs)
        self.item_id = data['id']
        self._is_esgotado = is_esgotado

        self.content_frame.grid_columnconfigure(0, weight=1)

        top_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 5))

        self.nome_entry = InlineEdit(top_row, data['nome'], self._make_saver('nome'),
                                     font=ctk.CTkFont(weight="bold", size=18),
                                     state="disabled" if is_esgotado else "normal")
        self.nome_entry.pack(side="left", fill="x", expand=True)

        # ── Botão de exclusão: sempre visível, independente do estado ────────────
        ctk.CTkButton(top_row, text="✕", width=30, height=25, fg_color="transparent",
                      text_color="#d64545", command=self._delete).pack(side="right", padx=5)

        if not is_esgotado:
            ctk.CTkButton(top_row, text="+", width=30, height=25, fg_color="transparent",
                          border_width=1, border_color="#555", hover_color="#333",
                          command=self._open_detalhes).pack(side="right", padx=5)
        else:
            ctk.CTkLabel(top_row, text="⛔ Esgotado", text_color="#d64545",
                         font=ctk.CTkFont(size=11, weight="bold")).pack(side="right", padx=8)

        if is_esgotado:
            # Read-only badge for esgotados
            badge = ctk.CTkFrame(self.content_frame, fg_color="#4a1a1a", corner_radius=5)
            badge.pack(anchor="w", pady=(5, 5))
            ctk.CTkLabel(badge, text="Esgotado", text_color="#d64545",
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=8, pady=2)
        else:
            badge = ctk.CTkFrame(self.content_frame,
                                  fg_color="#8b0000" if danger else "#444",
                                  corner_radius=5)
            badge.pack(anchor="w", pady=(5, 5))

            self.status_var = ctk.StringVar(value=data['quantidade_status'])
            self.status_menu = ctk.CTkOptionMenu(
                badge, variable=self.status_var,
                values=["Em estoque", "Comprar", "Falta", "Esgotado"],
                command=self._update_status, height=25, font=ctk.CTkFont(size=12)
            )
            self.status_menu.pack(side="left", padx=2, pady=2)

        bot_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        bot_row.pack(fill="x", pady=(5, 0))

        if data['ultimo_valor'] and data['ultimo_valor'] > 0:
            preco_frame = ctk.CTkFrame(bot_row, fg_color="transparent")
            preco_frame.pack(side="left", padx=(0, 10))
            ctk.CTkLabel(preco_frame, text="R$ ", text_color="#ccc",
                         font=ctk.CTkFont(size=14)).pack(side="left")
            if is_esgotado:
                ctk.CTkLabel(preco_frame,
                             text=f"{float(data['ultimo_valor']):.2f}",
                             text_color="#888", font=ctk.CTkFont(size=14)).pack(side="left")
            else:
                self.preco_entry = InlineEdit(
                    preco_frame, data['ultimo_valor'],
                    self._make_saver_float('ultimo_valor'),
                    text_color="#ccc", is_double=True, font=ctk.CTkFont(size=14)
                )
                self.preco_entry.pack(side="left")

        self._update_image()

    def _update_status(self, new_status):
        if new_status == 'Esgotado':
            if not messagebox.askyesno(
                "Confirmar",
                "Marcar este item como Esgotado?\n\n"
                "O item será movido para a aba Esgotados e não poderá ser editado ou excluído."
            ):
                self.status_var.set(self.data['quantidade_status'])
                return
        app_state.update_almoxarifado(self.item_id, {'quantidade_status': new_status})
        if new_status == 'Esgotado':
            app_state.load_almoxarifado()

    def _open_detalhes(self):
        self.winfo_toplevel().modals['detalhes'].show(
            self.data, lambda i, u: app_state.update_almoxarifado(i, u)
        )

    def update_data(self, data):
        self.data = data
        self.nome_entry.delete(0, 'end')
        self.nome_entry.insert(0, data['nome'])
        if not self._is_esgotado:
            self.status_var.set(data['quantidade_status'])
            if hasattr(self, 'preco_entry'):
                try:
                    uv = f"{float(data['ultimo_valor']):.2f}"
                except Exception:
                    uv = str(data['ultimo_valor'])
                self.preco_entry.delete(0, 'end')
                self.preco_entry.insert(0, uv)
        self._update_image()

    def _make_saver(self, field):
        def saver(val):
            app_state.update_almoxarifado(self.item_id, {field: val})
            return True
        return saver

    def _make_saver_float(self, field):
        def saver(val):
            try:
                f_val = float(val.replace(',', '.'))
                app_state.update_almoxarifado(self.item_id, {field: f_val})
                return True
            except ValueError:
                messagebox.showerror("Erro", "Valor deve ser numérico.")
                return False
        return saver

    def _delete(self):
        if messagebox.askyesno("Confirmar", "Remover este item?"):
            from core.database import db
            with db.get_connection() as conn:
                conn.execute("DELETE FROM ferramentas_insumos WHERE id=?", (self.item_id,))
                conn.commit()
            app_state.load_almoxarifado()


class TabAlmoxarifado(ctk.CTkFrame):
    PAGE_SIZE = 20

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        from core.widgets import ModernCard

        self.form_visible = False

        self.toggle_btn = ctk.CTkButton(
            self, text="+ Adicionar Novo Item",
            fg_color="transparent", text_color=ACCENT_COLOR,
            anchor="w", hover_color="#222", command=self._toggle_form
        )
        self.toggle_btn.pack(side="top", fill="x", padx=20, pady=(10, 0))

        self.form_card = ModernCard(self)

        ctk.CTkLabel(self.form_card, text="Novo Item de Almoxarifado",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 15))

        self.nome_var = ctk.StringVar()
        self.cat_var = ctk.StringVar(value="Ferramenta")
        self.status_var = ctk.StringVar(value="Em estoque")
        self.link_var = ctk.StringVar()
        self.preco_var = ctk.StringVar()
        self.data_reg_var = ctk.StringVar()
        self._new_foto_filename = None

        row1 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=5)
        row1.grid_columnconfigure((0, 1, 2), weight=1)

        def lrow(parent_frame, col, label, widget_fn):
            f = ctk.CTkFrame(parent_frame, fg_color="transparent")
            f.grid(row=0, column=col, sticky="ew", padx=5)
            ctk.CTkLabel(f, text=label, text_color="gray").pack(anchor="w")
            widget_fn(f)

        lrow(row1, 0, "Nome do Item",
             lambda f: ctk.CTkEntry(f, textvariable=self.nome_var,
                                    placeholder_text="Ex: Lixa d'água 400").pack(fill="x"))
        lrow(row1, 1, "Categoria",
             lambda f: ctk.CTkOptionMenu(f, variable=self.cat_var,
                                         values=["Ferramenta", "Insumo", "Peça Reposição"]).pack(fill="x"))
        lrow(row1, 2, "Situação",
             lambda f: ctk.CTkOptionMenu(f, variable=self.status_var,
                                         values=["Em estoque", "Comprar", "Falta"]).pack(fill="x"))

        row2 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=5)
        row2.grid_columnconfigure((0, 1, 2), weight=1)

        lrow(row2, 0, "Link de Compra",
             lambda f: ctk.CTkEntry(f, textvariable=self.link_var).pack(fill="x"))
        lrow(row2, 1, "Último Valor ($)",
             lambda f: ctk.CTkEntry(f, textvariable=self.preco_var,
                                    placeholder_text="25.50").pack(fill="x"))
        lrow(row2, 2, "Data de Registo (AAAA-MM-DD)",
             lambda f: ctk.CTkEntry(f, textvariable=self.data_reg_var,
                                    placeholder_text="2025-01-15").pack(fill="x"))

        row3 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        row3.pack(fill="x", padx=20, pady=5)
        row3.grid_columnconfigure((0, 1), weight=1)

        f6 = ctk.CTkFrame(row3, fg_color="transparent")
        f6.grid(row=0, column=0, sticky="ew", padx=5)
        ctk.CTkLabel(f6, text="Foto (Opcional)", text_color="gray").pack(anchor="w")
        self.btn_foto = ctk.CTkButton(f6, text="Selecionar", fg_color="#333",
                                      hover_color="#444", command=self._select_photo)
        self.btn_foto.pack(fill="x")

        ctk.CTkButton(self.form_card, text="Salvar Item", height=40,
                      font=ctk.CTkFont(weight="bold"), fg_color=ACCENT_COLOR,
                      command=self._save).pack(fill="x", padx=25, pady=(15, 20))

        # ── Tabview: Ativos / Esgotados ────────────────────────────────────
        self.tabview = ctk.CTkTabview(self, fg_color="transparent")
        self.tabview.pack(side="top", fill="both", expand=True, padx=20, pady=(5, 20))
        self.tab_ativos = self.tabview.add("Ativos")
        self.tab_esgotados = self.tabview.add("Esgotados")

        self.list_frame = ctk.CTkScrollableFrame(self.tab_ativos, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True)
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_columnconfigure(1, weight=1)

        self.list_esgotados = ctk.CTkScrollableFrame(self.tab_esgotados, fg_color="transparent")
        self.list_esgotados.pack(fill="both", expand=True)
        self.list_esgotados.grid_columnconfigure(0, weight=1)
        self.list_esgotados.grid_columnconfigure(1, weight=1)

        self.cards = {}
        self.col_count = 2
        self._loaded_ativos = 0
        self._loaded_esgotados = 0
        self._load_more_ativos_btn = None
        self._load_more_esgotados_btn = None

        app_state.subscribe('almoxarifado', self._on_state_change)
        app_state.load_almoxarifado()

    def _toggle_form(self):
        if self.form_visible:
            self.form_card.pack_forget()
            self.toggle_btn.configure(text="+ Adicionar Novo Item")
        else:
            self.form_card.pack(side="top", fill="x", padx=20, pady=(5, 5),
                                before=self.tabview)
            self.toggle_btn.configure(text="- Ocultar Formulário")
        self.form_visible = not self.form_visible

    def _select_photo(self):
        path = filedialog.askopenfilename()
        if not path:
            return
        try:
            self._new_foto_filename = copy_to_media(path)
            self.btn_foto.configure(text="Anexado", fg_color="#2b7a4b")
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))

    def _save(self):
        nome = self.nome_var.get()
        if not nome:
            return messagebox.showerror("Erro", "Nome é obrigatório.")
        try:
            preco = float(self.preco_var.get().replace(",", ".")) if self.preco_var.get() else 0.0
        except ValueError:
            return messagebox.showerror("Erro", "Preço deve ser numérico.")

        import datetime as _dt
        from core.database import db
        data_reg = self.data_reg_var.get().strip() or _dt.date.today().isoformat()
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO ferramentas_insumos "
                "(nome, categoria, quantidade_status, caminho_foto, link_compra, ultimo_valor, data_registro) "
                "VALUES (?,?,?,?,?,?,?)",
                (nome, self.cat_var.get(), self.status_var.get(),
                 self._new_foto_filename, self.link_var.get(), preco,
                 data_reg)
            )
            conn.commit()

        self.nome_var.set("")
        self.link_var.set("")
        self.preco_var.set("")
        self.data_reg_var.set("")
        self._new_foto_filename = None
        self.btn_foto.configure(text="Selecionar", fg_color="#333")
        app_state.load_almoxarifado()

    def _on_state_change(self, event=None):
        if event:
            action = event.get('action')
            i_id = event.get('id')
            if action == 'update' and i_id in self.cards:
                self.cards[i_id].update_data(event['data'])
                return
            elif action == 'remove' and i_id in self.cards:
                self.cards[i_id].destroy()
                del self.cards[i_id]
                return

        # Full rebuild
        for w in self.cards.values():
            w.destroy()
        self.cards = {}

        for c in range(self.col_count):
            self.list_frame.grid_columnconfigure(c, weight=1)
            self.list_esgotados.grid_columnconfigure(c, weight=1)

        self._ativos_data = [d for d in app_state.almoxarifado
                             if d.get('quantidade_status') != 'Esgotado']
        self._esgotados_data = [d for d in app_state.almoxarifado
                                if d.get('quantidade_status') == 'Esgotado']

        self._loaded_ativos = 0
        self._loaded_esgotados = 0

        for btn_attr in ('_load_more_ativos_btn', '_load_more_esgotados_btn'):
            btn = getattr(self, btn_attr, None)
            if btn and btn.winfo_exists():
                btn.destroy()
            setattr(self, btn_attr, None)

        self._load_page_ativos()
        self._load_page_esgotados()

    def _load_page_ativos(self):
        batch = self._ativos_data[self._loaded_ativos:
                                  self._loaded_ativos + self.PAGE_SIZE]
        for i, data in enumerate(batch):
            self._add_card(data, self._loaded_ativos + i, self.list_frame)
        self._loaded_ativos += len(batch)

        if self._load_more_ativos_btn and self._load_more_ativos_btn.winfo_exists():
            self._load_more_ativos_btn.destroy()
            self._load_more_ativos_btn = None

        if self._loaded_ativos < len(self._ativos_data):
            rem = len(self._ativos_data) - self._loaded_ativos
            self._load_more_ativos_btn = ctk.CTkButton(
                self.list_frame,
                text=f"Carregar Mais ({rem} restantes)",
                fg_color="#2a2a4a", hover_color="#3a3a6a",
                font=ctk.CTkFont(size=13),
                command=self._load_page_ativos
            )
            self._load_more_ativos_btn.grid(
                row=(self._loaded_ativos // self.col_count) + 1,
                column=0, columnspan=self.col_count,
                sticky="ew", padx=10, pady=10
            )

    def _load_page_esgotados(self):
        batch = self._esgotados_data[self._loaded_esgotados:
                                     self._loaded_esgotados + self.PAGE_SIZE]
        for i, data in enumerate(batch):
            self._add_card(data, self._loaded_esgotados + i, self.list_esgotados)
        self._loaded_esgotados += len(batch)

        if self._load_more_esgotados_btn and self._load_more_esgotados_btn.winfo_exists():
            self._load_more_esgotados_btn.destroy()
            self._load_more_esgotados_btn = None

        if self._loaded_esgotados < len(self._esgotados_data):
            rem = len(self._esgotados_data) - self._loaded_esgotados
            self._load_more_esgotados_btn = ctk.CTkButton(
                self.list_esgotados,
                text=f"Carregar Mais ({rem} restantes)",
                fg_color="#2a2a4a", hover_color="#3a3a6a",
                font=ctk.CTkFont(size=13),
                command=self._load_page_esgotados
            )
            self._load_more_esgotados_btn.grid(
                row=(self._loaded_esgotados // self.col_count) + 1,
                column=0, columnspan=self.col_count,
                sticky="ew", padx=10, pady=10
            )

    def _add_card(self, data, index, parent_frame):
        card = AlmoxarifadoCard(parent_frame, data)
        r, c = divmod(index, self.col_count)
        card.grid(row=r, column=c, sticky="nsew", padx=10, pady=10)
        self.cards[data['id']] = card
