<#
.SYNOPSIS
  在「可連外網的 Windows 建置機」用 Nuitka 把 {{app}} 編譯成 {{app}}.exe，並打包成可離線部署的 zip。

.DESCRIPTION
  步驟：
    1. 找 Python（3.12 優先，3.11～3.13 64 位元皆可）
    2. 建立建置用 venv（.venv-build），安裝執行與建置套件，輸出 build-freeze.txt
    3. 以原始碼跑單元測試，失敗即中止
    4. Nuitka --mode=standalone 編譯（資料夾形式；不用 onefile，排程頻繁啟動時 onefile 每次解壓，慢且易被防毒攔截）
    5. 驗證編譯結果：--version、selfcheck（必要套件必須能載入）
    6. 打包 release\{{app}}_<版本>_<日期時間>.zip（含 exe、部署腳本、SQL、說明、SHA256）

  目標主機不需要 Python，也不需要編譯器。

.PARAMETER Python
  建置用 python.exe 的路徑。預設依序找 py -3.12-64、-3.13-64、-3.11-64、PATH 上的 python。

.PARAMETER OdbcMsi
  （選用）msodbcsql.msi 的路徑，提供時一併放進部署包的 prereq\。

.PARAMETER Proxy
  （選用）公司 Proxy，格式 主機:埠。只在本腳本下載套件與編譯器時使用，結束後還原。

.PARAMETER ProxyUser
  （選用）Proxy 需要驗證（407）時的帳號，例如 DOMAIN\user。密碼以隱藏輸入詢問，不寫入任何檔案。

.PARAMETER TrustPyPI
  （選用）Proxy 會攔截 HTTPS（SSL: CERTIFICATE_VERIFY_FAILED）時加上，等同 pip 的
  --trusted-host pypi.org files.pythonhosted.org pypi.python.org。

.PARAMETER Compiler
  C 編譯器：auto（預設）、msvc、mingw64、zig。
  auto：有 Visual Studio Build Tools（C++）就用 MSVC；沒有時 Python ≤ 3.12 改用 MinGW64，否則用 Zig。
  MinGW64／Zig 由 Nuitka 第一次建置時自動下載（會經過 -Proxy），之後放在快取不再下載。

.PARAMETER SkipTests
  略過單元測試（重跑且測試已通過時使用）。

.EXAMPLE
  cd <專案>
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\deploy\build_nuitka.ps1
  .\deploy\build_nuitka.ps1 -Proxy "proxy.corp.local:8080" -ProxyUser "DOMAIN\user" -TrustPyPI
  .\deploy\build_nuitka.ps1 -OdbcMsi "C:\Downloads\msodbcsql.msi"
