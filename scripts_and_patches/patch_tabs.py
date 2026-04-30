import re

with open("app.py", "r") as f:
    code = f.read()

# TabFilamentos
code = re.sub(r'class TabFilamentos\(ctk\.CTkFrame\):.*?(?=class TabAcervo)', '''class TabFilamentos(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(side="top", fill="x", anchor="n", padx=20, pady=(10,0))
        
        self.alert_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        self.alert_frame.pack(side="top", fill="x")
        
        # CHANGED: Added distinct border to prove it changed visually
        self.form_card = ModernCard(self.top_frame, border_color="#00a2ff", border_width=2)
        self.form_card.pack(side="top", fill="x", anchor="n", pady=(10, 20))
        self.form_card.grid_columnconfigure((0,1,2,3), weight=1)
        
        ctk.CTkLabel(self.form_card, text="Cadastrar Novo Filamento", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=4, pady=(15, 20))
        
        self.marca_var = ctk.StringVar()
        f1 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f1.grid(row=1, column=0, padx=15, pady=5, sticky="new")
        ctk.CTkLabel(f1, text="Marca do Fabricante", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f1, textvariable=self.marca_var, placeholder_text="Ex: Bambu Lab").pack(fill="x")
        
        self.material_var = ctk.StringVar()
        f2 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f2.grid(row=1, column=1, padx=15, pady=5, sticky="new")
        ctk.CTkLabel(f2, text="Tipo de Material", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f2, textvariable=self.material_var, placeholder_text="Ex: PLA Basic").pack(fill="x")
        
        self.cor_var = ctk.StringVar()
        f3 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f3.grid(row=1, column=2, padx=15, pady=5, sticky="new")
        ctk.CTkLabel(f3, text="Cor", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f3, textvariable=self.cor_var, placeholder_text="Ex: Verde Neon").pack(fill="x")
        
        self.peso_var = ctk.StringVar(value="1.0")
        f4 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f4.grid(row=1, column=3, padx=15, pady=5, sticky="new")
        ctk.CTkLabel(f4, text="Peso Inicial (KG)", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f4, textvariable=self.peso_var, placeholder_text="Ex: 1.0").pack(fill="x")
        
        self.preco_var = ctk.StringVar()
        f_preco = ctk.CTkFrame(self.form_card, fg_color="transparent"); f_preco.grid(row=2, column=0, padx=15, pady=5, sticky="new")
        ctk.CTkLabel(f_preco, text="Valor do Rolo ($)", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f_preco, textvariable=self.preco_var, placeholder_text="Ex: 119.90").pack(fill="x")
        
        self.link_var = ctk.StringVar()
        f_link = ctk.CTkFrame(self.form_card, fg_color="transparent"); f_link.grid(row=2, column=1, padx=15, pady=5, sticky="new")
        ctk.CTkLabel(f_link, text="Link de Compra (Opcional)", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f_link, textvariable=self.link_var, placeholder_text="Ex: https://...").pack(fill="x")

        self.foto_path = None
        f5 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f5.grid(row=2, column=2, padx=15, pady=5, sticky="new")
        ctk.CTkLabel(f5, text="Foto de Identificação", text_color="gray").pack(anchor="w")
        self.btn_foto = ctk.CTkButton(f5, text="Buscar Imagem", fg_color="#333", hover_color="#444", command=self.select_photo)
        self.btn_foto.pack(fill="x")
        
        ctk.CTkButton(self.form_card, text="Salvar Filamento", height=40, font=ctk.CTkFont(weight="bold"), 
                      command=self.save_filamento, fg_color="#00a2ff").grid(row=2, column=3, padx=15, pady=(20, 5), sticky="new")
        
        ctk.CTkFrame(self.form_card, height=15, fg_color="transparent").grid(row=3, column=0)
        
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.load_filamentos()
        
    def select_photo(self):
        path = filedialog.askopenfilename(filetypes=[("Imagens", "*.jpg *.jpeg *.png")])
        if path:
            self.foto_path = path
            self.btn_foto.configure(text="Foto Anexada", fg_color="#2b7a4b")
            
    def save_filamento(self):
        m, mat, c, p, l = self.marca_var.get(), self.material_var.get(), self.cor_var.get(), self.peso_var.get(), self.link_var.get()
        try: p = float(p.replace(',', '.'))
        except: return messagebox.showerror("Erro", "O Peso deve ser numérico.")
        
        preco = 0.0
        if self.preco_var.get():
            try: preco = float(self.preco_var.get().replace(',','.'))
            except: return messagebox.showerror("Erro", "O Preço deve ser numérico.")
            
        if not all([m, mat, c, p]): return messagebox.showerror("Erro", "Preencha marca, material, cor e peso.")
            
        conn = sqlite3.connect("print_manager_v2.db")
        conn.execute("INSERT INTO filamentos (marca, material, cor, peso_inicial, peso_atual, caminho_foto, link_compra, preco_rolo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (m, mat, c, p, p, self.foto_path, l, preco))
        conn.commit(); conn.close()
        
        for var in (self.marca_var, self.material_var, self.cor_var, self.link_var, self.preco_var): var.set("")
        self.peso_var.set("1.0"); self.foto_path = None
        self.btn_foto.configure(text="Buscar Imagem", fg_color="#333")
        self.load_filamentos()

    def edit_item(self, id, r_marca, r_mat, r_cor, r_preco):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Editar {r_marca} {r_cor}")
        dialog.geometry("350x300")
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Somar Peso Extra (KG)", font=ctk.CTkFont(weight="bold")).pack(pady=(20,5))
        ctk.CTkLabel(dialog, text="Ex: Se comprou 1 rolo novo igual, digite 1.0", text_color="gray", font=ctk.CTkFont(size=11)).pack()
        add_peso = ctk.StringVar(value="0.0")
        ctk.CTkEntry(dialog, textvariable=add_peso).pack(pady=5)
        
        ctk.CTkLabel(dialog, text="Atualizar Preço do Rolo ($)", font=ctk.CTkFont(weight="bold")).pack(pady=(15,5))
        novo_preco = ctk.StringVar(value=str(r_preco or 0.0))
        ctk.CTkEntry(dialog, textvariable=novo_preco).pack(pady=5)
        
        def save():
            try:
                p_add = float(add_peso.get().replace(',','.'))
                pr = float(novo_preco.get().replace(',','.'))
            except:
                return messagebox.showerror("Erro", "Valores numéricos inválidos")
            conn = sqlite3.connect("print_manager_v2.db")
            conn.execute("UPDATE filamentos SET peso_inicial = peso_inicial + ?, peso_atual = peso_atual + ?, preco_rolo = ? WHERE id = ?", (p_add, p_add, pr, id))
            conn.commit(); conn.close()
            dialog.destroy()
            self.load_filamentos()
            
        ctk.CTkButton(dialog, text="Salvar Alterações", fg_color="#00a2ff", command=save).pack(pady=20)

    def delete_item(self, id):
        if messagebox.askyesno("Confirmar", "Tem certeza que deseja remover este filamento? (Isso afetará históricos)"):
            conn = sqlite3.connect("print_manager_v2.db")
            conn.execute("DELETE FROM filamentos WHERE id=?", (id,))
            conn.commit(); conn.close()
            self.load_filamentos()

    def load_filamentos(self):
        for w in self.list_frame.winfo_children(): w.destroy()
        for w in self.alert_frame.winfo_children(): w.destroy()
        
        conn = sqlite3.connect("print_manager_v2.db")
        rows = conn.execute("SELECT id, marca, material, cor, peso_inicial, peso_atual, caminho_foto, link_compra, preco_rolo FROM filamentos ORDER BY id DESC").fetchall()
        conn.close()
        self.list_frame.images = []
        
        # Changed to pack inside list frame to guarantee correct vertical layout!
        for row in rows:
            if row[5] < (row[4] * 0.2):
                af = ctk.CTkFrame(self.alert_frame, fg_color="#4a1515", corner_radius=8)
                af.pack(fill="x", pady=2)
                ctk.CTkLabel(af, text=f"ALERTA: Filamento {row[1]} {row[2]} ({row[3]}) está no fim! ({row[5]*1000:.0f}g restantes)", text_color="white", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=15, pady=5)
                if row[7]:
                    ctk.CTkButton(af, text="Comprar Novo", fg_color="#d64545", hover_color="#8b0000", height=24, command=lambda u=row[7]: open_url(u)).pack(side="right", padx=15, pady=5)
            
            card = ModernCard(self.list_frame)
            card.pack(side="top", fill="x", padx=10, pady=10)
            
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=5, pady=5)
            
            ctk.CTkButton(top, text="X", width=30, height=20, fg_color="transparent", text_color="#d64545", hover_color="#442222", 
                          command=lambda i=row[0]: self.delete_item(i)).pack(side="right", padx=2)
            
            ctk.CTkButton(top, text="✎", width=30, height=20, fg_color="transparent", text_color="#ccc", hover_color="#444", 
                          command=lambda r=row: self.edit_item(r[0], r[1], r[2], r[3], r[8])).pack(side="right")
                          
            if row[7]:
                 ctk.CTkButton(top, text="Link", width=40, height=20, fg_color="transparent", text_color="#00a2ff", hover_color="#1d303b", 
                          command=lambda url=row[7]: open_url(url)).pack(side="left")

            body = ctk.CTkFrame(card, fg_color="transparent")
            body.pack(fill="x")

            img_ctk = load_and_resize_image(row[6], size=(80, 80))
            if img_ctk:
                self.list_frame.images.append(img_ctk)
                ctk.CTkLabel(body, text="", image=img_ctk).pack(side="left", padx=15)
            else:
                f = ctk.CTkFrame(body, width=80, height=80, corner_radius=10, fg_color="#333")
                f.pack(side="left", padx=15)
                ctk.CTkLabel(f, text="Sem Img").place(relx=0.5, rely=0.5, anchor="center")
            
            info = ctk.CTkFrame(body, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(info, text=f"{row[1]} {row[2]} - {row[3]}", font=ctk.CTkFont(weight="bold", size=16)).pack(anchor="w")
            
            p_rolo = row[8] or 0.0
            if p_rolo > 0:
                ctk.CTkLabel(info, text=f"R$ {p_rolo:.2f} / rolo", text_color="#aaa", font=ctk.CTkFont(size=11)).pack(anchor="w")
            
            prog = row[5] / row[4] if row[4] > 0 else 0
            pb = ctk.CTkProgressBar(info, width=200, height=6, progress_color="#00a2ff" if prog > 0.2 else "#d64545")
            pb.pack(pady=5, anchor="w")
            pb.set(prog)
            
            ctk.CTkLabel(info, text=f"{row[5]:.2f}KG restantes", font=ctk.CTkFont(size=12)).pack(anchor="w")
''', code, flags=re.DOTALL)

