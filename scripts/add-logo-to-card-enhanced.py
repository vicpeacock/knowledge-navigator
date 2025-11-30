#!/usr/bin/env python3
"""
Script per aggiungere il logo Knowledge Navigator alla card image Kaggle
Versione migliorata con logo più visibile
"""
from PIL import Image, ImageEnhance
from pathlib import Path

def add_logo_to_card(card_image_path, logo_path, output_path, logo_position='top-left', logo_scale=0.25):
    """
    Aggiunge il logo alla card image con migliore visibilità
    
    Args:
        card_image_path: Path alla card image esistente
        logo_path: Path al logo da aggiungere
        output_path: Path dove salvare la card image con logo
        logo_position: Posizione del logo ('top-left', 'top-right', 'top-center')
        logo_scale: Scala del logo rispetto alla card (0.25 = 25% della larghezza)
    """
    # Carica card image
    card = Image.open(card_image_path).convert('RGBA')
    card_width, card_height = card.size
    
    print(f"   Card: {card_width}x{card_height}")
    
    # Carica logo
    logo = Image.open(logo_path).convert('RGBA')
    print(f"   Logo originale: {logo.width}x{logo.height}")
    
    # Calcola dimensioni logo mantenendo aspect ratio
    logo_target_width = int(card_width * logo_scale)
    logo_ratio = logo.height / logo.width
    logo_target_height = int(logo_target_width * logo_ratio)
    
    # Ridimensiona logo
    logo_resized = logo.resize((logo_target_width, logo_target_height), Image.Resampling.LANCZOS)
    print(f"   Logo ridimensionato: {logo_target_width}x{logo_target_height}")
    
    # Migliora il contrasto del logo per migliore visibilità
    # Aumenta leggermente la saturazione e il contrasto
    enhancer = ImageEnhance.Contrast(logo_resized)
    logo_resized = enhancer.enhance(1.2)
    enhancer = ImageEnhance.Brightness(logo_resized)
    logo_resized = enhancer.enhance(1.1)
    
    # Calcola posizione con padding più generoso
    padding = 30
    if logo_position == 'top-left':
        x = padding
        y = padding
    elif logo_position == 'top-right':
        x = card_width - logo_target_width - padding
        y = padding
    elif logo_position == 'top-center':
        x = (card_width - logo_target_width) // 2
        y = padding
    else:
        x = padding
        y = padding
    
    print(f"   Posizione logo: ({x}, {y})")
    
    # Crea una copia della card per non modificare l'originale durante il debug
    card_with_logo = card.copy()
    
    # Incolla logo sulla card usando alpha composite per migliore blending
    # Crea un'immagine temporanea per il compositing
    temp = Image.new('RGBA', card_with_logo.size, (0, 0, 0, 0))
    temp.paste(logo_resized, (x, y), logo_resized)
    card_with_logo = Image.alpha_composite(card_with_logo, temp)
    
    # Salva
    card_with_logo.save(output_path, 'PNG')
    print(f"   ✅ Salvato: {Path(output_path).name}")

if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    
    # Paths - usa le card images con ratio 2:1
    card_images = [
        ("assets/kaggle-card-image-2400x1200.png", "assets/kaggle-card-image-2400x1200-with-logo.png"),
        ("assets/kaggle-card-image-1200x600.png", "assets/kaggle-card-image-1200x600-with-logo.png"),
    ]
    
    logo_horizontal = base_dir / "assets" / "logos" / "logo-horizontal.png"
    
    # Verifica che il logo esista
    if not logo_horizontal.exists():
        print(f"❌ Logo non trovato: {logo_horizontal}")
        exit(1)
    
    print("🎨 Aggiunta logo alle card images Kaggle (ratio 2:1) - Versione migliorata...")
    print(f"   Logo: {logo_horizontal}")
    print()
    
    for card_image_name, output_name in card_images:
        card_image = base_dir / card_image_name
        
        if not card_image.exists():
            print(f"⚠️  Card image non trovata: {card_image_name}, saltata...")
            print()
            continue
        
        print(f"📐 Processing: {card_image_name}")
        add_logo_to_card(
            card_image_path=str(card_image),
            logo_path=str(logo_horizontal),
            output_path=str(base_dir / output_name),
            logo_position='top-left',
            logo_scale=0.25  # Logo 25% della larghezza della card
        )
        print()
    
    print("✅ Processo completato!")
    for _, output_name in card_images:
        print(f"   ✅ {output_name}")

