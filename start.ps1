$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Wenn keine .env existiert, kopiere .env.example -> .env
if (-not (Test-Path ".\.env") -and (Test-Path ".\.env.example")) {
  Copy-Item ".\.env.example" ".\.env"
  Write-Host "Created .env from .env.example"
}

Write-Host "Starting containers..."
docker compose up -d --pull always

# OLLAMA_MODEL aus .env lesen (einfacher Parser)
$ollamaModel = "llama3.1:latest"
if (Test-Path ".\.env") {
  Get-Content ".\.env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
      $k, $v = $line.Split("=", 2)
      if ($k.Trim() -eq "OLLAMA_MODEL") { $ollamaModel = $v.Trim() }
    }
  }
}

Write-Host "Pulling Ollama model: $ollamaModel"
docker compose exec -T ollama ollama pull $ollamaModel

Write-Host ""
Write-Host "Open WebUI: http://localhost:3000"
Write-Host "Done."
