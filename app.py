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

    # Récupérer les paramètres de filtrage
    sort_by = request.args.get("sort_by", "name")  # Default: tri par nom
    search_term = request.args.get("search", "").lower()
    
    # Récupérer tous les documents BMS
    docs = db.collection("Journal-bms").stream()
    
    # Créer une liste de BMS avec leurs métadonnées
    bms_data = []
    for doc in docs:
        bms_name = doc.id
        bms_info = doc.to_dict()
        
        # Trouvez la date la plus récente pour ce BMS
        latest_timestamp = None
        if bms_info:
            try:
                # Convertir les clés (timestamps) en objets datetime pour le tri
                dates = [datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") 
                         for ts in bms_info.keys() if ts]
                if dates:
                    latest_timestamp = max(dates)
            except (ValueError, TypeError):
                # En cas d'erreur de format de date, on continue simplement
                pass
        
        # Ajouter aux données seulement si correspond au terme de recherche
        if search_term in bms_name.lower():
            bms_data.append({
                "name": bms_name,
                "last_connection": latest_timestamp
            })
    
    # Trier les BMS selon le critère sélectionné
    if sort_by == "recent":
        # Trier par date la plus récente d'abord, puis par nom pour les BMS sans date
        bms_data.sort(key=lambda x: (x["last_connection"] is None, 
                                    "" if x["last_connection"] is None else -x["last_connection"].timestamp(), 
                                    x["name"]))
    else:  # sort_by == "name"
        bms_data.sort(key=lambda x: x["name"])
    
    # Formater les dates pour l'affichage
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