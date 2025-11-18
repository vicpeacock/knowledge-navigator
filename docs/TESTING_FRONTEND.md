# Frontend Testing Guide

## Setup

I test frontend usano **Jest** e **React Testing Library** per testare i componenti React.

### Dipendenze Installate

- `jest` - Framework di testing
- `@testing-library/react` - Utilities per testare componenti React
- `@testing-library/jest-dom` - Matchers aggiuntivi per DOM
- `@testing-library/user-event` - Simulazione interazioni utente
- `jest-environment-jsdom` - Ambiente DOM per Jest

### Configurazione

- `jest.config.js` - Configurazione Jest per Next.js
- `jest.setup.js` - Setup globale per i test (mock, environment variables)

## Eseguire i Test

```bash
cd frontend

# Esegui tutti i test
npm test

# Watch mode (ri-esegue test quando i file cambiano)
npm run test:watch

# Con coverage report
npm run test:coverage
```

## Test Implementati

### NotificationBell Component

**File**: `frontend/components/__tests__/NotificationBell.test.tsx`

**19 test** che coprono:

#### Rendering (3 test)
- ✅ Render bell icon
- ✅ Show notification count badge
- ✅ Show 9+ badge for many notifications

#### Popup Functionality (3 test)
- ✅ Open popup when bell clicked
- ✅ Close popup when backdrop clicked
- ✅ Close popup when close button clicked

#### Notification Fetching (4 test)
- ✅ Fetch notifications on mount
- ✅ Poll every 10 seconds when popup closed
- ✅ Don't poll when popup open
- ✅ Fetch when popup opens

#### Notification Display (4 test)
- ✅ Display email notifications
- ✅ Display calendar notifications
- ✅ Display contradiction notifications with details
- ✅ Show loading state

#### Error Handling (2 test)
- ✅ Handle network timeout gracefully
- ✅ Handle other errors by clearing notifications

#### Notification Resolution (1 test)
- ✅ Resolve notification structure

#### Edge Cases (2 test)
- ✅ Don't fetch when sessionId missing
- ✅ Handle empty notification list

## Struttura Test

### Esempio Test

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import axios from 'axios'
import NotificationBell from '../NotificationBell'

jest.mock('axios')
const mockedAxios = axios as jest.Mocked<typeof axios>

describe('NotificationBell', () => {
  it('renders bell icon', () => {
    mockedAxios.get.mockResolvedValue({ data: [] })
    render(<NotificationBell sessionId="test-id" />)
    expect(screen.getByTitle('Notifiche')).toBeInTheDocument()
  })
})
```

### Mocking

- **axios**: Mockato per evitare chiamate HTTP reali
- **next/navigation**: Mockato per evitare errori di routing
- **Environment variables**: Configurate in `jest.setup.js`

### Best Practices

1. **Isolamento**: Ogni test è indipendente
2. **Mock esterni**: Sempre mockare chiamate API
3. **Async handling**: Usare `waitFor` per operazioni asincrone
4. **Timer**: Usare `jest.useFakeTimers()` per testare polling
5. **Cleanup**: Jest pulisce automaticamente dopo ogni test

## Coverage

Per vedere la copertura dei test:

```bash
npm run test:coverage
```

Questo genera un report HTML in `coverage/` che mostra:
- Linee di codice coperte
- Branch coverage
- Function coverage
- Statement coverage

## Prossimi Sviluppi

- [ ] Test per altri componenti (ChatInterface, FileManager, etc.)
- [ ] Test di integrazione E2E con Playwright/Cypress
- [ ] Test per hook personalizzati
- [ ] Test per context providers
- [ ] Snapshot testing per UI regression

## Troubleshooting

### Errore: "Cannot find module"
- Verifica che le dipendenze siano installate: `npm install`
- Verifica che il path nel test sia corretto

### Errore: "Timeout"
- Aumenta il timeout nel test: `waitFor(..., { timeout: 5000 })`
- Verifica che i mock siano configurati correttamente

### Errore: "act() warning"
- Usa `waitFor` per operazioni asincrone
- Usa `act()` quando necessario per aggiornamenti di stato

## Riferimenti

- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [React Testing Library](https://testing-library.com/react)
- [Next.js Testing](https://nextjs.org/docs/testing)

