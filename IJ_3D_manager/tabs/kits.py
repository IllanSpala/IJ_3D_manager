"""
Aba de Kits — agrupa peças do Acervo em conjuntos (ex: Kit Dark Souls).
"""
import os
import datetime
import customtkinter as ctk
from tkinter import messagebox, filedialog
from core.database import db
from core.state import app_state
from core.widgets import ModernCard
from core.utils import (load_and_resize_image, copy_to_media,
                        resolve_media_path, ACCENT_COLOR, APP_BG_COLOR, BORDER_COLOR)


# ─── Kit card (displayed in the list) ────────────────────────────────────────
class KitCard(ModernCard):
    def __init__(self, master, kit, on_delete, on_edit, **kw):
        super().__init__(master, **kw)
        self.kit = kit
        self.kit_id = kit["id"]

        self.grid_columnconfigure(1, weight=1)

        # Thumbnail
        img_label = ctk.CTkLabel(self, text="S/ Img", fg_color="#222",
                                 width=80, height=80, corner_radius=6)
        img_label.grid(row=0, column=0, rowspan=4, padx=12, pady=12, sticky="n")
        if kit.get("caminho_foto"):
            full = resolve_media_path(kit["caminho_foto"])
            img = load_and_resize_image(full, size=(80, 80))
            if img:
                img_label.configure(image=img, text="")
                img_label.image = img

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(12, 0))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=kit["nome_kit"],
                     font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w")

        # Action buttons
        ctk.CTkButton(header, text="✏ Editar", width=80, height=26,
                      fg_color="#2d2d44", hover_color="#3d3d5c",
                      command=lambda: on_edit(kit)).grid(row=0, column=1, padx=4)
        ctk.CTkButton(header, text="✕", width=28, height=26,
                      fg_color="transparent", text_color="#d64545",
                      command=lambda: on_delete(self.kit_id)).grid(row=0, column=2, padx=4)

        # Description
        if kit.get("descricao"):
            ctk.CTkLabel(self, text=kit["descricao"],
                         text_color="#aaa", font=ctk.CTkFont(size=12),
                         wraplength=450, anchor="w", justify="left").grid(
                row=1, column=1, sticky="w", padx=(0, 12))

        # Items list
        itens = kit.get("itens", [])
        if itens:
            it_frame = ctk.CTkFrame(self, fg_color="transparent")
            it_frame.grid(row=2, column=1, sticky="w", pady=(4, 8), padx=(0, 12))
            for it in itens:
                qty_txt = f" ×{it['quantidade']}" if it.get("quantidade", 1) > 1 else ""
                ctk.CTkLabel(it_frame,
                             text=f"• {it['nome_peca']}{qty_txt}",
                             text_color="#89b4fa",
                             font=ctk.CTkFont(size=12)).pack(anchor="w")
        else:
            ctk.CTkLabel(self, text="Nenhuma peça vinculada.",
                         text_color="#555", font=ctk.CTkFont(size=11)).grid(
                row=2, column=1, sticky="w", padx=(0, 12), pady=(4, 8))


