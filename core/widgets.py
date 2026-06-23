import customtkinter as ctk

CARD_BG_COLOR = "#212121"
BORDER_COLOR  = "#333333"

class ModernCard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        bc = kwargs.pop("border_color", BORDER_COLOR)
        bw = kwargs.pop("border_width", 1)
        fc = kwargs.pop("fg_color", CARD_BG_COLOR)
        cr = kwargs.pop("corner_radius", 12)
        super().__init__(
            master, fg_color=fc, corner_radius=cr,
            border_width=bw, border_color=bc, **kwargs,
        )

class InlineEdit(ctk.CTkEntry):
    """An entry widget that looks like a label but allows editing on focus, saving on focus out."""
    def __init__(self, master, initial_value, on_save, text_color="white", font=None, is_double=False, **kwargs):
        super().__init__(
            master,
            fg_color="transparent",
            border_width=0,
            text_color=text_color,
            font=font,
            **kwargs
        )
        self.is_double = is_double
        self.on_save = on_save
        self.default_color = text_color
        
        if self.is_double:
            try:
                initial_value = f"{float(initial_value):.2f}"
            except (ValueError, TypeError):
                pass
                
        self.insert(0, str(initial_value))
        self._initial_value = initial_value
        
        self.bind("<Enter>", self._on_hover)
        self.bind("<Leave>", self._on_leave)
        
        self.bind("<FocusOut>", self._handle_save)
        self.bind("<Return>", lambda e: self.master.focus_set())

    def _on_hover(self, event):
        self.configure(text_color="#99c2ff", cursor="xterm")

    def _on_leave(self, event):
        # Only reset text_color. Never touch fg_color here — avoids ValueError
        # on transparent frames in certain CustomTkinter versions.
        self.configure(text_color=self.default_color)

    def _handle_save(self, event):
        # Only reset text_color. Same rationale as _on_leave.
        self.configure(text_color=self.default_color)
        new_val = self.get()
        if new_val != str(self._initial_value):
            success = self.on_save(new_val)
            if success is not False:
                if self.is_double:
                    try:
                        new_val = f"{float(new_val.replace(',', '.')):.2f}"
                        self.delete(0, 'end')
                        self.insert(0, new_val)
                    except ValueError:
                        pass
                self._initial_value = new_val
            else:
                self.delete(0, 'end')
                self.insert(0, str(self._initial_value))

class HorizontalInventoryCard(ModernCard):
    def __init__(self, master, data, **kwargs):
        super().__init__(master, **kwargs)
        self.data = data
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.img_frame = ctk.CTkFrame(self, fg_color="transparent", width=120, height=120)
        self.img_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        self.img_frame.grid_propagate(False)
        
        self.img_label = ctk.CTkLabel(self.img_frame, text="S/ Img", fg_color="#222", corner_radius=5)
        self.img_label.place(relwidth=1, relheight=1)
        
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, padx=(0, 15), pady=15, sticky="nsew")

    def _update_image(self):
        from core.utils import resolve_media_path, load_and_resize_image
        caminho = self.data.get('caminho_foto')
        if caminho:
            full_foto = resolve_media_path(caminho)
            img_ctk = load_and_resize_image(full_foto, size=(120, 120))
            if img_ctk:
                self.img_label.configure(image=img_ctk, text="")
                self.img_label.image = img_ctk
                return
        # Use image=None strictly — image="" can crash on some Tk backends.
        self.img_label.configure(text="S/ Img", image=None, fg_color="#222")


