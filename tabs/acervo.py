import os
import datetime
import customtkinter as ctk
from tkinter import messagebox, filedialog
from core.state import app_state
from core.widgets import ModernCard, InlineEdit, HorizontalInventoryCard, SearchableComboBox
from core.utils import load_and_resize_image, copy_to_media, resolve_media_path, ACCENT_COLOR, APP_BG_COLOR, BORDER_COLOR


# ── Lazy-loading image label ──────────────────────────────────────────────────
class _LazyImage:
    """
    Defers image loading until the widget is actually visible on screen.
    Uses `after_idle` so the main loop stays fluid while cards populate.
    """
    def __init__(self, label: ctk.CTkLabel, caminho: str | None, size=(90, 90)):
        self._label   = label
        self._caminho = caminho
        self._size    = size
        self._loaded  = False
        label.after_idle(self._load)

    def _load(self):
        if self._loaded or not self._label.winfo_exists():
            return
        self._loaded = True
        if not self._caminho:
            return
        full = resolve_media_path(self._caminho)
        img  = load_and_resize_image(full, size=self._size)
        if img and self._label.winfo_exists():
            self._label.configure(image=img, text="")
            self._label.image = img  # keep ref


class AcervoCard(HorizontalInventoryCard):
    def __init__(self, master, data, **kwargs):
        super().__init__(master, data, **kwargs)
        self.a_id = data['id']

        self.content_frame.grid_columnconfigure(0, weight=1)

        # ── Top bar ───────────────────────────────────────────────────────
        top_bar = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        top_bar.grid_columnconfigure(0, weight=1)

        self.nome_entry = InlineEdit(
            top_bar, data['nome_peca'],
            self._make_saver('nome_peca'),
            font=ctk.CTkFont(weight="bold", size=18)
        )
        self.nome_entry.grid(row=0, column=0, sticky="ew")

        # Action buttons — icon only
        # col 1: print count  col 2: −(falha)  col 3: ⚙(detalhes)  col 4: ✕(delete)  col 5: +(impressão)
        self.count_label = ctk.CTkLabel(
            top_bar, text=f"🖨 {data.get('total_impressoes', 0)}",
            font=ctk.CTkFont(weight="bold", size=13), text_color="#aaa"
        )
        self.count_label.grid(row=0, column=1, padx=(10, 4))

        ctk.CTkButton(top_bar, text="−", width=28, height=26,
                      fg_color="#7a2b2b", hover_color="#5c1d1d",
                      font=ctk.CTkFont(size=16, weight="bold"),
                      command=self._desregistrar_impressao).grid(row=0, column=2, padx=3)

        ctk.CTkButton(top_bar, text="⚙", width=28, height=26,
                      fg_color="transparent", border_width=1, border_color="#555",
                      hover_color="#333", font=ctk.CTkFont(size=15),
                      command=self._open_detalhes).grid(row=0, column=3, padx=3)

        ctk.CTkButton(top_bar, text="✕", width=28, height=26,
                      fg_color="transparent", text_color="#d64545",
                      hover_color="#3d1818", font=ctk.CTkFont(size=14),
                      command=self._delete).grid(row=0, column=4, padx=3)

        ctk.CTkButton(top_bar, text="+", width=28, height=26,
                      fg_color="#2b7a4b", hover_color="#1d5c36",
                      font=ctk.CTkFont(size=18, weight="bold"),
                      command=self._registrar_impressao).grid(row=0, column=5, padx=(3, 6))

        # ── Meta info ──────────────────────────────────────────────────────
        meta_row = 1

        # Tempo de impressão e preço de custo (sempre visíveis se existirem)
        tempo = data.get('tempo_impressao') or ''
        custo = data.get('preco_custo')
        if tempo or custo is not None:
            info_parts = []
            if tempo:
                info_parts.append(f"⏱ {tempo}")
            if custo is not None and custo > 0:
                info_parts.append(f"💰 R$ {custo:.2f}")
            self.info_label = ctk.CTkLabel(
                self.content_frame,
                text="  |  ".join(info_parts),
                text_color="#a0c4ff", font=ctk.CTkFont(size=12, weight="bold")
            )
            self.info_label.grid(row=meta_row, column=0, sticky="w")
            meta_row += 1
        else:
            self.info_label = None

        # Custo de material calculado (proporcional ao filamento)
        custo_mat = data.get('custo_material')
        if custo_mat is not None and custo_mat > 0:
            self.custo_mat_label = ctk.CTkLabel(
                self.content_frame,
                text=f"🧵 Custo Material: R$ {custo_mat:.2f}",
                text_color="#f0c060", font=ctk.CTkFont(size=11)
            )
            self.custo_mat_label.grid(row=meta_row, column=0, sticky="w")
            meta_row += 1
        else:
            self.custo_mat_label = None

        if data.get('ultima_impressao'):
            ctk.CTkLabel(self.content_frame,
                         text=f"Última impressão: {data['ultima_impressao']}",
                         text_color="#aaa", font=ctk.CTkFont(size=11)).grid(
                row=meta_row, column=0, sticky="w")
            meta_row += 1

        if data.get('arquivo_3d'):
            ctk.CTkLabel(self.content_frame,
                         text=f"3D: {os.path.basename(data['arquivo_3d'])}",
                         text_color=ACCENT_COLOR, font=ctk.CTkFont(size=11)).grid(
                row=meta_row, column=0, sticky="w")

        # ── Lazy-load card thumbnail ───────────────────────────────────────
        _LazyImage(self.img_label, data.get('caminho_foto'), size=(90, 90))

    def update_data(self, data):
        self.data = data
        self.nome_entry.delete(0, 'end')
        self.nome_entry.insert(0, data['nome_peca'])
        self.count_label.configure(text=f"🖨 {data.get('total_impressoes', 0)}")
        # Atualiza label de tempo/custo se existir
        if self.info_label and self.info_label.winfo_exists():
            tempo = data.get('tempo_impressao') or ''
            custo = data.get('preco_custo')
            info_parts = []
            if tempo:
                info_parts.append(f"⏱ {tempo}")
            if custo is not None and custo > 0:
                info_parts.append(f"💰 R$ {custo:.2f}")
            self.info_label.configure(text="  |  ".join(info_parts) if info_parts else "")
        # Atualiza custo material
        if self.custo_mat_label and self.custo_mat_label.winfo_exists():
            custo_mat = data.get('custo_material')
            if custo_mat is not None and custo_mat > 0:
                self.custo_mat_label.configure(text=f"🧵 Custo Material: R$ {custo_mat:.2f}")
            else:
                self.custo_mat_label.configure(text="")
        _LazyImage(self.img_label, data.get('caminho_foto'), size=(90, 90))

    def _make_saver(self, field):
        def saver(val):
            app_state.update_acervo(self.a_id, {field: val})
            return True
        return saver

    def _delete(self):
        if messagebox.askyesno("Confirmar", "Remover esta peça?"):
            from core.database import db
            with db.get_connection() as conn:
                conn.execute("DELETE FROM acervo_impressoes WHERE acervo_id=?", (self.a_id,))
                conn.execute("DELETE FROM acervo_filamentos WHERE acervo_id=?", (self.a_id,))
                conn.execute("DELETE FROM acervo WHERE id=?", (self.a_id,))
                conn.commit()
            app_state.load_acervo()

    def _open_detalhes(self):
        self.winfo_toplevel().modals['detalhes'].show(
            self.data,
            lambda i, u: app_state.update_acervo(i, u),
            mode='acervo'
        )

    def _registrar_impressao(self):
        dialog = ctk.CTkInputDialog(text="Desperdício/Purga gerada (gramas):",
                                    title="Registrar Nova Impressão")
        val = dialog.get_input()
        if val is None:
            return
        try:
            purga_g = float(val.replace(',', '.'))
        except ValueError:
            messagebox.showerror("Erro", "Valor de purga inválido.")
            return

        from core.database import db
        with db.get_connection() as conn:
            c = conn.cursor()
            agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("INSERT INTO acervo_impressoes (acervo_id, data_impressao) VALUES (?,?)",
                      (self.a_id, agora))

            materiais = self.data.get('materiais', [])
            if materiais:
                purga_por_material = (purga_g / 1000.0) / len(materiais)
                for f in materiais:
                    f_id = f['filamento_id']
                    peso_gasto = f['peso_gasto']
                    row = c.execute(
                        "SELECT peso_atual, rolos_reserva, peso_inicial FROM filamentos WHERE id=?",
                        (f_id,)
                    ).fetchone()
                    if row:
                        peso_atual, rolos_reserva, peso_inicial = row
                        consumo_total = peso_gasto + purga_por_material
                        novo_peso = peso_atual - consumo_total
                        while novo_peso <= 0 and rolos_reserva > 0:
                            rolos_reserva -= 1
                            novo_peso += peso_inicial
                        novo_status = ('Arquivado'
                                       if (novo_peso <= 0 and rolos_reserva == 0) else 'Ativo')
                        c.execute(
                            "UPDATE filamentos SET peso_atual=?, rolos_reserva=?, status=? WHERE id=?",
                            (max(0, novo_peso), rolos_reserva, novo_status, f_id)
                        )
            conn.commit()

        app_state.load_acervo()
        app_state.load_filamentos()

    def _desregistrar_impressao(self):
        from core.database import db
        with db.get_connection() as conn:
            c = conn.cursor()
            row = c.execute(
                "SELECT id FROM acervo_impressoes WHERE acervo_id=? ORDER BY id DESC LIMIT 1",
                (self.a_id,)
            ).fetchone()
            if not row:
                messagebox.showinfo("Info", "Nenhuma impressão registrada para reverter.")
                return
            impressao_id = row[0]
            c.execute("DELETE FROM acervo_impressoes WHERE id=?", (impressao_id,))

            materiais = self.data.get('materiais', [])
            if materiais:
                for f in materiais:
                    f_id = f['filamento_id']
                    peso_gasto = f['peso_gasto']
                    peso_purga = f.get('peso_desperdicio', 0)
                    devolver = peso_gasto + peso_purga
                    row2 = c.execute(
                        "SELECT peso_atual, rolos_reserva, peso_inicial FROM filamentos WHERE id=?",
                        (f_id,)
                    ).fetchone()
                    if row2:
                        peso_atual, rolos_reserva, peso_inicial = row2
                        novo_peso = peso_atual + devolver
                        while novo_peso > peso_inicial and rolos_reserva > 0:
                            rolos_reserva -= 1
                            novo_peso -= peso_inicial
                        c.execute(
                            "UPDATE filamentos SET peso_atual=?, rolos_reserva=?, status=? WHERE id=?",
                            (min(novo_peso, peso_inicial), rolos_reserva, 'Ativo', f_id)
                        )
            conn.commit()

        app_state.load_acervo()
        app_state.load_filamentos()


