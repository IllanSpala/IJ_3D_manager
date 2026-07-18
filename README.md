# IJ 3D Manager - Windows Desktop

Sistema ERP pessoal para gestao de impressao 3D - Bambu Lab A1 e compativeis.

Desenvolvido em Python 3.11+ com CustomTkinter, banco de dados SQLite local e empacotamento via PyInstaller.

[Aviso] Este repositorio gera exclusivamente o executavel Windows (.exe).
Para a versao Web (visualizacao via navegador), consulte o repositorio IJ_3D_web.

---

## Funcionalidades

### Filamentos
- Cadastro completo: marca, material, cor, peso, link de compra, nota fiscal
- Controle de peso atual, rolos de reserva e status (Ativo / Arquivado)
- Foto e descricao

### Acervo de Pecas
- Registro de modelos 3D com foto, arquivo STL/3MF, pos-processamento
- Vinculacao de filamentos com peso gasto (g) e purga (g) por material
- Registro e reversao de sessoes de impressao com desconto automatico no estoque
- Galeria de prints do fatiador (Bambu Studio / PrusaSlicer)
- Parametros de fatiamento por peca (texto livre)
- Link de compra / referencia

### Historico de Impressoes
- Tabela completa de todas as sessoes de impressao registradas
- Colunas: Data, Peca, Status, Filamento(s), Purga (g), Modelo (g), Total (g), Observacao
- Filtro por nome de peca/filamento e por status
- Edicao inline de status e observacao por sessao
- Modal de detalhes com galeria de prints do fatiador e materiais

### Pedidos
- Kanban de pedidos com status: Aguardando -> Imprimindo -> Finalizado
- Vinculacao de pecas e clientes

### Calculadora Financeira
- Extrato analitico de custo: material + operacao + embalagem
- Margem de lucro configuravel + taxa de plataforma (Shopee, Mercado Livre, OLX, Direto)
- Quantidade de Copias - divide o custo total por N pecas identicas, mostrando custo unitario e preco de venda por peca
- Engenharia reversa: informe o preco de venda e calcule a margem real
- Modo avulso: teste sem peca cadastrada
- Salvar teste diretamente no Acervo

### Almoxarifado
- Inventario de ferramentas e insumos


---

## Ferramenta Windows - Exportar para o Historico

Arquivo: tools/Exportar_para_Historico.bat (duplo clique) ou tools/exportar_historico_windows.ps1

Permite, diretamente do Windows (sem abrir o app):
1. Selecionar a peca/impressao no banco de dados
2. Abrir o Notepad para colar/digitar os parametros do fatiador
3. Selecionar um ou mais prints/screenshots do fatiador
4. Gravar tudo no banco de dados automaticamente

Pre-requisitos:
- Python 3.x instalado e no PATH
- Banco de dados acessivel (detectado automaticamente na pasta do .exe)

---

## Instalacao e Execucao (Desenvolvimento)

git clone https://github.com/seu-usuario/IJ_3D_manager.git
cd IJ_3D_manager
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python app.py

---

## Empacotamento (PyInstaller)

build_executable.bat

O executavel final ficara em dist\IJ-3D-Manager.exe.

Dados do usuario (banco de dados e midias) sao salvos ao lado do executavel na primeira execucao.

---

## Estrutura do Projeto

IJ_3D_manager/
|-- app.py                  # Ponto de entrada, sidebar e navegacao
|-- requirements.txt
|-- build_executable.bat    # Build Windows (PyInstaller)
|
|-- core/
|   |-- database.py         # Schema SQLite, migracoes automaticas
|   |-- state.py            # StateManager + cache LRU
|   |-- modals.py           # DetalhesModal (acervo + filamentos)
|   |-- paths.py            # Resolucao de caminhos (dev vs frozen)
|   |-- utils.py            # Helpers de imagem, midia, cores
|   |-- db_worker.py        # Worker thread para operacoes DB pesadas
|   |-- widgets.py          # ModernCard, InlineEdit, HorizontalInventoryCard
|
|-- tabs/
|   |-- filamentos.py       # Aba de filamentos
|   |-- acervo.py           # Aba do acervo de pecas
|   |-- almoxarifado.py     # Aba de ferramentas e insumos
|   |-- pedidos.py          # Aba de pedidos (Kanban)
|   |-- historico.py        # Aba de historico de impressoes
|   |-- financeiro.py       # Calculadora financeira
|   |-- sumario.py          # Sumario / balanco financeiro
|   |-- manutencao.py       # Aba de manutencao preventiva
|
|-- tools/
    |-- exportar_historico_windows.ps1   # Script PowerShell (Windows)
    |-- Exportar_para_Historico.bat      # Launcher (duplo clique)

---

## Banco de Dados

SQLite local. Principais tabelas:

| Tabela | Descricao |
|--------|-----------|
| filamentos | Estoque de filamentos |
| acervo | Catalogo de pecas 3D |
| acervo_filamentos | Vinculo peca - filamento com pesos |
| acervo_impressoes | Historico de sessoes |
| acervo_fotos_extras | Galeria de prints do fatiador |
| hist_impressoes / hist_filamentos / hist_fotos | Historico geral de impressoes |
| pedidos_v2 / pedidos_itens | Pedidos de clientes |
| ferramentas_insumos | Almoxarifado |
| manutencao | Tarefas de manutencao preventiva |
| configuracoes | Parametros globais (custos, margens) |

Migracoes sao aplicadas automaticamente ao iniciar o app - nenhuma acao manual necessaria ao atualizar.

---

## Backup e Integracao com a Versao Web

Use os botoes da barra lateral:
- Exportar Backup - gera .zip com DB + midias
- Importar Backup - restaura .zip (sobrescreve dados atuais)

O arquivo .zip exportado e compativel com a versao Web do IJ 3D Manager.
Basta fazer o upload do backup na versao Web para visualizar seus dados no navegador.

---

## Requisitos

customtkinter>=5.2.0
Pillow>=10.0.0
pyinstaller>=6.0
