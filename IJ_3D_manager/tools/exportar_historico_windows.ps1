# ==============================================================================
# IJ 3D Manager — Exportar Configurações do Fatiador para o Histórico
# Versão para Windows (PowerShell)
# ==============================================================================
# USO:
#   Execute este script no PowerShell dentro da pasta do IJ 3D Manager.
#   O script abrirá um diálogo para você selecionar um arquivo .3mf ou print
#   do fatiador (screenshot), e irá atualizar a última impressão cadastrada
#   no banco de dados com as configurações coletadas.
#
# COMO USAR:
#   1. Clique com botão direito no arquivo → "Executar com PowerShell"
#   2. OU: No PowerShell, execute: .\tools\exportar_historico_windows.ps1
#
# PRÉ-REQUISITO:
#   - Python instalado e no PATH (com sqlite3 disponível, já incluso no Python)
#   - O banco de dados print_manager_v2.db deve existir na pasta do usuário
#     (%APPDATA%\IJ3DManager\ ou na pasta do executável)
# ==============================================================================

param(
    [string]$DbPath = "",
    [string]$ConfigText = "",
    [string]$PrintPath = ""
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName Microsoft.VisualBasic

$Host.UI.RawUI.WindowTitle = "IJ 3D Manager — Exportar para Histórico"

# ── 1. Localizar o banco de dados ──────────────────────────────────────────────
if (-not $DbPath) {
    $appdata = [System.Environment]::GetFolderPath("ApplicationData")
    $candidates = @(
        "$appdata\IJ3DManager\print_manager_v2.db",
        "$PSScriptRoot\..\print_manager_v2.db",
        ".\print_manager_v2.db"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $DbPath = $c; break }
    }
}

if (-not $DbPath -or -not (Test-Path $DbPath)) {
    $dlg = New-Object System.Windows.Forms.OpenFileDialog
    $dlg.Title = "Localizar banco de dados IJ 3D Manager"
    $dlg.Filter = "SQLite Database|*.db;*.sqlite;*.sqlite3|Todos|*.*"
    $dlg.InitialDirectory = [System.Environment]::GetFolderPath("ApplicationData")
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $DbPath = $dlg.FileName
    } else {
        [System.Windows.Forms.MessageBox]::Show(
            "Banco de dados não encontrado. Operação cancelada.",
            "IJ 3D Manager", "OK", "Warning")
        exit 1
    }
}

Write-Host "✅ Banco de dados: $DbPath" -ForegroundColor Green

# ── 2. Listar últimas peças do acervo ──────────────────────────────────────────
$pyQuery = @"
import sqlite3, sys, json
db = sqlite3.connect(r'$DbPath')
db.row_factory = sqlite3.Row
rows = db.execute('''
    SELECT a.id, a.nome_peca, ai.id as imp_id, ai.data_impressao
    FROM acervo a
    LEFT JOIN acervo_impressoes ai ON ai.acervo_id = a.id
    ORDER BY ai.id DESC NULLS LAST
    LIMIT 20
''').fetchall()
print(json.dumps([dict(r) for r in rows]))
db.close()
"@

try {
    $jsonResult = python -c $pyQuery 2>&1
    $pecas = $jsonResult | ConvertFrom-Json
} catch {
    [System.Windows.Forms.MessageBox]::Show(
        "Erro ao consultar banco de dados:`n$_",
        "IJ 3D Manager", "OK", "Error")
    exit 1
}

if ($pecas.Count -eq 0) {
    [System.Windows.Forms.MessageBox]::Show(
        "Nenhuma peça/impressão encontrada no banco de dados.",
        "IJ 3D Manager", "OK", "Warning")
    exit 1
}

# Montar lista para seleção
$opcoes = $pecas | ForEach-Object {
    $data = if ($_.data_impressao) { " [Imp: $($_.data_impressao.Substring(0,16))]" } else { " [Sem impressão]" }
    "$($_.nome_peca)$data (ID acervo: $($_.id))"
}

$selecionada = [Microsoft.VisualBasic.Interaction]::InputBox(
    "Selecione a peça/impressão para registrar configuração:`n`n" + ($opcoes -join "`n"),
    "IJ 3D Manager — Selecionar Peça",
    $opcoes[0]
)

if (-not $selecionada) { Write-Host "Cancelado pelo usuário."; exit 0 }

# Extrair imp_id da seleção
$idx = [Array]::IndexOf($opcoes, $selecionada)
if ($idx -lt 0) { $idx = 0 }
$impRow = $pecas[$idx]
$acervoId = $impRow.id
$impId    = $impRow.imp_id

Write-Host "Peça selecionada: $($impRow.nome_peca) (acervo_id=$acervoId, imp_id=$impId)" -ForegroundColor Cyan

