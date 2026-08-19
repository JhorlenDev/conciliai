#!/usr/bin/env bash
set -e

git add .
git diff --cached --quiet || git commit -m "feat: atualização"
git push origin main
