# Guida all'Integrazione: Firestore, Flutter e Cloud Run

Questa guida spiega come collegare i pezzi del puzzle che abbiamo creato: il Frontend Flutter, il Database Firestore e il Backend Python su Google Cloud.

## PARTE 1: Collegare Flutter a Firebase

Il progetto Flutter in `frontend/` ha bisogno delle credenziali per parlare con Firebase.

### 1. Installare il CLI
Esegui questi comandi nel terminale (se non li hai già):
```bash
npm install -g firebase-tools
dart pub global activate flutterfire_cli
```

### 2. Configurazione Automatica
Dalla cartella root del progetto (`frontend/`):
```bash
cd frontend
flutterfire configure
```
- Seleziona il progetto Firebase che hai creato nella Fase 1.
- Seleziona le piattaforme (Android, iOS, Web, macOS).
- Questo comando creerà automaticamente il file `lib/firebase_options.dart` e scaricherà i file di configurazione (`google-services.json` / `GoogleService-Info.plist`).

### 3. Aggiornare `main.dart`
Una volta generato `firebase_options.dart`, apri `lib/main.dart` e de-commenta le righe relative:

```dart
// import 'firebase_options.dart'; // <--- De-commenta questo
...
await Firebase.initializeApp(
  options: DefaultFirebaseOptions.currentPlatform, // <--- Usa questo
);
```

---

## PARTE 2: Collegare Python (Cloud Run) a Firestore

Il container Python deve poter leggere/scrivere su Firestore.

### 1. Account di Servizio (IAM)
Quando le Cloud Functions o Cloud Run girano su Google Cloud, usano un "Service Account" predefinito. Dobbiamo assicurarci che abbia i permessi.

1.  Vai su [Google Cloud Console > IAM](https://console.cloud.google.com/iam-admin/iam).
2.  Trova l'account di servizio "Compute Engine default service account" (finisce con `...-compute@developer.gserviceaccount.com`).
3.  Clicca matita (Edit) e aggiungi il ruolo: **"Cloud Datastore User"** (o "Firebase Admin" per pieni poteri).

### 2. Deploy su Cloud Run

**⚠️ IMPORTANTE: Sicurezza e Isolamento**
Visto che lavori su un computer con altri progetti, usiamo una configurazione isolata per non toccare le tue impostazioni globali.

```bash
# 1. Crea una nuova configurazione isolata per questo progetto
gcloud config configurations create hr2o-scheduler

# 2. Autenticati (questo login vale solo per questa config)
gcloud auth login

# 3. Imposta il progetto corrente
gcloud config set project IL_TUO_PROJECT_ID
```
In questo modo, quando hai finito, puoi tornare ai tuoi altri progetti semplicemente con `gcloud config configurations activate default`.

Ora pubblichiamo il container Python:

Assicurati di avere `gcloud` installato.

```bash
# Entra nella cartella del solver
cd backend/python_solver

# 1. Costruisci l'immagine e caricala su Container Registry (Google Artifact Registry è meglio, ma usiamo gcr per semplicità)
gcloud builds submit --tag gcr.io/IL_TUO_PROJECT_ID/hr2o-solver

# 2. Fai il deploy su Cloud Run
gcloud run deploy hr2o-solver \
  --image gcr.io/IL_TUO_PROJECT_ID/hr2o-solver \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 5
```
**Ottimizzazione Costi**: `--min-instances 0` permette al servizio di spegnersi quando non usato (costo zero). `--max-instances 5` evita spese folli se il traffico esplodesse.
*(Sostituisci `IL_TUO_PROJECT_ID` con l'ID del tuo progetto Firebase/GCloud)*.

L'opzione `--allow-unauthenticated` rende l'API pubblica. Se vuoi proteggerla, dovrai implementare l'autenticazione anche lì o usare un VPC Connector, ma per ora va bene così per testare dal Frontend Flutter.

---

## PARTE 3: Collegamento Finale

Ora hai:
1.  **Frontend**: Conosce Firebase grazie a `flutterfire configure`.
2.  **Backend Python**: Gira su Cloud Run e ha i permessi IAM per scrivere su Firestore.
3.  **Cloud Functions**: Già deployate nella Fase 2.

### Aggiornare URL nel Frontend
Nel file `lib/repositories/schedule_repository.dart`, dovrai inserire l'URL del servizio Cloud Run appena deployato per far funzionare il tasto "Generate Magic Shift".

Cerca:
```dart
Future<void> triggerGeneration(...) async {
  // Call the Cloud Run API here via HTTP
}
```
E implementa la chiamata HTTP verso: `https://hr2o-solver-xxxxx-ew.a.run.app/schedule/generate`.

---

## PARTE 4: The Living Grid (Nuove Features Fase 12)

Ecco le nuove funzionalità "intelligenti" che abbiamo aggiunto all'interfaccia:

### 1. Heatmap Ambientale 🌡️
Lo sfondo della griglia cambia colore in base al carico di lavoro:
-   **Rosso**: Understaffed (Sotto organico, manca gente!).
-   **Verde**: Optimal (Staff perfetto).
-   **Blu**: Overstaffed (Troppa gente, spreco di budget).

### 2. AI Auto-Pilot 🤖
Nelle impostazioni (ingranaggio), puoi attivare "AI Auto-Pilot".
-   Il backend analizza lo storico dei turni degli ultimi 30 giorni.
-   Impara automaticamente quanti dipendenti servono nei giorni feriali vs weekend.
-   Aggiorna i target della Heatmap da solo.

### 3. Semantic Drag & Drop 🧲
Spostare le persone ora ha un feedback "fisico":
-   **Attrazione (Verde)**: Se trascini una persona su un turno adatto al suo ruolo, la cella si ingrandisce e diventa verde.
-   **Resistenza (Rosso)**: Se il ruolo non combacia, la cella diventa rossa e vibra (haptic feedback pesante).

### 4. Synapse Feedback 🧠
Ogni volta che sposti qualcuno o approvi un turno, l'AI "impara".
-   Una notifica **"Preferenza Salvata! 🧠"** appare in basso per confermare che l'azione è stata registrata nel cervello dell'AI.
