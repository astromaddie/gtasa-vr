# Recovery when a third-party pack prevents reaching the in-game menu.
param([string]$WorkDir='C:\SAVRBuild', [string]$Adb, [string]$Serial)
$ErrorActionPreference='Stop'
if (-not $Adb) {
    $toolRoot = Join-Path $WorkDir '.tools'
    if (Test-Path -LiteralPath $toolRoot) {
        $hit = Get-ChildItem -LiteralPath $toolRoot -Recurse -Filter adb.exe -File | Select-Object -First 1
        if ($hit) { $Adb=$hit.FullName }
    }
    if (-not $Adb) { $hit=Get-Command adb.exe -ErrorAction SilentlyContinue; if ($hit) { $Adb=$hit.Source } }
}
if (-not $Adb) { throw 'adb missing. Run BUILD_AND_INSTALL first or pass -Adb.' }
if (-not $Serial) {
    $devices = @(& $Adb devices)
    if ($LASTEXITCODE -ne 0) { throw 'adb devices failed' }
    $ready=@($devices | Where-Object { $_ -match '^\S+\s+device$' } | ForEach-Object { ($_ -split '\s+')[0] })
    if ($ready.Count -ne 1) { throw 'Connect and authorize one Quest, or pass -Serial.' }
    $Serial=$ready[0]
}
function Invoke-Adb([string[]]$Arguments) {
    $result=& $Adb -s $Serial @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "adb failed: $($Arguments -join ' ')`n$($result -join "`n")" }
    return $result
}
$remote='/sdcard/Android/data/com.rockstargames.gtasa/files'
$backup=Join-Path $WorkDir ('optional-mods\disabled-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$settings=@(
    @{File='vr_modelsets.ini'; Keys=@('ProperFixes')},
    @{File='vr_graphics.ini'; Keys=@('HdWeapons')}
)
Invoke-Adb @('shell','am','force-stop','com.rockstargames.gtasa') | Out-Null
foreach ($item in $settings) {
    $file=$item.File
    $present=(Invoke-Adb @('shell',"if [ -f '$remote/$file' ]; then echo yes; else echo no; fi") | Out-String).Trim()
    if ($present -ne 'yes') { continue } # An absent file already means OFF.
    Invoke-Adb @('pull',"$remote/$file",(Join-Path $backup $file)) | Out-Null
    $original=Get-Content -LiteralPath (Join-Path $backup $file) -Raw
    $edited=$original
    foreach ($key in $item.Keys) {
        $pattern='(?m)^\s*' + [regex]::Escape($key) + '\s*=.*$'
        if ($edited -match $pattern) { $edited=[regex]::Replace($edited,$pattern,"$key=0") }
        else { $edited=$edited.TrimEnd("`r","`n") + "`n$key=0`n" }
    }
    $prepared=Join-Path $backup ($file+'.off')
    [IO.File]::WriteAllText($prepared,$edited,[Text.UTF8Encoding]::new($false))
    $item.Prepared=$prepared
}
foreach ($item in $settings) {
    if (-not $item.Prepared) { continue }
    $file=$item.File
    Invoke-Adb @('push',$item.Prepared,"$remote/$file.optional-off") | Out-Null
    Invoke-Adb @('shell',"chmod a+r '$remote/$file.optional-off' && mv '$remote/$file.optional-off' '$remote/$file'") | Out-Null
    $expected=(Get-FileHash -LiteralPath $item.Prepared -Algorithm SHA256).Hash
    $actual=(Invoke-Adb @('shell',"sha256sum '$remote/$file'") | Out-String).Trim().Split(' ')[0]
    if ($actual -ne $expected) { throw "Readback mismatch for $file" }
}
Write-Host 'Optional packs are OFF. Start GTA yourself. Assets and saves were not deleted.' -ForegroundColor Green
Write-Host "Settings backup: $backup"
