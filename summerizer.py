import os #load environment variables
import json #json to specify the schema and texts
from datetime import datetime #for pydantic to define types of the individual fields
import threading
from typing import List, Optional
import PyPDF2
from google import genai #to communicate with Gemini
from dotenv import load_dotenv


"""
BaseModel: Define the model 
Field: Provided description 
"""
from pydantic import BaseModel, Field
import tkinter as tk
from tkinter import messagebox, scrolledtext

from markdown2 import markdown
from weasyprint import HTML

import pyttsx3
import speech_recognition as sr
load_dotenv()

#Initialize engines
engine = pyttsx3.init()
recognizer = sr.Recognizer()

def load_file(path):
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        return "".join(page.extract_text() or "" for page in reader.pages)
    


class AnnualReport(BaseModel):
    company_name: str = Field(..., description="The name of the company as reported in the 10-K")
    cik: str = Field(..., description="Central Index Key (CIK) identifier assigned by the SEC")
    fiscal_year_end: datetime = Field(..., description="Fiscal year end date")
    filing_date: datetime = Field(..., description="Date when the 10-K was filed with the SEC")
    total_revenue: Optional[float] = Field(None, description="Total revenue for the fiscal year (in USD)")
    net_income: Optional[float] = Field(None, description="Net income for the fiscal year (in USD)")
    total_assets: Optional[float] = Field(None, description="Total assets at fiscal year end (in USD)")
    total_liabilities: Optional[float] = Field(None, description="Total liabilities at fiscal year end (in USD)")
    operating_cash_flow: Optional[float] = Field(None, description="Net cash provided by operating activities (in USD)")
    cash_and_equivalents: Optional[float] = Field(None, description="Cash and cash equivalents at fiscal year (in USD)")
    num_employees: Optional[int] = Field(None, description="Number of employees reported")
    auditor: Optional[str] = Field(None, description="Name of the external auditor")
    business_description: Optional[str] = Field(None, description="Key risk factors (Item 1)")
    risk_factors: Optional[List[str]] = Field(None, description="Key risk factors (Item 1A)")
    management_discussion: Optional[str] = Field(None, description="Management's Discussion & Analysus (Item 7)") 
    advice: Optional[str] = Field(None, description="Give an advice to the user on how to improve the company standing.")
    roles: Optional[str] = Field(None, description="Treat this as a role playing game. Name the roles that the employees contribute to the company of the 10-K report")
    skills: Optional[str] = Field(None, description="Treat this as a roleplaying game, name the skills reqiured to improve company standing. Give rank of 1 to 10, 1 being novice, 10 being expert")
    tools: Optional[str] = Field(None, description="Pretend you are a quest-giver NPC from a role-playing game. List the tools/equipments/files required for the company's benefits")

#voice recognition
def start_voice():
    """Trigger by the voice input button to run listening background thread"""
    status_label.config(text="Listening for filename...", fg = "orange")
    threading.Thread(target = listen_thread, daemon=True).start()
    
def listen_thread():
    try: 
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=5)

            #convert speech to text
            text = recognizer.recognize_google(audio)

            #clean up text
            filename = text.lower().replace(" ", "_")
            if not filename.endswith(".pdf"):
                filename += ".pdf"

            #update UI from the thread safely
            file_input.delete(0, tk.END)
            file_input.insert(0, filename)
            status_label.config(text = f"Recognized {filename}", fg = "blue")
    except sr.WaitTimeoutError:
        status_label.config(text="Listening timed out", fg="red")
    except sr.UnknownValueError:
        status_label.config(text="Could not understand audio", fg="red")
    except Exception as e:
        status_label.config(text=f"Error: {str(e)}", fg="red")


