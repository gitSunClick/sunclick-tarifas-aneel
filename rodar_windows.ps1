# rodar_windows.ps1
# Roda os passos do README na ordem certa, direto no PowerShell.
# Uso: abra o PowerShell nesta pasta e rode:  .\rodar_windows.ps1
#
# Se der erro de "não é possível carregar o arquivo ... políticas de
# execução", rode isto uma vez (como Administrador) e tente de novo:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

$ErrorActionPreference = "Stop"

Write-Host "== 0. Instalando dependências ==" -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host "`n== 1. Descobrindo os códigos SigAgente reais ==" -ForegroundColor Cyan
Write-Host "Isso baixa a base oficial da ANEEL (pode demorar na 1a vez)." -ForegroundColor DarkGray
python descobrir_sigagente.py

Write-Host "`nAgora abra config.py, confira as sugestões acima e preencha o campo" -ForegroundColor Yellow
Write-Host "'sig_agente' de cada distribuidora (pelo menos a CEEE-RS pra seguir)." -ForegroundColor Yellow
$continuar = Read-Host "`nJá preencheu o sig_agente da CEEE-RS em config.py? (s/n)"
if ($continuar -ne "s") {
    Write-Host "OK, edite config.py e rode este script de novo." -ForegroundColor Yellow
    exit 0
}

Write-Host "`n== 2. Validando contra o valor de controle (CEEE-RS) ==" -ForegroundColor Cyan
python validar_controle.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nValidação FALHOU — pare aqui e investigue antes de continuar." -ForegroundColor Red
    exit 1
}

Write-Host "`n== 3. Configurando credenciais do Google Sheets ==" -ForegroundColor Cyan
$env:GOOGLE_SERVICE_ACCOUNT_FILE = Read-Host "Caminho do service_account.json (Enter = pasta atual\service_account.json)"
if ([string]::IsNullOrWhiteSpace($env:GOOGLE_SERVICE_ACCOUNT_FILE)) {
    $env:GOOGLE_SERVICE_ACCOUNT_FILE = Join-Path (Get-Location) "service_account.json"
}
$env:GOOGLE_SHEET_ID = Read-Host "ID da planilha do Google Sheets"
$env:GOOGLE_WORKSHEET = Read-Host "Nome exato da aba"

Write-Host "`n== 4. Rodando em DRY RUN (preview, nada é gravado ainda) ==" -ForegroundColor Cyan
$env:DRY_RUN = "true"
python atualizar_google_sheets.py

$gravar = Read-Host "`nO preview acima está correto? Gravar de verdade na planilha? (s/n)"
if ($gravar -eq "s") {
    Write-Host "`n== 5. Gravando na planilha ==" -ForegroundColor Cyan
    $env:DRY_RUN = "false"
    python atualizar_google_sheets.py
} else {
    Write-Host "Nada foi gravado. Ajuste o que precisar e rode de novo." -ForegroundColor Yellow
}