#>
param(
    [string]$Python = "",
    [string]$OdbcMsi = "",
    [string]$Proxy = "",
    [string]$ProxyUser = "",
    [switch]$TrustPyPI,
    [ValidateSet("auto", "msvc", "mingw64", "zig")][string]$Compiler = "auto",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$App = "{{app}}"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

# ---------------------------------------------------------------------------
# 編譯時要明列的套件與模組。
# C／Cython 擴充在執行期才 import 的模組，Nuitka 靜態分析看不到，漏掉會在目標主機執行時才 ModuleNotFoundError。
# 新增套件時：先編譯，用編譯版實際跑 selfcheck --db 與 dryrun，缺什麼補什麼（規範 §8.2）。
# 不要列入 array、sys、time 等內建模組（會出現 is built-in 警告）。
$IncludePackages = @($App)
$IncludeModules  = @()
$VerifyPackages  = @()     # 編譯後 selfcheck 必須 [ OK ] 的套件（對應 selfcheck.py 的 REQUIRED_PACKAGES）
# {{#oracle}}
$IncludePackages += @("oracledb", "cryptography.hazmat.primitives", "cryptography.x509")
$IncludeModules  += @(
    "asyncio", "base64", "collections", "copy", "datetime", "decimal", "functools",
    "getpass", "hashlib", "inspect", "json", "locale", "os", "random", "re", "secrets",
    "select", "socket", "ssl", "string", "subprocess", "threading", "uuid", "warnings"
)
$VerifyPackages  += @("oracledb", "cryptography")
# {{/oracle}}
# {{#sqlserver}}
$IncludeModules  += @("pyodbc")
$VerifyPackages  += @("pyodbc")
# {{/sqlserver}}
# TODO(專案)：本程式另外用到的第三方套件加在這裡，例如 $IncludePackages += @("requests")
# ---------------------------------------------------------------------------

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Check-Exit($what) { if ($LASTEXITCODE -ne 0) { throw "$what 失敗（exit $LASTEXITCODE）" } }

# Proxy：只在下載時（pip、Nuitka）以環境變數帶給子程序，用完立即還原；不放在命令列（避免密碼出現在程序清單）
$ProxyUrl = ""
if ($Proxy) {
    $hostPort = $Proxy -replace "^https?://", ""
    if ($ProxyUser) {
        $sec = Read-Host "Proxy 密碼（$ProxyUser）" -AsSecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
        try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
        # 帳號、密碼含 \ @ : # 等字元時必須編碼
        $ProxyUrl = "http://{0}:{1}@{2}" -f [uri]::EscapeDataString($ProxyUser), [uri]::EscapeDataString($plain), $hostPort
        $plain = $null
    } else {
        $ProxyUrl = "http://$hostPort"
    }
    Write-Host ("Proxy：{0}{1}" -f $hostPort, $(if ($ProxyUser) { "（帳號 $ProxyUser）" } else { "" }))
}
# 一律用環境變數：pip 的 --proxy／--trusted-host 不會傳給「安裝建置相依」的子程序（nuitka 是原始碼套件，
# 安裝時 pip 會另開子程序下載 setuptools），環境變數則會被子程序繼承。PIP_PROXY 也蓋過 pip.ini 裡沒有帳密的 proxy。
function With-Proxy([scriptblock]$block) {
    $names = "HTTP_PROXY", "HTTPS_PROXY", "PIP_PROXY", "PIP_TRUSTED_HOST"
    $saved = @{}; foreach ($n in $names) { $saved[$n] = [Environment]::GetEnvironmentVariable($n, "Process") }
    if ($ProxyUrl) { $env:HTTP_PROXY = $ProxyUrl; $env:HTTPS_PROXY = $ProxyUrl; $env:PIP_PROXY = $ProxyUrl }
    if ($TrustPyPI) { $env:PIP_TRUSTED_HOST = "pypi.org files.pythonhosted.org pypi.python.org" }
    try { & $block } finally {
        foreach ($n in $names) { [Environment]::SetEnvironmentVariable($n, $saved[$n], "Process") }
    }
}
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

# ---------------------------------------------------------------------------
Step "1. 檢查 Python"
# 外部程式寫 stderr 時，Windows PowerShell 5.1 在 Stop 模式下會直接中止，所以找 Python 時暫時改為 Continue
function Try-Python([string[]]$cmd) {
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    try {
        $exe = $cmd[0]; $rest = @($cmd | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { return $null }
        $out = & $exe @rest -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return ($out | Select-Object -First 1).Trim() }
    } catch { } finally { $ErrorActionPreference = $old }
    return $null
}
if (-not $Python) {
    foreach ($c in @("py -3.12-64", "py -3.13-64", "py -3.11-64", "python")) {
        $Python = Try-Python ($c -split " ")
        if ($Python) { break }
    }
    if (-not $Python) { throw "找不到 Python（3.11～3.13 64 位元），請安裝或以 -Python 指定 python.exe 路徑" }
}
# 注意：Windows PowerShell 5.1 傳給外部程式的參數會吃掉雙引號，python -c 內只用單引號
$info = & $Python -c "import sys, struct; print(sys.version_info[0], sys.version_info[1], struct.calcsize('P') * 8)"
Check-Exit "執行 Python"
$parts = "$info".Trim() -split " "
if ($parts[0] -ne "3" -or [int]$parts[1] -lt 11 -or [int]$parts[1] -gt 13 -or $parts[2] -ne "64") {
    throw "需要 Python 3.11～3.13 64 位元，目前為 $info（$Python）"
}
if ($parts[1] -ne "12") { Write-Host "注意：建議 3.12，目前為 3.$($parts[1])，仍可建置" -ForegroundColor Yellow }
Write-Host "Python：$Python（$info）"

$Version = (& $Python -c "import $App; print($App.__version__)")
Check-Exit "讀取版本"
$Stamp = Get-Date -Format "yyyyMMdd_HHmm"
Write-Host "版本：$Version"

# ---------------------------------------------------------------------------
Step "2. 建置用 venv"
$Venv = Join-Path $Root ".venv-build"
if (-not (Test-Path $Venv)) { & $Python -m venv $Venv; Check-Exit "建立 venv" }
$Py = Join-Path $Venv "Scripts\python.exe"
With-Proxy {
    & $Py -m pip install --upgrade pip --quiet
    if ($LASTEXITCODE -ne 0) { Write-Host "升級 pip 失敗，沿用現有版本繼續" -ForegroundColor Yellow }
    & $Py -m pip install -r requirements.txt -r requirements-build.txt --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "安裝套件失敗（exit $LASTEXITCODE）。若訊息有 407／ProxyError，請加 -Proxy 主機:埠 -ProxyUser 帳號 重跑"
    }
}
& $Py -m pip freeze | Out-File -Encoding utf8 (Join-Path $Root "build-freeze.txt")

# ---------------------------------------------------------------------------
if (-not $SkipTests) {
    Step "3. 單元測試（原始碼）"
    & $Py -m unittest discover -s tests -t .; Check-Exit "單元測試"
}

