import sqlite3
import functools
from typing import Callable, Dict, List, Any
from core.database import db

def _lru_db_cache(maxsize: int = 32):
    def decorator(fn):
        cached = functools.lru_cache(maxsize=maxsize)(fn)
        fn._cached_impl = cached
        def wrapper(*args, **kwargs):
            return cached(*args, **kwargs)
        wrapper.cache_clear = cached.cache_clear
        wrapper.cache_info  = cached.cache_info
        return wrapper
    return decorator

class StateManager:
    def __init__(self):
        self.filamentos   = []
        self.acervo       = []
        self.almoxarifado = []
        self.pedidos      = []
        self._shutting_down = False

        self.listeners: Dict[str, List[Callable]] = {
            'filamentos':   [],
            'acervo':       [],
            'almoxarifado': [],
            'pedidos':      [],
        }

    def subscribe(self, key: str, listener: Callable):
        if key in self.listeners:
            self.listeners[key].append(listener)

    def notify(self, key: str, data: Any = None):
        if self._shutting_down:
            return
        for listener in self.listeners.get(key, []):
            try:
                listener(data)
            except Exception:
                pass

    def get_filamentos_ativos(self) -> list[dict]:
        return _get_filamentos_ativos_cached()

    def invalidate_filamentos_cache(self):
        _get_filamentos_ativos_cached.cache_clear()

    def get_configuracoes(self) -> dict:
        return _get_configuracoes_cached()

    def invalidate_config_cache(self):
        _get_configuracoes_cached.cache_clear()

    def load_filamentos(self):
        self.invalidate_filamentos_cache()
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM filamentos ORDER BY id DESC").fetchall()
            self.filamentos = [dict(r) for r in rows]
        self.notify('filamentos')

    def add_filamento(self, data: dict):
        self.invalidate_filamentos_cache()
        with db.get_connection() as conn:
            c = conn.cursor()
            cols   = ', '.join(data.keys())
            places = ', '.join(['?'] * len(data))
            c.execute(f"INSERT INTO filamentos ({cols}) VALUES ({places})", tuple(data.values()))
            conn.commit()
        self.load_filamentos()

    def update_filamento(self, f_id: int, updates: dict):
        self.invalidate_filamentos_cache()
        with db.get_connection() as conn:
            c = conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            c.execute(f"UPDATE filamentos SET {set_clause} WHERE id = ?",
                      (*updates.values(), f_id))
            conn.commit()
        for f in self.filamentos:
            if f['id'] == f_id:
                f.update(updates)
                self.notify('filamentos', {'action': 'update', 'id': f_id, 'data': f})
                break

    def archive_filamento(self, f_id: int):
        self.invalidate_filamentos_cache()
        self.update_filamento(f_id, {'status': 'Arquivado'})
        self.filamentos = [f for f in self.filamentos if f['id'] != f_id]
        self.notify('filamentos', {'action': 'remove', 'id': f_id})

    def load_acervo(self):
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM acervo ORDER BY id DESC").fetchall()
            self.acervo = [dict(r) for r in rows]

            for ac in self.acervo:
                fils = conn.execute(
                    """SELECT af.filamento_id, f.marca, f.cor, af.peso_gasto, af.peso_desperdicio
                       FROM acervo_filamentos af
                       JOIN filamentos f ON af.filamento_id = f.id
                       WHERE af.acervo_id=?""", (ac['id'],)
                ).fetchall()
                ac['materiais'] = [dict(f) for f in fils]

                last_print = conn.execute(
                    "SELECT data_impressao FROM acervo_impressoes "
                    "WHERE acervo_id=? ORDER BY id DESC LIMIT 1",
                    (ac['id'],)
                ).fetchone()
                ac['ultima_impressao'] = (last_print['data_impressao']
                                          if last_print else None)

                count = conn.execute(
                    "SELECT COUNT(*) FROM acervo_impressoes WHERE acervo_id=?",
                    (ac['id'],)
                ).fetchone()[0]
                ac['total_impressoes'] = count

        self.notify('acervo')

    def update_acervo(self, a_id: int, updates: dict):
        with db.get_connection() as conn:
            c = conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            c.execute(f"UPDATE acervo SET {set_clause} WHERE id = ?",
                      (*updates.values(), a_id))
            conn.commit()
        for a in self.acervo:
            if a['id'] == a_id:
                a.update(updates)
                self.notify('acervo', {'action': 'update', 'id': a_id, 'data': a})
                break

    def load_almoxarifado(self):
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM ferramentas_insumos ORDER BY categoria, nome"
            ).fetchall()
            self.almoxarifado = [dict(r) for r in rows]
        self.notify('almoxarifado')

    def update_almoxarifado(self, item_id: int, updates: dict):
        with db.get_connection() as conn:
            c = conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            c.execute(f"UPDATE ferramentas_insumos SET {set_clause} WHERE id = ?",
                      (*updates.values(), item_id))
            conn.commit()
        for i in self.almoxarifado:
            if i['id'] == item_id:
                i.update(updates)
                self.notify('almoxarifado', {'action': 'update', 'id': item_id, 'data': i})
                break

    def load_pedidos(self):
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM pedidos_v2").fetchall()
            self.pedidos = [dict(r) for r in rows]

            for p in self.pedidos:
                pecas_acervo = conn.execute(
                    """SELECT a.nome_peca
                       FROM pedidos_itens pi
                       JOIN acervo a ON pi.acervo_id=a.id
                       WHERE pi.pedido_id=? AND (pi.tipo='acervo' OR pi.tipo IS NULL)""", (p['id'],)
                ).fetchall()
                
                pecas_avulsas = conn.execute(
                    """SELECT COALESCE(nome_avulso, nome_custom, 'Peça Avulsa') as nome_peca
                       FROM pedidos_itens
                       WHERE pedido_id=? AND tipo='avulso'""", (p['id'],)
                ).fetchall()
                
                p['pecas'] = [dict(pc) for pc in pecas_acervo] + [dict(pc) for pc in pecas_avulsas]

        self.notify('pedidos')

    def update_pedido(self, p_id: int, updates: dict):
        with db.get_connection() as conn:
            c = conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            c.execute(f"UPDATE pedidos_v2 SET {set_clause} WHERE id = ?",
                      (*updates.values(), p_id))
            conn.commit()
        for p in self.pedidos:
            if p['id'] == p_id:
                p.update(updates)
                self.notify('pedidos', {'action': 'update', 'id': p_id, 'data': p})
                break


@functools.lru_cache(maxsize=1)
def _get_filamentos_ativos_cached() -> list[dict]:
    with db.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        # Restrição rígida: Traz somente o que está explicitamente 'Ativo'
        rows = conn.execute(
            "SELECT id, marca, material, cor, peso_inicial, preco_rolo "
            "FROM filamentos WHERE status = 'Ativo'"
        ).fetchall()
    return [dict(r) for r in rows]

@functools.lru_cache(maxsize=1)
def _get_configuracoes_cached() -> dict:
    with db.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM configuracoes WHERE id=1").fetchone()
    return dict(row) if row else {}

_get_filamentos_ativos_cached = _get_filamentos_ativos_cached
_get_configuracoes_cached     = _get_configuracoes_cached

app_state = StateManager()