# TabPedidos
code = re.sub(r'class TabPedidos\(ctk\.CTkFrame\):.*?(?=class TabFinanceiro)', '''class TabPedidos(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        # MUDANCA CRITICA DA ABA PEDIDOS
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(side="top", fill="x", anchor="n", padx=20, pady=(10,0))
        
        self.form_card = ModernCard(self.top_frame, border_color="#00a2ff", border_width=2)
        self.form_card.pack(side="top", fill="x", anchor="n", pady=(10, 5))
        
        f1 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f1.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(f1, text="Cliente:").pack(side="left", padx=5)
        self.cliente_var = ctk.StringVar()
        ctk.CTkEntry(f1, textvariable=self.cliente_var, width=150).pack(side="left", padx=5)
        
        ctk.CTkLabel(f1, text="Peça:").pack(side="left", padx=5)
        self.acervo_dict = self.get_acervo_dict()
        self.peca_combo = ctk.CTkComboBox(f1, values=list(self.acervo_dict.keys()) if self.acervo_dict else ["Nenhuma Peça"])
        self.peca_combo.pack(side="left", padx=5)
        
        ctk.CTkButton(f1, text="+ Peça", width=50, fg_color="#333", command=self.add_peca_ui).pack(side="left", padx=5)
        
        ctk.CTkLabel(f1, text="Data:").pack(side="left", padx=5)
        self.data_var = ctk.StringVar()
        ctk.CTkEntry(f1, textvariable=self.data_var, width=90, placeholder_text="Ex: 30/05").pack(side="left", padx=5)
        
        ctk.CTkLabel(f1, text="Valor Total ($):").pack(side="left", padx=5)
        self.valor_var = ctk.StringVar()
        ctk.CTkEntry(f1, textvariable=self.valor_var, width=80).pack(side="left", padx=5)
        
        ctk.CTkButton(f1, text="Criar Pedido", fg_color="#00a2ff", command=self.criar_pedido).pack(side="right", padx=5)
        
        self.pecas_selecionadas = []
        self.pecas_ui_frame = ctk.CTkFrame(self.form_card, fg_color="transparent")
        self.pecas_ui_frame.pack(fill="x", padx=15, pady=(0, 6))
        
        self.kanban_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.kanban_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(0,20))
        self.kanban_frame.grid_columnconfigure((0,1,2), weight=1)
        self.kanban_frame.grid_rowconfigure(0, weight=1)
        
        self.col_fazer = self.create_col(0, "A Fazer", "#1a1a1a")
        self.col_imp = self.create_col(1, "Imprimindo", "#1a1a1a")
        self.col_entregue = self.create_col(2, "Entregue", "#1a1a1a")
        
        self.load_pedidos()

    def create_col(self, col, title, color):
        f = ctk.CTkFrame(self.kanban_frame, fg_color=color, corner_radius=10, border_width=1, border_color="#333333")
        f.grid(row=0, column=col, sticky="nsew", padx=5)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(weight="bold", size=16), pady=10).pack()
        scroll = ctk.CTkScrollableFrame(f, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        return scroll

    def get_acervo_dict(self):
        conn = sqlite3.connect("print_manager_v2.db")
        rows = conn.execute("SELECT id, nome_peca FROM acervo").fetchall()
        conn.close()
        return {r[1]: r[0] for r in rows}

    def add_peca_ui(self):
        p_name = self.peca_combo.get()
        if not p_name or p_name not in self.acervo_dict: return
        p_id = self.acervo_dict[p_name]
        
        row_ui = ctk.CTkFrame(self.pecas_ui_frame, fg_color="#333", corner_radius=5)
        row_ui.pack(side="left", padx=5)
        ctk.CTkLabel(row_ui, text=p_name).pack(side="left", padx=10)
        ctk.CTkButton(row_ui, text="X", width=20, fg_color="transparent", text_color="#d64545", hover_color="#442222", command=lambda r=row_ui: self.remover_peca_ui(r)).pack(side="right")
        self.pecas_selecionadas.append({'id': p_id, 'ui': row_ui})

    def remover_peca_ui(self, row_ui):
        row_ui.destroy()
        self.pecas_selecionadas = [i for i in self.pecas_selecionadas if i['ui'] != row_ui]

    def criar_pedido(self):
        cliente, data, val = self.cliente_var.get(), self.data_var.get(), self.valor_var.get()
        if not cliente or not self.pecas_selecionadas: 
            return messagebox.showerror("Erro", "Adicione cliente e ao menos 1 peça.")
        try: v = float(val.replace(',', '.')) if val else 0.0
        except: v = 0.0
        
        conn = sqlite3.connect("print_manager_v2.db")
        c = conn.cursor()
        c.execute("INSERT INTO pedidos_v2 (nome_cliente, data_entrega, valor_cobrado, status) VALUES (?, ?, ?, ?)",
                     (cliente, data, v, "A Fazer"))
        p_id = c.lastrowid
        for item in self.pecas_selecionadas:
            c.execute("INSERT INTO pedidos_itens (pedido_id, acervo_id) VALUES (?, ?)", (p_id, item['id']))
            item['ui'].destroy()
            
        conn.commit(); conn.close()
        self.pecas_selecionadas = []
        self.cliente_var.set(""); self.valor_var.set(""); self.data_var.set("")
        self.load_pedidos()

    def move_pedido(self, p_id, novo_status):
        conn = sqlite3.connect("print_manager_v2.db")
        conn.execute("UPDATE pedidos_v2 SET status=? WHERE id=?", (novo_status, p_id))
        conn.commit(); conn.close()
        self.load_pedidos()

    def delete_pedido(self, p_id):
        if messagebox.askyesno("Confirmar", "Excluir este pedido?"):
            conn = sqlite3.connect("print_manager_v2.db")
            conn.execute("DELETE FROM pedidos_itens WHERE pedido_id=?", (p_id,))
            conn.execute("DELETE FROM pedidos_v2 WHERE id=?", (p_id,))
            conn.commit(); conn.close()
            self.load_pedidos()

    def load_pedidos(self):
        for col in [self.col_fazer, self.col_imp, self.col_entregue]:
            for w in col.winfo_children(): w.destroy()
            
        conn = sqlite3.connect("print_manager_v2.db")
        rows = conn.execute("SELECT id, nome_cliente, data_entrega, valor_cobrado, status FROM pedidos_v2").fetchall()
        
        for r in rows:
            p_id, cliente, data, valor, status = r
            parent = self.col_fazer if status == "A Fazer" else self.col_imp if status == "Imprimindo" else self.col_entregue
            
            card = ModernCard(parent, border_color="#00a2ff" if status=="Imprimindo" else "#333333")
            card.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(card, text=f"👤 {cliente}", font=ctk.CTkFont(weight="bold")).pack(pady=(5,0))
            
            itens = conn.execute("SELECT a.nome_peca FROM pedidos_itens pi JOIN acervo a ON pi.acervo_id = a.id WHERE pi.pedido_id=?", (p_id,)).fetchall()
            for (nome_p,) in itens:
                ctk.CTkLabel(card, text=f"- {nome_p}", text_color="#ccc", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=15)
            
            if data: ctk.CTkLabel(card, text=f"📅 Entrega: {data}", text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=(5,0))
            if valor > 0: ctk.CTkLabel(card, text=f"R$ {valor:.2f}", text_color="#2b7a4b").pack()
            
            btns = ctk.CTkFrame(card, fg_color="transparent")
            btns.pack(fill="x", pady=5)
            if status == "Imprimindo" or status == "Entregue":
                prev = "A Fazer" if status == "Imprimindo" else "Imprimindo"
                ctk.CTkButton(btns, text="<", width=30, height=20, command=lambda i=p_id, s=prev: self.move_pedido(i, s)).pack(side="left", padx=5)
            
            ctk.CTkButton(btns, text="X", width=30, height=20, fg_color="#d64545", hover_color="#8b0000", command=lambda i=p_id: self.delete_pedido(i)).pack(side="left", expand=True)
            
            if status == "A Fazer" or status == "Imprimindo":
                nxt = "Imprimindo" if status == "A Fazer" else "Entregue"
                ctk.CTkButton(btns, text=">", width=30, height=20, command=lambda i=p_id, s=nxt: self.move_pedido(i, s)).pack(side="right", padx=5)
        conn.close()

''', code, flags=re.DOTALL)

with open("app.py", "w") as f:
    f.write(code)