# ─── Edit/Create dialog ───────────────────────────────────────────────────────
class KitDialog(ctk.CTkToplevel):
    """Modal to create or edit a kit."""
    def __init__(self, master, kit=None, on_saved=None):
        super().__init__(master)
        self.title("Editar Kit" if kit else "Novo Kit")
        self.geometry("560x620")
        self.configure(fg_color=APP_BG_COLOR)
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.kit = kit
        self.on_saved = on_saved
        self._foto_filename = kit.get("caminho_foto") if kit else None
        self._item_rows: list[dict] = []   # {acervo_id, qty_var, frame}

        self.grid_columnconfigure(0, weight=1)

        # ── Fields ──────────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Nome do Kit:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 0))
        self.nome_var = ctk.StringVar(value=kit["nome_kit"] if kit else "")
        ctk.CTkEntry(self, textvariable=self.nome_var, placeholder_text="Ex: Kit Dark Souls").grid(
            row=1, column=0, sticky="ew", padx=20, pady=(4, 0))

        ctk.CTkLabel(self, text="Descrição:", font=ctk.CTkFont(weight="bold")).grid(
            row=2, column=0, sticky="w", padx=20, pady=(12, 0))
        self.txt_desc = ctk.CTkTextbox(self, height=70, fg_color="#181818",
                                       border_width=1, border_color="#333")
        self.txt_desc.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 0))
        if kit and kit.get("descricao"):
            self.txt_desc.insert("1.0", kit["descricao"])

        # Foto
        foto_row = ctk.CTkFrame(self, fg_color="transparent")
        foto_row.grid(row=4, column=0, sticky="w", padx=20, pady=(12, 0))
        self.btn_foto = ctk.CTkButton(foto_row, text="Foto do Kit (opcional)",
                                      fg_color="#333", hover_color="#444",
                                      command=self._select_foto)
        self.btn_foto.pack(side="left")
        if self._foto_filename:
            self.btn_foto.configure(text="📷 Foto Anexada", fg_color="#2b7a4b")

        # ── Peças ────────────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Peças do Kit:", font=ctk.CTkFont(weight="bold")).grid(
            row=5, column=0, sticky="w", padx=20, pady=(16, 0))

        self.items_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", height=160)
        self.items_scroll.grid(row=6, column=0, sticky="nsew", padx=20, pady=(4, 0))
        self.grid_rowconfigure(6, weight=1)

        # Add-item row
        add_row = ctk.CTkFrame(self, fg_color="transparent")
        add_row.grid(row=7, column=0, sticky="ew", padx=20, pady=(8, 0))
        add_row.grid_columnconfigure(0, weight=1)

        self._acervo_dict = self._get_acervo()
        self._combo = ctk.CTkComboBox(add_row,
                                      values=list(self._acervo_dict.keys()) or ["Nenhuma peça"])
        self._combo.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(add_row, text="+ Adicionar Peça", width=130, fg_color="#333",
                      hover_color="#444", command=self._add_item_row).grid(row=0, column=1)

        # Save
        ctk.CTkButton(self, text="💾 Salvar Kit", height=40,
                      font=ctk.CTkFont(weight="bold"), fg_color=ACCENT_COLOR,
                      command=self._salvar).grid(row=8, column=0, sticky="ew",
                                                  padx=20, pady=(12, 20))

        # Pre-populate if editing
        if kit and kit.get("itens"):
            for it in kit["itens"]:
                self._add_item_row(
                    acervo_id=it["acervo_id"],
                    nome=it["nome_peca"],
                    qty=it.get("quantidade", 1)
                )

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _get_acervo(self):
        with db.get_connection() as conn:
            rows = conn.execute("SELECT id, nome_peca FROM acervo ORDER BY nome_peca").fetchall()
        return {r[1]: r[0] for r in rows}

    def _select_foto(self):
        path = filedialog.askopenfilename(filetypes=[("Imagens", "*.jpg *.jpeg *.png")])
        if not path: return
        try:
            self._foto_filename = copy_to_media(path)
            self.btn_foto.configure(text="📷 Foto Anexada", fg_color="#2b7a4b")
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))

    def _add_item_row(self, acervo_id=None, nome=None, qty=1):
        if acervo_id is None:
            nome = self._combo.get()
            if nome not in self._acervo_dict:
                return
            acervo_id = self._acervo_dict[nome]

        if any(r["acervo_id"] == acervo_id for r in self._item_rows):
            messagebox.showwarning("Duplicado", "Esta peça já está no kit.")
            return

        frame = ctk.CTkFrame(self.items_scroll, fg_color="#2a2a2a", corner_radius=6)
        frame.pack(fill="x", pady=2, padx=2)

        ctk.CTkLabel(frame, text=nome or "Peça",
                     font=ctk.CTkFont(size=12), width=200, anchor="w").pack(side="left", padx=8)

        ctk.CTkLabel(frame, text="Qtd:", text_color="gray",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(8, 2))
        qty_var = ctk.StringVar(value=str(qty))
        ctk.CTkEntry(frame, textvariable=qty_var, width=50, height=24).pack(side="left", padx=(0, 8))

        row_ref = {"acervo_id": acervo_id, "qty_var": qty_var, "frame": frame}

        def _rem(rr=row_ref):
            rr["frame"].destroy()
            self._item_rows[:] = [r for r in self._item_rows if r is not rr]

        ctk.CTkButton(frame, text="✕", width=24, height=24,
                      fg_color="transparent", text_color="#d64545",
                      command=_rem).pack(side="right", padx=4)

        self._item_rows.append(row_ref)

    def _salvar(self):
        nome = self.nome_var.get().strip()
        if not nome:
            messagebox.showerror("Erro", "O nome do kit é obrigatório.")
            return
        if not self._item_rows:
            messagebox.showerror("Erro", "Adicione pelo menos uma peça ao kit.")
            return

        descricao = self.txt_desc.get("1.0", "end-1c")
        hoje = datetime.date.today().isoformat()

        with db.get_connection() as conn:
            c = conn.cursor()
            if self.kit:
                c.execute(
                    "UPDATE kits_acervo SET nome_kit=?, descricao=?, caminho_foto=? WHERE id=?",
                    (nome, descricao, self._foto_filename, self.kit["id"])
                )
                c.execute("DELETE FROM kit_itens WHERE kit_id=?", (self.kit["id"],))
                kit_id = self.kit["id"]
            else:
                c.execute(
                    "INSERT INTO kits_acervo (nome_kit, descricao, caminho_foto, data_registro) VALUES (?,?,?,?)",
                    (nome, descricao, self._foto_filename, hoje)
                )
                kit_id = c.lastrowid

            for row in self._item_rows:
                try:
                    qty = int(row["qty_var"].get())
                except ValueError:
                    qty = 1
                c.execute(
                    "INSERT INTO kit_itens (kit_id, acervo_id, quantidade) VALUES (?,?,?)",
                    (kit_id, row["acervo_id"], qty)
                )
            conn.commit()

        if self.on_saved:
            self.on_saved()
        self.destroy()


