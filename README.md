# IJ 3D Manager — Windows Desktop

![Platform](https://img.shields.io/badge/platform-Windows-0078D6?style=flat-square&logo=windows)
![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)

Sistema ERP pessoal para gestão de impressão 3D — Bambu Lab A1 e compatíveis.

Desenvolvido em **Python 3.11+** com **CustomTkinter**, banco de dados **SQLite** local e empacotamento via **PyInstaller**.

> ⚠️ **Este repositório gera exclusivamente o executável Windows (.exe).**
> Para a versão Web (visualização via navegador), consulte o repositório **[IJ_3D_web](https://github.com/IllanSpala/IJ_3D_web)**.

---

## Funcionalidades

### 📦 Filamentos
- Cadastro completo: marca, material, cor, peso, link de compra, nota fiscal
- Controle de peso atual, rolos de reserva e status (Ativo / Arquivado)
- Foto e descrição

### 📚 Acervo de Peças
- Registro de modelos 3D com foto, arquivo STL/3MF, pós-processamento
- Vinculação de filamentos com peso gasto (g) e purga (g) por material
- Registro e reversão de sessões de impressão com desconto automático no estoque
- Galeria de prints do fatiador (Bambu Studio / PrusaSlicer)
- Parâmetros de fatiamento por peça (texto livre)
- Link de compra / referência

### 🗂 Histórico de Impressões
- Tabela completa de todas as sessões de impressão registradas
- Colunas: Data · Peça · Status · Filamento(s) · Purga (g) · Modelo (g) · Total (g) · Conf. Fatiador · Arquivo 3D · **Preço de Venda (R$)** · Observação
- Filtro por nome de peça/filamento e por status
- Edição inline de status, preço de venda e observação por sessão
- Modal de detalhes com galeria de prints do fatiador e materiais

### 🎺 Kits
- Agrupamento de peças em kits para venda conjunta
- Cálculo financeiro por kit completo

### 📝 Pedidos
- Kanban de pedidos com status: Aguardando → Imprimindo → Finalizado
- Vinculação de peças e clientes

### 💰 Calculadora Financeira
- Extrato analítico de custo: material + operação + embalagem
- Margem de lucro configurável + taxa de plataforma (Shopee, Mercado Livre, OLX, Direto)
- **Quantidade de Cópias** — divide o custo total por N peças idênticas, mostrando custo unitário e preço de venda por peça
- Engenharia reversa: informe o preço de venda e calcule a margem real
- Modo avulso: teste sem peça cadastrada
- Salvar teste diretamente no Acervo

### ⚙ Almoxarifado / Manutenção
- Inventário de ferramentas e insumos
- Checklist de manutenção preventiva com intervalos configuráveis

---

## Ferramenta Windows — Exportar para o Histórico

> **Arquivo:** `tools/Exportar_para_Historico.bat` (duplo clique) ou `tools/exportar_historico_windows.ps1`

Permite, **diretamente do Windows** (sem abrir o app):
1. Selecionar a peça/impressão no banco de dados
2. Abrir o Notepad para colar/digitar os parâmetros do fatiador
3. Selecionar um ou mais prints/screenshots do fatiador
4. Gravar tudo no banco de dados automaticamente

**Pré-requisitos:**
- Python 3.x instalado e no `PATH`
- Banco de dados acessível (detectado automaticamente na pasta do `.exe`)

---

## Instalação e Execução (Desenvolvimento)

```bat
git clone https://github.com/seu-usuario/IJ_3D_manager.git
cd IJ_3D_manager
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

---

## Empacotamento (PyInstaller)

```bat
build_executable.bat
```

O executável final ficará em `dist\IJ-3D-Manager.exe`.

> **Dados do usuário** (banco de dados e mídias) são salvos ao lado do executável na primeira execução.

---

## Estrutura do Projeto

```
IJ_3D_manager/
├── app.py                  # Ponto de entrada, sidebar e navegação
├── requirements.txt
├── build_executable.bat    # Build Windows (PyInstaller)
│
├── core/
│   ├── database.py         # Schema SQLite, migrações automáticas
│   ├── state.py            # StateManager + cache LRU
│   ├── modals.py           # DetalhesModal (acervo + filamentos)
│   ├── paths.py            # Resolução de caminhos (dev vs frozen)
│   ├── utils.py            # Helpers de imagem, mídia, cores
│   ├── db_worker.py        # Worker thread para operações DB pesadas
│   └── widgets.py          # ModernCard, InlineEdit, HorizontalInventoryCard
│
├── tabs/
│   ├── filamentos.py       # Aba de filamentos
│   ├── acervo.py           # Aba do acervo de peças
│   ├── almoxarifado.py     # Aba de ferramentas e insumos
│   ├── kits.py             # Aba de kits
│   ├── pedidos.py          # Aba de pedidos (Kanban)
│   ├── historico.py        # Aba de histórico de impressões
│   ├── financeiro.py       # Calculadora financeira
│   ├── sumario.py          # Sumário / balanço financeiro
│   └── manutencao.py       # Aba de manutenção preventiva
│
└── tools/
    ├── exportar_historico_windows.ps1   # Script PowerShell (Windows)
    └── Exportar_para_Historico.bat      # Launcher (duplo clique)
```

---

## Banco de Dados

SQLite local. Principais tabelas:

| Tabela | Descrição |
|--------|-----------|
| `filamentos` | Estoque de filamentos |
| `acervo` | Catálogo de peças 3D |
| `acervo_filamentos` | Vínculo peça ↔ filamento com pesos |
| `acervo_impressoes` | Histórico de sessões (+ status, preço venda, obs) |
| `acervo_fotos_extras` | Galeria de prints do fatiador |
| `hist_impressoes` / `hist_filamentos` / `hist_fotos` | Histórico geral de impressões |
| `kits_acervo` / `kit_itens` | Kits de peças |
| `pedidos_v2` / `pedidos_itens` | Pedidos de clientes |
| `ferramentas_insumos` | Almoxarifado |
| `manutencao` | Tarefas de manutenção preventiva |
| `configuracoes` | Parâmetros globais (custos, margens) |

Migrações são aplicadas automaticamente ao iniciar o app — nenhuma ação manual necessária ao atualizar.

---

## Backup e Integração com a Versão Web

Use os botões da barra lateral:
- 💾 **Exportar Backup** — gera `.zip` com DB + mídias
- 📂 **Importar Backup** — restaura `.zip` (sobrescreve dados atuais)

> O arquivo `.zip` exportado é compatível com a **versão Web** do IJ 3D Manager.
> Basta fazer o upload do backup na versão Web para visualizar seus dados no navegador.

---

## Requisitos

```
customtkinter>=5.2.0
Pillow>=10.0.0
pyinstaller>=6.0
```
