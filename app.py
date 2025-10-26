from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)
DATA_FILE = "buracos.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/buracos", methods=["GET"])
def listar_buracos():
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/registrar", methods=["POST"])
def registrar_buraco():
    novo_buraco = request.get_json()
    if not novo_buraco or "lat" not in novo_buraco or "lng" not in novo_buraco:
        return jsonify({"erro": "Dados inválidos"}), 400

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    data.append(novo_buraco)

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return jsonify({"status": "Buraco registrado com sucesso!"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
