param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dataDir = Join-Path $projectRoot ".local-data"
$runDir = Join-Path $dataDir "run"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

function Test-Url([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

$apiUrl = "http://127.0.0.1:$ApiPort/api/v1/health"
$apiBaseUrl = "http://127.0.0.1:$ApiPort"
$webUrl = "http://127.0.0.1:$WebPort/"

if (-not (Test-Url $apiUrl)) {
    $apiLog = Join-Path $dataDir "api.log"
    $apiErrorLog = Join-Path $dataDir "api-error.log"
    $api = Start-Process -FilePath "py" -ArgumentList @(
        "-3.12", "-m", "uvicorn", "kongpu_api.main:app",
        "--host", "127.0.0.1", "--port", $ApiPort
    ) -WorkingDirectory (Join-Path $projectRoot "services\api") -WindowStyle Hidden -PassThru -RedirectStandardOutput $apiLog -RedirectStandardError $apiErrorLog
    Set-Content -LiteralPath (Join-Path $runDir "api.pid") -Value $api.Id
}

if (-not (Test-Url $webUrl)) {
    $webLog = Join-Path $dataDir "web.log"
    $webErrorLog = Join-Path $dataDir "web-error.log"
    $env:KONGPU_API_TARGET = $apiBaseUrl
    $web = Start-Process -FilePath "npm.cmd" -ArgumentList @(
        "run", "dev", "--", "--host", "127.0.0.1", "--port", $WebPort
    ) -WorkingDirectory (Join-Path $projectRoot "kongpu-demo") -WindowStyle Hidden -PassThru -RedirectStandardOutput $webLog -RedirectStandardError $webErrorLog
    Set-Content -LiteralPath (Join-Path $runDir "web.pid") -Value $web.Id
}

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ((Test-Url $apiUrl) -and (Test-Url $webUrl)) {
        $projects = @(Invoke-RestMethod -Uri "$apiBaseUrl/api/v1/projects?include_archived=true" -TimeoutSec 5)
        if ($projects.Count -eq 0) {
            & py -3.12 (Join-Path $projectRoot "scripts\seed-demo.py") --base-url $apiBaseUrl
            if ($LASTEXITCODE -ne 0) {
                throw "Demo seed failed. Check API logs before continuing."
            }
        }
        Write-Output "Web: $webUrl"
        Write-Output "API: http://127.0.0.1:$ApiPort"
        Write-Output "Docs: http://127.0.0.1:$ApiPort/docs"
        exit 0
    }
    Start-Sleep -Milliseconds 500
}

throw "Services did not become ready within 15 seconds. Check .local-data/api-error.log and .local-data/web-error.log."
