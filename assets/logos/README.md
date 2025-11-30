# Knowledge Navigator - Logo Assets

Questo repository contiene tutte le versioni del logo Knowledge Navigator.

## Design

Il logo rappresenta una **bussola/navigator** stilizzata, simbolo perfetto per un sistema che aiuta a "navigare" attraverso la conoscenza. I colori utilizzati sono coerenti con il brand:

- **Primary Blue**: `#2563eb` - Colore principale del brand
- **Secondary Blue**: `#60a5fa` - Colore secondario
- **Light Blue**: `#93c5fd` - Accenti e decorazioni

## File Disponibili

### Icone (Solo simbolo)

- `logo-icon-512x512.png` - Icona ad alta risoluzione (512x512px)
- `logo-icon-256x256.png` - Icona media risoluzione (256x256px)
- `logo-icon-128x128.png` - Icona standard (128x128px)
- `logo-icon-64x64.png` - Icona piccola (64x64px)
- `logo-icon-32x32.png` - Icona molto piccola (32x32px)
- `logo-icon.svg` - Versione vettoriale SVG (scalabile)

### Logo Orizzontale (Icona + Testo)

- `logo-horizontal.png` - Logo orizzontale standard (800x200px)
- `logo-horizontal-large.png` - Logo orizzontale grande per header (1200x300px)

### Logo Verticale (Icona sopra, Testo sotto)

- `logo-vertical.png` - Logo verticale (300x400px)

### Favicon

- `favicon-16x16.png` - Favicon 16x16px
- `favicon-32x32.png` - Favicon 32x32px

## Utilizzo

### Frontend (Next.js)

```tsx
import Image from 'next/image'

// Logo orizzontale in header
<Image 
  src="/assets/logos/logo-horizontal.png" 
  alt="Knowledge Navigator" 
  width={400} 
  height={100}
/>

// Icona favicon
<link rel="icon" href="/assets/logos/favicon-32x32.png" />
```

### Documentazione

Usa il logo SVG per documentazione Markdown:

```markdown
![Knowledge Navigator Logo](./assets/logos/logo-icon.svg)
```

### Presentazioni

- **Slide title**: Usa `logo-horizontal-large.png`
- **Slide footer**: Usa `logo-horizontal.png`
- **Watermark**: Usa `logo-icon-128x128.png` con opacità ridotta

## Rigenerazione

Per rigenerare i logo, esegui:

```bash
python scripts/create-logo.py
```

## Note

- Tutti i PNG hanno sfondo trasparente (alpha channel)
- Il logo SVG è scalabile senza perdita di qualità
- I colori sono definiti nella palette del brand (`#2563eb`, `#60a5fa`, `#93c5fd`)