# ── 3. Coletar configurações do fatiador ───────────────────────────────────────
if (-not $ConfigText) {
    # Abrir Notepad para o usuário digitar/colar as configs
    $tmpFile = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.txt'
    $template = @"
# Cole aqui as configurações do fatiador (Bambu Studio / PrusaSlicer / Cura etc.)
# Exemplo:
Paredes: 3
Infill: Gyroid 15%
Suportes: Nenhum
Temp Bico: 220°C
Temp Mesa: 60°C
Velocidade: 300 mm/s
Altura Camada: 0.24mm
Material: PLA
Torre: Sim (15g)
Purga: 8g
"@
    $template | Out-File -FilePath $tmpFile -Encoding UTF8
    Start-Process notepad $tmpFile -Wait
    $ConfigText = Get-Content $tmpFile -Raw
    Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
}

if (-not $ConfigText.Trim()) {
    Write-Host "Nenhuma configuração informada. Pulando config_fatiador." -ForegroundColor Yellow
}

# ── 4. Selecionar print do fatiador (screenshot) ───────────────────────────────
$printPaths = @()
$addPrint = [System.Windows.Forms.MessageBox]::Show(
    "Deseja adicionar um ou mais prints/screenshots do fatiador?",
    "IJ 3D Manager", "YesNo", "Question")

if ($addPrint -eq [System.Windows.Forms.DialogResult]::Yes) {
    $dlg = New-Object System.Windows.Forms.OpenFileDialog
    $dlg.Title = "Selecionar Print(s) do Fatiador"
    $dlg.Filter = "Imagens|*.png;*.jpg;*.jpeg;*.bmp;*.webp|Todos|*.*"
    $dlg.Multiselect = $true
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $printPaths = $dlg.FileNames
    }
}

# ── 5. Salvar no banco de dados via Python ─────────────────────────────────────
$configEscaped = $ConfigText -replace "'", "''" -replace '"', '\"'

# Copiar prints para a pasta de mídia do app
$mediaDir = [System.IO.Path]::GetDirectoryName($DbPath) + "\src_media"
if (-not (Test-Path $mediaDir)) { New-Item -ItemType Directory $mediaDir -Force | Out-Null }

$copiedFiles = @()
foreach ($p in $printPaths) {
    $dest = "$mediaDir\$(Split-Path $p -Leaf)"
    if (Test-Path $dest) {
        $ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $ext = [System.IO.Path]::GetExtension($p)
        $base = [System.IO.Path]::GetFileNameWithoutExtension($p)
        $dest = "$mediaDir\${base}_${ts}${ext}"
    }
    Copy-Item $p $dest
    $copiedFiles += [System.IO.Path]::GetFileName($dest)
    Write-Host "📷 Print copiado: $(Split-Path $dest -Leaf)" -ForegroundColor Cyan
}

# Gerar script Python para update + insert
$copiedJson = ($copiedFiles | ForEach-Object { "`"$_`"" }) -join ","
$pyUpdate = @"
import sqlite3, sys, datetime
db = sqlite3.connect(r'$DbPath')
c = db.cursor()

# 1. Atualizar config_fatiador na tabela acervo
config_text = """$configEscaped"""
if config_text.strip():
    c.execute('UPDATE acervo SET config_fatiador=? WHERE id=?', (config_text.strip(), $acervoId))

# 2. Registrar prints extras
fotos = [$copiedJson]
for nome in fotos:
    if nome:
        c.execute('INSERT INTO acervo_fotos_extras (acervo_id, caminho_foto, legenda) VALUES (?,?,?)',
                  ($acervoId, nome, 'Print Fatiador - ' + datetime.date.today().isoformat()))

# 3. Se houver imp_id, atualizar status
imp_id = $(if ($impId) { $impId } else { 'None' })
if imp_id:
    c.execute('UPDATE acervo_impressoes SET status=? WHERE id=?', ('Sucesso', imp_id))

db.commit()
db.close()
print('OK')
"@

try {
    $result = python -c $pyUpdate 2>&1
    if ($result -eq "OK") {
        [System.Windows.Forms.MessageBox]::Show(
            "✅ Configurações exportadas com sucesso para o IJ 3D Manager!`n`nPeça: $($impRow.nome_peca)`nPrints adicionados: $($copiedFiles.Count)",
            "IJ 3D Manager — Sucesso", "OK", "Information")
        Write-Host "✅ Exportação concluída!" -ForegroundColor Green
    } else {
        [System.Windows.Forms.MessageBox]::Show(
            "Erro ao salvar:`n$result",
            "IJ 3D Manager", "OK", "Error")
    }
} catch {
    [System.Windows.Forms.MessageBox]::Show(
        "Erro inesperado:`n$_",
        "IJ 3D Manager", "OK", "Error")
}
