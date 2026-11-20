<#
.SYNOPSIS
  上線前檢查（唯讀）：網路連線、時間同步、設定來源與 .env 權限、執行檔與套件、資料庫連線。

.DESCRIPTION
  以系統管理員或排程執行帳號執行皆可。不會寫入任何資料，也不會顯示密碼內容。
  執行檔自動判斷：<InstallDir>\app\{{app}}.exe（Nuitka 版）優先，否則用 .venv（原始碼版）。

.PARAMETER TimeServer
  （選用）要比對時間的主機（例如上下游系統所在主機）；差距應 < 5 秒。

.EXAMPLE
  .\deploy\preflight.ps1
  .\deploy\preflight.ps1 -TimeServer upstream-host
#>
param(
# {{#sqlserver}}
    [string]$SqlHost = "",                 # 不填時從 .env 的 {{PREFIX}}_SQL_SERVER 推得
    [int]$SqlPort = 1433,
# {{/sqlserver}}
# {{#oracle}}
    [string]$OraHost = "",                 # 不填時從 .env 的 {{PREFIX}}_ORA_DSN 推得
    [int]$OraPort = 1521,
# {{/oracle}}
    [string]$TimeServer = "",
    [string]$InstallDir = (Split-Path $PSScriptRoot -Parent)
)

function Show($ok, $msg) {
    if ($ok) { Write-Host "[ OK ] $msg" -ForegroundColor Green }
    else     { Write-Host "[FAIL] $msg" -ForegroundColor Red }
}
function Test-Port([string]$h, [int]$p, [string]$label) {
    if (-not $h) { Write-Host "[WARN] $label：未提供主機，略過" -ForegroundColor Yellow; return }
    Show (Test-NetConnection $h -Port $p -WarningAction SilentlyContinue).TcpTestSucceeded "$label ${h}:$p"
}

$envFile = Join-Path $InstallDir ".env"
function Get-EnvValue([string]$key) {
    $v = [Environment]::GetEnvironmentVariable($key, "Machine")
    if ($v) { return $v }
    if (Test-Path $envFile) {
        $m = Select-String -Path $envFile -Pattern ("^\s*{0}\s*=\s*(.*)$" -f [regex]::Escape($key)) | Select-Object -First 1
        if ($m) { return $m.Matches[0].Groups[1].Value.Trim().Trim('"') }
    }
    return ""
}

Write-Host "== 1. 網路 =="
# {{#sqlserver}}
if (-not $SqlHost) {
    $server = (Get-EnvValue "{{PREFIX}}_SQL_SERVER") -replace "^tcp:", ""
    $SqlHost = ($server -split ",")[0] -replace "\\.*$", ""
    if ($server -match ",(\d+)") { $SqlPort = [int]$Matches[1] }
}
Test-Port $SqlHost $SqlPort "SQL Server"
# {{/sqlserver}}
# {{#oracle}}
if (-not $OraHost) {
    $dsn = Get-EnvValue "{{PREFIX}}_ORA_DSN"
    if ($dsn -match "^([^:/]+)(:(\d+))?") { $OraHost = $Matches[1]; if ($Matches[3]) { $OraPort = [int]$Matches[3] } }
}
Test-Port $OraHost $OraPort "Oracle"
# {{/oracle}}

Write-Host "`n== 2. 時間同步（與相關主機差距應 < 5 秒）=="
w32tm /query /status | Select-String "Source|Last Successful Sync Time|上次成功同步|來源"
if ($TimeServer) {
    Write-Host "與 $TimeServer 的時間差（o: 後的值，單位秒）："
    w32tm /stripchart /computer:$TimeServer /samples:3 /dataonly
}

Write-Host "`n== 3. 設定來源 =="
if (Test-Path $envFile) {
    Show $true ".env：$envFile（已設定的環境變數優先於 .env）"
    $acl = (icacls $envFile) -join "`n"
    if ($acl -match "Users|BUILTIN\\使用者|Everyone|Authenticated Users|\(I\)") {
        Show $false ".env 權限過寬（含一般使用者或繼承權限），請執行 deploy\protect_env.ps1 -RunAs ""SYSTEM"""
    } else {
        Show $true ".env 權限已限制"
    }
    Write-Host $acl
} else {
    Show $false "找不到 $envFile（請由 .env.example 複製並填寫）"
}
$machine = [Environment]::GetEnvironmentVariables("Machine").Keys | Where-Object { $_ -like "{{PREFIX}}_*" } | Sort-Object
if ($machine) {
    Write-Host "注意：以下機器層級環境變數會蓋過 .env：" -ForegroundColor Yellow
    foreach ($k in $machine) {
        $v = if ($k -like "*PASSWORD*") { "（已設定，不顯示）" } else { [Environment]::GetEnvironmentVariable($k, "Machine") }
        Write-Host ("  {0} = {1}" -f $k, $v)
    }
}

Write-Host "`n== 4. 執行檔、套件、資料庫連線（selfcheck --db）=="
$exe    = Join-Path $InstallDir "app\{{app}}.exe"
$python = Join-Path $InstallDir ".venv\Scripts\python.exe"
Push-Location $InstallDir
try {
    if (Test-Path $exe) {
        Show $true "Nuitka 版：$exe"
        & $exe selfcheck --db
        Show ($LASTEXITCODE -eq 0) "selfcheck --db 結束碼 $LASTEXITCODE"
    } elseif (Test-Path $python) {
        Show $true "原始碼版：$python"
        & $python -m {{app}} selfcheck --db
        Show ($LASTEXITCODE -eq 0) "selfcheck --db 結束碼 $LASTEXITCODE"
    } else {
        Show $false "在 $InstallDir 找不到 app\{{app}}.exe 或 .venv"
    }
} finally { Pop-Location }

Write-Host "`n下一步：dryrun（唯讀，不寫入），連續 2～3 輪確認 errors=0"
Write-Host ("  cd {0}; .\app\{{app}}.exe dryrun" -f $InstallDir)
