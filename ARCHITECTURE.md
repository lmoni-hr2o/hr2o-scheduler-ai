# 🏗️ HR2O Scheduler AI - Architecture

## Data Model

### Hierarchy
```
Namespace (e.g., "OVERCLEAN") = Your service company
├── Employees (Person entities)
│   └── Your workforce
├── Company (from API) = Client companies
│   ├── id, code, name, address, etc.
│   └── Companies you provide services to
├── Employment = Contracts with client companies
│   └── Relationship between your company and clients
├── Activity = Jobs/Projects for clients
│   ├── Specific tasks to complete
│   └── Linked to Company clients
└── Period = Historical work shifts
    ├── Which employee
    ├── Which activity
    ├── When (tmentry, tmexit)
    └── Used for AI training

```

## APIs

### External
- **Company API**: `https://europe-west3-hrtimeplace.cloudfunctions.net/company?namespace={namespace}`
  - Returns list of client companies
  - Fields: id, code, name, address, city, VATNumber, phone, mail

### Internal (Cloud Run)
- `/agent/employment` - Get employees for a namespace
- `/agent/activities` - Get activities/jobs
- `/training/retrain` - Trigger AI retraining from Period data
- `/schedule/generate` - Generate optimized schedule

## Workflow

1. **Select Namespace** (e.g., "OVERCLEAN")
2. **Load Data**:
   - Employees from Datastore
   - Client Companies from API
   - Activities from Datastore
   - Historical Periods for training
3. **Generate Schedule**:
   - AI learns from Period history
   - Assigns employees to activities
   - Respects labor laws and preferences
4. **Manage Jobs**:
   - View active activities/commesse
   - Update job details
   - Track completion

## Key Entities

### Period (Training Data)
```python
{
  "employment": {...},      # Employee info
  "activities": {...},      # Job/activity info
  "tmregister": datetime,   # Registration time
  "tmentry": datetime,      # Start time
  "tmexit": datetime,       # End time
}
```

### Activity (Jobs/Commesse)
```python
{
  "id": str,
  "name": str,
  "project": {
    "customer": {...},      # Client company
    "code": str
  },
  "typeActivity": str
}
```

### Company (Clients)
```python
{
  "id": int,
  "code": str,
  "name": str,
  "address": str,
  "city": str,
  "VATNumber": str,
  "phone": str,
  "mail": str
}
```


# gcloud run deploy timeplanner --source . --region europe-west3 --project hrtimeplace --allow-unauthenticated --quiet
