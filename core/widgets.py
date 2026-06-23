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
