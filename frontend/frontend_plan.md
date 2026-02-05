# Frontend Refactoring Plan - AI Focus

## Goal
Simplify the UI to focus on the new Previsionale-integrated workflow:
1.  **Generate Schedule** (using ML demand).
2.  **View Schedule** (highlighting High Risk).
3.  **View AI Report** (using Insights API).

## 1. Dashboard Cleanup (`DashboardScreen.dart`)
- **Sidebar**: Remove "Gestione Dipendenti", "Gestione Commesse", "Labor Profiles", "Developer Hub", "Analisi & Confronto".
- **Keep**: "Active Company", "AI Monitor" (Neural Engine Monitor), "Legend".
- **AppBar**: Remove "Demand Settings", "Gestione Dipendenti", "Gestione Commesse". 
- **Add**: "AI Report" button (prominent).

## 2. New Component `AiReportDialog` (`ui/widgets/ai_report_dialog.dart`)
- **Trigger**: New "AI ANALYSIS" button in Dashboard.
- **Logic**: 
    - Fetch current schedule (from Bloc/Repository).
    - Call POST `/reports/analysis`.
    - Show Loading state.
    - Show Report (Summary, Risks, Actions) in a nice UI (e.g. Cards with color coding for severity).

## 3. High Risk Visualization (`ui/calendar/calendar_grid.dart`)
- **Logic**: Inspect `shift['absence_risk']`. 
- **UI**: If risk > 0.5 (or threshold), show a warning icon or red border on the shift card.

## 4. Dependencies
- Update `ScheduleRepository` to include `getAiAnalysis(schedule)`.

