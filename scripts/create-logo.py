#!/usr/bin/env python3
"""
Script per creare logo Knowledge Navigator
Genera diverse versioni: icona, logo orizzontale, logo verticale
"""
from PIL import Image, ImageDraw, ImageFont
import math
import os
from pathlib import Path

# Colori del brand (da kaggle-card-enhanced.mmd)
COLORS = {
    'primary_blue': '#2563eb',
    'secondary_blue': '#60a5fa',
    'light_blue': '#93c5fd',
    'green': '#10b981',
    'purple': '#8b5cf6',
    'orange': '#f59e0b',
    'white': '#ffffff',
    'dark_blue': '#1e40af',
}

def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_compass_icon(size=512, bg_color=None):
    """
    Crea icona compass/navigator stilizzata
    """
    # Crea immagine con canale alpha per trasparenza
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    center = size // 2
    radius = int(size * 0.4)
    
    # Colore principale: blu
    primary = hex_to_rgb(COLORS['primary_blue'])
    secondary = hex_to_rgb(COLORS['secondary_blue'])
    light = hex_to_rgb(COLORS['light_blue'])
    
    # Cerchio esterno con gradiente simulato (cerchi concentrici)
    for i in range(5):
        r = radius - (i * radius // 5)
        alpha = 255 - (i * 30)
        color = (*primary, alpha)
        draw.ellipse([center-r, center-r, center+r, center+r], 
                    outline=color, width=max(2, size//128))
    
    # Freccia Nord (puntata verso l'alto) - rappresenta navigazione
    arrow_size = radius * 0.6
    arrow_points = [
        (center, center - arrow_size),  # Punta
        (center - arrow_size * 0.3, center - arrow_size * 0.3),
        (center - arrow_size * 0.15, center - arrow_size * 0.15),
        (center, center),
        (center + arrow_size * 0.15, center - arrow_size * 0.15),
        (center + arrow_size * 0.3, center - arrow_size * 0.3),
    ]
    draw.polygon(arrow_points, fill=(*secondary, 200))
    
    # Linea orizzontale (E-W)
    line_width = max(2, size // 128)
    draw.line([center - radius * 0.7, center, center + radius * 0.7, center], 
             fill=(*primary, 180), width=line_width)
    
    # Linea verticale (N-S)
    draw.line([center, center - radius * 0.7, center, center + radius * 0.7], 
             fill=(*primary, 180), width=line_width)
    
    # Punto centrale
    dot_radius = max(3, size // 64)
    draw.ellipse([center - dot_radius, center - dot_radius, 
                 center + dot_radius, center + dot_radius], 
                fill=(*primary, 255))
    
    # Cerchio interno decorativo
    inner_radius = radius * 0.3
    draw.ellipse([center - inner_radius, center - inner_radius,
                 center + inner_radius, center + inner_radius],
                outline=(*light, 150), width=max(1, size//128))
    
    return img

def create_logo_horizontal(width=800, height=200, icon_size=160):
    """
    Logo orizzontale: icona + testo affiancati
    """
    img = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Crea icona
    icon = create_compass_icon(icon_size)
    
    # Posiziona icona a sinistra
    icon_offset_x = 20
    icon_offset_y = (height - icon_size) // 2
    img.paste(icon, (icon_offset_x, icon_offset_y), icon)
    
    # Testo "Knowledge Navigator"
    try:
        # Prova a usare font di sistema
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except:
        try:
            font_large = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 48)
            font_small = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
        except:
            # Fallback a font default
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
    
    primary = hex_to_rgb(COLORS['primary_blue'])
    
    text_x = icon_offset_x + icon_size + 30
    text_y = height // 2 - 30
    
    # "Knowledge" - grande, grassetto
    draw.text((text_x, text_y), "Knowledge", 
             fill=(*primary, 255), font=font_large)
    
    # "Navigator" - grande, grassetto
    bbox = draw.textbbox((text_x, text_y), "Knowledge", font=font_large)
    draw.text((text_x, text_y + 50), "Navigator", 
             fill=(*primary, 255), font=font_large)
    
    # Sottotitolo opzionale
    # subtitle = "Multi-Agent AI Assistant"
    # draw.text((text_x, text_y + 100), subtitle, 
    #          fill=(*hex_to_rgb(COLORS['dark_blue']), 200), font=font_small)
    
    return img

def create_logo_vertical(width=300, height=400, icon_size=200):
    """
    Logo verticale: icona sopra, testo sotto
    """
    img = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Crea icona
    icon = create_compass_icon(icon_size)
    
    # Posiziona icona in alto, centrata
    icon_offset_x = (width - icon_size) // 2
    icon_offset_y = 20
    img.paste(icon, (icon_offset_x, icon_offset_y), icon)
    
    # Testo sotto l'icona
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except:
        try:
            font_large = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 32)
            font_small = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 16)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
    
    primary = hex_to_rgb(COLORS['primary_blue'])
    
    text_y = icon_offset_y + icon_size + 30
    
    # "Knowledge" - centrato
    bbox = draw.textbbox((0, 0), "Knowledge", font=font_large)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    draw.text((text_x, text_y), "Knowledge", 
             fill=(*primary, 255), font=font_large)
    
    # "Navigator" - centrato
    bbox2 = draw.textbbox((0, 0), "Navigator", font=font_large)
    text_width2 = bbox2[2] - bbox2[0]
    text_x2 = (width - text_width2) // 2
    draw.text((text_x2, text_y + 40), "Navigator", 
             fill=(*primary, 255), font=font_large)
    
    return img

def main():
    """Genera tutte le versioni del logo"""
    output_dir = Path(__file__).parent.parent / "assets" / "logos"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🎨 Generazione logo Knowledge Navigator...")
    print(f"   Output directory: {output_dir}")
    print()
    
    # 1. Icona standalone (varie dimensioni)
    sizes = [512, 256, 128, 64, 32]
    for size in sizes:
        icon = create_compass_icon(size)
        filename = output_dir / f"logo-icon-{size}x{size}.png"
        icon.save(filename, "PNG")
        print(f"✅ Creato: {filename.name}")
    
    # 2. Logo orizzontale
    logo_h = create_logo_horizontal(800, 200, 160)
    filename_h = output_dir / "logo-horizontal.png"
    logo_h.save(filename_h, "PNG")
    print(f"✅ Creato: {filename_h.name}")
    
    # 3. Logo verticale
    logo_v = create_logo_vertical(300, 400, 200)
    filename_v = output_dir / "logo-vertical.png"
    logo_v.save(filename_v, "PNG")
    print(f"✅ Creato: {filename_v.name}")
    
    # 4. Logo orizzontale grande (per header)
    logo_h_large = create_logo_horizontal(1200, 300, 240)
    filename_h_large = output_dir / "logo-horizontal-large.png"
    logo_h_large.save(filename_h_large, "PNG")
    print(f"✅ Creato: {filename_h_large.name}")
    
    # 5. Favicon (16x16 e 32x32)
    favicon_16 = create_compass_icon(16)
    favicon_32 = create_compass_icon(32)
    filename_favicon_16 = output_dir / "favicon-16x16.png"
    filename_favicon_32 = output_dir / "favicon-32x32.png"
    favicon_16.save(filename_favicon_16, "PNG")
    favicon_32.save(filename_favicon_32, "PNG")
    print(f"✅ Creato: {filename_favicon_16.name}")
    print(f"✅ Creato: {filename_favicon_32.name}")
    
    print()
    print("✅ Logo generation completa!")
    print(f"   Tutti i file salvati in: {output_dir}")

if __name__ == "__main__":
    main()

