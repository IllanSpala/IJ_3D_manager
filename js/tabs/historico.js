/* ═══════════════════════════════════════════════════════════════
   Tab: Histórico de Impressões (CRUD Completo)
   ═══════════════════════════════════════════════════════════════ */
import * as idb from '../db.js';
import { formatBRL, formatDate, formatWeight, statusBadgeClass, escapeHtml } from '../utils.js';

const PAGE_SIZE = 20;
let _allItems = [], _displayed = 0, _filter = '';
let _todosFils = [];
// Todas as linhas de hist_filamentos carregadas (necessário para edição e exclusão)
let _allFilRows = [];
// Callback de escopo de módulo: permite que _page() abra o modal de edição
let _openModalEdit = (_h) => {};

/**
 * Converte um valor string (aceita vírgula OU ponto) para float.
 * Resolve o problema de teclados numéricos BR que digitam "1,5".
 */
function parsePeso(val) {
    if (val === null || val === undefined) return 0;
    return parseFloat(String(val).replace(',', '.')) || 0;
}

export async function render(container) {
    _allItems    = await idb.getAll('hist_impressoes');
    _allFilRows  = await idb.getAll('hist_filamentos');
    _todosFils   = await idb.getAll('filamentos');

    const filMap = {};
    for (const f of _todosFils) filMap[f.id] = f;

    // Enriquecer cada linha de filamento com dados do catálogo
    const filByHist = {};
    for (const f of _allFilRows) {
        const realFil = filMap[f.filamento_id] || {};
        f.marca    = realFil.marca    || '';
        f.material = realFil.material || '';
        f.cor      = realFil.cor      || '';
        (filByHist[f.hist_id] ??= []).push(f);
    }
    for (const h of _allItems) h._filamentos = filByHist[h.id] || [];
    _allItems.sort((a, b) => (b.id || 0) - (a.id || 0));
    _displayed = 0;

    const filAtivos = _todosFils.filter(f => f.status === 'Ativo');
    const filOptsHTML = filAtivos.map(f =>
        `<option value="${f.id}">${escapeHtml(f.marca)} - ${escapeHtml(f.cor)}</option>`
    ).join('');

    container.innerHTML = `
        <div class="card">
            <div class="card-header" style="display:flex; justify-content:space-between; align-items:center;">
                <span>🗂 Histórico de Impressões</span>
                <button class="btn btn-primary" id="hist-add-btn">+ Registro Manual</button>
            </div>
            <div class="filter-bar"><input type="text" id="hist-search" placeholder="Buscar peça ou filamento…"></div>
            <div style="overflow-x:auto;">
                <table class="data-table">
                    <thead><tr>
                        <th>Data</th><th>Pedido/Peça</th><th>Horas Gastas (hh:mm)</th><th>Filamento Gasto por Cor (g)</th><th>Status</th><th style="width:80px; text-align:center;">Ações</th>
                    </tr></thead>
                    <tbody id="hist-tbody"></tbody>
                </table>
            </div>
            <div class="load-more-container" id="hist-lm"></div>
        </div>

        <!-- Modal CRUD -->
        <div id="hist-modal-overlay" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:800;"></div>
        <div id="hist-modal" style="display:none; position:fixed; top:10%; left:50%; transform:translateX(-50%); background:#1e1e1e; padding:20px; border-radius:12px; border:1px solid #333; z-index:1000; min-width:450px; max-height:80vh; overflow-y:auto; box-shadow:0 8px 32px rgba(0,0,0,0.8);">
            <h3 style="margin-top:0; color:#00a2ff;" id="hist-modal-title">Adicionar Registro Manual</h3>
            <input type="hidden" id="hist-editing-id">

            <div style="display:flex; flex-direction:column; gap:10px; margin-bottom:16px;">
                <label>Data <input type="date" id="hist-data" style="width:100%; background:#111; border:1px solid #444; color:#fff; padding:6px; border-radius:4px;"></label>
                <label>Nome da Peça / Pedido <input type="text" id="hist-nome" style="width:100%; background:#111; border:1px solid #444; color:#fff; padding:6px; border-radius:4px;"></label>
                <label>Duração (hh:mm) <input type="time" id="hist-duracao" style="width:100%; background:#111; border:1px solid #444; color:#fff; padding:6px; border-radius:4px;"></label>
                <label>Status
                    <select id="hist-status" style="width:100%; background:#111; border:1px solid #444; color:#fff; padding:6px; border-radius:4px;">
                        <option value="Sucesso">Sucesso</option>
                        <option value="Falha">Falha</option>
                    </select>
                </label>
            </div>

            <div style="margin-bottom:16px;">
                <strong>Filamentos Utilizados:</strong>
                <div id="hist-fil-list" style="margin-bottom:8px;"></div>
                <div style="display:flex; gap:6px;">
                    <select id="hist-sel-fil" style="flex:2; background:#111; border:1px solid #444; color:#fff; padding:6px; border-radius:4px;">
                        ${filOptsHTML}
                    </select>
                    <input type="number" id="hist-sel-peso" placeholder="Peso (g)" step="0.1"
                           style="flex:1; background:#111; border:1px solid #444; color:#fff; padding:6px; border-radius:4px;">
                    <button class="btn btn-ghost" id="hist-add-fil-btn" style="background:#222;">+ Add</button>
                </div>
            </div>

            <div style="display:flex; justify-content:flex-end; gap:8px;">
                <button class="btn btn-ghost" id="hist-cancel-btn">Cancelar</button>
                <button class="btn btn-success" id="hist-save-btn">Salvar Registro</button>
            </div>
        </div>
    `;

    /* ── Referências ──────────────────────────────── */
    const searchEl  = container.querySelector('#hist-search');
    const overlay   = container.querySelector('#hist-modal-overlay');
    const modal     = container.querySelector('#hist-modal');
    const modalTitle = container.querySelector('#hist-modal-title');
    const editingIdEl = container.querySelector('#hist-editing-id');

    let currentFilamentos = []; // [{id, cor, peso}] — estado do modal

    /* ── Render filamentos no modal ─────────────────── */
    function renderFilsForm() {
        const listDiv = container.querySelector('#hist-fil-list');
        if (!listDiv) return;
        listDiv.innerHTML = currentFilamentos.map((f, i) => `
            <div style="display:flex; justify-content:space-between; align-items:center; background:#1c1c1c; padding:6px 10px; border-radius:4px; margin-bottom:4px; font-size:0.82rem;">
                <span style="color:#eee;">🎨 ${escapeHtml(f.cor)} — ${f.peso}g</span>
                <button type="button" class="btn btn-ghost hist-rem-fil-btn" data-idx="${i}" style="color:#d64545; padding:0 6px;">✕</button>
            </div>
        `).join('');

        container.querySelectorAll('.hist-rem-fil-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.currentTarget.dataset.idx);
                currentFilamentos.splice(idx, 1);
                renderFilsForm();
            });
        });
    }

    /* ── Abre modal limpo (modo "Adicionar") ─────────── */
    function openModalAdd() {
        modalTitle.textContent = 'Adicionar Registro Manual';
        editingIdEl.value = '';
        container.querySelector('#hist-data').value    = new Date().toISOString().split('T')[0];
        container.querySelector('#hist-nome').value    = '';
        container.querySelector('#hist-duracao').value = '01:00';
        container.querySelector('#hist-status').value  = 'Sucesso';
        currentFilamentos = [];
        renderFilsForm();
        overlay.style.display = 'block';
        modal.style.display   = 'block';
    }

    /* ── Abre modal preenchido (modo "Editar") ───────── */
    function openModalEdit(h) {
        modalTitle.textContent = 'Editar Registro';
        editingIdEl.value = h.id;
        container.querySelector('#hist-data').value    = h.data_impressao || '';
        container.querySelector('#hist-nome').value    = h.nome_peca      || '';
        container.querySelector('#hist-duracao').value = h.tempo_impressao || '01:00';
        container.querySelector('#hist-status').value  = h.status          || 'Sucesso';

        // Carrega os filamentos já vinculados a este registro
        currentFilamentos = (h._filamentos || []).map(f => ({
            id:   f.filamento_id,
            cor:  f.cor || '—',
            peso: (f.peso_modelo_g || 0) + (f.peso_purga_g || 0)
        }));
        renderFilsForm();
        overlay.style.display = 'block';
        modal.style.display   = 'block';
    }
    // Expõe para _page() que está fora do closure de render()
    _openModalEdit = openModalEdit;

    /* ── Fecha modal ─────────────────────────────────── */
    function closeModal() {
        overlay.style.display = 'none';
        modal.style.display   = 'none';
    }

    /* ── Botão "+ Filamento" no modal ───────────────── */
    container.querySelector('#hist-add-fil-btn').addEventListener('click', () => {
        const sel = container.querySelector('#hist-sel-fil');
        const opt = sel.options[sel.selectedIndex];
        if (!opt) return;

        const pesoRaw = container.querySelector('#hist-sel-peso').value;
        const peso    = parsePeso(pesoRaw);

        currentFilamentos.push({
            id:   Number(opt.value),
            cor:  opt.text.split(' - ')[1] || opt.text,
            peso: peso
        });
        container.querySelector('#hist-sel-peso').value = '';
        renderFilsForm();
    });

    /* ── Botões do header ───────────────────────────── */
    container.querySelector('#hist-add-btn').addEventListener('click', openModalAdd);
    container.querySelector('#hist-cancel-btn').addEventListener('click', closeModal);
    overlay.addEventListener('click', closeModal);

    /* ── Salvar (Adicionar OU Editar) ───────────────── */
    container.querySelector('#hist-save-btn').addEventListener('click', async () => {
        const editingId = editingIdEl.value;
        const isEdit    = !!editingId;

        // ID: preserva o existente em edição; gera novo timestamp para inclusão
        const h_id = isEdit ? (isNaN(Number(editingId)) ? editingId : Number(editingId)) : Date.now();

        const registro = {
            id:             h_id,
            data_impressao: container.querySelector('#hist-data').value,
            nome_peca:      container.querySelector('#hist-nome').value.trim() || 'Sem nome',
            tempo_impressao:container.querySelector('#hist-duracao').value,
            status:         container.querySelector('#hist-status').value
        };

        /* ── Atualiza _allItems em memória ───────────── */
        if (isEdit) {
            const idx = _allItems.findIndex(x => String(x.id) === String(h_id));
            if (idx > -1) {
                // Preserva _filamentos enriquecido para que a exibição não quebre antes do reload
                registro._filamentos = _allItems[idx]._filamentos || [];
                _allItems[idx] = registro;
            } else {
                _allItems.push(registro);
            }
        } else {
            registro._filamentos = [];
            _allItems.push(registro);
        }

        /* ── Persiste hist_impressoes (todas as linhas) ── */
        // Remove a propriedade virtual _filamentos antes de gravar
        const toSave = _allItems.map(({ _filamentos, ...rest }) => rest);
        await idb.putAll('hist_impressoes', toSave);

        /* ── Monta as novas linhas de filamento ─────────── */
        const novasFilRows = currentFilamentos.map((f, i) => ({
            id:            Date.now() + i + Math.floor(Math.random() * 9999),
            hist_id:       h_id,
            filamento_id:  f.id,
            peso_modelo_g: f.peso,
            peso_purga_g:  0
        }));

        // Em edição: remove todas as linhas antigas deste registro e substitui pelas novas
        // Em adição: simplesmente acrescenta ao final
        if (isEdit) {
            _allFilRows = _allFilRows.filter(f => String(f.hist_id) !== String(h_id));
        }
        _allFilRows.push(...novasFilRows);

        await idb.putAll('hist_filamentos', _allFilRows);

        closeModal();
        render(container); // recarrega tudo para re-enriquecer os dados
    });

    /* ── Busca ──────────────────────────────────────── */
    searchEl.addEventListener('input', e => {
        _filter = e.target.value.toLowerCase();
        _reset(container);
    });

    _reset(container);
}

