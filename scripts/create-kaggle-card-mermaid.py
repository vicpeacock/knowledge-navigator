#!/usr/bin/env python3
"""
Script per creare Card Image per Kaggle usando Mermaid
Converte il diagramma Mermaid in un'immagine PNG 1200x630px
"""
import subprocess
import sys
import os
from pathlib import Path

def create_card_image():
    """Crea card image da Mermaid diagram"""
    
    mermaid_file = Path(__file__).parent.parent / "docs" / "kaggle-card-architecture.mmd"
    output_file = Path(__file__).parent.parent / "assets" / "kaggle-card-image.png"
    
    if not mermaid_file.exists():
        print(f"❌ File Mermaid non trovato: {mermaid_file}")
        return False
    
    print("🎨 Creazione Card Image da Mermaid diagram")
    print(f"   Input: {mermaid_file}")
    print(f"   Output: {output_file}")
    print()
    
    # Metodo 1: Usa Mermaid CLI se disponibile
    if command_exists("mmdc"):
        print("✅ Trovato Mermaid CLI (mmdc)")
        try:
            cmd = [
                "mmdc",
                "-i", str(mermaid_file),
                "-o", str(output_file),
                "-w", "1200",
                "-H", "630",
                "-b", "white",
                "-t", "default"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Card Image creata: {output_file}")
                return True
            else:
                print(f"❌ Errore: {result.stderr}")
        except Exception as e:
            print(f"❌ Errore esecuzione mmdc: {e}")
    
    # Metodo 2: Usa Puppeteer + mermaid
    if command_exists("node") and command_exists("npx"):
        print("📦 Tentativo con Puppeteer...")
        script_content = f"""
const mermaid = require('@mermaid-js/mermaid');
const puppeteer = require('puppeteer');
const fs = require('fs');

async function generate() {{
    const mermaidCode = fs.readFileSync('{mermaid_file}', 'utf8');
    
    const browser = await puppeteer.launch();
    const page = await browser.newPage();
    await page.setViewport({{ width: 1200, height: 630 }});
    
    const html = `
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>body {{ margin: 0; padding: 20px; background: white; }}</style>
</head>
<body>
    <div class="mermaid">
${{mermaidCode}}
    </div>
    <script>
        mermaid.initialize({{ startOnLoad: true }});
    </script>
</body>
</html>`;
    
    await page.setContent(html);
    await page.waitForSelector('.mermaid svg', {{ timeout: 10000 }});
    await page.screenshot({{ path: '{output_file}', width: 1200, height: 630 }});
    await browser.close();
}}

generate().catch(console.error);
"""
        try:
            script_file = Path("/tmp/kaggle_mermaid.js")
            script_file.write_text(script_content)
            result = subprocess.run(
                ["node", str(script_file)],
                capture_output=True,
                text=True,
                cwd=str(mermaid_file.parent)
            )
            if result.returncode == 0 and output_file.exists():
                print(f"✅ Card Image creata: {output_file}")
                return True
        except Exception as e:
            print(f"⚠️  Puppeteer non disponibile: {e}")
    
    # Metodo 3: Istruzioni manuali
    print()
    print("⚠️  Tool automatici non disponibili")
    print()
    print("📋 Istruzioni Manuali:")
    print("=" * 50)
    print()
    print("1. Apri https://mermaid.live/")
    print(f"2. Copia il contenuto di: {mermaid_file}")
    print("3. Incolla nel editor Mermaid Live")
    print("4. Clicca 'Actions' > 'Download PNG'")
    print("5. Ridimensiona l'immagine a 1200x630px")
    print(f"6. Salva come: {output_file}")
    print()
    print("OPPURE:")
    print()
    print("1. Installa Mermaid CLI:")
    print("   npm install -g @mermaid-js/mermaid-cli")
    print()
    print("2. Esegui:")
    print(f"   mmdc -i {mermaid_file} -o {output_file} -w 1200 -H 630")
    print()
    
    return False

def command_exists(cmd):
    """Verifica se un comando esiste"""
    return subprocess.run(
        ["which", cmd],
        capture_output=True
    ).returncode == 0

if __name__ == "__main__":
    success = create_card_image()
    sys.exit(0 if success else 1)

