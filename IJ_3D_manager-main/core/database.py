import sqlite3
import datetime
from pathlib import Path
from core.paths import DATA_DIR

BASE_DIR = DATA_DIR
DB_PATH = DATA_DIR / "print_manager_v2.db"

class DatabaseManager:
    def __init__(self):
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(str(DB_PATH))

    def init_db(self):
        with self.get_connection() as conn:
            c = conn.cursor()
            
            # configuracoes
            c.execute('''CREATE TABLE IF NOT EXISTS configuracoes
                         (id INTEGER PRIMARY KEY, printer_name TEXT,
                          calc_custo_hora TEXT DEFAULT '1.50',
                          calc_lucro_pct TEXT DEFAULT '100',
                          calc_embalagem TEXT DEFAULT '0.00')''')
            if c.execute("SELECT COUNT(*) FROM configuracoes").fetchone()[0] == 0:
                c.execute("INSERT INTO configuracoes (id, printer_name) VALUES (1, 'BAMBU LAB A1')")
            # migrations for configuracoes
            for _col, _def in [("calc_custo_hora", "TEXT DEFAULT '1.50'"),
                               ("calc_lucro_pct",  "TEXT DEFAULT '100'"),
                               ("calc_embalagem",   "TEXT DEFAULT '0.00'")]:
                try:
                    c.execute(f"ALTER TABLE configuracoes ADD COLUMN {_col} {_def}")
                except sqlite3.OperationalError:
                    pass

            # filamentos
            c.execute('''CREATE TABLE IF NOT EXISTS filamentos
                         (id INTEGER PRIMARY KEY,
                          marca TEXT, material TEXT, cor TEXT,
                          peso_inicial REAL, peso_atual REAL,
                          caminho_foto TEXT, link_compra TEXT,
                          preco_rolo REAL DEFAULT 0.0,
                          caminho_nota_fiscal TEXT,
                          status TEXT DEFAULT 'Ativo',
                          descricao TEXT)''')

            # Migrations for filamentos
            for col, definition in [
                ("link_compra", "TEXT"),
                ("preco_rolo", "REAL DEFAULT 0.0"),
                ("caminho_nota_fiscal", "TEXT"),
                ("status", "TEXT DEFAULT 'Ativo'"),
                ("descricao", "TEXT"),
                ("rolos_reserva", "INTEGER DEFAULT 0")
            ]:
                try:
                    c.execute(f"ALTER TABLE filamentos ADD COLUMN {col} {definition}")
                except sqlite3.OperationalError:
                    pass

            # historico_impressao (legacy — kept for backward compat)
            c.execute('''CREATE TABLE IF NOT EXISTS historico_impressao
                         (id INTEGER PRIMARY KEY,
                           filamento_id INTEGER NOT NULL,
                           data_impressao TEXT NOT NULL,
                           peso_peca_g REAL NOT NULL DEFAULT 0.0,
                           peso_desperdicio_g REAL NOT NULL DEFAULT 0.0,
                           status TEXT NOT NULL DEFAULT 'Sucesso',
                           observacao TEXT,
                           FOREIGN KEY(filamento_id) REFERENCES filamentos(id) ON DELETE CASCADE)''')

            # acervo
            c.execute('''CREATE TABLE IF NOT EXISTS acervo
                         (id INTEGER PRIMARY KEY,
                          nome_peca TEXT, caminho_foto TEXT,
                          arquivo_3d TEXT, pos_processamento TEXT,
                          data_registro TEXT,
                          descricao TEXT)''')
            for _acol, _adef in [
                ("descricao",       "TEXT"),
                ("config_fatiador", "TEXT"),
                ("link_compra",     "TEXT"),
                ("tempo_impressao", "TEXT"),
                ("preco_custo",     "REAL DEFAULT 0.0"),
            ]:
                try:
                    c.execute(f"ALTER TABLE acervo ADD COLUMN {_acol} {_adef}")
                except sqlite3.OperationalError:
                    pass

            c.execute('''CREATE TABLE IF NOT EXISTS acervo_filamentos
                         (acervo_id INTEGER, filamento_id INTEGER, peso_gasto REAL,
                          peso_desperdicio REAL DEFAULT 0.0,
                          FOREIGN KEY(acervo_id) REFERENCES acervo(id),
                          FOREIGN KEY(filamento_id) REFERENCES filamentos(id))''')
            for _col, _def in [
                ("peso_desperdicio", "REAL DEFAULT 0.0"),
                ("peso_torre",       "REAL DEFAULT 0.0"),
            ]:
                try:
                    c.execute(f"ALTER TABLE acervo_filamentos ADD COLUMN {_col} {_def}")
                except sqlite3.OperationalError:
                    pass

            c.execute('''CREATE TABLE IF NOT EXISTS acervo_impressoes
                         (id INTEGER PRIMARY KEY,
                          acervo_id INTEGER,
                          data_impressao TEXT,
                          status TEXT DEFAULT 'Sucesso',
                          preco_venda REAL,
                          observacao TEXT,
                          FOREIGN KEY(acervo_id) REFERENCES acervo(id) ON DELETE CASCADE)''')
            # Migrations for acervo_impressoes
            for _col, _def in [
                ("status",          "TEXT DEFAULT 'Sucesso'"),
                ("preco_venda",     "REAL"),
                ("observacao",      "TEXT"),
                ("tempo_impressao", "TEXT"),
            ]:
                try:
                    c.execute(f"ALTER TABLE acervo_impressoes ADD COLUMN {_col} {_def}")
                except sqlite3.OperationalError:
                    pass

            # Foto do fatiador nos detalhes da peça
            try:
                c.execute("ALTER TABLE acervo ADD COLUMN foto_fatiador TEXT")
            except sqlite3.OperationalError:
                pass

            # Galeria de prints extras por peça
            c.execute('''CREATE TABLE IF NOT EXISTS acervo_fotos_extras
                         (id INTEGER PRIMARY KEY,
                          acervo_id INTEGER NOT NULL,
                          caminho_foto TEXT NOT NULL,
                          legenda TEXT,
                          FOREIGN KEY(acervo_id) REFERENCES acervo(id) ON DELETE CASCADE)''')

            # hist_impressoes — general print history (linked to acervo or standalone)
            c.execute('''CREATE TABLE IF NOT EXISTS hist_impressoes
                         (id INTEGER PRIMARY KEY,
                          acervo_id INTEGER,
                          nome_peca TEXT,
                          data_impressao TEXT,
                          tempo_impressao TEXT,
                          status TEXT DEFAULT 'Sucesso',
                          preco_venda REAL,
                          observacao TEXT,
                          config_fatiador TEXT,
                          arquivo_3d TEXT)''')

            c.execute('''CREATE TABLE IF NOT EXISTS hist_filamentos
                         (id INTEGER PRIMARY KEY,
                          hist_id INTEGER NOT NULL,
                          filamento_id INTEGER,
                          nome_custom TEXT,
                          cor TEXT,
                          material TEXT,
                          marca TEXT,
                          peso_modelo_g REAL DEFAULT 0.0,
                          peso_purga_g  REAL DEFAULT 0.0,
                          peso_torre_g  REAL DEFAULT 0.0,
                          FOREIGN KEY(hist_id) REFERENCES hist_impressoes(id) ON DELETE CASCADE)''')

            c.execute('''CREATE TABLE IF NOT EXISTS hist_fotos
                         (id INTEGER PRIMARY KEY,
                          hist_id INTEGER NOT NULL,
                          caminho_foto TEXT NOT NULL,
                          legenda TEXT,
                          FOREIGN KEY(hist_id) REFERENCES hist_impressoes(id) ON DELETE CASCADE)''')

            # kits_acervo — agrupamento de peças
            c.execute('''CREATE TABLE IF NOT EXISTS kits_acervo
                         (id INTEGER PRIMARY KEY,
                          nome_kit TEXT NOT NULL,
                          descricao TEXT,
                          caminho_foto TEXT,
                          data_registro TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS kit_itens
                         (id INTEGER PRIMARY KEY,
                          kit_id INTEGER NOT NULL,
                          acervo_id INTEGER NOT NULL,
                          quantidade INTEGER DEFAULT 1,
                          FOREIGN KEY(kit_id) REFERENCES kits_acervo(id) ON DELETE CASCADE,
                          FOREIGN KEY(acervo_id) REFERENCES acervo(id))''')

            # manutencao
            c.execute('''CREATE TABLE IF NOT EXISTS manutencao
                         (id INTEGER PRIMARY KEY,
                          tarefa TEXT, guia_instrucao TEXT,
                          intervalo_dias INTEGER, ultima_execucao TEXT,
                          link_tutorial TEXT)''')

            # ferramentas_insumos
            c.execute('''CREATE TABLE IF NOT EXISTS ferramentas_insumos
                         (id INTEGER PRIMARY KEY,
                          nome TEXT, categoria TEXT, quantidade_status TEXT,
                          caminho_foto TEXT, link_compra TEXT,
                          ultimo_valor REAL,
                          descricao TEXT)''')
            try:
                c.execute("ALTER TABLE ferramentas_insumos ADD COLUMN descricao TEXT")
            except sqlite3.OperationalError:
                pass

            # pedidos_v2
            c.execute('''CREATE TABLE IF NOT EXISTS pedidos_v2
                         (id INTEGER PRIMARY KEY,
                          nome_cliente TEXT, data_entrega TEXT,
                          valor_cobrado REAL, status TEXT,
                          plataforma_venda TEXT)''')
            try:
                c.execute("ALTER TABLE pedidos_v2 ADD COLUMN plataforma_venda TEXT")
            except sqlite3.OperationalError:
                pass
            c.execute('''CREATE TABLE IF NOT EXISTS pedidos_itens
                         (pedido_id INTEGER, acervo_id INTEGER,
                          FOREIGN KEY(pedido_id) REFERENCES pedidos_v2(id),
                          FOREIGN KEY(acervo_id) REFERENCES acervo(id))''')

            # Seed manutencao
            if c.execute("SELECT COUNT(*) FROM manutencao").fetchone()[0] == 0:
                hoje = datetime.date.today().isoformat()
                tarefas = [
                    ("Lubrificar eixo Y", "Limpe os trilhos com pano e álcool isopropílico. Aplique graxa.", 30, hoje, "https://wiki.bambulab.com/en/a1/maintenance/lubricate-y-axis"),
                    ("Lubrificar eixo Z", "Limpe os fusos. Aplique graxa nos fusos e mova o eixo Z.", 30, hoje, "https://wiki.bambulab.com/en/a1/maintenance/lubricate-z-axis"),
                    ("Limpar bico (Nozzle)", "Aqueça a 250°C, use escova de latão para remover resíduos.", 7, hoje, "https://wiki.bambulab.com/en/a1/maintenance/hotend-maintenance"),
                    ("Limpar Engrenagens AMS", "Pressione botões para remover PTFE, sopre ou use pincel.", 30, hoje, "https://wiki.bambulab.com/en/ams-lite/maintenance/cleaning-ams-lite"),
                    ("Tensionar Correias", "Afrouxe parafusos X/Y, mova cabeçote/cama. Reaperte.", 30, hoje, "https://wiki.bambulab.com/en/a1/maintenance/belt-tensioning"),
                    ("Limpar PEI (Mesa)", "Use detergente e água morna. Não use dedos na superfície.", 7, hoje, "https://wiki.bambulab.com/en/general/textured-pei-plate-cleaning"),
                ]
                c.executemany("INSERT INTO manutencao (tarefa, guia_instrucao, intervalo_dias, ultima_execucao, link_tutorial) VALUES (?,?,?,?,?)", tarefas)
            conn.commit()

db = DatabaseManager()