class TabAcervo(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.form_visible = False

        self.toggle_btn = ctk.CTkButton(
            self, text="+ Adicionar Nova Peça",
            fg_color="transparent", text_color=ACCENT_COLOR,
            anchor="w", hover_color="#222", command=self._toggle_form
        )
        self.toggle_btn.pack(side="top", fill="x", padx=20, pady=(10, 0))

        self.form_card = ModernCard(self)
        self.form_card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(self.form_card, text="Registrar Peça no Acervo",
                     font=ctk.CTkFont(size=20, weight="bold")).grid(
            row=0, column=0, columnspan=2, pady=(15, 10))

        self.nome_var = ctk.StringVar()
        f1 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f1.grid(row=1, column=0, padx=15, pady=5, sticky="ew")
        ctk.CTkLabel(f1, text="Nome da Peça", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f1, textvariable=self.nome_var,
                     placeholder_text="Ex: Suporte Fone").pack(fill="x")

        self.pos_var = ctk.StringVar()
        f4 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f4.grid(row=1, column=1, padx=15, pady=5, sticky="ew")
        ctk.CTkLabel(f4, text="Pós-Processamento (Opcional)", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f4, textvariable=self.pos_var,
                     placeholder_text="Ex: Lixamento, Pintura").pack(fill="x")

        files_frame = ctk.CTkFrame(self.form_card, fg_color="transparent")
        files_frame.grid(row=2, column=0, columnspan=2, padx=15, pady=10, sticky="ew")
        files_frame.grid_columnconfigure((0, 1), weight=1)

        self._new_foto_filename = None
        self._arquivo_3d_path   = None

        self.btn_foto = ctk.CTkButton(files_frame, text="Foto da Peça Pronta",
                                      fg_color="#333", hover_color="#444",
                                      command=self._select_photo)
        self.btn_foto.grid(row=0, column=0, padx=5, sticky="ew")

        self.btn_3d = ctk.CTkButton(files_frame, text="Anexar Arquivo 3D (STL/3MF)",
                                    fg_color="#333", hover_color="#444",
                                    command=self._select_3d)
        self.btn_3d.grid(row=0, column=1, padx=5, sticky="ew")

        # Tempo de impressão + Preço de custo
        tempo_frame = ctk.CTkFrame(self.form_card, fg_color="transparent")
        tempo_frame.grid(row=3, column=0, columnspan=2, padx=15, pady=(0, 5), sticky="ew")
        tempo_frame.grid_columnconfigure((0, 1), weight=1)

        tf_left = ctk.CTkFrame(tempo_frame, fg_color="transparent")
        tf_left.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        ctk.CTkLabel(tf_left, text="Tempo de Impressão *", text_color="gray").pack(anchor="w")
        hm_row = ctk.CTkFrame(tf_left, fg_color="transparent")
        hm_row.pack(fill="x")
        self.tempo_h_var = ctk.StringVar(value="0")
        self.tempo_m_var = ctk.StringVar(value="0")
        ctk.CTkEntry(hm_row, textvariable=self.tempo_h_var, width=60).pack(side="left")
        ctk.CTkLabel(hm_row, text="h", text_color="#888", width=18).pack(side="left")
        ctk.CTkEntry(hm_row, textvariable=self.tempo_m_var, width=60).pack(side="left", padx=(6, 0))
        ctk.CTkLabel(hm_row, text="min", text_color="#888").pack(side="left", padx=(4, 0))

        tf_right = ctk.CTkFrame(tempo_frame, fg_color="transparent")
        tf_right.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(tf_right, text="Preço de Custo (R$)", text_color="gray").pack(anchor="w")
        self.preco_custo_var = ctk.StringVar(value="0.00")
        ctk.CTkEntry(tf_right, textvariable=self.preco_custo_var).pack(fill="x")


        self.filamentos_selecionados = []
        self.fil_frame = ctk.CTkFrame(self.form_card, fg_color=APP_BG_COLOR,
                                      corner_radius=10, border_width=1, border_color=BORDER_COLOR)
        self.fil_frame.grid(row=4, column=0, columnspan=2, padx=15, pady=10, sticky="nsew")
        ctk.CTkLabel(self.fil_frame, text="Filamentos Utilizados", text_color="gray").pack(pady=5)

        self.f_list_ui = ctk.CTkFrame(self.fil_frame, fg_color="transparent")
        self.f_list_ui.pack(fill="x", padx=10, pady=5)

        add_row = ctk.CTkFrame(self.fil_frame, fg_color="transparent")
        add_row.pack(fill="x", padx=10, pady=5)

        self.filamentos_dict = self._get_filamentos()
        self.f_combo = SearchableComboBox(
            add_row,
            values=list(self.filamentos_dict.keys()) if self.filamentos_dict else [],
            placeholder_text="Buscar filamento..."
        )
        self.f_combo.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(add_row, text="Adicionar Filamento", width=150,
                      fg_color="#333", command=self._add_filamento_ui).pack(side="right")

        ctk.CTkButton(self.form_card, text="Salvar Peça Completa",
                      height=40, font=ctk.CTkFont(weight="bold"),
                      fg_color=ACCENT_COLOR, command=self._save_peca).grid(
            row=5, column=0, columnspan=2, padx=15, pady=(15, 15), sticky="ew")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(side="top", fill="both", expand=True, padx=20, pady=10)
        self.cards = {}

        app_state.subscribe('acervo', self._on_state_change)
        app_state.subscribe('filamentos', self._on_filamentos_change)
        app_state.load_acervo()

    def _toggle_form(self):
        if self.form_visible:
            self.form_card.pack_forget()
            self.toggle_btn.configure(text="+ Adicionar Nova Peça")
        else:
            self.list_frame.pack_forget()
            self.form_card.pack(side="top", fill="x", padx=20, pady=(5, 5))
            self.list_frame.pack(side="top", fill="both", expand=True, padx=20, pady=10)
            self.toggle_btn.configure(text="- Ocultar Formulário")
        self.form_visible = not self.form_visible

    def _get_filamentos(self):
        from core.database import db
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT id, marca, material, cor FROM filamentos WHERE status != 'Arquivado'"
            ).fetchall()
        return {f"{r[1]} {r[2]} ({r[3]})": r[0] for r in rows}

    def _on_filamentos_change(self, event=None):
        self.filamentos_dict = self._get_filamentos()
        new_keys = list(self.filamentos_dict.keys()) if self.filamentos_dict else []
        self.f_combo.configure_values(new_keys)
        if new_keys:
            self.f_combo.set(new_keys[0])
        else:
            self.f_combo.set("")

    def _select_photo(self):
        path = filedialog.askopenfilename(filetypes=[("Imagens", "*.jpg *.jpeg *.png")])
        if not path:
            return
        try:
            self._new_foto_filename = copy_to_media(path)
            self.btn_foto.configure(text="Foto Anexada", fg_color="#2b7a4b")
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))

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

        d_frame = ctk.CTkFrame(row_ui, fg_color="transparent")
        d_frame.pack(side="right", padx=5)
        ctk.CTkLabel(d_frame, text="Purga (g)", font=ctk.CTkFont(size=10),
                     text_color="gray").pack()
        d_var = ctk.StringVar()
        ctk.CTkEntry(d_frame, textvariable=d_var, placeholder_text="15",
                     width=80, height=24).pack()

        p_frame = ctk.CTkFrame(row_ui, fg_color="transparent")
        p_frame.pack(side="right", padx=5)
        ctk.CTkLabel(p_frame, text="Gasto (g)", font=ctk.CTkFont(size=10),
                     text_color="gray").pack()
        p_var = ctk.StringVar()
        ctk.CTkEntry(p_frame, textvariable=p_var, placeholder_text="120",
                     width=80, height=24).pack()

        self.filamentos_selecionados.append({"id": f_id, "ui": row_ui,
                                             "peso_var": p_var, "desp_var": d_var})

    def _remove_f_ui(self, row_ui):
        row_ui.destroy()
        self.filamentos_selecionados = [i for i in self.filamentos_selecionados
                                        if i["ui"] != row_ui]

    def _save_peca(self):
        nome = self.nome_var.get()
        if not nome:
            return messagebox.showerror("Erro", "Nome da peça é obrigatório.")
        if not self.filamentos_selecionados:
            return messagebox.showerror("Erro", "Adicione pelo menos um filamento.")

        # Validar e formatar tempo
        try:
            _h = int(self.tempo_h_var.get().strip() or "0")
            _m = int(self.tempo_m_var.get().strip() or "0")
            if _m < 0 or _m >= 60 or _h < 0:
                raise ValueError
        except ValueError:
            return messagebox.showerror("Erro", "Tempo inválido. Use horas (≥0) e minutos (0-59).")
        tempo_str = f"{_h:02d}:{_m:02d}"

        try:
            preco_custo = float(self.preco_custo_var.get().replace(",", ".") or "0")
        except ValueError:
            return messagebox.showerror("Erro", "Preço de custo deve ser numérico.")

        pesos = []
        for item in self.filamentos_selecionados:
            try:
                p_g = float(item["peso_var"].get().replace(",", ".")) if item["peso_var"].get() else 0.0
                d_g = float(item["desp_var"].get().replace(",", ".")) if item["desp_var"].get() else 0.0
                pesos.append((item["id"], p_g / 1000.0, d_g / 1000.0))
            except ValueError:
                return messagebox.showerror("Erro",
                                            "Pesos dos filamentos e purga devem ser numéricos (gramas).")

        from core.database import db
        with db.get_connection() as conn:
            c = conn.cursor()
            for f_id, p_kg, d_kg in pesos:
                row = c.execute(
                    "SELECT peso_atual, rolos_reserva, peso_inicial FROM filamentos WHERE id=?",
                    (f_id,)
                ).fetchone()
                atual, reserva, inicial = row
                peso_disp = atual + (reserva * inicial)
                if peso_disp < (p_kg + d_kg):
                    if not messagebox.askyesno("Aviso", "Filamento insuficiente. Salvar mesmo assim?"):
                        return

            c.execute(
                "INSERT INTO acervo (nome_peca, caminho_foto, arquivo_3d, pos_processamento, "
                "data_registro, tempo_impressao, preco_custo) VALUES (?,?,?,?,?,?,?)",
                (nome, self._new_foto_filename, self._arquivo_3d_path,
                 self.pos_var.get(), datetime.date.today().isoformat(),
                 tempo_str, preco_custo),
            )
            acervo_id = c.lastrowid

            for f_id, p_kg, d_kg in pesos:
                c.execute(
                    "INSERT INTO acervo_filamentos (acervo_id, filamento_id, peso_gasto, peso_desperdicio) "
                    "VALUES (?,?,?,?)",
                    (acervo_id, f_id, p_kg, d_kg)
                )
            conn.commit()

        # Reset form
        self.nome_var.set(""); self.pos_var.set("")
        self.tempo_h_var.set("0"); self.tempo_m_var.set("0")
        self.preco_custo_var.set("0.00")
        self._new_foto_filename = None; self._arquivo_3d_path = None
        self.btn_foto.configure(text="Foto da Peça Pronta", fg_color="#333")
        self.btn_3d.configure(text="Anexar Arquivo 3D (STL/3MF)", fg_color="#333")
        for item in self.filamentos_selecionados:
            item["ui"].destroy()
        self.filamentos_selecionados = []
        app_state.load_acervo()
        app_state.load_filamentos()

    PAGE_SIZE = 20

    def _on_state_change(self, event=None):
        if event:
            action = event.get('action')
            a_id   = event.get('id')
            if action == 'update' and a_id in self.cards:
                self.cards[a_id].update_data(event['data'])
                return
            elif action == 'remove' and a_id in self.cards:
                self.cards[a_id].destroy()
                del self.cards[a_id]
                return

        # Full rebuild (initial load or structural change)
        for w in self.cards.values():
            w.destroy()
        self.cards = {}
        self._loaded_count = 0
        if hasattr(self, '_load_more_btn') and self._load_more_btn.winfo_exists():
            self._load_more_btn.destroy()
        self._load_more_btn = None
        self._load_page()

    def _load_page(self):
        data_slice = app_state.acervo[self._loaded_count:
                                      self._loaded_count + self.PAGE_SIZE]
        for data in data_slice:
            self._add_card(data)
        self._loaded_count += len(data_slice)

        # Remove old "Carregar Mais" button if present
        if hasattr(self, '_load_more_btn') and self._load_more_btn and \
                self._load_more_btn.winfo_exists():
            self._load_more_btn.destroy()
            self._load_more_btn = None

        if self._loaded_count < len(app_state.acervo):
            remaining = len(app_state.acervo) - self._loaded_count
            self._load_more_btn = ctk.CTkButton(
                self.list_frame,
                text=f"Carregar Mais ({remaining} restantes)",
                fg_color="#2a2a4a", hover_color="#3a3a6a",
                font=ctk.CTkFont(size=13),
                command=self._load_page
            )
            self._load_more_btn.pack(fill="x", padx=10, pady=10)

    def _add_card(self, data):
        card = AcervoCard(self.list_frame, data)
        card.pack(fill="x", padx=10, pady=5)
        self.cards[data['id']] = card
