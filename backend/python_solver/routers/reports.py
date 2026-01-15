from fastapi import APIRouter, Depends, HTTPException, Response
from typing import List
import csv
import io
from utils.security import verify_hmac

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.post("/export-csv")
def export_csv(schedule: List[dict], environment: str = Depends(verify_hmac)):
    """
    Exports the provided schedule JSON to a CSV file.
    """
    if not schedule:
        raise HTTPException(status_code=400, detail="Schedule data is empty")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=schedule[0].keys())
    writer.writeheader()
    writer.writerows(schedule)
    
    csv_content = output.getvalue()
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=schedule_{environment}.csv"}
    )

@router.post("/export-ics")
def export_ics(schedule: List[dict], environment: str = Depends(verify_hmac)):
    """
    Exports the schedule to iCalendar format.
    Simple implementation for MVP.
    """
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TimePlanner AI//EN"
    ]
    
    for shift in schedule:
        # Expected format: date (YYYY-MM-DD), start_time (HH:mm), end_time (HH:mm)
        date_str = shift.get("date", "").replace("-", "")
        start_time = shift.get("start_time", "09:00").replace(":", "")
        end_time = shift.get("end_time", "17:00").replace(":", "")
        
        ics_lines.extend([
            "BEGIN:VEVENT",
            f"DTSTART:{date_str}T{start_time}00",
            f"DTEND:{date_str}T{end_time}00",
            f"SUMMARY:Shift: {shift.get('employee_name')} ({shift.get('role')})",
            "END:VEVENT"
        ])
        
    ics_lines.append("END:VCALENDAR")
    ics_content = "\n".join(ics_lines)
    
from fpdf import FPDF

@router.post("/export-pdf")
def export_pdf(schedule: List[dict], environment: str = Depends(verify_hmac)):
    """
    Exports a professional PDF grid of the schedule.
    """
    if not schedule:
        raise HTTPException(status_code=400, detail="Schedule data is empty")

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Optimized Schedule - Environment: {environment.upper()}", ln=True, align='C')
    pdf.ln(10)

    # Headers: Employee, Mon, Tue, Wed, Thu, Fri, Sat, Sun
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header = ["Employee"] + days
    
    # Calculate column widths
    col_width = pdf.epw / len(header)
    
    # Set header style
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(240, 240, 240)
    for col in header:
        pdf.cell(col_width, 10, col, border=1, align='C', fill=True)
    pdf.ln()

    # Get data structure
    employees = sorted(list(set([s['employee_name'] for s in schedule])))
    
    pdf.set_font("Helvetica", "", 8)
    for emp in employees:
        row_height = 20
        # First cell: Employee Name
        pdf.cell(col_width, row_height, emp, border=1, align='C')
        
        # Save current position
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        # Day cells
        for day in days:
            shifts = [s for s in schedule if s['employee_name'] == emp and s['day'] == day]
            txt = ""
            if shifts:
                for s in shifts:
                    txt += f"{s.get('role')}\n{s.get('start_time')}-{s.get('end_time')}\n"
            
            # Draw empty cell as border
            current_x = pdf.get_x()
            pdf.rect(current_x, y_start, col_width, row_height)
            
            # Draw content
            pdf.multi_cell(col_width, 5, txt, border=0, align='C')
            
            # Step back to top of row for next day
            pdf.set_xy(current_x + col_width, y_start)
            
        pdf.ln(row_height)

    pdf_output = pdf.output()
    
    return Response(
        content=pdf_output,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=schedule_{environment}.pdf"}
    )
