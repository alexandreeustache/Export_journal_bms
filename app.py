from flask import Flask, render_template, request, send_file, redirect, url_for, session
import firebase_admin
from firebase_admin import credentials, firestore
import csv
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key")


cred = credentials.Certificate("etricks-bms-firebase-adminsdk-fbsvc-e0019cb086.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def extraire_date_bms(content):
    try:
        # Supposons que la date est à la fin, comme : "2025/04/30"
        date_str = content.strip().split()[-3]  # Exemple : '2025/04/30'
        return datetime.strptime(date_str, "%Y/%m/%d")
    except Exception:
        return None


def get_bms_data(sort_by=None, search_term=None):
    bms_docs = db.collection('bms').stream()
    bms_list = []

    for doc in bms_docs:
        name = doc.id
        content = doc.to_dict().get("data", "")
        date_obj = extraire_date_bms(content)
        last_connection_str = date_obj.strftime("%d/%m/%Y") if date_obj else "Inconnue"

        if search_term and search_term.lower() not in name.lower():
            continue

        bms_list.append({
            "name": name,
            "content": content,
            "last_connection": date_obj,
            "last_connection_str": last_connection_str
        })

    # Appliquer le tri
    if sort_by == "recent":
        bms_list.sort(key=lambda b: b["last_connection"] or datetime.min, reverse=True)
    elif sort_by == "name_asc":
        bms_list.sort(key=lambda b: b["name"])
    elif sort_by == "name_desc":
        bms_list.sort(key=lambda b: b["name"], reverse=True)

    return bms_list


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form["password"]
        if password == "etricks": 
            session["authenticated"] = True
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Mot de passe incorrect")
    return render_template("login.html")


@app.route("/", methods=["GET"])
def index():
    if not session.get("authenticated"):
        return redirect(url_for("login"))

    sort_by = request.args.get("sort_by", "name_asc")
    search_term = request.args.get("search", "").lower()

    docs = db.collection("Journal-bms").stream()

    bms_data = []
    for doc in docs:
        bms_name = doc.id
        bms_info = doc.to_dict()

        # Filtrage côté serveur (optionnel)
        if search_term and search_term not in bms_name.lower():
            continue

        latest_timestamp = extraire_date_bms(bms_info) if bms_info else None

        bms_data.append({
            "name": bms_name,
            "last_connection": latest_timestamp
        })

    # Tri
    if sort_by == "name_asc":
        bms_data.sort(key=lambda x: x["name"])
    elif sort_by == "name_desc":
        bms_data.sort(key=lambda x: x["name"], reverse=True)
    elif sort_by == "recent":
        bms_data.sort(key=lambda x: (x["last_connection"] is None,
                                     datetime.min if x["last_connection"] is None else -x["last_connection"].timestamp(),
                                     x["name"]))
    else:
        bms_data.sort(key=lambda x: x["name"])

    # Format d'affichage
    for bms in bms_data:
        if bms["last_connection"]:
            bms["last_connection_str"] = bms["last_connection"].strftime("%d-%m-%Y %H:%M")
        else:
            bms["last_connection_str"] = "Inconnue"

    return render_template("index.html",
                           bms_data=bms_data,
                           sort_by=sort_by,
                           search_term=search_term)

@app.route("/export", methods=["POST"])
def export():
    if not session.get("authenticated"):
        return redirect(url_for("login"))
    
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