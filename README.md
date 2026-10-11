# QueueCare

Local hackathon prototype: a patient-first clinic app where people check wait times and book appointments, and where emergencies alert the doctor immediately and show every other waiting patient a longer wait with the reason.

**Know your wait, skip the crowd, and never delay an emergency.**

This is **triage support, not a diagnosis**. In a real emergency, call an ambulance.

## Run locally

Python 3.10+ (3.11 works well). No Docker, no cloud.

From this folder (`queuecare/`):

```powershell
python -m pip install -r requirements.txt
python model/generate_data.py
python model/train.py
python test_logic.py
streamlit run app.py
```

The app also creates `queuecare.db` and trains `model/wait_model.pkl` automatically if they are missing, so `streamlit run app.py` after installing packages is enough.

## Clinic (demo)

| ID | Doctor | Specialty | Avg consult |
| --- | --- | --- | --- |
| 1 | Dr. Mehta | General Physician | 10 min |
| 2 | Dr. Sharma | Cardiologist | 15 min |
| 3 | Dr. Rao | Pediatrician | 12 min |

Slots every 15 minutes, 9:00 to 17:00.

Each waiting emergency adds `round(1.5 × avg consult)` minutes to other patients for that doctor (15 min extra on Doctor 1).

## Doctor login

Only the Doctor view requires a PIN; patients can check waits and book appointments without an account. For local use, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and replace the example values with private PINs. The real `secrets.toml` is ignored by Git. If no doctor PIN secrets are configured, the app uses demo PINs: Doctor 1 `1111`, Doctor 2 `2222`, and Doctor 3 `3333`.

## How to test the emergency flow

a) Open **Patient → Book Appointment**. Book two routine patients for **Doctor 1** (for example “mild cough” and “routine checkup”). Note each appointment ID and the wait shown on **My Appointment**.

b) Book a third patient for the same doctor with symptoms **chest pain**. Save that ID too.

c) Switch the sidebar to **Doctor**, select **Dr. Mehta**, and log in with PIN `1111` when using the demo PINs. You should see a red emergency banner with name, age, symptoms, matched keyword `chest pain`, and how many extra minutes this adds to other waits. The emergency is first in the colour-coded queue.

d) Go back to **Patient → My Appointment**, enter a **routine** appointment ID. Position, base wait, emergency delay, and total wait appear. You should see: *An emergency case was prioritized. Your wait increased by D min.*

e) On the Doctor page, click **Mark as Seen** on the emergency patient. After the 3-second refresh, the red banner is gone. Reload the routine ID: the extra delay disappears.

Shortcut: sidebar **Load demo data** books five Doctor 1 patients (four routine + one chest pain) so the delay message appears immediately. **Reset demo** clears the queue.

## Project layout

```
queuecare/
├── app.py
├── pages/
│   ├── patient.py
│   ├── doctor.py
│   └── performance.py
├── model/
│   ├── generate_data.py
│   ├── train.py
│   └── predict.py
├── logic/
│   ├── database.py
│   └── triage.py
├── test_logic.py
├── requirements.txt
└── README.md
```
