# Script para compilar PCDetection con PyQt6
# Asegúrate de estar en el entorno virtual .\.venv\Scripts\Activate.ps1

Write-Host "Compilando PCDetection a ejecutable..."

pyinstaller --noconfirm --onefile --windowed --name "PCDetection" .\app.py

Write-Host "Compilación terminada. El archivo ejecutable está en la carpeta 'dist'."
