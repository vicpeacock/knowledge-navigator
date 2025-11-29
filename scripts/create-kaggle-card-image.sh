#!/bin/bash

# Script per creare Card Image per Kaggle submission
# Usa Playwright per fare screenshot automatico dell'UI

set -e

FRONTEND_URL="${FRONTEND_URL:-https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app}"
OUTPUT_FILE="${OUTPUT_FILE:-kaggle-card-image.png}"
WIDTH=1200
HEIGHT=630

echo "🎨 Creazione Card Image per Kaggle"
echo "=================================="
echo ""
echo "Frontend URL: $FRONTEND_URL"
echo "Output file: $OUTPUT_FILE"
echo "Dimensioni: ${WIDTH}x${HEIGHT}px"
echo ""

# Verifica se Playwright è installato
if ! command -v playwright &> /dev/null; then
    echo "⚠️  Playwright non trovato. Installazione..."
    npm install -g playwright
    playwright install chromium
fi

# Crea script Python temporaneo per screenshot
cat > /tmp/kaggle_screenshot.py << 'EOF'
import asyncio
from playwright.async_api import async_playwright
import sys

async def main():
    frontend_url = sys.argv[1]
    output_file = sys.argv[2]
    width = int(sys.argv[3])
    height = int(sys.argv[4])
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Imposta viewport
        await page.set_viewport_size({"width": width, "height": height})
        
        # Naviga alla pagina
        print(f"📸 Navigazione a {frontend_url}...")
        await page.goto(frontend_url, wait_until="networkidle")
        
        # Aspetta che la pagina carichi completamente
        await page.wait_for_timeout(3000)
        
        # Fai screenshot
        print(f"📷 Screenshot in corso...")
        await page.screenshot(path=output_file, full_page=False)
        
        await browser.close()
        print(f"✅ Screenshot salvato: {output_file}")

asyncio.run(main())
EOF

# Esegui script Python
python3 /tmp/kaggle_screenshot.py "$FRONTEND_URL" "$OUTPUT_FILE" "$WIDTH" "$HEIGHT"

# Verifica che il file sia stato creato
if [ -f "$OUTPUT_FILE" ]; then
    FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo ""
    echo "✅ Card Image creata con successo!"
    echo "   File: $OUTPUT_FILE"
    echo "   Dimensione: $FILE_SIZE"
    echo ""
    echo "📋 Prossimi passi:"
    echo "   1. Verifica che l'immagine sia chiara e professionale"
    echo "   2. Se necessario, ritaglia o modifica con un editor"
    echo "   3. Carica su Kaggle submission form"
else
    echo "❌ Errore: File non creato"
    exit 1
fi