# ─── Kits tab ────────────────────────────────────────────────────────────────
class TabKits(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.toggle_btn = ctk.CTkButton(
            self, text="+ Criar Novo Kit",
            fg_color="transparent", text_color=ACCENT_COLOR,
            anchor="w", hover_color="#222", command=self._novo_kit
        )
        self.toggle_btn.pack(side="top", fill="x", padx=20, pady=(10, 0))

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(side="top", fill="both", expand=True, padx=20, pady=10)

        self._cards: list = []
        self._refresh()

    # ── Data ─────────────────────────────────────────────────────────────────
    def _load_kits(self):
        with db.get_connection() as conn:
            import sqlite3
            conn.row_factory = sqlite3.Row
            kits = [dict(r) for r in conn.execute(
                "SELECT * FROM kits_acervo ORDER BY id DESC"
            ).fetchall()]
            for k in kits:
                rows = conn.execute(
                    """SELECT ki.acervo_id, ki.quantidade, a.nome_peca
                       FROM kit_itens ki JOIN acervo a ON ki.acervo_id=a.id
                       WHERE ki.kit_id=?""", (k["id"],)
                ).fetchall()
                k["itens"] = [dict(r) for r in rows]
        return kits

    def _refresh(self):
        for w in self._cards:
            w.destroy()
        self._cards = []
        for kit in self._load_kits():
            card = KitCard(
                self.list_frame, kit,
                on_delete=self._delete_kit,
                on_edit=self._edit_kit
            )
            card.pack(fill="x", padx=6, pady=6)
            self._cards.append(card)

    # ── Actions ──────────────────────────────────────────────────────────────
    def _novo_kit(self):
        KitDialog(self, kit=None, on_saved=self._refresh)

    def _edit_kit(self, kit):
        KitDialog(self, kit=kit, on_saved=self._refresh)

    def _delete_kit(self, kit_id):
        if messagebox.askyesno("Confirmar", "Remover este kit? As peças individuais não serão afetadas."):
            with db.get_connection() as conn:
                conn.execute("DELETE FROM kit_itens WHERE kit_id=?", (kit_id,))
                conn.execute("DELETE FROM kits_acervo WHERE id=?", (kit_id,))
                conn.commit()
            self._refresh()
