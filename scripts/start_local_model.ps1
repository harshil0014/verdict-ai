$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $projectPath 'runtime\local-model\worker.json'
$workerPath = Join-Path $PSScriptRoot 'ollama_worker.py'
$pythonPath = Join-Path $projectPath 'backend\.venv\Scripts\pythonw.exe'
if (!(Test-Path -LiteralPath $configPath) -or !(Test-Path -LiteralPath $pythonPath)) {
    throw 'The private local-model configuration and worker environment must be installed first.'
}
$existingWorker = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'pythonw.exe' -and $_.CommandLine -and $_.CommandLine.Contains($workerPath) -and $_.CommandLine.Contains($configPath)
} | Select-Object -First 1
if ($existingWorker) { return }
try {
    Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 3 -UseBasicParsing | Out-Null
} catch {
    $ollamaExecutable = (Get-Command ollama -ErrorAction Stop).Source
    $previousHost = $env:OLLAMA_HOST
    try {
        $env:OLLAMA_HOST = '127.0.0.1:11434'
        Start-Process -FilePath $ollamaExecutable -ArgumentList 'serve' -WindowStyle Hidden | Out-Null
    } finally { $env:OLLAMA_HOST = $previousHost }
}
$workerProcess = Start-Process -FilePath $pythonPath -ArgumentList @("`"$workerPath`"", '--config', "`"$configPath`"") -WindowStyle Hidden -PassThru
$workerProcess.Id | Set-Content -LiteralPath (Join-Path $projectPath 'runtime\local-model\worker.pid')
