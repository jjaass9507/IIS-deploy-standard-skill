<#
.SYNOPSIS
  建立（或更新）{{app}} 的 Windows 工作排程（規範 §10）。

.DESCRIPTION
  - 預設以 SYSTEM 執行：不需密碼、不會過期；資料庫以 .env 的資料庫帳號連線，不受影響
  - 上一輪還在執行時不啟動新的一輪（MultipleInstances IgnoreNew）
  - 執行時間上限必須小於排程間隔（卡住的程序不拖到下一輪）
  - 錯過的排程不補跑（以 run --cycle 等方式手動補跑）
  - 起始目錄為安裝目錄，exe 依此找到 .env

  執行檔自動判斷：<InstallDir>\app\{{app}}.exe（Nuitka 版）優先，
  否則用 <InstallDir>\.venv\Scripts\python.exe -m {{app}}（原始碼版）。

.PARAMETER RunAs
  執行帳號。建議 "SYSTEM"。需要存取網路共用資料夾或以 Windows 整合驗證連資料庫時，改用網域服務帳號
  （需「以批次工作登入」權限，執行時會跳出視窗輸入密碼；該帳號改密碼後必須重跑本腳本）。

.PARAMETER IntervalMinutes
  每幾分鐘執行一次。設 0 表示每天執行一次（於 -At 時間）。

.PARAMETER At
  第一次觸發的時間（HH:mm:ss）。每 N 分鐘執行時，之後依間隔重複；每天執行時為每天的執行時間。
  若下游會讀取本程式的結果，請排在下游起跑之前並留緩衝。

.PARAMETER TimeLimitMinutes
  單次執行時間上限（分鐘）。0 = 自動：間隔 - 1 分鐘（每天執行時 60 分鐘）。必須小於間隔。

.EXAMPLE
  .\deploy\register_task.ps1 -RunAs "SYSTEM"
  .\deploy\register_task.ps1 -RunAs "SYSTEM" -IntervalMinutes 15 -At "00:02:00"
  .\deploy\register_task.ps1 -RunAs "SYSTEM" -IntervalMinutes 0 -At "06:30:00" -TimeLimitMinutes 30
#>
param(
    [Parameter(Mandatory = $true)][string]$RunAs,
    [string]$TaskName         = "{{TaskName}}",
    [string]$InstallDir       = (Split-Path $PSScriptRoot -Parent),
    [string]$Arguments        = "run",
    [int]$IntervalMinutes     = 5,         # TODO(專案)：依業務需求設定預設頻率
    [string]$At               = "00:00:00",
    [int]$TimeLimitMinutes    = 0
)

$ErrorActionPreference = "Stop"

if ($IntervalMinutes -lt 0) { throw "-IntervalMinutes 不可小於 0" }
if ($TimeLimitMinutes -le 0) {
    $TimeLimitMinutes = if ($IntervalMinutes -gt 1) { $IntervalMinutes - 1 } elseif ($IntervalMinutes -eq 1) { 1 } else { 60 }
}
if ($IntervalMinutes -gt 1 -and $TimeLimitMinutes -ge $IntervalMinutes) {
    throw "-TimeLimitMinutes（$TimeLimitMinutes）必須小於 -IntervalMinutes（$IntervalMinutes），否則卡住的程序會拖到下一輪"
}

$exe    = Join-Path $InstallDir "app\{{app}}.exe"
$python = Join-Path $InstallDir ".venv\Scripts\python.exe"
if (Test-Path $exe) {
    $action = New-ScheduledTaskAction -Execute $exe -Argument $Arguments -WorkingDirectory $InstallDir
    Write-Host "執行檔：$exe $Arguments"
} elseif (Test-Path $python) {
    $action = New-ScheduledTaskAction -Execute $python -Argument "-m {{app}} $Arguments" -WorkingDirectory $InstallDir
    Write-Host "執行檔：$python -m {{app}} $Arguments"
} else {
    throw "在 $InstallDir 找不到 app\{{app}}.exe 或 .venv，請先依部署說明安裝"
}

$envFile = Join-Path $InstallDir ".env"
if (Test-Path $envFile) {
    Write-Host "設定來源：$envFile"
} else {
    throw "找不到 $envFile：請由 .env.example 複製並填寫，再執行 deploy\protect_env.ps1"
}

if ($IntervalMinutes -gt 0) {
    # 不指定 RepetitionDuration = 無限期重複（Windows Server 2016 以上）
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date $At) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
    $when = "每 $IntervalMinutes 分鐘（首次 $At）"
} else {
    $trigger = New-ScheduledTaskTrigger -Daily -At (Get-Date $At)
    $when = "每天 $At"
}

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes $TimeLimitMinutes) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

$desc = "{{description}}。$when，執行上限 $TimeLimitMinutes 分鐘。安裝目錄 $InstallDir"
if ((($RunAs -split "\\")[-1]) -eq "SYSTEM") {
    $principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal -Description $desc -Force | Out-Null
} else {
    $cred = Get-Credential -UserName $RunAs -Message "輸入排程執行帳號 $RunAs 的密碼"
    if (-not $cred) { throw "已取消，未建立排程" }
    Register-ScheduledTask -TaskName $TaskName `
        -Action $action -Trigger $trigger -Settings $settings `
        -User $cred.UserName -Password $cred.GetNetworkCredential().Password `
        -RunLevel Limited -Description $desc -Force | Out-Null
}

Write-Host "已建立工作排程 $TaskName（執行帳號 $RunAs，$when，執行上限 $TimeLimitMinutes 分鐘）"
Write-Host "確認：Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo"
Write-Host "停用：Disable-ScheduledTask -TaskName $TaskName"
