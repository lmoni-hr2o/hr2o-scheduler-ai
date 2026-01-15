# HR2O Scheduler AI

## Project Overview
This project targets the creation of an intelligent, secure, and self-learning shift management system using Firebase, Google Cloud, and Flutter.

## Architecture
- **Frontend**: Flutter (Web/Mobile)
- **Backend**:
    - **Ingestion**: Google Cloud Functions (Node.js/Python) with HMAC security.
    - **Compute**: Google Cloud Run (Python container) running FastAPI, OR-Tools, and TensorFlow.
- **Database**: Firebase Firestore (NoSQL).

## Setup Instructions

### Prerequisites
- Google Cloud Platform Account
- Firebase CLI
- Docker
- Flutter SDK

### Quick Start
1.  **Firebase Setup**:
    - Create a project on the Firebase Console.
    - Enable Firestore, Authentication, and Functions.
    - Upgrade to Blaze Plan.

2.  **Backend (Python)**:
    ```bash
    cd backend/python_solver
    pip install -r requirements.txt
    ```

3.  **Functions**:
    ```bash
    cd backend/functions
    npm install
    ```