# ---------------------------------------------------------------------------
Step "4. Nuitka 編譯"
if ($Compiler -eq "auto") {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    $vs = $null
    if (Test-Path $vswhere) {
        $vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    }
    if ($vs) { $Compiler = "msvc" }
    elseif ([int]$parts[1] -le 12) { $Compiler = "mingw64" }
    else { $Compiler = "zig" }
    if ($Compiler -ne "msvc") {
        Write-Host "找不到 Visual Studio Build Tools（C++），改用 $Compiler（Nuitka 會自動下載）" -ForegroundColor Yellow
    }
}
Write-Host "C 編譯器：$Compiler"

$BuildDir = Join-Path $Root "build"
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }

$FileVersion = (($Version -split "\.") + @("0", "0", "0", "0"))[0..3] -join "."
$nuitkaArgs = @(
    "-m", "nuitka",
    "--mode=standalone",
    $(if ($Compiler -eq "msvc") { "--msvc=latest" } else { "--$Compiler" }),
    "--assume-yes-for-downloads",
    "--output-dir=$BuildDir",
    "--output-filename=$App.exe",
    "--windows-console-mode=force",
    "--company-name={{company}}",
    "--product-name=$App",
    "--file-description={{description}}",
    "--file-version=$FileVersion",
    "--product-version=$FileVersion",
    "--report=$BuildDir\nuitka-report.xml"
)
$nuitkaArgs += $IncludePackages | ForEach-Object { "--include-package=$_" }
$nuitkaArgs += $IncludeModules  | ForEach-Object { "--include-module=$_" }
$nuitkaArgs += "run_$App.py"

With-Proxy { & $Py @nuitkaArgs }; Check-Exit "Nuitka 編譯"
$Dist = Join-Path $BuildDir "run_$App.dist"
$Exe = Join-Path $Dist "$App.exe"
if (-not (Test-Path $Exe)) { throw "找不到編譯結果 $Exe" }

# ---------------------------------------------------------------------------
Step "5. 驗證編譯結果"
$v = & $Exe --version; Check-Exit "$App.exe --version"
if ($v -ne "$App $Version") { throw "版本不符：$v" }
Write-Host $v

# selfcheck 不帶 --db：只驗證套件。建置機若沒裝 ODBC Driver，該項 FAIL 可忽略（FAQ B14）。
$out = & $Exe selfcheck 2>&1 | Out-String
Write-Host $out
foreach ($pkg in $VerifyPackages) {
    if ($out -match "\[FAIL\] $([regex]::Escape($pkg))") {
        throw "編譯版無法載入 $pkg，請把缺少的模組加入 `$IncludeModules／`$IncludePackages 後重建（查 build\nuitka-report.xml）"
    }
}

# ---------------------------------------------------------------------------
Step "6. 打包"
$Name = "${App}_${Version}_$Stamp"
$Release = Join-Path $Root "release\$Name"
New-Item -ItemType Directory -Force -Path $Release | Out-Null

Copy-Item -Recurse $Dist (Join-Path $Release "app")
New-Item -ItemType Directory -Force -Path (Join-Path $Release "deploy") | Out-Null
Copy-Item (Join-Path $Root "deploy\*.ps1") (Join-Path $Release "deploy")
Copy-Item (Join-Path $Root "deploy\README.md") (Join-Path $Release "README_DEPLOY.md")
if (Test-Path (Join-Path $Root "sql")) { Copy-Item -Recurse (Join-Path $Root "sql") (Join-Path $Release "sql") }
Copy-Item (Join-Path $Root "build-freeze.txt") (Join-Path $Release "build-freeze.txt")
Copy-Item (Join-Path $Root ".env.example") (Join-Path $Release ".env.example")
if ($OdbcMsi) {
    if (-not (Test-Path $OdbcMsi)) { throw "找不到 $OdbcMsi" }
    New-Item -ItemType Directory -Force -Path (Join-Path $Release "prereq") | Out-Null
    Copy-Item $OdbcMsi (Join-Path $Release "prereq\msodbcsql.msi")
}

@"
$App $Version
建置時間：$(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
建置機：$env:COMPUTERNAME
Python：$info
C 編譯器：$Compiler
"@ | Out-File -Encoding utf8 (Join-Path $Release "VERSION.txt")

Get-ChildItem -Recurse -File $Release |
    ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash, $_.FullName.Substring($Release.Length + 1) } |
    Out-File -Encoding utf8 (Join-Path $Release "SHA256SUMS.txt")

$Zip = "$Release.zip"
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path "$Release\*" -DestinationPath $Zip
$ZipHash = (Get-FileHash $Zip -Algorithm SHA256).Hash
"$ZipHash  $Name.zip" | Out-File -Encoding ascii "$Zip.sha256"

Write-Host "`n完成：$Zip" -ForegroundColor Green
Write-Host ("大小：{0:N1} MB" -f ((Get-Item $Zip).Length / 1MB))
Write-Host "SHA256：$ZipHash（另存於 $Name.zip.sha256，目標主機以 Get-FileHash 核對）"
Write-Host "下一步：先用編譯版跑 selfcheck --db 與 dryrun（規範階段 2），再把 zip 複製到目標主機，依 README_DEPLOY.md 安裝。"
