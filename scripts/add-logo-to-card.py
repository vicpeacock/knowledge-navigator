#!/usr/bin/env python3
"""
Script per aggiungere il logo Knowledge Navigator alla card image Kaggle
"""
from PIL import Image
from pathlib import Path

def add_logo_to_card(card_image_path, logo_path, output_path, logo_position='top-left', logo_scale=0.2):
    """
    Aggiunge il logo alla card image
    
    Args:
        card_image_path: Path alla card image esistente
        logo_path: Path al logo da aggiungere
        output_path: Path dove salvare la card image con logo
        logo_position: Posizione del logo ('top-left', 'top-right', 'top-center')
        logo_scale: Scala del logo rispetto alla card (0.2 = 20% della larghezza)
    """
    # Carica card image
    card = Image.open(card_image_path).convert('RGBA')
    card_width, card_height = card.size
    
    # Carica logo
    logo = Image.open(logo_path).convert('RGBA')
    
    # Calcola dimensioni logo mantenendo aspect ratio
    logo_target_width = int(card_width * logo_scale)
    logo_ratio = logo.height / logo.width
    logo_target_height = int(logo_target_width * logo_ratio)
    
    # Ridimensiona logo
    logo_resized = logo.resize((logo_target_width, logo_target_height), Image.Resampling.LANCZOS)
    
    # Calcola posizione
    padding = 20
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
    
    # Aggiungi leggero effetto shadow al logo per migliore visibilità
    # Crea una versione leggermente più scura per shadow
    shadow_offset = 3
    shadow = Image.new('RGBA', (logo_target_width + shadow_offset * 2, 
                                 logo_target_height + shadow_offset * 2), 
                       (0, 0, 0, 0))
    shadow_draw = shadow.copy()
    
    # Incolla logo sulla card
    card.paste(logo_resized, (x, y), logo_resized)
    
    # Salva
    card.save(output_path, 'PNG')
    print(f"✅ Card image con logo creata: {output_path}")
    print(f"   Logo posizionato: {logo_position}")
    print(f"   Dimensione logo: {logo_target_width}x{logo_target_height}px")

if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    
    # Paths
    card_image = base_dir / "kaggle-card-image.png"
    logo_horizontal = base_dir / "assets" / "logos" / "logo-horizontal.png"
    output_with_logo = base_dir / "kaggle-card-image-with-logo.png"
    
    # Verifica che i file esistano
    if not card_image.exists():
        print(f"❌ Card image non trovata: {card_image}")
        exit(1)
    
    if not logo_horizontal.exists():
        print(f"❌ Logo non trovato: {logo_horizontal}")
        exit(1)
    
    print("🎨 Aggiunta logo alla card image Kaggle...")
    print(f"   Card image: {card_image}")
    print(f"   Logo: {logo_horizontal}")
    print()
    
    # Aggiungi logo in alto a sinistra (posizione standard per branding)
    add_logo_to_card(
        card_image_path=str(card_image),
        logo_path=str(logo_horizontal),
        output_path=str(output_with_logo),
        logo_position='top-left',
        logo_scale=0.25  # Logo 25% della larghezza della card
    )
    
    # Crea anche versione con logo in alto a destra (alternativa)
    output_with_logo_right = base_dir / "kaggle-card-image-with-logo-right.png"
    add_logo_to_card(
        card_image_path=str(card_image),
        logo_path=str(logo_horizontal),
        output_path=str(output_with_logo_right),
        logo_position='top-right',
        logo_scale=0.25
    )
    
    print()
    print("✅ Processo completato!")
    print(f"   - Versione logo sinistra: {output_with_logo.name}")
    print(f"   - Versione logo destra: {output_with_logo_right.name}")

