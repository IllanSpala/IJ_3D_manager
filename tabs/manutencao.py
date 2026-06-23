import sqlite3
import datetime
import customtkinter as ctk
from core.database import db
from core.widgets import ModernCard
from core.utils import open_url, BORDER_COLOR

class TabManutencao(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="Rotinas de Manutenção", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 20))
        self._load()

    def _mark_done(self, tid: int):
        with db.get_connection() as conn:
            conn.execute("UPDATE manutencao SET ultima_execucao=? WHERE id=?", (datetime.date.today().isoformat(), tid))
            conn.commit()
        self._load()

    def _load(self):
        for w in self.scroll.winfo_children(): w.destroy()
        with db.get_connection() as conn:
            rows = conn.execute("SELECT id, tarefa, guia_instrucao, intervalo_dias, ultima_execucao, link_tutorial FROM manutencao").fetchall()

        hoje = datetime.date.today()
        for row in rows:
            t_id, tarefa, guia, inv, ult, link = row
            try: data_ult = datetime.date.fromisoformat(ult)
            except Exception: data_ult = hoje
            dias = (hoje - data_ult).days
            atrasado = dias >= inv

            card = ModernCard(self.scroll, border_color="#d64545" if atrasado else BORDER_COLOR, border_width=2 if atrasado else 1)
            card.pack(fill="x", pady=8)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=15, pady=(15, 5))
            ctk.CTkLabel(top, text=tarefa, font=ctk.CTkFont(weight="bold", size=16), text_color="#d64545" if atrasado else "white").pack(side="left")
            ctk.CTkLabel(top, text=f"Última: {ult} ({dias} dias atrás)", text_color="gray").pack(side="left", padx=10)
            ctk.CTkButton(top, text="Feito Hoje", width=100, fg_color="#2b7a4b", hover_color="#1d5c36", command=lambda t=t_id: self._mark_done(t)).pack(side="right")

            mid = ctk.CTkFrame(card, fg_color="transparent")
            mid.pack(fill="x", padx=15, pady=(5, 15))
            ctk.CTkLabel(mid, text=guia, wraplength=700, justify="left", text_color="#ccc").pack(side="left", fill="x", expand=True)
            if link:
                ctk.CTkButton(mid, text="Ver Tutorial", fg_color="transparent", border_width=1, border_color=BORDER_COLOR, width=100, hover_color="#333", command=lambda l=link: open_url(l)).pack(side="right", padx=(10, 0))