def run_analysis():

    pdf_path = file_input.get()

    if not os.path.exists(pdf_path):
        messagebox.showerror("Error", f"File {pdf_path} was not found")
        return
    
    status_label.config(text="Processing with Gemini AI... please wait", fg = "green")
    root.update_idletasks()

    try:
        text = load_file(pdf_path)
        #call api key
        client = genai.Client(api_key = os.getenv('GEMINI_API_KEY'))

        schema_definition = json.dumps(AnnualReport.model_json_schema(), indent=2, ensure_ascii = 'False')

        prompt = f'Analyze the following annual report (10-K) and fill the data model based on it:\n\n{text}\n\n'
        prompt += f'The output needs to be in the following data format: \n\n{schema_definition}\n\nNo extra fields allowed!'

        response = client.models.generate_content(
            model = 'gemini-2.5-flash',
            contents = prompt,
            config = {
                'response_mime_type': 'application/json',
                'response_schema': AnnualReport
            }
        )

        ar = AnnualReport.model_validate_json(response.text)
        #basically takes a text which is going to be in that format

        print(ar)

        md_lines = [
            f'#{ar.company_name} Annual Report Summary ({ar.fiscal_year_end})',
            f'**CIK*** {ar.cik}',
            f'**Fiscal Year End: ** {ar.fiscal_year_end.strftime("%Y-%m-%d")}',
            f'**Filing Date: ** {ar.filing_date.strftime("%Y-%m-%d")}',
        ]

        if ar.total_revenue is not None:
            md_lines.append(f'- **Total Revenue:** ${ar.total_revenue:.2f}')
        if ar.net_income is not None:
            md_lines.append(f'- **Net Income:** ${ar.net_income:.2f}')
        if ar.total_assets is not None:
            md_lines.append(f'- **Total Assets:** ${ar.total_assets:.2f}')
        if ar.total_liabilities is not None:
            md_lines.append(f'- **Total Liabilities:** ${ar.total_liabilities:.2f}')
        if ar.operating_cash_flow is not None:
            md_lines.append(f'- **Operating Cash Flow:** ${ar.operating_cash_flow:.2f}')
        if ar.cash_and_equivalents is not None:
            md_lines.append(f'- **Cash and Equivalents:** ${ar.cash_and_equivalents:.2f}')
        if ar.num_employees is not None:
            md_lines.append(f'- **Number of Employees:** ${ar.num_employees}')
        if ar.auditor is not None:
            md_lines.append(f'- **Auditor:** ${ar.auditor}')

        if ar.business_description:
            md_lines += ['\n## Business Description', ar.business_description]
        if ar.risk_factors:
            risk_list_text = '\n'.join([f'- {rf}' for rf in ar.risk_factors])
            md_lines += ['\n## Risk Factors' + risk_list_text]
        if ar.management_discussion:
            md_lines += ['\n## Management Discussion', ar.management_discussion]
        if ar.advice:
            md_lines += ['\n## Advice', ar.advice]
        if ar.roles:
            md_lines += ['\n## Roles of employees', ar.roles]
        if ar.skills:
            md_lines += ['\n## Skills required', ar.skills]
        if ar.tools:
            md_lines += ['\n## tools required', ar.tools]
            
        md = '\n\n'.join(md_lines)

        #GUI update
        output_display.delete('1.0', tk.END)
        output_display.insert(tk.END, md)

        #Save PDF
        html = markdown(md)
        company = ar.company_name.replace(' ', '_')
        filename = f'annual_report_{company}_{ar.fiscal_year_end}.pdf'
        HTML(string=html).write_pdf(filename)

        status_label.config(text=f"Success")
    except Exception as e:
        status_label.config(text="Error occurred", fg="red")
        messagebox.showerror("Error", str(e))



#GUI Layout
root = tk.Tk()
root.title("Summarizer")
root.geometry("900x900")

tk.Label(root, text="Enter PDF File Name:")

input_frame = tk.Frame(root)
input_frame.pack(pady=5)

file_input = tk.Entry(input_frame, width=50)
file_input.pack(side = tk.LEFT, padx = 5)

mic = tk.Button(input_frame, text="Microphone", command=start_voice)
mic.pack(side=tk.LEFT)


analyze_btn = tk.Button(root, text="Generate Summary", command=run_analysis)
analyze_btn.pack()

status_label = tk.Label(root, text="Waiting for input...", fg="gray")
status_label.pack()

output_display = scrolledtext.ScrolledText(root, width =70, height = 50)
output_display.pack(pady=10, padx=20)

root.mainloop()