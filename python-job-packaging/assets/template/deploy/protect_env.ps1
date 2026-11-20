<#
.SYNOPSIS
  限制 .env 的檔案權限：只有排程執行帳號（讀取）、Administrators 與 SYSTEM（完全控制）能存取。

.DESCRIPTION
  .env 內含資料庫密碼。移除繼承的權限後，一般使用者與其他程式都讀不到。
  以系統管理員身分執行。Administrators／SYSTEM 以 SID 指定，中文版 Windows 也適用。

  -RunAs 為 SYSTEM 或 Administrator 時，該帳號本來就有完全控制，不另外加讀取權限。

.EXAMPLE
  .\deploy\protect_env.ps1 -RunAs "SYSTEM"
  .\deploy\protect_env.ps1 -RunAs "DOMAIN\svc_account"
  .\deploy\protect_env.ps1 -RunAs "SYSTEM" -Path "E:\Jobs\{{app}}\.env"
#>
param(
    [Parameter(Mandatory = $true)][string]$RunAs,
    [string]$Path = (Join-Path (Split-Path $PSScriptRoot -Parent) ".env")
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $Path)) { throw "找不到 $Path，請先由 .env.example 複製並填寫" }

# *S-1-5-32-544 = Administrators、*S-1-5-18 = SYSTEM
$grants = @("*S-1-5-32-544:(F)", "*S-1-5-18:(F)")
$name = ($RunAs -split "\\")[-1]
if ($name -notin @("SYSTEM", "Administrator", "Administrators")) { $grants = @("${RunAs}:(R)") + $grants }
icacls $Path /inheritance:r /grant:r @grants | Out-Host
if ($LASTEXITCODE -ne 0) { throw "icacls 失敗（exit $LASTEXITCODE），請確認以系統管理員執行、帳號名稱 $RunAs 正確" }

Write-Host "`n目前權限："
icacls $Path | Out-Host
