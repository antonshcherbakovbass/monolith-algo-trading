$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python build_all.py --all
