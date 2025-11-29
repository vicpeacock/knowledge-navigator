# Guida Creazione Card Image per Kaggle

## Requisiti
- **Dimensione**: 1200x630px (rapporto 1.91:1)
- **Formato**: PNG o JPG
- **Dimensione file**: < 5MB (raccomandato)
- **Contenuto**: Screenshot UI o diagramma architettura

---

## Opzione 1: Screenshot UI (Raccomandato)

### Metodo A: Screenshot Manuale

1. **Apri l'applicazione** su Cloud Run:
   - Frontend: https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app
   - Login con le tue credenziali

2. **Prepara la schermata**:
   - Chat attiva con qualche messaggio interessante
   - Notifiche visibili (se presenti)
   - UI pulita e professionale

3. **Fai screenshot**:
   - **macOS**: `Cmd + Shift + 4`, seleziona area 1200x630px
   - **Windows**: `Win + Shift + S`, seleziona area
   - **Linux**: `Shift + Print Screen`

4. **Ritaglia e ridimensiona**:
   - Usa un editor (Preview su macOS, Paint su Windows, GIMP)
   - Imposta dimensione esatta: 1200x630px
   - Salva come PNG

### Metodo B: Screenshot Automatico (Script)

Ho creato uno script Python che puoi usare con Selenium/Playwright per fare screenshot automatici.

**Tool consigliati**:
- **Selenium** (Python): Automazione browser
- **Playwright** (già nel progetto): Browser automation
- **Puppeteer** (Node.js): Screenshot headless

---

## Opzione 2: Diagramma Architettura

### Metodo A: Mermaid Diagram (Raccomandato)

Ho creato un template Mermaid che puoi usare con:
- **Mermaid Live Editor**: https://mermaid.live/
- **VS Code Extension**: Mermaid Preview
- **GitHub**: Renderizza automaticamente nei markdown

### Metodo B: Tool Esterni

**Tool gratuiti**:
- **Excalidraw**: https://excalidraw.com/ (disegno a mano libera)
- **draw.io**: https://app.diagrams.net/ (diagrammi professionali)
- **Figma**: https://www.figma.com/ (design tool, versione gratuita)
- **Canva**: https://www.canva.com/ (template predefiniti)

**Tool a pagamento**:
- **Lucidchart**: Diagrammi professionali
- **Whimsical**: Diagrammi veloci e puliti

---

## Opzione 3: AI-Generated Image

**Tool AI**:
- **DALL-E** (OpenAI): Genera immagini da prompt
- **Midjourney**: Genera immagini artistiche
- **Stable Diffusion**: Open source, locale o online

**Prompt suggerito**:
```
"Modern AI assistant interface, multi-agent architecture diagram, 
enterprise software, clean design, blue and white color scheme, 
professional, technology illustration"
```

---

## Template Mermaid per Architettura

Ho creato `docs/kaggle-card-architecture.mmd` che puoi usare con Mermaid Live Editor.

---

## Checklist Finale

- [ ] Immagine 1200x630px
- [ ] Formato PNG o JPG
- [ ] Dimensione file < 5MB
- [ ] Contenuto chiaro e professionale
- [ ] Testo leggibile (se presente)
- [ ] Colori contrastati
- [ ] Nessun elemento sensibile (email, password, etc.)

---

## Prossimi Passi

1. Scegli metodo (Screenshot UI o Diagramma)
2. Crea immagine
3. Verifica requisiti
4. Salva come `kaggle-card-image.png`
5. Aggiungi al repository (opzionale) o carica direttamente su Kaggle

