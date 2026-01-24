#!/usr/bin/env bash
# Start with GPU if supported (Linux/Windows-WSL), otherwise fall back to CPU.
# On macOS we skip GPU attempt entirely to avoid errors/aborts.

set +e

cd "$(dirname "$0")" || exit 1

GPU_LOG="./gpu_start_attempt.log"

# Choose compose command
if docker compose version >/dev/null 2>&1; then
  COMPOSE=("docker" "compose")
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=("docker-compose")
else
  echo "ERROR: Neither 'docker compose' nor 'docker-compose' found."
  exit 1
fi

# Detect OS
UNAME="$(uname -s 2>/dev/null || echo "")"

start_cpu() {
  echo "Starting CPU mode (default compose)..."
  "${COMPOSE[@]}" -f docker-compose.yml up -d --build
  return $?
}

try_start_gpu() {
  echo "Trying GPU mode (compose override)... (logs: $GPU_LOG)"
  "${COMPOSE[@]}" -f docker-compose.yml -f docker-compose.gpu.yml up -d --build >"$GPU_LOG" 2>&1
  return $?
}

cleanup_gpu() {
  "${COMPOSE[@]}" -f docker-compose.yml -f docker-compose.gpu.yml down >/dev/null 2>&1
}

# macOS: do NOT attempt GPU (avoids errors)
if [ "$UNAME" = "Darwin" ]; then
  echo "macOS detected -> skipping GPU attempt (CPU only)."
  start_cpu
  exit $?
fi

# Try GPU on non-macOS
try_start_gpu
if [ $? -eq 0 ]; then
  echo "✅ Started with GPU override."
  exit 0
else
  echo "⚠️ GPU start failed -> falling back to CPU (no changes kept)."
  cleanup_gpu
  start_cpu
  exit $?
fi
