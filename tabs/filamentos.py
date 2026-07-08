import customtkinter as ctk
from tkinter import messagebox, filedialog
from core.state import app_state
from core.widgets import ModernCard, InlineEdit, HorizontalInventoryCard
from core.utils import load_and_resize_image, copy_to_media, resolve_media_path, open_url, ACCENT_COLOR

class FilamentoCard(HorizontalInventoryCard):
    def __init__(self, master, data, **kwargs):
        super().__init__(master, data, **kwargs)
        self.f_id = data['id']
        
        self.content_frame.grid_columnconfigure(0, weight=1)

        top_bar = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 5))

        if data.get('status') == 'Esgotado':
            ctk.CTkButton(top_bar, text="Retornar ao Estoque", width=120, height=22, fg_color="#2b7a4b", command=self._restore).pack(side="left")
        else:
            ctk.CTkButton(top_bar, text="✕", width=22, height=22,
                          fg_color="transparent", text_color="#d64545",
                          command=self._esgotar).pack(side="right", padx=5)
                      
        ctk.CTkButton(top_bar, text="+", width=30, height=22, fg_color="transparent", border_width=1, border_color="#555", hover_color="#333", command=self._open_detalhes).pack(side="right", padx=5)

        info_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        info_frame.pack(fill="x", expand=True)
        
        self.marca_entry = InlineEdit(info_frame, data['marca'], self._make_saver('marca'), font=ctk.CTkFont(weight="bold", size=16))
        self.marca_entry.pack(anchor="w", pady=2)
        
        self.mat_entry = InlineEdit(info_frame, data['material'], self._make_saver('material'), font=ctk.CTkFont(weight="bold", size=16))
        self.mat_entry.pack(anchor="w", pady=2)

        self.cor_entry = InlineEdit(info_frame, data['cor'], self._make_saver('cor'), text_color="gray", font=ctk.CTkFont(size=12))
        self.cor_entry.pack(anchor="w", pady=2)
        
        preco_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        preco_frame.pack(anchor="w", pady=(10, 5))
        ctk.CTkLabel(preco_frame, text="R$", text_color="#10b981", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=(0, 5))
        self.preco_entry = InlineEdit(preco_frame, data['preco_rolo'], self._make_saver_float('preco_rolo'), text_color="#10b981", font=ctk.CTkFont(size=18, weight="bold"), is_double=True)
        self.preco_entry.pack(side="left")

        peso_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        peso_row.pack(fill="x", pady=(4, 2))

        ctk.CTkLabel(peso_row, text="Peso atual (kg):",
                     text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left")

        self._peso_var = ctk.StringVar(value=self._fmt_peso(data['peso_atual']))
        self._peso_entry = ctk.CTkEntry(
            peso_row, textvariable=self._peso_var,
            width=80, height=26, font=ctk.CTkFont(size=13, weight="bold")
        )
        self._peso_entry.pack(side="left", padx=(6, 0))
        self._peso_entry.bind("<FocusOut>", self._save_peso)
        self._peso_entry.bind("<Return>",   self._save_peso)

        res_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        res_row.pack(fill="x", pady=(2, 2))
        self.lbl_reserva = ctk.CTkLabel(res_row, text="", text_color="gray", font=ctk.CTkFont(size=11))
        self.lbl_reserva.pack(side="left")
        ctk.CTkButton(res_row, text="-", width=22, height=22, fg_color="#333",
                      command=self._sub_reserva).pack(side="left", padx=(10, 2))
        ctk.CTkButton(res_row, text="+", width=22, height=22, fg_color="#333",
                      command=self._add_reserva).pack(side="left", padx=2)

        self._refresh_reserva_label()
        self._update_image()

    @staticmethod
    def _fmt_peso(val):
        try:
            return f"{float(val):.2f}"
        except (ValueError, TypeError):
            return "0.00"

    def _refresh_reserva_label(self):
        rolos = int(self.data.get('rolos_reserva', 0) or 0)
        txt = f"+ {rolos} rolo(s) reserva" if rolos > 0 else "sem reserva"
        self.lbl_reserva.configure(text=txt)

    def _save_peso(self, _event=None):
        val = self._peso_var.get().replace(',', '.')
        try:
            f_val = float(val)
            limite = float(self.data['peso_inicial']) if self.data['peso_inicial'] > 0 else 1.0
            if f_val > limite:
                messagebox.showerror("Erro", f"O peso inserido não pode ser maior que o limite de {limite:.2f} kg.")
                self._peso_var.set(self._fmt_peso(self.data['peso_atual']))
                return
            app_state.update_filamento(self.f_id, {'peso_atual': f_val})
        except ValueError:
            messagebox.showerror("Erro", "Valor de peso numérico inválido.")
            self._peso_var.set(self._fmt_peso(self.data['peso_atual']))

    def update_data(self, data):
        self.data = data
        self.marca_entry.delete(0, 'end'); self.marca_entry.insert(0, data['marca'])
        self.mat_entry.delete(0, 'end'); self.mat_entry.insert(0, data['material'])
        self.cor_entry.delete(0, 'end'); self.cor_entry.insert(0, data['cor'])
        
        try: pr = f"{float(data['preco_rolo']):.2f}"
        except: pr = str(data['preco_rolo'])
        self.preco_entry.delete(0, 'end'); self.preco_entry.insert(0, pr)
        
        self._peso_var.set(self._fmt_peso(data['peso_atual']))
        self._refresh_reserva_label()
        self._update_image()

    def _add_reserva(self):
        atual = int(self.data.get('rolos_reserva', 0))
        app_state.update_filamento(self.f_id, {'rolos_reserva': atual + 1})

    def _sub_reserva(self):
        atual = int(self.data.get('rolos_reserva', 0))
        if atual > 0:
            app_state.update_filamento(self.f_id, {'rolos_reserva': atual - 1})

    def _make_saver(self, field):
        def saver(val):
            app_state.update_filamento(self.f_id, {field: val})
            return True
        return saver
        
    def _make_saver_float(self, field):
        def saver(val):
            try:
                f_val = float(val.replace(',', '.'))
                app_state.update_filamento(self.f_id, {field: f_val})
                return True
            except ValueError:
                messagebox.showerror("Erro", "Valor deve ser numérico.")
                return False
        return saver

    def _esgotar(self):
        if messagebox.askyesno("Confirmar", "Mover este filamento para esgotados?"):
            app_state.update_filamento(self.f_id, {'status': 'Esgotado'})

    def _restore(self):
        if messagebox.askyesno("Confirmar", "Retornar este filamento ao estoque?"):
            app_state.update_filamento(self.f_id, {'status': 'Ativo'})

    def _open_detalhes(self):
        self.winfo_toplevel().modals['detalhes'].show(self.data, lambda i, u: app_state.update_filamento(i, u))

class TabFilamentos(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.form_visible = False
        
        from core.utils import ACCENT_COLOR
        self.toggle_btn = ctk.CTkButton(
            self, text="+ Cadastrar Novo Filamento",
            fg_color="transparent", text_color=ACCENT_COLOR,
            anchor="w", hover_color="#222", command=self._toggle_form
        )
        self.toggle_btn.pack(side="top", fill="x", padx=20, pady=(10, 0))

        self.form_card = ModernCard(self, border_width=0)
        self.form_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(self.form_card, text="Cadastrar Novo Filamento", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=4, pady=(5, 0))

        def lbl_entry(parent_frame, row, col, label, var, placeholder=""):
            f = ctk.CTkFrame(parent_frame, fg_color="transparent")
            f.grid(row=row, column=col, padx=10, sticky="ew")
            ctk.CTkLabel(f, text=label, text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
            ctk.CTkEntry(f, textvariable=var, height=25, placeholder_text=placeholder, placeholder_text_color="#555").pack(fill="x")

        self.marca_var = ctk.StringVar()
        self.material_var = ctk.StringVar()
        self.cor_var = ctk.StringVar()
        self.peso_var = ctk.StringVar(value="1.0")
        self.preco_var = ctk.StringVar()
        self.link_var = ctk.StringVar()
        self.status_var = ctk.StringVar(value="Ativo")

        lbl_entry(self.form_card, 1, 0, "Marca", self.marca_var)
        lbl_entry(self.form_card, 1, 1, "Material", self.material_var)
        lbl_entry(self.form_card, 1, 2, "Cor", self.cor_var)
        lbl_entry(self.form_card, 1, 3, "Peso (KG)", self.peso_var)
        
        lbl_entry(self.form_card, 2, 0, "Valor ($)", self.preco_var)
        lbl_entry(self.form_card, 2, 1, "Link", self.link_var)
        
        f_status = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f_status.grid(row=2, column=2, padx=10, sticky="ew")
        ctk.CTkLabel(f_status, text="Status Inicial", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkOptionMenu(f_status, variable=self.status_var, values=["Ativo", "Esgotado"], height=25).pack(fill="x")

        self._new_foto_filename = None
        f_foto = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f_foto.grid(row=3, column=0, padx=10, pady=(10, 10), sticky="ew")
        ctk.CTkLabel(f_foto, text="Foto", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.btn_foto = ctk.CTkButton(f_foto, text="Buscar", height=25, fg_color="#333", hover_color="#444", command=self._select_photo)
        self.btn_foto.pack(fill="x")

        f_salvar = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f_salvar.grid(row=3, column=3, padx=10, pady=(10, 10), sticky="ew")
        ctk.CTkLabel(f_salvar, text="", font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkButton(f_salvar, text="Salvar", height=25, font=ctk.CTkFont(weight="bold"), command=self._save_filamento, fg_color=ACCENT_COLOR).pack(fill="x")

        self.tabview = ctk.CTkTabview(self, fg_color="transparent")
        self.tabview.pack(side="top", fill="both", expand=True, padx=20, pady=(5, 20))
        self.tab_ativos = self.tabview.add("Ativos")
        self.tab_esgot = self.tabview.add("Esgotados")
        
        self.list_frame = ctk.CTkScrollableFrame(self.tab_ativos, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True)
        
        self.list_esgot = ctk.CTkScrollableFrame(self.tab_esgot, fg_color="transparent")
        self.list_esgot.pack(fill="both", expand=True)
        
        self.cards = {}
        self.col_count = 2
        
        app_state.subscribe('filamentos', self._on_state_change)
        app_state.load_filamentos()

    def _toggle_form(self):
        if self.form_visible:
            self.form_card.pack_forget()
            self.toggle_btn.configure(text="+ Cadastrar Novo Filamento")
        else:
            self.form_card.pack(side="top", fill="x", padx=20, pady=(5, 5), before=self.tabview)
            self.toggle_btn.configure(text="- Ocultar Formulário")
        self.form_visible = not self.form_visible

    def _select_photo(self):
        path = filedialog.askopenfilename(filetypes=[("Imagens", "*.jpg *.jpeg *.png")])
        if not path: return
        try:
            self._new_foto_filename = copy_to_media(path)
            self.btn_foto.configure(text="Anexada", fg_color="#2b7a4b")
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))

    def _save_filamento(self):
        try: p = float(self.peso_var.get().replace(",", "."))
        except ValueError: return messagebox.showerror("Erro", "Peso deve ser numérico.")
        try: preco = float(self.preco_var.get().replace(",", ".")) if self.preco_var.get() else 0.0
        except ValueError: return messagebox.showerror("Erro", "Preço deve ser numérico.")
        
        if not all([self.marca_var.get(), self.material_var.get(), self.cor_var.get()]):
            return messagebox.showerror("Erro", "Preencha marca, material e cor.")

        app_state.add_filamento({
            'marca': self.marca_var.get(),
            'material': self.material_var.get(),
            'cor': self.cor_var.get(),
            'peso_inicial': p,
            'peso_atual': p,
            'caminho_foto': self._new_foto_filename,
            'link_compra': self.link_var.get(),
            'preco_rolo': preco,
            'status': self.status_var.get(),
            'rolos_reserva': 0
        })

        for var in (self.marca_var, self.material_var, self.cor_var, self.link_var, self.preco_var): var.set("")
        self.peso_var.set("1.0")
        self.status_var.set("Ativo")
        self._new_foto_filename = None
        self.btn_foto.configure(text="Buscar", fg_color="#333")

    def _on_state_change(self, event=None):
        for w in self.cards.values(): w.destroy()
        self.cards = {}
        
        for c in range(self.col_count):
            self.list_frame.grid_columnconfigure(c, weight=1)
            self.list_esgot.grid_columnconfigure(c, weight=1)
            
        ativos = [d for d in app_state.filamentos if d['status'] == 'Ativo']
        esgotados = [d for d in app_state.filamentos if d['status'] == 'Esgotado']
        
        for i, data in enumerate(ativos):
            self._add_card(data, i, self.list_frame)
            
        for i, data in enumerate(esgotados):
            self._add_card(data, i, self.list_esgot)

    def _add_card(self, data, index, parent_frame):
        card = FilamentoCard(parent_frame, data)
        r, c = divmod(index, self.col_count)
        card.grid(row=r, column=c, sticky="nsew", padx=5, pady=5)
        self.cards[data['id']] = card