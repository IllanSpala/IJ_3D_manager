import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import sqlite3
import datetime
import os
import webbrowser
from PIL import Image

ctk.set_appearance_mode("dark")

# UI THEME COLORS
APP_BG_COLOR = "#141414"
CARD_BG_COLOR = "#212121"
BORDER_COLOR = "#333333"
ACCENT_COLOR = "#00a2ff"
DB_NAME = "print_manager_v2.db"
APP_ICON_PATH = "app_icon.png"

# ==========================================
# DATABASE INITIALIZATION
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS configuracoes
                 (id INTEGER PRIMARY KEY, printer_name TEXT)''')
    
    c.execute("SELECT COUNT(*) FROM configuracoes")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO configuracoes (id, printer_name) VALUES (1, 'BAMBU LAB A1')")

    c.execute('''CREATE TABLE IF NOT EXISTS filamentos
                 (id INTEGER PRIMARY KEY, marca TEXT, material TEXT, cor TEXT, peso_inicial REAL, peso_atual REAL, caminho_foto TEXT, link_compra TEXT)''')
                 
    try: c.execute("ALTER TABLE filamentos ADD COLUMN link_compra TEXT")
    except: pass
    
    try: c.execute("ALTER TABLE filamentos ADD COLUMN preco_rolo REAL DEFAULT 0.0")
    except: pass

    c.execute('''CREATE TABLE IF NOT EXISTS acervo
                 (id INTEGER PRIMARY KEY, nome_peca TEXT, caminho_foto TEXT, arquivo_3d TEXT, pos_processamento TEXT, data_registro TEXT)''')
                 
    c.execute('''CREATE TABLE IF NOT EXISTS acervo_filamentos
                 (acervo_id INTEGER, filamento_id INTEGER, peso_gasto REAL,
                 FOREIGN KEY(acervo_id) REFERENCES acervo(id),
                 FOREIGN KEY(filamento_id) REFERENCES filamentos(id))''')
                 
    c.execute('''CREATE TABLE IF NOT EXISTS acervo_impressoes
                 (id INTEGER PRIMARY KEY, acervo_id INTEGER, data_impressao TEXT,
                 FOREIGN KEY(acervo_id) REFERENCES acervo(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS manutencao
                 (id INTEGER PRIMARY KEY, tarefa TEXT, guia_instrucao TEXT, intervalo_dias INTEGER, ultima_execucao TEXT, link_tutorial TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS ferramentas_insumos
                 (id INTEGER PRIMARY KEY, nome TEXT, categoria TEXT, quantidade_status TEXT, caminho_foto TEXT, link_compra TEXT, ultimo_valor REAL)''')
                 
    try:
        c.execute("SELECT 1 FROM pedidos_itens LIMIT 1")
    except:
        c.execute('''CREATE TABLE IF NOT EXISTS pedidos_v2
                     (id INTEGER PRIMARY KEY, nome_cliente TEXT, data_entrega TEXT, valor_cobrado REAL, status TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS pedidos_itens
                     (pedido_id INTEGER, acervo_id INTEGER,
                     FOREIGN KEY(pedido_id) REFERENCES pedidos_v2(id),
                     FOREIGN KEY(acervo_id) REFERENCES acervo(id))''')
        
        try:
            old_pedidos = c.execute("SELECT id, acervo_id, nome_cliente, data_entrega, valor_cobrado, status FROM pedidos").fetchall()
            for p in old_pedidos:
                c.execute("INSERT INTO pedidos_v2 (id, nome_cliente, data_entrega, valor_cobrado, status) VALUES (?, ?, ?, ?, ?)", (p[0], p[2], p[3], p[4], p[5]))
                c.execute("INSERT INTO pedidos_itens (pedido_id, acervo_id) VALUES (?, ?)", (p[0], p[1]))
            c.execute("DROP TABLE pedidos")
        except: pass

    c.execute("SELECT COUNT(*) FROM manutencao")
    if c.fetchone()[0] == 0:
        hoje = datetime.date.today().isoformat()
        tarefas_a1 = [
            ("Lubrificar eixo Y", "Limpe os trilhos com pano e álcool isopropílico. Aplique graxa.", 30, hoje, "https://wiki.bambulab.com/en/a1/maintenance/lubricate-y-axis"),
            ("Lubrificar eixo Z", "Limpe os fusos. Aplique graxa nos fusos e mova o eixo Z.", 30, hoje, "https://wiki.bambulab.com/en/a1/maintenance/lubricate-z-axis"),
            ("Limpar bico (Nozzle)", "Aqueça a 250C, use escova de latão para remover resíduos.", 7, hoje, "https://wiki.bambulab.com/en/a1/maintenance/hotend-maintenance"),
            ("Limpar Engrenagens AMS", "Pressione botões para remover PTFE, sopre ou use pincel.", 30, hoje, "https://wiki.bambulab.com/en/ams-lite/maintenance/cleaning-ams-lite"),
            ("Tensionar Correias", "Afrouxe parafusos X/Y, mova cabeçote/cama. Reaperte.", 30, hoje, "https://wiki.bambulab.com/en/a1/maintenance/belt-tensioning"),
            ("Limpar PEI (Mesa)", "Use detergente e água morna. Não use dedos na superfície.", 7, hoje, "https://wiki.bambulab.com/en/general/textured-pei-plate-cleaning")
        ]
        c.executemany("INSERT INTO manutencao (tarefa, guia_instrucao, intervalo_dias, ultima_execucao, link_tutorial) VALUES (?, ?, ?, ?, ?)", tarefas_a1)

    conn.commit()
    conn.close()

# ==========================================
# HELPERS
# ==========================================
def open_url(url):
    if url: webbrowser.open(url)

def load_and_resize_image(path, size=(150, 150)):
    try:
        if path and os.path.exists(path):
            img = Image.open(path)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            return ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
    except: pass
    return None

class ModernCard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        bc = kwargs.pop("border_color", BORDER_COLOR)
        bw = kwargs.pop("border_width", 1)
        super().__init__(master, fg_color=CARD_BG_COLOR, corner_radius=12, border_width=bw, border_color=bc, **kwargs)


# ==========================================
# TABS
# ==========================================
class TabFilamentos(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(side="top", fill="x", anchor="n", padx=20, pady=(10,0))
        
        self.form_card = ModernCard(self.top_frame, border_width=0)
        self.form_card.pack(side="top", fill="x", pady=(0, 20))
        
        self.alert_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        self.alert_frame.pack(side="top", fill="x", pady=0, anchor="n")
        
        self.form_card.grid_columnconfigure((0,1,2,3), weight=1)
        
        ctk.CTkLabel(self.form_card, text="Cadastrar Novo Filamento", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=4, pady=(5, 0))
        
        self.marca_var = ctk.StringVar()
        f1 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f1.grid(row=1, column=0, padx=10, sticky="ew")
        ctk.CTkLabel(f1, text="Marca", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkEntry(f1, textvariable=self.marca_var, height=25).pack(fill="x")
        
        self.material_var = ctk.StringVar()
        f2 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f2.grid(row=1, column=1, padx=10, sticky="ew")
        ctk.CTkLabel(f2, text="Material", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkEntry(f2, textvariable=self.material_var, height=25).pack(fill="x")
        
        self.cor_var = ctk.StringVar()
        f3 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f3.grid(row=1, column=2, padx=10, sticky="ew")
        ctk.CTkLabel(f3, text="Cor", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkEntry(f3, textvariable=self.cor_var, height=25).pack(fill="x")
        
        self.peso_var = ctk.StringVar(value="1.0")
        f4 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f4.grid(row=1, column=3, padx=10, sticky="ew")
        ctk.CTkLabel(f4, text="Peso (KG)", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkEntry(f4, textvariable=self.peso_var, height=25).pack(fill="x")
        
        self.preco_var = ctk.StringVar()
        f_preco = ctk.CTkFrame(self.form_card, fg_color="transparent"); f_preco.grid(row=2, column=0, padx=10, sticky="ew")
        ctk.CTkLabel(f_preco, text="Valor ($)", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkEntry(f_preco, textvariable=self.preco_var, height=25).pack(fill="x")
        
        self.link_var = ctk.StringVar()
        f_link = ctk.CTkFrame(self.form_card, fg_color="transparent"); f_link.grid(row=2, column=1, padx=10, sticky="ew")
        ctk.CTkLabel(f_link, text="Link", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkEntry(f_link, textvariable=self.link_var, height=25).pack(fill="x")

        self.foto_path = None
        f5 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f5.grid(row=2, column=2, padx=10, sticky="ew")
        ctk.CTkLabel(f5, text="Foto", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.btn_foto = ctk.CTkButton(f5, text="Buscar", height=25, fg_color="#333", hover_color="#444", command=self.select_photo)
        self.btn_foto.pack(fill="x")
        
        f6 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f6.grid(row=2, column=3, padx=10, sticky="ew")
        ctk.CTkLabel(f6, text="", font=ctk.CTkFont(size=11)).pack(anchor="w")
        ctk.CTkButton(f6, text="Salvar", height=25, font=ctk.CTkFont(weight="bold"), 
                      command=self.save_filamento, fg_color=ACCENT_COLOR).pack(fill="x")
        
        ctk.CTkFrame(self.form_card, height=10, fg_color="transparent").grid(row=3, column=0)
        
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(5, 20))
        
        self.load_filamentos()
        
    def select_photo(self):
        path = filedialog.askopenfilename(filetypes=[("Imagens", "*.jpg *.jpeg *.png")])
        if path:
            self.foto_path = path
            self.btn_foto.configure(text="Anexada", fg_color="#2b7a4b")
            
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
        self.btn_foto.configure(text="Buscar", fg_color="#333")
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
            
        ctk.CTkButton(dialog, text="Salvar", fg_color=ACCENT_COLOR, command=save).pack(pady=20)

    def delete_item(self, id):
        if messagebox.askyesno("Confirmar", "Remover este filamento?"):
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
        
        col = 0; r_idx = 0
        self.list_frame.grid_columnconfigure((0,1,2,3), weight=1)
        
        for row in rows:
            if row[5] < (row[4] * 0.2):
                af = ctk.CTkFrame(self.alert_frame, fg_color="#4a1515", corner_radius=8)
                af.pack(fill="x", pady=2)
                ctk.CTkLabel(af, text=f"ALERTA: {row[1]} {row[2]} ({row[3]}) no fim!", text_color="white", font=ctk.CTkFont(weight="bold", size=11)).pack(side="left", padx=10, pady=2)
                if row[7]:
                    ctk.CTkButton(af, text="Comprar", fg_color="#d64545", height=20, command=lambda u=row[7]: open_url(u)).pack(side="right", padx=10, pady=2)
            
            card = ModernCard(self.list_frame)
            card.grid(row=r_idx, column=col, sticky="nsew", padx=5, pady=5)
            
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=5, pady=2)
            ctk.CTkButton(top, text="X", width=20, height=20, fg_color="transparent", text_color="#d64545", command=lambda i=row[0]: self.delete_item(i)).pack(side="right")
            ctk.CTkButton(top, text="✎", width=20, height=20, fg_color="transparent", text_color="#ccc", command=lambda r=row: self.edit_item(r[0], r[1], r[2], r[3], r[8])).pack(side="right")
            if row[7]: ctk.CTkButton(top, text="Link", width=30, height=20, fg_color="transparent", text_color=ACCENT_COLOR, command=lambda url=row[7]: open_url(url)).pack(side="left")

            img_ctk = load_and_resize_image(row[6], size=(80, 80))
            if img_ctk:
                self.list_frame.images.append(img_ctk)
                ctk.CTkLabel(card, text="", image=img_ctk).pack(pady=2)
            else:
                f = ctk.CTkFrame(card, width=80, height=80, corner_radius=5, fg_color="#333")
                f.pack(pady=2)
                ctk.CTkLabel(f, text="S/ Img").place(relx=0.5, rely=0.5, anchor="center")
            
            ctk.CTkLabel(card, text=f"{row[1]} {row[2]}", font=ctk.CTkFont(weight="bold", size=14)).pack()
            ctk.CTkLabel(card, text=row[3], text_color="gray", font=ctk.CTkFont(size=11)).pack()
            
            p_rolo = row[8] or 0.0
            if p_rolo > 0: ctk.CTkLabel(card, text=f"R$ {p_rolo:.2f}", text_color="#aaa", font=ctk.CTkFont(size=11)).pack()
            
            prog = row[5] / row[4] if row[4] > 0 else 0
            pb = ctk.CTkProgressBar(card, width=120, height=5, progress_color=ACCENT_COLOR if prog > 0.2 else "#d64545")
            pb.pack(pady=5)
            pb.set(prog)
            
            ctk.CTkLabel(card, text=f"{row[5]:.2f}KG", font=ctk.CTkFont(size=11)).pack(pady=(0,5))
            
            col += 1
            if col > 3: col = 0; r_idx += 1


class TabAcervo(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(side="top", fill="x", anchor="n", padx=20, pady=(10,0))
        
        self.form_card = ModernCard(self.top_frame)
        self.form_card.pack(side="top", fill="x", pady=(0, 20))
        self.form_card.grid_columnconfigure((0,1), weight=1)
        
        ctk.CTkLabel(self.form_card, text="Registrar Peça no Acervo", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=2, pady=(15, 10))
        
        self.nome_var = ctk.StringVar()
        f1 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f1.grid(row=1, column=0, padx=15, pady=5, sticky="ew")
        ctk.CTkLabel(f1, text="Nome da Peça", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f1, textvariable=self.nome_var, placeholder_text="Ex: Suporte Fone").pack(fill="x")
        
        self.pos_var = ctk.StringVar()
        f4 = ctk.CTkFrame(self.form_card, fg_color="transparent"); f4.grid(row=1, column=1, padx=15, pady=5, sticky="ew")
        ctk.CTkLabel(f4, text="Processos de Acabamento (Opcional)", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f4, textvariable=self.pos_var, placeholder_text="Ex: Lixamento, Pintura").pack(fill="x")

        files_frame = ctk.CTkFrame(self.form_card, fg_color="transparent")
        files_frame.grid(row=2, column=0, columnspan=2, padx=15, pady=10, sticky="ew")
        files_frame.grid_columnconfigure((0,1), weight=1)
        
        self.foto_path = None
        self.arquivo_3d_path = None
        
        self.btn_foto = ctk.CTkButton(files_frame, text="Foto da Peça Pronta", fg_color="#333", hover_color="#444", command=self.select_photo)
        self.btn_foto.grid(row=0, column=0, padx=5, sticky="ew")

        self.btn_3d = ctk.CTkButton(files_frame, text="Anexar Arquivo 3D (STL/3MF)", fg_color="#333", hover_color="#444", command=self.select_3d)
        self.btn_3d.grid(row=0, column=1, padx=5, sticky="ew")

        self.filamentos_selecionados = []
        
        self.filamentos_frame = ctk.CTkFrame(self.form_card, fg_color=APP_BG_COLOR, corner_radius=10, border_width=1, border_color=BORDER_COLOR)
        self.filamentos_frame.grid(row=3, column=0, columnspan=2, padx=15, pady=10, sticky="nsew")
        ctk.CTkLabel(self.filamentos_frame, text="Filamentos Utilizados na Peça", text_color="gray").pack(pady=5)
        
        self.f_list_ui = ctk.CTkFrame(self.filamentos_frame, fg_color="transparent")
        self.f_list_ui.pack(fill="x", padx=10, pady=5)
        
        add_f_frame = ctk.CTkFrame(self.filamentos_frame, fg_color="transparent")
        add_f_frame.pack(fill="x", padx=10, pady=5)
        
        self.filamentos_dict = self.get_filamentos()
        self.f_combo = ctk.CTkComboBox(add_f_frame, values=list(self.filamentos_dict.keys()) if self.filamentos_dict else ["Nenhum"])
        self.f_combo.pack(side="left", fill="x", expand=True, padx=(0,10))
        ctk.CTkButton(add_f_frame, text="Adicionar Filamento", width=150, fg_color="#333", command=self.add_filamento_ui).pack(side="right")
        
        ctk.CTkButton(self.form_card, text="Salvar Peça Completa", height=40, font=ctk.CTkFont(weight="bold"), 
                      command=self.save_peca, fg_color=ACCENT_COLOR).grid(row=4, column=0, columnspan=2, padx=15, pady=(15, 15), sticky="ew")
        
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.load_acervo()

    def get_filamentos(self):
        conn = sqlite3.connect(DB_NAME)
        rows = conn.execute("SELECT id, marca, material, cor FROM filamentos").fetchall()
        conn.close()
        return {f"{r[1]} {r[2]} ({r[3]})": r[0] for r in rows}

    def add_filamento_ui(self):
        f_name = self.f_combo.get()
        if f_name not in self.filamentos_dict: return
        f_id = self.filamentos_dict[f_name]
        
        row_ui = ctk.CTkFrame(self.f_list_ui, fg_color="#333", corner_radius=5)
        row_ui.pack(fill="x", pady=2)
        
        ctk.CTkLabel(row_ui, text=f_name).pack(side="left", padx=10)
        
        btn_del = ctk.CTkButton(row_ui, text="X", width=30, fg_color="#d64545", hover_color="#8b0000", command=lambda r=row_ui: self.remover_f_ui(r))
        btn_del.pack(side="right", padx=5)
        
        p_var = ctk.StringVar()
        ctk.CTkEntry(row_ui, textvariable=p_var, placeholder_text="Gasto (gramas) ex: 120", width=150).pack(side="right", padx=10)
        
        self.filamentos_selecionados.append({'id': f_id, 'ui': row_ui, 'peso_var': p_var})

    def remover_f_ui(self, row_ui):
        row_ui.destroy()
        self.filamentos_selecionados = [i for i in self.filamentos_selecionados if i['ui'] != row_ui]

    def select_photo(self):
        path = filedialog.askopenfilename()
        if path:
            self.foto_path = path
            self.btn_foto.configure(text="Foto Anexada", fg_color="#2b7a4b")
            
    def select_3d(self):
        path = filedialog.askopenfilename(filetypes=[("3D Files", "*.3mf *.stl *.obj")])
        if path:
            self.arquivo_3d_path = path
            self.btn_3d.configure(text=f"3D: {os.path.basename(path)}", fg_color="#2b7a4b")

    def check_filamentos_suficientes(self, pesos_finais):
        conn = sqlite3.connect(DB_NAME)
        for f_id, p_kg in pesos_finais:
            peso_atual = conn.execute("SELECT peso_atual FROM filamentos WHERE id=?", (f_id,)).fetchone()[0]
            if peso_atual < p_kg:
                conn.close()
                return messagebox.askyesno("Aviso", "Você não tem filamento suficiente cadastrado para salvar essa peça. Deseja ignorar e salvar mesmo assim? (O peso ficará zerado)")
        conn.close()
        return True

    def save_peca(self):
        nome, pos = self.nome_var.get(), self.pos_var.get()
        if not nome: return messagebox.showerror("Erro", "Nome da peça é obrigatório.")
        if not self.filamentos_selecionados: return messagebox.showerror("Erro", "Adicione pelo menos um filamento com o peso gasto.")
        
        pesos_finais = []
        for item in self.filamentos_selecionados:
            try:
                p_gramas = float(item['peso_var'].get().replace(',', '.'))
                p_kg = p_gramas / 1000.0
                pesos_finais.append((item['id'], p_kg))
            except:
                return messagebox.showerror("Erro", "Todos os pesos de filamentos devem ser numéricos (gramas).")
                
        if not self.check_filamentos_suficientes(pesos_finais): return
                
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        c.execute("INSERT INTO acervo (nome_peca, caminho_foto, arquivo_3d, pos_processamento, data_registro) VALUES (?, ?, ?, ?, ?)",
                  (nome, self.foto_path, self.arquivo_3d_path, pos, datetime.date.today().isoformat()))
        acervo_id = c.lastrowid
        
        agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO acervo_impressoes (acervo_id, data_impressao) VALUES (?, ?)", (acervo_id, agora))
        
        for f_id, p_kg in pesos_finais:
            c.execute("INSERT INTO acervo_filamentos (acervo_id, filamento_id, peso_gasto) VALUES (?, ?, ?)", (acervo_id, f_id, p_kg))
            peso_atual = c.execute("SELECT peso_atual FROM filamentos WHERE id=?", (f_id,)).fetchone()[0]
            c.execute("UPDATE filamentos SET peso_atual=? WHERE id=?", (max(0, peso_atual - p_kg), f_id))
            
        conn.commit(); conn.close()
        
        self.nome_var.set(""); self.pos_var.set("")
        self.foto_path = None; self.arquivo_3d_path = None
        self.btn_foto.configure(text="Foto da Peça Pronta", fg_color="#333")
        self.btn_3d.configure(text="Anexar Arquivo 3D (STL/3MF)", fg_color="#333")
        
        for item in self.filamentos_selecionados: item['ui'].destroy()
        self.filamentos_selecionados = []
        self.load_acervo()

    def delete_item(self, id):
        if messagebox.askyesno("Confirmar", "Remover esta peça?"):
            conn = sqlite3.connect(DB_NAME)
            conn.execute("DELETE FROM acervo_impressoes WHERE acervo_id=?", (id,))
            conn.execute("DELETE FROM acervo_filamentos WHERE acervo_id=?", (id,))
            conn.execute("DELETE FROM acervo WHERE id=?", (id,))
            conn.commit(); conn.close()
            self.load_acervo()

    def add_impressao(self, acervo_id):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        fils = c.execute("SELECT filamento_id, peso_gasto FROM acervo_filamentos WHERE acervo_id=?", (acervo_id,)).fetchall()
        for f_id, p_kg in fils:
            peso_atual = c.execute("SELECT peso_atual FROM filamentos WHERE id=?", (f_id,)).fetchone()[0]
            if peso_atual < p_kg:
                if not messagebox.askyesno("Aviso", "Filamento insuficiente. Adicionar registro mesmo assim?"):
                    conn.close(); return
            c.execute("UPDATE filamentos SET peso_atual=? WHERE id=?", (max(0, peso_atual - p_kg), f_id))
            
        c.execute("INSERT INTO acervo_impressoes (acervo_id, data_impressao) VALUES (?, ?)", (acervo_id, agora))
        conn.commit(); conn.close()
        self.load_acervo()

    def remove_impressao(self, acervo_id):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        ult = c.execute("SELECT id FROM acervo_impressoes WHERE acervo_id=? ORDER BY id DESC LIMIT 1", (acervo_id,)).fetchone()
        if not ult:
            conn.close(); return
            
        if not messagebox.askyesno("Confirmar", "Deseja remover a última impressão e devolver o filamento gasto para o estoque?"):
            conn.close(); return
            
        fils = c.execute("SELECT filamento_id, peso_gasto FROM acervo_filamentos WHERE acervo_id=?", (acervo_id,)).fetchall()
        for f_id, p_kg in fils:
            peso_atual = c.execute("SELECT peso_atual FROM filamentos WHERE id=?", (f_id,)).fetchone()[0]
            c.execute("UPDATE filamentos SET peso_atual=? WHERE id=?", (peso_atual + p_kg, f_id))
            
        c.execute("DELETE FROM acervo_impressoes WHERE id=?", (ult[0],))
        conn.commit(); conn.close()
        self.load_acervo()

    def load_acervo(self):
        for w in self.list_frame.winfo_children(): w.destroy()
        conn = sqlite3.connect(DB_NAME)
        rows = conn.execute("SELECT id, nome_peca, pos_processamento, caminho_foto, data_registro, arquivo_3d FROM acervo ORDER BY id DESC").fetchall()
        
        self.list_frame.images = []
        for r in rows:
            card = ModernCard(self.list_frame)
            card.pack(fill="x", padx=10, pady=5)
            
            top_action = ctk.CTkFrame(card, fg_color="transparent")
            top_action.pack(fill="x", padx=5)
            
            ctk.CTkButton(top_action, text="X", width=30, height=20, fg_color="transparent", text_color="#d64545", hover_color="#442222", 
                          command=lambda i=r[0]: self.delete_item(i)).pack(side="right")
                          
            count = conn.execute("SELECT COUNT(*) FROM acervo_impressoes WHERE acervo_id=?", (r[0],)).fetchone()[0]
            
            btn_add = ctk.CTkButton(top_action, text=f"+1", width=40, height=20, fg_color="#2b7a4b", hover_color="#1d5c36", 
                                    command=lambda i=r[0]: self.add_impressao(i))
            btn_add.pack(side="left", padx=(0,5))
            
            ctk.CTkLabel(top_action, text=f"Total de Impressões: {count}", text_color="white", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
            
            if count > 0:
                btn_rem = ctk.CTkButton(top_action, text="-1", width=40, height=20, fg_color="#d64545", hover_color="#8b0000", 
                                        command=lambda i=r[0]: self.remove_impressao(i))
                btn_rem.pack(side="left")

            body = ctk.CTkFrame(card, fg_color="transparent")
            body.pack(fill="x", expand=True)

            img_ctk = load_and_resize_image(r[3], size=(80, 80))
            if img_ctk:
                self.list_frame.images.append(img_ctk)
                ctk.CTkLabel(body, text="", image=img_ctk).pack(side="left", padx=15, pady=(0,10))
            else:
                f = ctk.CTkFrame(body, width=80, height=80, corner_radius=5, fg_color="#333")
                f.pack(side="left", padx=15, pady=(0,10))
            
            info = ctk.CTkFrame(body, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(info, text=r[1], font=ctk.CTkFont(weight="bold", size=18)).pack(anchor="w")
            
            fils = conn.execute('''SELECT f.marca, f.cor, af.peso_gasto FROM acervo_filamentos af 
                                   JOIN filamentos f ON af.filamento_id = f.id WHERE af.acervo_id=?''', (r[0],)).fetchall()
            fils_txt = " + ".join([f"{f[0]} {f[1]} ({f[2]*1000:.0f}g)" for f in fils]) if fils else "Nenhum filamento"
            
            ctk.CTkLabel(info, text=f"Materiais: {fils_txt}", text_color="#aaa").pack(anchor="w")
            ctk.CTkLabel(info, text=f"Pós: {r[2] or 'Nenhum'}", text_color="gray").pack(anchor="w")
            
            last_print = conn.execute("SELECT data_impressao FROM acervo_impressoes WHERE acervo_id=? ORDER BY id DESC LIMIT 1", (r[0],)).fetchone()
            if last_print:
                ctk.CTkLabel(info, text=f"Última impressão: {last_print[0]}", text_color="#aaa").pack(anchor="w")
                
            if r[5]:
                ctk.CTkLabel(info, text=f"Arquivo 3D: {os.path.basename(r[5])}", text_color=ACCENT_COLOR).pack(anchor="w")
        
        conn.close()


class TabAlmoxarifado(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(side="top", fill="x", anchor="n", padx=20, pady=(10,0))
        
        self.form_card = ModernCard(self.top_frame)
        self.form_card.pack(side="top", fill="x", pady=(0, 20))
        ctk.CTkLabel(self.form_card, text="Novo Item de Almoxarifado", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15,15))
        
        self.nome_var = ctk.StringVar()
        self.cat_var = ctk.StringVar(value="Ferramenta")
        self.status_var = ctk.StringVar(value="Em estoque")
        self.link_var = ctk.StringVar()
        self.preco_var = ctk.StringVar()
        self.foto_path = None
        
        row1 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=5)
        row1.grid_columnconfigure((0,1,2), weight=1)
        
        f1=ctk.CTkFrame(row1, fg_color="transparent"); f1.grid(row=0,column=0, sticky="ew", padx=5)
        ctk.CTkLabel(f1, text="Nome do Item", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f1, textvariable=self.nome_var, placeholder_text="Ex: Lixa d'água 400").pack(fill="x")
        
        f2=ctk.CTkFrame(row1, fg_color="transparent"); f2.grid(row=0,column=1, sticky="ew", padx=5)
        ctk.CTkLabel(f2, text="Categoria", text_color="gray").pack(anchor="w")
        ctk.CTkOptionMenu(f2, variable=self.cat_var, values=["Ferramenta", "Insumo", "Peça Reposição"]).pack(fill="x")
        
        f3=ctk.CTkFrame(row1, fg_color="transparent"); f3.grid(row=0,column=2, sticky="ew", padx=5)
        ctk.CTkLabel(f3, text="Situação", text_color="gray").pack(anchor="w")
        ctk.CTkOptionMenu(f3, variable=self.status_var, values=["Em estoque", "Comprar", "Falta"]).pack(fill="x")

        row2 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=5)
        row2.grid_columnconfigure((0,1,2), weight=1)
        
        f4=ctk.CTkFrame(row2, fg_color="transparent"); f4.grid(row=0,column=0, sticky="ew", padx=5)
        ctk.CTkLabel(f4, text="Link de Compra (Opcional)", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f4, textvariable=self.link_var, placeholder_text="Ex: https://...").pack(fill="x")
        
        f5=ctk.CTkFrame(row2, fg_color="transparent"); f5.grid(row=0,column=1, sticky="ew", padx=5)
        ctk.CTkLabel(f5, text="Último Valor Pago ($)", text_color="gray").pack(anchor="w")
        ctk.CTkEntry(f5, textvariable=self.preco_var, placeholder_text="Ex: 25.50").pack(fill="x")
        
        f6=ctk.CTkFrame(row2, fg_color="transparent"); f6.grid(row=0,column=2, sticky="ew", padx=5)
        ctk.CTkLabel(f6, text="Foto (Opcional)", text_color="gray").pack(anchor="w")
        self.btn_foto = ctk.CTkButton(f6, text="Selecionar", fg_color="#333", hover_color="#444", command=self.select_photo)
        self.btn_foto.pack(fill="x")

        ctk.CTkButton(self.form_card, text="Salvar Item", height=40, font=ctk.CTkFont(weight="bold"), fg_color=ACCENT_COLOR, command=self.save_item).pack(fill="x", padx=25, pady=(15,20))
        
        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_scroll.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.list_panel = ModernCard(self.main_scroll)
        self.list_panel.pack(fill="both", expand=True, pady=(0, 20))
        ctk.CTkLabel(self.list_panel, text="Inventário Geral", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15,10))
        
        self.list_items = ctk.CTkFrame(self.list_panel, fg_color="transparent")
        self.list_items.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.load_items()

    def select_photo(self):
        path = filedialog.askopenfilename()
        if path:
            self.foto_path = path
            self.btn_foto.configure(text="Anexado", fg_color="#2b7a4b")

    def save_item(self):
        nome, cat, status, link = self.nome_var.get(), self.cat_var.get(), self.status_var.get(), self.link_var.get()
        if not nome: return messagebox.showerror("Erro", "Nome é obrigatório.")
        
        preco = 0.0
        if self.preco_var.get():
            try: preco = float(self.preco_var.get().replace(',','.'))
            except: return messagebox.showerror("Erro", "Preço deve ser numérico.")
            
        conn = sqlite3.connect(DB_NAME)
        conn.execute("INSERT INTO ferramentas_insumos (nome, categoria, quantidade_status, caminho_foto, link_compra, ultimo_valor) VALUES (?, ?, ?, ?, ?, ?)", 
                     (nome, cat, status, self.foto_path, link, preco))
        conn.commit(); conn.close()
        self.nome_var.set(""); self.link_var.set(""); self.preco_var.set("")
        self.foto_path = None; self.btn_foto.configure(text="Selecionar", fg_color="#333")
        self.load_items()

    def delete_item(self, id):
        if messagebox.askyesno("Confirmar", "Tem certeza que deseja remover este item?"):
            conn = sqlite3.connect(DB_NAME)
            conn.execute("DELETE FROM ferramentas_insumos WHERE id=?", (id,))
            conn.commit(); conn.close()
            self.load_items()

    def load_items(self):
        for w in self.list_items.winfo_children(): w.destroy()
        conn = sqlite3.connect(DB_NAME)
        rows = conn.execute("SELECT id, nome, categoria, quantidade_status, caminho_foto, link_compra, ultimo_valor FROM ferramentas_insumos ORDER BY categoria, nome").fetchall()
        conn.close()
        
        self.list_items.images = []
        for r in rows:
            color = "#d64545" if r[3] in ["Comprar", "Falta"] else "white"
            f = ctk.CTkFrame(self.list_items, fg_color="#333", corner_radius=8)
            f.pack(fill="x", pady=4)
            
            ctk.CTkButton(f, text="X", width=30, height=25, fg_color="transparent", text_color="#d64545", hover_color="#442222", 
                          command=lambda i=r[0]: self.delete_item(i)).pack(side="right", padx=5)
            
            img_ctk = load_and_resize_image(r[4], size=(40, 40))
            if img_ctk:
                self.list_items.images.append(img_ctk)
                ctk.CTkLabel(f, text="", image=img_ctk).pack(side="left", padx=(10,5), pady=5)
            else:
                p_f = ctk.CTkFrame(f, width=40, height=40, fg_color="#222")
                p_f.pack(side="left", padx=(10,5), pady=5)
                
            info = ctk.CTkFrame(f, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(info, text=f"{r[1]}", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
            
            badge = ctk.CTkFrame(info, fg_color="#444" if color=="white" else "#8b0000", corner_radius=5)
            badge.pack(anchor="w", pady=(2,0))
            ctk.CTkLabel(badge, text=f" {r[2]} | {r[3]} ", text_color="white", font=ctk.CTkFont(size=10)).pack()
            
            if r[6] > 0:
                ctk.CTkLabel(f, text=f"R$ {r[6]:.2f}", text_color="#ccc").pack(side="right", padx=10)
            if r[5]:
                ctk.CTkButton(f, text="Comprar", width=80, height=25, border_width=1, border_color=ACCENT_COLOR, fg_color="transparent", text_color=ACCENT_COLOR, hover_color="#1d303b", command=lambda l=r[5]: open_url(l)).pack(side="right", padx=10)


class TabManutencao(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(side="top", fill="x", anchor="n", padx=20, pady=(20,10))
        ctk.CTkLabel(self.header, text="Rotinas de Manutenção", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        
        self.scroll_tasks = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_tasks.pack(side="top", fill="both", expand=True, padx=20, pady=(0,20))
        
        self.load_tasks()

    def mark_done(self, task_id):
        try:
            conn = sqlite3.connect(DB_NAME)
            conn.execute("UPDATE manutencao SET ultima_execucao=? WHERE id=?", (datetime.date.today().isoformat(), task_id))
            conn.commit(); conn.close()
            self.load_tasks()
        except: pass

    def load_tasks(self):
        for w in self.scroll_tasks.winfo_children(): w.destroy()
        try:
            conn = sqlite3.connect(DB_NAME)
            rows = conn.execute("SELECT id, tarefa, guia_instrucao, intervalo_dias, ultima_execucao, link_tutorial FROM manutencao").fetchall()
            conn.close()
        except: return
            
        hoje = datetime.date.today()
        for row in rows:
            try:
                t_id, tarefa, guia, inv, ult, link = row
                try: data_ult = datetime.date.fromisoformat(ult)
                except: data_ult = hoje
                
                dias = (hoje - data_ult).days
                atrasado = dias >= inv
                
                b_color = "#d64545" if atrasado else BORDER_COLOR
                card = ModernCard(self.scroll_tasks, border_color=b_color, border_width=2 if atrasado else 1)
                card.pack(fill="x", pady=8)
                
                top = ctk.CTkFrame(card, fg_color="transparent")
                top.pack(fill="x", padx=15, pady=(15,5))
                
                color = "#d64545" if atrasado else "white"
                ctk.CTkLabel(top, text=tarefa, font=ctk.CTkFont(weight="bold", size=16), text_color=color).pack(side="left")
                ctk.CTkLabel(top, text=f"Última: {ult} ({dias} dias atrás)", text_color="gray").pack(side="left", padx=10)
                
                btn_ok = ctk.CTkButton(top, text="Feito Hoje", width=100, fg_color="#2b7a4b", hover_color="#1d5c36", command=lambda t=t_id: self.mark_done(t))
                btn_ok.pack(side="right")
                
                mid = ctk.CTkFrame(card, fg_color="transparent")
                mid.pack(fill="x", padx=15, pady=(5,15))
                ctk.CTkLabel(mid, text=guia, wraplength=700, justify="left", text_color="#ccc").pack(side="left", fill="x", expand=True)
                if link:
                    ctk.CTkButton(mid, text="Ver Tutorial", fg_color="transparent", border_width=1, border_color=BORDER_COLOR, width=100, hover_color="#333", command=lambda l=link: open_url(l)).pack(side="right", padx=(10,0))
            except: pass


class TabPedidos(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.form_visible = False
        
        self.toggle_btn = ctk.CTkButton(self, text="▶ Exibir Formulário de Pedido", fg_color="transparent", text_color=ACCENT_COLOR, anchor="w", hover_color="#222", command=self.toggle_form)
        self.toggle_btn.pack(side="top", fill="x", padx=20, pady=0, anchor="n")
        
        self.form_card = ModernCard(self, border_width=0)
        
        f1 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f1.pack(fill="x", padx=10, pady=(5, 0))
        f1.grid_columnconfigure((0,1,2), weight=1)
        
        fc = ctk.CTkFrame(f1, fg_color="transparent"); fc.grid(row=0, column=0, padx=2, sticky="ew")
        ctk.CTkLabel(fc, text="Cliente:", font=ctk.CTkFont(size=11)).pack(side="left", padx=2)
        self.cliente_var = ctk.StringVar()
        ctk.CTkEntry(fc, textvariable=self.cliente_var, height=25).pack(side="left", fill="x", expand=True, padx=2)
        
        fd = ctk.CTkFrame(f1, fg_color="transparent"); fd.grid(row=0, column=1, padx=2, sticky="ew")
        ctk.CTkLabel(fd, text="Data:", font=ctk.CTkFont(size=11)).pack(side="left", padx=2)
        self.data_var = ctk.StringVar()
        ctk.CTkEntry(fd, textvariable=self.data_var, height=25).pack(side="left", fill="x", expand=True, padx=2)
        
        fv = ctk.CTkFrame(f1, fg_color="transparent"); fv.grid(row=0, column=2, padx=2, sticky="ew")
        ctk.CTkLabel(fv, text="Valor:", font=ctk.CTkFont(size=11)).pack(side="left", padx=2)
        self.valor_var = ctk.StringVar()
        ctk.CTkEntry(fv, textvariable=self.valor_var, height=25).pack(side="left", fill="x", expand=True, padx=2)
        
        f2 = ctk.CTkFrame(self.form_card, fg_color="transparent")
        f2.pack(fill="x", padx=10, pady=(5, 5))
        
        ctk.CTkLabel(f2, text="Peça:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 2))
        self.acervo_dict = self.get_acervo_dict()
        self.peca_combo = ctk.CTkComboBox(f2, values=list(self.acervo_dict.keys()) if self.acervo_dict else ["Nenhuma Peça"], height=25)
        self.peca_combo.pack(side="left", fill="x", expand=True, padx=2)
        ctk.CTkButton(f2, text="+ Add Peça", width=40, height=25, fg_color="#333", command=self.add_peca_ui).pack(side="left", padx=5)
        
        ctk.CTkButton(f2, text="Salvar Pedido", width=100, height=25, font=ctk.CTkFont(weight="bold"), fg_color=ACCENT_COLOR, command=self.criar_pedido).pack(side="right", padx=(10, 4))
        
        self.pecas_selecionadas = []
        self.pecas_ui_frame = ctk.CTkFrame(self.form_card, fg_color="transparent")
        self.pecas_ui_frame.pack(fill="x", padx=10, pady=(0, 5))
        
        self.kanban_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.kanban_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(5, 20))
        
        self.kanban_frame.grid_columnconfigure((0,1,2), weight=1)
        self.kanban_frame.grid_rowconfigure(0, weight=1)
        
        self.col_fazer = self.create_col(0, "A Fazer", "#1a1a1a")
        self.col_imp = self.create_col(1, "Imprimindo", "#1a1a1a")
        self.col_encaminhado = self.create_col(2, "Enviado", "#1a1a1a")
        
        self.load_pedidos()

    def toggle_form(self):
        if self.form_visible:
            self.form_card.pack_forget()
            self.toggle_btn.configure(text="▶ Exibir Formulário de Pedido")
            self.form_visible = False
        else:
            self.form_card.pack(side="top", fill="x", padx=20, pady=(0, 5), before=self.kanban_frame)
            self.toggle_btn.configure(text="▼ Ocultar Formulário de Pedido")
            self.form_visible = True

    def create_col(self, col, title, color):
        f = ctk.CTkFrame(self.kanban_frame, fg_color=color, corner_radius=10, border_width=1, border_color="#333")
        f.grid(row=0, column=col, sticky="nsew", padx=5)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(weight="bold", size=14), pady=5).pack()
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
        
        row_ui = ctk.CTkFrame(self.pecas_ui_frame, fg_color="#333", corner_radius=3)
        row_ui.pack(side="left", padx=2)
        ctk.CTkLabel(row_ui, text=p_name, font=ctk.CTkFont(size=11)).pack(side="left", padx=5)
        ctk.CTkButton(row_ui, text="X", width=15, height=15, fg_color="transparent", text_color="#d64545", command=lambda r=row_ui: self.remover_peca_ui(r)).pack(side="right")
        self.pecas_selecionadas.append({'id': p_id, 'ui': row_ui})

    def remover_peca_ui(self, row_ui):
        row_ui.destroy()
        self.pecas_selecionadas = [i for i in self.pecas_selecionadas if i['ui'] != row_ui]

    def criar_pedido(self):
        cliente, data, val = self.cliente_var.get(), self.data_var.get(), self.valor_var.get()
        if not cliente or not self.pecas_selecionadas: 
            return messagebox.showerror("Erro", "Adicione cliente e peça.")
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
        for col in [self.col_fazer, self.col_imp, self.col_encaminhado]:
            for w in col.winfo_children(): w.destroy()
            
        conn = sqlite3.connect("print_manager_v2.db")
        rows = conn.execute("SELECT id, nome_cliente, data_entrega, valor_cobrado, status FROM pedidos_v2").fetchall()
        
        for r in rows:
            p_id, cliente, data, valor, status = r
            parent = self.col_fazer if status == "A Fazer" else self.col_imp if status == "Imprimindo" else self.col_encaminhado
            
            if status == "Encaminhado":
                card = ModernCard(parent, border_color="#d64545", border_width=2)
                card.configure(fg_color="#3d1818")
            elif status == "Entregue":
                card = ModernCard(parent, border_color="#2b7a4b", border_width=2)
                card.configure(fg_color="#1c3b22")
            else:
                card = ModernCard(parent, border_width=0)
                
            card.pack(fill="x", padx=5, pady=3)
            
            ctk.CTkLabel(card, text=f"  {cliente}", font=ctk.CTkFont(weight="bold", size=13)).pack(pady=(3,0))
            
            itens = conn.execute("SELECT a.nome_peca FROM pedidos_itens pi JOIN acervo a ON pi.acervo_id = a.id WHERE pi.pedido_id=?", (p_id,)).fetchall()
            for (nome_p,) in itens:
                ctk.CTkLabel(card, text=f"- {nome_p}", text_color="#ccc", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=10)
            
            if data: ctk.CTkLabel(card, text=f"  {data}", text_color="gray", font=ctk.CTkFont(size=10)).pack(pady=(2,0))
            if valor > 0: ctk.CTkLabel(card, text=f"R$ {valor:.2f}", text_color=ACCENT_COLOR, font=ctk.CTkFont(size=11)).pack()
            
            btns = ctk.CTkFrame(card, fg_color="transparent")
            btns.pack(fill="x", pady=2)
            
            if status in ["Imprimindo", "Encaminhado", "Entregue"]:
                prev = "A Fazer" if status == "Imprimindo" else ("Imprimindo" if status == "Encaminhado" else "Encaminhado")
                ctk.CTkButton(btns, text="<", width=25, height=20, command=lambda i=p_id, s=prev: self.move_pedido(i, s)).pack(side="left", padx=2)
            
            ctk.CTkButton(btns, text="X", width=25, height=20, fg_color="#d64545", hover_color="#8b0000", command=lambda i=p_id: self.delete_pedido(i)).pack(side="left", expand=True)
            
            if status in ["A Fazer", "Imprimindo"]:
                nxt = "Imprimindo" if status == "A Fazer" else "Encaminhado"
                ctk.CTkButton(btns, text=">", width=25, height=20, command=lambda i=p_id, s=nxt: self.move_pedido(i, s)).pack(side="right", padx=2)
            elif status == "Encaminhado":
                ctk.CTkButton(btns, text="✔ Entregue", width=70, height=20, fg_color="#2b7a4b", hover_color="#1d5c36", command=lambda i=p_id: self.move_pedido(i, "Entregue")).pack(side="right", padx=2)

        conn.close()


class TabFinanceiro(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.main_card = ModernCard(self)
        self.main_card.grid(row=0, column=0, padx=40, pady=40, sticky="nsew")
        self.main_card.grid_columnconfigure((0,1), weight=1)
        
        ctk.CTkLabel(self.main_card, text="Simulador Financeiro Inteligente", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, columnspan=2, pady=30)
        
        f_in = ctk.CTkFrame(self.main_card, fg_color="transparent")
        f_in.grid(row=1, column=0, padx=30, sticky="nsew")
        f_in.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(f_in, text="Selecione a Peça:").grid(row=0, column=0, padx=10, pady=15, sticky="e")
        self.acervo_dict = self.get_acervo_dict()
        self.peca_combo = ctk.CTkComboBox(f_in, values=list(self.acervo_dict.keys()) if self.acervo_dict else ["Nenhuma Peça"])
        self.peca_combo.grid(row=0, column=1, padx=10, pady=15, sticky="we")
        
        ctk.CTkLabel(f_in, text="Custo de Operação Fixo / Hora ($):").grid(row=1, column=0, padx=10, pady=15, sticky="e")
        self.energia_var = ctk.StringVar(value="1.50")
        ctk.CTkEntry(f_in, textvariable=self.energia_var).grid(row=1, column=1, padx=10, pady=15, sticky="we")
        
        ctk.CTkLabel(f_in, text="Tempo Médio (Horas):").grid(row=2, column=0, padx=10, pady=15, sticky="e")
        self.horas_var = ctk.StringVar(value="1.0")
        ctk.CTkEntry(f_in, textvariable=self.horas_var).grid(row=2, column=1, padx=10, pady=15, sticky="we")
        
        ctk.CTkLabel(f_in, text="Margem de Lucro (%):").grid(row=3, column=0, padx=10, pady=15, sticky="e")
        self.lucro_var = ctk.StringVar(value="100")
        ctk.CTkEntry(f_in, textvariable=self.lucro_var).grid(row=3, column=1, padx=10, pady=15, sticky="we")
        
        ctk.CTkButton(f_in, text="Calcular Extrato", font=ctk.CTkFont(weight="bold", size=16), height=45, fg_color=ACCENT_COLOR, command=self.calcular).grid(row=4, column=0, columnspan=2, pady=30, sticky="we", padx=10)
        
        self.res_frame = ctk.CTkFrame(self.main_card, fg_color="#181818", corner_radius=15)
        self.res_frame.grid(row=1, column=1, padx=30, sticky="nsew", pady=(0, 30))
        
        ctk.CTkLabel(self.res_frame, text="Extrato de Precificação", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(30,20))
        
        self.lbl_material = ctk.CTkLabel(self.res_frame, text="Custo do Material: R$ 0.00", font=ctk.CTkFont(size=16), text_color="#aaa")
        self.lbl_material.pack(pady=10)
        self.lbl_energia = ctk.CTkLabel(self.res_frame, text="Custo Operacional: R$ 0.00", font=ctk.CTkFont(size=16), text_color="#aaa")
        self.lbl_energia.pack(pady=10)
        
        ctk.CTkFrame(self.res_frame, height=1, fg_color=BORDER_COLOR).pack(fill="x", padx=40, pady=20)
        
        self.lbl_total = ctk.CTkLabel(self.res_frame, text="Custo Total: R$ 0.00", font=ctk.CTkFont(size=20, weight="bold"), text_color="#d64545")
        self.lbl_total.pack(pady=10)
        
        self.lbl_venda = ctk.CTkLabel(self.res_frame, text="Preço de Venda: R$ 0.00", font=ctk.CTkFont(size=28, weight="bold"), text_color="#2b7a4b")
        self.lbl_venda.pack(pady=(20,10))

    def get_acervo_dict(self):
        conn = sqlite3.connect(DB_NAME)
        rows = conn.execute("SELECT id, nome_peca FROM acervo").fetchall()
        conn.close()
        return {r[1]: r[0] for r in rows}

    def calcular(self):
        peca_name = self.peca_combo.get()
        if not peca_name or peca_name not in self.acervo_dict: return
        a_id = self.acervo_dict[peca_name]
        
        try:
            ch = float(self.energia_var.get().replace(',','.'))
            hrs = float(self.horas_var.get().replace(',','.'))
            lucro = float(self.lucro_var.get().replace(',','.'))
        except: return messagebox.showerror("Erro", "Valores devem ser numéricos.")
        
        conn = sqlite3.connect(DB_NAME)
        fils = conn.execute('''SELECT af.peso_gasto, f.peso_inicial, f.preco_rolo 
                                FROM acervo_filamentos af JOIN filamentos f ON af.filamento_id = f.id 
                                WHERE af.acervo_id=?''', (a_id,)).fetchall()
        conn.close()
        
        custo_material = 0.0
        for p_gasto, p_ini, p_rolo in fils:
            p_rolo = p_rolo or 0.0
            if p_ini > 0:
                custo_material += p_gasto * (p_rolo / p_ini)
                
        custo_energia = ch * hrs
        custo_total = custo_material + custo_energia
        preco_venda = custo_total * (1 + (lucro/100))
        
        self.lbl_material.configure(text=f"Custo do Material: R$ {custo_material:.2f}")
        self.lbl_energia.configure(text=f"Custo Operacional: R$ {custo_energia:.2f}")
        self.lbl_total.configure(text=f"Custo Total: R$ {custo_total:.2f}")
        self.lbl_venda.configure(text=f"Preço de Venda: R$ {preco_venda:.2f}")


# ==========================================
# MAIN APP
# ==========================================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IJ 3D")
        self.geometry("1200x800")
        self.configure(fg_color=APP_BG_COLOR)
        
        try:
            if os.path.exists(APP_ICON_PATH):
                icon = tk.PhotoImage(file=APP_ICON_PATH)
                self.wm_iconphoto(True, icon)
        except: pass
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.sidebar_expanded = True
        self.sidebar_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#111111", border_width=1, border_color=BORDER_COLOR)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(8, weight=1)
        
        self.btn_toggle = ctk.CTkButton(self.sidebar_frame, text="≡", width=40, height=40, fg_color="transparent", font=ctk.CTkFont(size=20), command=self.toggle_sidebar)
        self.btn_toggle.grid(row=0, column=0, padx=10, pady=(20, 10), sticky="w")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="IJ 3D", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=1, padx=(0, 20), pady=(20, 10), sticky="w")
        
        conn = sqlite3.connect(DB_NAME)
        p_name = conn.execute("SELECT printer_name FROM configuracoes WHERE id=1").fetchone()[0]
        conn.close()
        
        self.printer_var = ctk.StringVar(value=p_name)
        self.printer_entry = ctk.CTkEntry(self.sidebar_frame, textvariable=self.printer_var, width=150, fg_color="transparent", border_width=0, font=ctk.CTkFont(size=12, slant="italic"), text_color=ACCENT_COLOR)
        self.printer_entry.grid(row=1, column=1, padx=(0,20), pady=(0, 30), sticky="w")
        self.printer_entry.bind("<FocusOut>", self.save_printer_name)
        self.printer_entry.bind("<Return>", self.save_printer_name)
        
        self.nav_btns = []
        def create_nav_btn(row, icon, text, cmd):
            btn = ctk.CTkButton(self.sidebar_frame, text=f"{icon}   {text}", width=200, fg_color="transparent", text_color="white", anchor="w", font=ctk.CTkFont(size=15), command=cmd)
            btn.grid(row=row, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
            self.nav_btns.append((btn, f"{icon}   {text}", f"{icon}"))
        
        create_nav_btn(2, "⚙", "Filamentos", self.show_filamentos)
        create_nav_btn(3, "📦", "Almoxarifado", self.show_insumos)
        create_nav_btn(4, "📚", "Acervo", self.show_acervo)
        create_nav_btn(5, "📝", "Pedidos", self.show_pedidos)
        create_nav_btn(6, "💰", "Calculadora", self.show_financeiro)
        create_nav_btn(7, "🔧", "Manutenção", self.show_manutencao)
        
        self.footer = ctk.CTkButton(self.sidebar_frame, text="  github.com/IllanSpala", width=200, fg_color="transparent", text_color="gray", hover_color="#222", anchor="w", command=lambda: open_url("https://github.com/IllanSpala"))
        self.footer.grid(row=9, column=0, columnspan=2, padx=10, pady=(10,20), sticky="ew")
        
        self.main_frame = ctk.CTkFrame(self, fg_color=APP_BG_COLOR, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        
        self.current_frame = None
        self.show_filamentos()

    def save_printer_name(self, event=None):
        name = self.printer_var.get()
        conn = sqlite3.connect(DB_NAME)
        conn.execute("UPDATE configuracoes SET printer_name=? WHERE id=1", (name,))
        conn.commit(); conn.close()
        self.focus()

    def toggle_sidebar(self):
        self.sidebar_expanded = not self.sidebar_expanded
        if self.sidebar_expanded:
            self.sidebar_frame.configure(width=220)
            self.logo_label.grid()
            self.printer_entry.grid()
            self.footer.configure(text="  github.com/IllanSpala", width=200)
            for btn, full_text, short_text in self.nav_btns:
                btn.configure(text=full_text, width=200)
        else:
            self.sidebar_frame.configure(width=50)
            self.logo_label.grid_remove()
            self.printer_entry.grid_remove()
            self.footer.configure(text=" ", width=30)
            for btn, full_text, short_text in self.nav_btns:
                btn.configure(text=short_text, width=30)

    def clear_main(self):
        if self.current_frame is not None: self.current_frame.destroy()
            
    def show_filamentos(self):
        self.clear_main()
        self.current_frame = TabFilamentos(self.main_frame)
        self.current_frame.pack(fill="both", expand=True)

    def show_acervo(self):
        self.clear_main()
        self.current_frame = TabAcervo(self.main_frame)
        self.current_frame.pack(fill="both", expand=True)
            
    def show_pedidos(self):
        self.clear_main()
        self.current_frame = TabPedidos(self.main_frame)
        self.current_frame.pack(fill="both", expand=True)

    def show_financeiro(self):
        self.clear_main()
        self.current_frame = TabFinanceiro(self.main_frame)
        self.current_frame.pack(fill="both", expand=True)

    def show_manutencao(self):
        self.clear_main()
        self.current_frame = TabManutencao(self.main_frame)
        self.current_frame.pack(fill="both", expand=True)

    def show_insumos(self):
        self.clear_main()
        self.current_frame = TabAlmoxarifado(self.main_frame)
        self.current_frame.pack(fill="both", expand=True)

if __name__ == "__main__":
    init_db()
    app = App()
    app.mainloop()