/* ── Funções de paginação e filtragem ─────────────── */

function _filtered() {
    return _allItems.filter(h => {
        if (!_filter) return true;
        const hay = `${h.nome_peca || ''} ${(h._filamentos || []).map(f => f.nome_custom || f.marca || f.cor || '').join(' ')}`.toLowerCase();
        return hay.includes(_filter);
    });
}

function _reset(c) {
    _displayed = 0;
    const tb = c.querySelector('#hist-tbody');
    if (tb) tb.innerHTML = '';
    _page(c);
}

function _page(c) {
    const f  = _filtered();
    const tb = c.querySelector('#hist-tbody');
    const lm = c.querySelector('#hist-lm');
    if (!tb || !lm) return;

    for (const h of f.slice(_displayed, _displayed + PAGE_SIZE)) {
        const fils       = h._filamentos || [];
        const consumoStr = fils.length
            ? fils.map(f => `<div style="font-size:0.8rem; color:#ccc;">🎨 ${escapeHtml(f.cor || '—')} — ${formatWeight((f.peso_modelo_g || 0) + (f.peso_purga_g || 0))}</div>`).join('')
            : '<span style="color:#666;">Sem filamento</span>';

        const tr = document.createElement('tr');
        tr.dataset.histId = h.id;
        tr.innerHTML = `
            <td>${formatDate(h.data_impressao)}</td>
            <td style="font-weight:500;color:#e8e8e8">${escapeHtml(h.nome_peca || '—')}</td>
            <td>${escapeHtml(h.tempo_impressao || '—')}</td>
            <td>${consumoStr}</td>
            <td><span class="badge ${statusBadgeClass(h.status)}">${escapeHtml(h.status || 'Sucesso')}</span></td>
            <td style="text-align:center; white-space:nowrap;">
                <button class="btn btn-ghost hist-edit-btn" data-id="${h.id}"
                        style="padding:4px 7px; font-size:0.8rem; margin-right:2px;" title="Editar">✏️</button>
                <button class="btn btn-ghost hist-del-btn"  data-id="${h.id}"
                        style="padding:4px 7px; font-size:0.8rem; color:#d64545;" title="Excluir">🗑️</button>
            </td>
        `;
        tb.appendChild(tr);
    }

    _displayed += Math.min(PAGE_SIZE, f.length - _displayed);

    // Bind dos botões de ação recém-adicionados
    c.querySelectorAll('.hist-edit-btn').forEach(btn => {
        if (btn.dataset.bound) return;
        btn.dataset.bound = 'true';
        btn.addEventListener('click', (e) => {
            const id   = e.currentTarget.dataset.id;
            const item = _allItems.find(x => String(x.id) === String(id));
            if (item) _openModalEdit(item);
        });
    });

    c.querySelectorAll('.hist-del-btn').forEach(btn => {
        if (btn.dataset.bound) return;
        btn.dataset.bound = 'true';
        btn.addEventListener('click', async (e) => {
            const id = e.currentTarget.dataset.id;
            if (!confirm('Excluir este registro do histórico? Esta ação não pode ser desfeita.')) return;

            // Remove da memória
            _allItems   = _allItems.filter(x => String(x.id) !== String(id));
            _allFilRows = _allFilRows.filter(x => String(x.hist_id) !== String(id));

            // Persiste
            const toSave = _allItems.map(({ _filamentos, ...rest }) => rest);
            await idb.putAll('hist_impressoes', toSave);
            await idb.putAll('hist_filamentos', _allFilRows);

            // Re-renderiza sem reload completo (mais rápido)
            _displayed = 0;
            const tbody = c.querySelector('#hist-tbody');
            if (tbody) tbody.innerHTML = '';
            _page(c);
        });
    });

    if (_displayed < f.length) {
        lm.innerHTML = `<button class="btn btn-ghost" id="hist-mb">Carregar mais (${f.length - _displayed})</button>`;
        lm.querySelector('#hist-mb').addEventListener('click', () => _page(c));
    } else {
        lm.innerHTML = '';
        if (!f.length) tb.innerHTML = `<tr><td colspan="6" class="empty-state"><span class="empty-state-icon">🗂</span>Nenhum registro.</td></tr>`;
    }
}


