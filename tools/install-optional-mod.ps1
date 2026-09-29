# Player-owned packs stay outside the APK and outside the original game files.
param(
    [Parameter(Mandatory=$true)][ValidateSet('properfixes')][string]$Kind,
    [string]$Archive,
    [string]$WorkDir = 'C:\SAVRBuild',
    [string]$Serial,
    [string]$Python,
    [string]$Adb,
    [string]$PreparedPayload,
    [switch]$PrepareOnly
)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
function Find-Tool([string]$Name) {
    foreach ($base in @((Join-Path $WorkDir '.tools'), (Join-Path $WorkDir '.downloads'))) {
        if (Test-Path -LiteralPath $base) {
            $hit = Get-ChildItem -LiteralPath $base -Recurse -Filter $Name -File | Select-Object -First 1
            if ($hit) { return $hit.FullName }
        }
    }
    $hit = Get-Command $Name -ErrorAction SilentlyContinue
    if ($hit) { return $hit.Source }
    return $null
}
$Stage = Join-Path $WorkDir ('optional-mods\' + $Kind + '-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Stage -Force | Out-Null
if ($PreparedPayload) {
    $Payload = (Resolve-Path -LiteralPath $PreparedPayload).Path
} else {
  if (-not $Python) { $Python = Find-Tool 'python.exe' }
  if (-not $Python) { throw 'Python missing. Run BUILD_AND_INSTALL.bat first.' }
  if (-not $Archive) {
    Write-Host "Drag your downloaded $Kind archive (or extracted folder) here."
    $Archive = (Read-Host 'Pack').Trim().Trim('"')

  }
  if (-not (Test-Path -LiteralPath $Archive)) { throw "Pack not found: $Archive" }
  $Archive = (Resolve-Path -LiteralPath $Archive).Path
  $PackRoot = $Archive
  if (-not (Test-Path -LiteralPath $Archive -PathType Container)) {
    $Extract = Join-Path $Stage 'extracted'
    New-Item -ItemType Directory -Path $Extract | Out-Null
    $tar = Find-Tool 'tar.exe'
    if (-not $tar) {
        throw 'Windows tar.exe is unavailable. Extract the archive and drag its folder into this installer.'
    }
    $entries = @(& $tar -tf $Archive)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read archive. Extract it with 7-Zip and use the extracted folder.' }
    foreach ($name in $entries) {
        $normalized = $name.Replace('\','/')
        if ($normalized -match '(^/|^[A-Za-z]:|(^|/)\.\.(/|$))') { throw "Unsafe archive path: $name" }
    }
    & $tar -xf $Archive -C $Extract
    if ($LASTEXITCODE -ne 0) { throw 'Archive extraction failed.' }
    $PackRoot = $Extract
  }
  $Payload = Join-Path $Stage 'payload'
  & $Python -X utf8 (Join-Path $RepoRoot 'tools\build_optional_mods.py') $Kind $PackRoot --out $Payload
  if ($LASTEXITCODE -ne 0) { throw 'Pack validation/conversion failed. Nothing was installed.' }
}
$Report = Get-Content -LiteralPath (Join-Path $Payload 'install.json') -Raw | ConvertFrom-Json
if ($Report.generation -notmatch '^[0-9a-f]{24}$' -or $Report.kind -ne $Kind) { throw 'Invalid build report' }
$expectedSums = @()
foreach ($record in $Report.files) {
    if ($record.path -notmatch '^[a-z0-9_./-]+$' -or $record.path -match '(^/|(^|/)\.\.?(/|$)|//)' -or
        $record.sha256 -notmatch '^[0-9a-f]{64}$') { throw 'Unsafe payload manifest entry' }
    $file = Join-Path $Payload $record.path
    if ((Get-Item -LiteralPath $file).Length -ne $record.size -or
        (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $record.sha256) { throw "Payload changed: $($record.path)" }
    $expectedSums += "$($record.sha256)  $($record.path)"
}
if (($expectedSums -join "`n") -ne (Get-Content -LiteralPath (Join-Path $Payload 'SHA256SUMS') -Raw).TrimEnd("`r","`n")) {
    throw 'SHA256SUMS does not match the checked install report'
}
Write-Host "Prepared: $Payload"
if ($PrepareOnly) { return }
if (-not $Adb) { $Adb = Find-Tool 'adb.exe' }
if (-not $Adb) { throw 'adb missing. Run BUILD_AND_INSTALL.bat first or pass -Adb.' }
if (-not $Serial) {
    $devices = @(& $Adb devices)
    if ($LASTEXITCODE -ne 0) { throw 'adb devices failed' }
    $ready = @($devices | Where-Object { $_ -match '^\S+\s+device$' } | ForEach-Object { ($_ -split '\s+')[0] })
    if ($ready.Count -ne 1) { throw 'Connect and authorize one Quest, or pass -Serial for the desired headset.' }
    $Serial = $ready[0]
}
function Invoke-Adb([string[]]$Arguments) {
    # Windows PowerShell 5 wraps ordinary native stderr progress in error
    # records. The native exit code, not the presence of stderr, decides success.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $result = & $Adb -s $Serial @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    $lines = @($result | ForEach-Object { $_.ToString() })
    if ($exitCode -ne 0) { throw "adb failed: $($Arguments -join ' ')`n$($lines -join "`n")" }
    return $lines
}
$packagePaths = Invoke-Adb @('shell','pm','path','com.rockstargames.gtasa')
if (-not ($packagePaths -match '^package:')) { throw 'GTA SA VR must be installed first.' }
$remote = '/sdcard/Android/data/com.rockstargames.gtasa/files/optionalmods/' + $Kind
$generation = $Report.generation
$version = "$remote/$generation"
$incoming = "$remote/incoming-" + [guid]::NewGuid().ToString('N')
$locked = $false
try {
    Invoke-Adb @('shell',"mkdir -p '$remote' && mkdir '$remote/install-lock'") | Out-Null
    $locked = $true
    Invoke-Adb @('shell',"chmod a+rx '/sdcard/Android/data/com.rockstargames.gtasa/files/optionalmods' '$remote'") | Out-Null
    $exists = (Invoke-Adb @('shell',"if [ -d '$version' ]; then echo yes; else echo no; fi") | Out-String).Trim()
    if ($exists -ne 'yes') {
        Write-Host 'Copying the optional pack to Quest...'
        # Quest scoped storage can allow shell mkdir but reject adb sync's
        # secure_mkdirs. Create the full directory tree through the shell first.
        $directories = @($incoming)
        foreach ($record in $Report.files) {
            if ($record.path.Contains('/')) { $directories += "$incoming/" + $record.path.Substring(0,$record.path.LastIndexOf('/')) }
        }
        foreach ($dir in ($directories | Sort-Object -Unique)) {
            Invoke-Adb @('shell',"mkdir -p '$dir'") | Out-Null
        }
        Invoke-Adb @('push',($Payload + '\.'),($incoming + '/')) | Write-Host
        Invoke-Adb @('shell',"chmod -R a+rX '$incoming'") | Out-Null
        $verified = Invoke-Adb @('shell',"cd '$incoming' && sha256sum -c SHA256SUMS")
        $verified | Set-Content -LiteralPath (Join-Path $Stage 'device-sha256.txt') -Encoding UTF8
        Invoke-Adb @('shell',"mv '$incoming' '$version'") | Out-Null
    } else {
        # Never overwrite a generation: a running session may still read it.
        $deviceSums = (Invoke-Adb @('shell',"cat '$version/SHA256SUMS'") | Out-String).TrimEnd("`r","`n").Replace("`r`n","`n")
        if ($deviceSums -ne ($expectedSums -join "`n")) { throw 'Installed generation manifest differs; refusing to overwrite it.' }
        $verified = Invoke-Adb @('shell',"cd '$version' && sha256sum -c SHA256SUMS")
        $verified | Set-Content -LiteralPath (Join-Path $Stage 'device-sha256.txt') -Encoding UTF8
    }
    $active = Join-Path $Stage 'active.txt'
    [IO.File]::WriteAllText($active, "$generation`n", [Text.Encoding]::ASCII)
    Invoke-Adb @('push',$active,"$remote/active.next") | Out-Null
    Invoke-Adb @('shell',"chmod a+r '$remote/active.next' && mv '$remote/active.next' '$remote/active.txt'") | Out-Null
    $readback = (Invoke-Adb @('shell',"cat '$remote/active.txt'") | Out-String).Trim()
    if ($readback -ne $generation) { throw 'Active generation readback mismatch' }
    Write-Host 'Installed and SHA-256 verified. Original game files and settings are unchanged.' -ForegroundColor Green
    Write-Host 'Restart GTA, open VR MENU > MODEL SET, select ON, then fully restart GTA again.'
    Write-Host 'To restore the original assets: choose OFF and fully restart GTA. No reinstall is needed.'
    Write-Host "Verification report: $Stage"
} finally {
    if ($locked) { Invoke-Adb @('shell',"rmdir '$remote/install-lock'") | Out-Null }
}
