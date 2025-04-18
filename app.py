from flask import Flask, render_template, request, send_file
import firebase_admin
from firebase_admin import credentials, firestore
import csv
import os
from datetime import datetime

app = Flask(__name__)

cred = credentials.Certificate("etricks-bms-firebase-adminsdk-fbsvc-e0019cb086.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

@app.route("/", methods=["GET"])
def index():
    docs = db.collection("Journal-bms").stream()
    bms_list = [doc.id for doc in docs]
    return render_template("index.html", bms_list=bms_list)

@app.route("/export", methods=["POST"])
def export():
    bms_name = request.form["bms_name"]
    doc = db.collection("Journal-bms").document(bms_name).get()

    if not doc.exists:
        return f"BMS {bms_name} introuvable", 404

    data = doc.to_dict()
    
    now = datetime.now()
    timestamp = now.strftime("%d-%m-%Y_%H-%M")
    filename = f"{bms_name}_{timestamp}.csv"
    filepath = os.path.join("exports", filename)

    os.makedirs("exports", exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, delimiter=",", quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(["Date", "Version Firmware + Data + Derniere erreur"])
        for horodatage, payload in sorted(data.items()):
            writer.writerow([horodatage, str(payload).replace("\n", " ").replace("\r", "")])

    return send_file(filepath, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)