class SearchableComboBox(ctk.CTkFrame):
    """
    Searchable combobox: a CTkEntry with a 🔍 icon that shows a floating
    CTkToplevel list filtered dynamically on each keypress.
    
    Usage:
        combo = SearchableComboBox(parent, values=[...], command=callback)
        combo.get()      → current text
        combo.set(text)  → set current text
    """

    def __init__(self, master, values: list[str] = None, command=None,
                 width=200, height=32, placeholder_text="Buscar...", **kwargs):
        super().__init__(master, fg_color="transparent", width=width, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self._all_values: list[str] = values or []
        self._command = command
        self._popup: ctk.CTkToplevel | None = None
        self._popup_btns: list[ctk.CTkButton] = []
        self._suppress_filter = False

        # Search entry + icon
        entry_row = ctk.CTkFrame(self, fg_color="#2a2a3a", corner_radius=8,
                                  border_width=1, border_color="#444")
        entry_row.grid(row=0, column=0, sticky="ew")
        entry_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(entry_row, text="🔍", width=26,
                     font=ctk.CTkFont(size=13), text_color="#888").grid(
            row=0, column=1, padx=(4, 0))

        self._var = ctk.StringVar()
        self._entry = ctk.CTkEntry(
            entry_row, textvariable=self._var,
            height=height, border_width=0, fg_color="transparent",
            placeholder_text=placeholder_text
        )
        self._entry.grid(row=0, column=0, sticky="ew", padx=(6, 2))

        self._var.trace_add("write", self._on_key)
        self._entry.bind("<FocusIn>",  self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)
        self._entry.bind("<Escape>",   lambda e: self._close_popup())
        self._entry.bind("<Down>",     self._focus_first_popup_btn)

    # ── Public API ─────────────────────────────────────────────────────────
    def get(self) -> str:
        return self._var.get()

    def set(self, value: str):
        self._suppress_filter = True
        self._var.set(value)
        self._suppress_filter = False
        self._close_popup()

    def configure_values(self, values: list[str]):
        self._all_values = values
        self._show_popup(self._filtered(self.get()))

    # ── Internal ───────────────────────────────────────────────────────────
    def _filtered(self, query: str) -> list[str]:
        q = query.strip().lower()
        if not q:
            return self._all_values[:50]  # cap at 50 for performance
        return [v for v in self._all_values if q in v.lower()][:50]

    def _on_key(self, *_):
        if self._suppress_filter:
            return
        # small delay so we don't rebuild on every character burst
        self._entry.after(80, lambda: self._show_popup(self._filtered(self.get())))

    def _on_focus_in(self, _event):
        self._show_popup(self._filtered(self.get()))

    def _on_focus_out(self, _event):
        # defer so clicks on popup buttons register first
        self._entry.after(200, self._close_popup)

    def _focus_first_popup_btn(self, _event):
        if self._popup_btns:
            self._popup_btns[0].focus_set()

    def _show_popup(self, items: list[str]):
        if not items:
            self._close_popup()
            return

        # Reuse existing popup or create new
        if self._popup is None or not self._popup.winfo_exists():
            self._popup = ctk.CTkToplevel(self._entry.winfo_toplevel())
            self._popup.withdraw()
            self._popup.overrideredirect(True)
            self._popup.attributes("-topmost", True)
            self._popup.configure(fg_color="#1e1e2e")
            self._scroll = ctk.CTkScrollableFrame(
                self._popup, fg_color="#1e1e2e", corner_radius=8
            )
            self._scroll.pack(fill="both", expand=True)

        # Clear old buttons
        for b in self._popup_btns:
            b.destroy()
        self._popup_btns = []

        max_visible = min(8, len(items))
        for item in items:
            btn = ctk.CTkButton(
                self._scroll, text=item,
                anchor="w", fg_color="transparent",
                hover_color="#2a2a4a", corner_radius=0,
                font=ctk.CTkFont(size=12),
                command=lambda v=item: self._select(v)
            )
            btn.pack(fill="x", pady=1)
            self._popup_btns.append(btn)

        # Position popup below the entry
        self._entry.update_idletasks()
        x = self._entry.winfo_rootx()
        y = self._entry.winfo_rooty() + self._entry.winfo_height() + 2
        w = max(self.winfo_width(), 200)
        row_h = 32
        h = min(max_visible * row_h + 8, 280)
        self._popup.geometry(f"{w}x{h}+{x}+{y}")
        self._popup.deiconify()

    def _close_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.withdraw()

    def _select(self, value: str):
        self._suppress_filter = True
        self._var.set(value)
        self._suppress_filter = False
        self._close_popup()
        self._entry.icursor("end")
        if self._command:
            self._command(value)
