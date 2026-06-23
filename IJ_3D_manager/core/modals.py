import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from core.state import app_state
from core.utils import load_and_resize_image, copy_to_media, resolve_media_path, ACCENT_COLOR, APP_BG_COLOR, BORDER_COLOR


class DetalhesModal(ctk.CTkToplevel):
    """
    Unified details modal.
    - mode='acervo'    → full acervo editing panel (images, filaments, post, 3mf, slicer prints)
    - mode='filamento' → simple description + link panel (almoxarifado / filamento)

    All edits are held in UI state and committed to DB only when "SALVAR" is pressed.
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("Editar Detalhes")
        self.geometry("820x780")
        self.configure(fg_color=APP_BG_COLOR)
        self.resizable(True, True)

        self.withdraw()
        self.protocol("WM_DELETE_WINDOW", self.hide)

        self.data = None
        self.update_callback = None
        self._mode = None
        self._fotos_extras: list[dict] = []
        self._fil_rows: list[dict] = []
        self._ativos_dict: dict = {}

        # Pending 3MF path chosen but not yet committed
        self._pending_arquivo_3d: str | None = None

        # ── Outer scrollable container ─────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=APP_BG_COLOR)
        self._scroll.pack(fill="both", expand=True)
        self._scroll.grid_columnconfigure(0, weight=1)

        inner = self._scroll

        # ── Section: Images (compact 2-column layout) ──────────────────────
        img_section = ctk.CTkFrame(inner, fg_color="#1a1a1a", corner_radius=10,
                                   border_width=1, border_color=BORDER_COLOR)
        img_section.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        img_section.grid_columnconfigure(1, weight=1)

        # Left: piece photo (compact)
        slot_peca = ctk.CTkFrame(img_section, fg_color="transparent")
        slot_peca.grid(row=0, column=0, padx=(12, 8), pady=12, sticky="nw")

        ctk.CTkLabel(slot_peca, text="Foto da Peça",
                     font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w")
        self.img_label = ctk.CTkLabel(slot_peca, text="Sem Imagem",
                                      width=90, height=90, fg_color="#222", corner_radius=8)
        self.img_label.pack()
        ctk.CTkButton(slot_peca, text="Trocar", height=22, width=90,
                      fg_color="#333", hover_color="#444",
                      font=ctk.CTkFont(size=11),
                      command=self._trocar_imagem).pack(pady=(4, 0))

        # Right: slicer prints gallery (horizontal scroll, compact height)
        self.slot_fat = ctk.CTkFrame(img_section, fg_color="transparent")
        self.slot_fat.grid(row=0, column=1, padx=(0, 12), pady=12, sticky="nsew")

        fat_header = ctk.CTkFrame(self.slot_fat, fg_color="transparent")
        fat_header.pack(fill="x")
        ctk.CTkLabel(fat_header, text="Prints do Fatiador",
                     font=ctk.CTkFont(size=10), text_color="gray").pack(side="left")
        self._btn_add_print = ctk.CTkButton(
            fat_header, text="+ Print", height=22, width=80,
            fg_color="#2d2d44", hover_color="#3d3d5c",
            font=ctk.CTkFont(size=10), command=self._adicionar_print
        )
        self._btn_add_print.pack(side="right")

        self.fat_canvas_frame = ctk.CTkScrollableFrame(
            self.slot_fat, orientation="horizontal",
            fg_color="#181818", corner_radius=6, height=120
        )
        self.fat_canvas_frame.pack(fill="x", pady=(4, 0))

        # ── Section: Descrição + Link ──────────────────────────────────────
        info_section = ctk.CTkFrame(inner, fg_color="#1a1a1a", corner_radius=10,
                                    border_width=1, border_color=BORDER_COLOR)
        info_section.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
        info_section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(info_section, text="Descrição / Configurações de Impressão",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#aaa").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        self.txt_desc = ctk.CTkTextbox(info_section, wrap="word", fg_color="#222",
                                       border_width=1, border_color="#333", height=70)
        self.txt_desc.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(info_section, text="Link de Compra / Referência",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#aaa").grid(row=2, column=0, sticky="w", padx=12, pady=(0, 2))
        self.link_var = ctk.StringVar()
        ctk.CTkEntry(info_section, textvariable=self.link_var,
                     placeholder_text="https://...").grid(
            row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

        # ── Section: Acervo-only widgets ─────────────────────────────────
        # Post-processing
        self._sec_pos = ctk.CTkFrame(inner, fg_color="#1a1a1a", corner_radius=10,
                                     border_width=1, border_color=BORDER_COLOR)
        self._sec_pos.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self._sec_pos, text="Pós-Processamento / Acabamento",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#aaa").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        self.pos_var = ctk.StringVar()
        ctk.CTkEntry(self._sec_pos, textvariable=self.pos_var,
                     placeholder_text="Ex: Lixamento, Pintura Esmalte, UV Resin Coat...").grid(
            row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

        # Fatiador config
        ctk.CTkLabel(self._sec_pos, text="Parâmetros de Fatiamento (chave: valor, 1 por linha)",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#aaa").grid(row=2, column=0, sticky="w", padx=12, pady=(4, 2))
        self.txt_fat = ctk.CTkTextbox(self._sec_pos, wrap="word", fg_color="#222",
                                      border_width=1, border_color="#333", height=80)
        self.txt_fat.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))

        # 3MF file
        file_row = ctk.CTkFrame(self._sec_pos, fg_color="transparent")
        file_row.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))
        file_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(file_row, text="Arquivo 3D (STL/3MF):",
                     text_color="#aaa", font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        self._lbl_arquivo = ctk.CTkLabel(file_row, text="Nenhum", text_color="gray",
                                         font=ctk.CTkFont(size=11), anchor="w")
        self._lbl_arquivo.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ctk.CTkButton(file_row, text="Selecionar", width=90, height=26,
                      fg_color="#333", hover_color="#444",
                      command=self._selecionar_3d).grid(row=0, column=2, padx=(8, 0))

        # ── Section: Filamentos vinculados ────────────────────────────────
        self._sec_fils = ctk.CTkFrame(inner, fg_color="#1a1a1a", corner_radius=10,
                                      border_width=1, border_color=BORDER_COLOR)
        self._sec_fils.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self._sec_fils, text="Filamentos Vinculados (Gasto de Material)",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#aaa").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        self.fil_scroll = ctk.CTkScrollableFrame(self._sec_fils, fg_color="transparent", height=120)
        self.fil_scroll.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))

        add_fil_row = ctk.CTkFrame(self._sec_fils, fg_color="transparent")
        add_fil_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        self._fil_combo_var = ctk.StringVar()
        self._fil_combo = ctk.CTkComboBox(add_fil_row, variable=self._fil_combo_var, width=220)
        self._fil_combo.pack(side="left", padx=(0, 8))
        ctk.CTkButton(add_fil_row, text="+ Vincular Filamento", width=160,
                      fg_color="#333", hover_color="#444",
                      command=self._add_filamento_row).pack(side="left")

        # ── SALVAR button ─────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.grid(row=10, column=0, sticky="ew", padx=16, pady=(4, 20))
        btn_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(btn_frame, text="SALVAR", height=44,
                      font=ctk.CTkFont(size=15, weight="bold"),
                      fg_color=ACCENT_COLOR, hover_color="#007acc",
                      command=self._salvar).grid(row=0, column=0, sticky="ew")

    # ── Public API ─────────────────────────────────────────────────────────────
    def hide(self):
        self.withdraw()

    def show(self, data, update_callback, mode='filamento'):
        self.data = data
        self.update_callback = update_callback
        self._mode = mode
        self._pending_arquivo_3d = None

        # Reset common fields
        self.txt_desc.delete("1.0", "end")
        self.txt_desc.insert("1.0", data.get("descricao") or "")
        self.link_var.set(data.get("link_compra") or "")
        self._update_image()

        if mode == 'acervo':
            self.geometry("820x780")
            # Show acervo sections
            self._sec_pos.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
            self._sec_fils.grid(row=3, column=0, sticky="ew", padx=16, pady=8)
            self.slot_fat.grid()
            self._btn_add_print.pack(side="right")

            # Populate acervo-specific fields
            self.pos_var.set(data.get("pos_processamento") or "")
            self.txt_fat.delete("1.0", "end")
            self.txt_fat.insert("1.0", data.get("config_fatiador") or
                "Paredes: 3\nInfill: Gyroid 15%\nSuportes: Nenhum\n"
                "Temp Bico: 220°C\nTemp Mesa: 60°C\n")

            arquivo = data.get("arquivo_3d")
            self._lbl_arquivo.configure(
                text=os.path.basename(arquivo) if arquivo else "Nenhum",
                text_color=ACCENT_COLOR if arquivo else "gray"
            )

            self._load_fotos_extras(data['id'])
            self._build_filament_section(data)
        else:
            self.geometry("560x500")
            # Hide acervo-only sections
            self._sec_pos.grid_remove()
            self._sec_fils.grid_remove()
            self.slot_fat.grid_remove()

        self.deiconify()
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()

    # ── Image helpers ──────────────────────────────────────────────────────────
    def _update_image(self):
        caminho = self.data.get('caminho_foto') if self.data else None
        if caminho:
            img = load_and_resize_image(resolve_media_path(caminho), size=(90, 90))
            if img:
                self.img_label.configure(image=img, text="")
                self.img_label.image = img
                return
        self.img_label.configure(text="Sem Imagem", image=None)

    def _trocar_imagem(self):
        path = filedialog.askopenfilename(filetypes=[("Imagens", "*.jpg *.jpeg *.png")])
        if path:
            self.attributes("-topmost", False)
            try:
                # Store pending change in self.data — committed only on SALVAR
                self.data['caminho_foto'] = copy_to_media(path)
                self._update_image()
            except RuntimeError as exc:
                messagebox.showerror("Erro", str(exc))
            self.attributes("-topmost", True)

    def _selecionar_3d(self):
        path = filedialog.askopenfilename(
            filetypes=[("Arquivos 3D", "*.3mf *.stl *.obj")],
            title="Selecionar Arquivo 3D"
        )
        if path:
            self._pending_arquivo_3d = path
            self._lbl_arquivo.configure(
                text=os.path.basename(path), text_color=ACCENT_COLOR
            )

    # ── Slicer-prints gallery ──────────────────────────────────────────────────
    def _load_fotos_extras(self, acervo_id):
        for info in self._fotos_extras:
            if info['frame'].winfo_exists():
                info['frame'].destroy()
        self._fotos_extras = []

        from core.database import db
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT id, caminho_foto, legenda FROM acervo_fotos_extras WHERE acervo_id=? ORDER BY id",
                (acervo_id,)
            ).fetchall()

        for foto_id, caminho, legenda in rows:
            self._add_thumbnail(foto_id=foto_id, caminho=caminho,
                                legenda=legenda, is_new=False)

    def _add_thumbnail(self, foto_id, caminho, legenda=None, is_new=True):
        frame = ctk.CTkFrame(self.fat_canvas_frame, fg_color="#2a2a2a",
                             corner_radius=6, width=90)
        frame.pack(side="left", padx=3, pady=3)
        frame.pack_propagate(False)

        lbl = ctk.CTkLabel(frame, text="...", fg_color="#1a1a1a",
                            width=82, height=68, corner_radius=4)
        lbl.pack(padx=4, pady=(4, 2))
        if caminho:
            full = resolve_media_path(caminho)
            img = load_and_resize_image(full, size=(82, 68))
            if img:
                lbl.configure(image=img, text="")
                lbl.image = img

        leg_var = ctk.StringVar(value=legenda or "")
        ctk.CTkEntry(frame, textvariable=leg_var, height=18,
                     placeholder_text="legenda", fg_color="#1a1a1a",
                     font=ctk.CTkFont(size=9)).pack(fill="x", padx=4, pady=(0, 2))

        info = {"id": foto_id, "caminho": caminho, "frame": frame,
                "leg_var": leg_var, "is_new": is_new, "deleted": False}

        def _remove(i=info):
            i["deleted"] = True
            i["frame"].destroy()

        ctk.CTkButton(frame, text="✕", height=18,
                      fg_color="transparent", text_color="#d64545",
                      font=ctk.CTkFont(size=9),
                      command=_remove).pack(fill="x", padx=4, pady=(0, 3))

        self._fotos_extras.append(info)

    def _adicionar_print(self):
        paths = filedialog.askopenfilenames(
            filetypes=[("Imagens", "*.jpg *.jpeg *.png")],
            title="Selecionar Print(s) do Fatiador"
        )
        if not paths:
            return
        self.attributes("-topmost", False)
        for path in paths:
            try:
                caminho = copy_to_media(path)
                self._add_thumbnail(foto_id=None, caminho=caminho, is_new=True)
            except RuntimeError as exc:
                messagebox.showerror("Erro", str(exc))
        self.attributes("-topmost", True)

    # ── Filament section ───────────────────────────────────────────────────────
    def _build_filament_section(self, data):
        for info in self._fil_rows:
            info['frame'].destroy()
        self._fil_rows = []

        from core.database import db
        with db.get_connection() as conn:
            rows = conn.execute(
                """SELECT af.rowid, af.filamento_id, f.marca, f.cor, af.peso_gasto, af.peso_desperdicio
                   FROM acervo_filamentos af
                   JOIN filamentos f ON af.filamento_id = f.id
                   WHERE af.acervo_id=?""", (data['id'],)
            ).fetchall()

        for _, fil_id, marca, cor, peso_g, peso_d in rows:
            self._add_fil_display_row(fil_id=fil_id, label=f"{marca} {cor}",
                                      peso_g=peso_g, peso_d=peso_d, is_new=False)

        with db.get_connection() as conn:
            ativos = conn.execute(
                "SELECT id, marca, material, cor FROM filamentos WHERE status != 'Arquivado'"
            ).fetchall()
        self._ativos_dict = {f"{r[1]} {r[2]} ({r[3]})": r[0] for r in ativos}
        vals = list(self._ativos_dict.keys()) or ["Nenhum"]
        self._fil_combo.configure(values=vals)
        if vals:
            self._fil_combo.set(vals[0])

    def _add_fil_display_row(self, fil_id, label, peso_g, peso_d, is_new=True):
        frame = ctk.CTkFrame(self.fil_scroll, fg_color="#2a2a2a", corner_radius=6)
        frame.pack(fill="x", pady=2)

        ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#ccc", width=160, anchor="w").pack(side="left", padx=(8, 4))

        # Gasto label in green
        ctk.CTkLabel(frame, text="Gasto(g):", text_color="#2b7a4b",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(4, 2))
        p_var = ctk.StringVar(value=f"{round(peso_g * 1000, 2):.2f}")
        ctk.CTkEntry(frame, textvariable=p_var, width=70, height=24,
                     text_color="#2b7a4b").pack(side="left", padx=(0, 6))

        # Purga label in red
        ctk.CTkLabel(frame, text="Purga(g):", text_color="#d64545",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(4, 2))
        d_var = ctk.StringVar(value=f"{round(peso_d * 1000, 2):.2f}")
        ctk.CTkEntry(frame, textvariable=d_var, width=70, height=24,
                     text_color="#d64545").pack(side="left", padx=(0, 6))

        row_ref = {"fil_id": fil_id, "peso_var": p_var, "desp_var": d_var,
                   "frame": frame, "is_new": is_new}

        def _remove(rr=row_ref):
            rr['frame'].destroy()
            self._fil_rows = [r for r in self._fil_rows if r is not rr]

        ctk.CTkButton(frame, text="✕", width=24, height=24, fg_color="transparent",
                      text_color="#d64545", hover_color="#3d1818",
                      command=_remove).pack(side="right", padx=5)

        self._fil_rows.append(row_ref)

    def _add_filamento_row(self):
        name = self._fil_combo.get()
        if not name or name not in self._ativos_dict:
            return
        fil_id = self._ativos_dict[name]
        if any(r['fil_id'] == fil_id for r in self._fil_rows):
            messagebox.showwarning("Duplicado", "Este filamento já está na lista.")
            return
        self._add_fil_display_row(fil_id=fil_id, label=name,
                                  peso_g=0.0, peso_d=0.0, is_new=True)

    # ── SALVAR ─────────────────────────────────────────────────────────────────
    def _salvar(self):
        """Commit all staged changes to DB in a single transaction."""
        nova_desc = self.txt_desc.get("1.0", "end-1c")
        updates = {
            "caminho_foto": self.data.get("caminho_foto"),
            "descricao":    nova_desc,
            "link_compra":  self.link_var.get(),
        }

        if self._mode == 'acervo':
            updates["pos_processamento"] = self.pos_var.get()
            updates["config_fatiador"]   = self.txt_fat.get("1.0", "end-1c")

            if self._pending_arquivo_3d:
                updates["arquivo_3d"] = self._pending_arquivo_3d

            from core.database import db
            a_id = self.data['id']
            with db.get_connection() as conn:
                c = conn.cursor()

                # Rebuild filaments
                c.execute("DELETE FROM acervo_filamentos WHERE acervo_id=?", (a_id,))
                for info in self._fil_rows:
                    try:
                        p_kg = float(info['peso_var'].get().replace(",", ".")) / 1000.0
                        d_kg = float(info['desp_var'].get().replace(",", ".")) / 1000.0
                    except ValueError:
                        messagebox.showerror("Erro", "Pesos dos filamentos devem ser numéricos.")
                        return
                    c.execute(
                        "INSERT INTO acervo_filamentos (acervo_id, filamento_id, peso_gasto, peso_desperdicio) VALUES (?,?,?,?)",
                        (a_id, info['fil_id'], p_kg, d_kg)
                    )

                # Rebuild slicer photos (delete removed, insert new)
                for foto_info in self._fotos_extras:
                    if foto_info["deleted"] and foto_info["id"] is not None:
                        c.execute("DELETE FROM acervo_fotos_extras WHERE id=?",
                                  (foto_info["id"],))

                for foto_info in self._fotos_extras:
                    if foto_info["deleted"]:
                        continue
                    legenda = foto_info["leg_var"].get()
                    if foto_info["is_new"] and foto_info["id"] is None:
                        c.execute(
                            "INSERT INTO acervo_fotos_extras (acervo_id, caminho_foto, legenda) VALUES (?,?,?)",
                            (a_id, foto_info["caminho"], legenda)
                        )
                    elif foto_info["id"] is not None:
                        c.execute(
                            "UPDATE acervo_fotos_extras SET legenda=? WHERE id=?",
                            (legenda, foto_info["id"])
                        )
                conn.commit()

            app_state.load_acervo()

        self.update_callback(self.data['id'], updates)
        self.hide()
