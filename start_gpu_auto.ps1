# Start Ollama with GPU if available; otherwise fall back to CPU.
# Does not modify your existing docker-compose.yml. Uses docker-compose.gpu.yml as an override.
# Requirements for GPU mode: NVIDIA GPU + NVIDIA Container Toolkit configured for Docker.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Start-CPU {
  Write-Host "Starting CPU mode (default compose)..." -ForegroundColor Cyan
  docker compose -f docker-compose.yml up -d --build
}

function Try-Start-GPU {
  Write-Host "Trying GPU mode (compose override)..." -ForegroundColor Cyan
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
}

function Cleanup-GPU {
  try {
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml down | Out-Null
  } catch {
    # ignore
  }
}

# Quick GPU sanity check using NVIDIA Container Toolkit sample approach
# If this fails, we skip GPU mode and start CPU mode.
$gpuOk = $false
try {
  docker run --rm --gpus all ubuntu nvidia-smi | Out-Null
  if ($LASTEXITCODE -eq 0) { $gpuOk = $true }
} catch {
  $gpuOk = $false
}

if ($gpuOk) {
  try {
    Try-Start-GPU
    Write-Host "✅ Started with GPU override." -ForegroundColor Green
    exit 0
  } catch {
    Write-Warning "GPU start failed. Falling back to CPU (no changes kept)."
    Cleanup-GPU
    Start-CPU
    exit 0
  }
} else {
  Write-Host "No usable GPU detected for Docker. Using CPU mode." -ForegroundColor Yellow
  Start-CPU
  exit 0
}
