# Guida Implementazione Firebase & Cloud Functions

Questa guida ti accompagna passo passo nella pubblicazione del backend che abbiamo creato (Phase 1 e 2).

## Prerequisiti
Assicurati di avere installato:
- **Node.js** (v18+)
- **Firebase CLI**: `npm install -g firebase-tools`
- **Google Cloud SDK** (opzionale, ma utile)

## 1. Setup Iniziale del Progetto Firebase

Se non l'hai ancora fatto:
1.  Vai su [Firebase Console](https://console.firebase.google.com/).
2.  Clicca su **"Add project"** e chiamalo (es. `hr2o-scheduler-ai`).
3.  **Disabilita Google Analytics** per questo progetto (non serve per il backend).
4.  Una volta creato, clicca su **Upgrade** in basso a sinistra e seleziona il piano **Blaze** (necessario per Cloud Functions e chiamate esterne).

## 2. Configurazione Firestore
1.  Nel menu di sinistra, vai su **Build > Firestore Database**.
2.  Clicca **Create database**.
3.  Scegli una location (es. `europe-west1` per il Belgio o `europe-west6` per Zurigo - *importante scegliere una regione vicina*).
4.  Scegli **Start in production mode**.

## 3. Login e Inizializzazione Locale
Apri il terminale nella cartella del progetto:

```bash
# 1. Login
firebase login

# 2. Inizializzazione (se non collegato)
firebase use --add
# Seleziona il progetto che hai appena creato
```

## 4. Deploy delle Cloud Functions (Phase 2)
Abbiamo scritto il codice in `backend/functions`. Ora dobbiamo pubblicarlo.

```bash
# Entra nella cartella functions
cd backend/functions

# Installa le dipendenze
npm install

# Torna alla root
cd ../..

# Deploy solo delle Functions
firebase deploy --only functions
```

Se tutto va a buon fine, il terminale ti restituirà l'URL della tua funzione, simile a:
`https://us-central1-YOUR-PROJECT.cloudfunctions.net/api`

## 5. Deploy delle Security Rules (Phase 1)
Per proteggere il database, pubblichiamo le regole che abbiamo scritto in `firestore/firestore.rules`.

```bash
firebase deploy --only firestore:rules
```

## 6. Testare l'Importazione
Ora che è tutto online, puoi testare l'importazione dati usando lo script Python che abbiamo creato.

1.  Apri `scripts/test_hmac.py`.
2.  Modifica `API_URL` con l'URL vero che hai ottenuto al passo 4 + `/v1/import-data`.
    *   Esempio: `https://us-central1-hr2o-ai.cloudfunctions.net/api/api/v1/import-data` (nota il doppio `api` se l'export è `api` e la rotta express è `/api/...` - controlla bene l'output del deploy).
3.  Esegui lo script:
    ```bash
    python3 scripts/test_hmac.py
    ```
4.  Vai sulla console Firebase > Firestore e verifica che i dati siano apparsi!

## 7. Prossimi Passi (Cloud Run - Phase 3)
La prossima fase richiederà Google Cloud Run per il motore Python.
1.  Abilita **Cloud Build API** e **Cloud Run API** nella console Google Cloud associata al progetto Firebase.
2.  Installeremo `gcloud` CLI per fare il deploy del container Docker.
