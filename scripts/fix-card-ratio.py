#!/usr/bin/env python3
"""
Script per correggere il ratio delle card images a esattamente 2:1
Ritaglia e ridimensiona le immagini per avere le dimensioni corrette
"""
from PIL import Image
from pathlib import Path

def fix_card_ratio(input_path, output_path, target_width, target_height):
    """
    Ritaglia e ridimensiona la card image per avere esattamente ratio 2:1
    
    Args:
        input_path: Path all'immagine originale
        output_path: Path dove salvare l'immagine corretta
        target_width: Larghezza target (es. 2400)
        target_height: Altezza target (es. 1200, per ratio 2:1)
    """
    # Carica immagine
    img = Image.open(input_path).convert('RGBA')
    orig_width, orig_height = img.size
    
    print(f"   Originale: {orig_width}x{orig_height} (ratio: {orig_width/orig_height:.2f}:1)")
    
    # Calcola il ratio target
    target_ratio = target_width / target_height  # Dovrebbe essere 2.0
    
    # Calcola il ratio attuale
    current_ratio = orig_width / orig_height
    
    # Determina come ritagliare
    if current_ratio > target_ratio:
        # L'immagine è più larga del necessario, ritaglia i lati
        new_height = orig_height
        new_width = int(orig_height * target_ratio)
        left = (orig_width - new_width) // 2
        top = 0
        right = left + new_width
        bottom = orig_height
    else:
        # L'immagine è più alta del necessario, ritaglia sopra/sotto
        new_width = orig_width
        new_height = int(orig_width / target_ratio)
        left = 0
        top = (orig_height - new_height) // 2
        right = orig_width
        bottom = top + new_height
    
    # Ritaglia al centro
    img_cropped = img.crop((left, top, right, bottom))
    print(f"   Dopo ritaglio: {img_cropped.size[0]}x{img_cropped.size[1]} (ratio: {img_cropped.size[0]/img_cropped.size[1]:.2f}:1)")
    
    # Ridimensiona alle dimensioni esatte
    img_resized = img_cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    # Salva
    img_resized.save(output_path, 'PNG')
    output_file = Path(output_path)
    print(f"   Finale: {target_width}x{target_height} (ratio: {target_width/target_height:.2f}:1)")
    print(f"   ✅ Salvato: {output_file.name}")

if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    
    print("🔧 Correzione ratio card images a 2:1...")
    print()
    
    # Card images da correggere
    cards_to_fix = [
        ("assets/kaggle-card-image-2400x1200.png", 2400, 1200),
        ("assets/kaggle-card-image-1200x600.png", 1200, 600),
        ("assets/kaggle-card-image-2400x1200-with-logo.png", 2400, 1200),
        ("assets/kaggle-card-image-1200x600-with-logo.png", 1200, 600),
    ]
    
    for card_name, width, height in cards_to_fix:
        input_file = base_dir / card_name
        
        if not input_file.exists():
            print(f"⚠️  File non trovato: {card_name}, saltato...")
            print()
            continue
        
        print(f"📐 Processing: {card_name}")
        fix_card_ratio(
            input_path=str(input_file),
            output_path=str(input_file),  # Sovrascrivi il file originale
            target_width=width,
            target_height=height
        )
        print()
    
    print("✅ Processo completato!")

