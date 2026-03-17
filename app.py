#!/usr/bin/env python3
"""
RUN Risk Scanner - Serveur Flask
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import subprocess
import json
import os
import sys
import tempfile
import shutil

app = Flask(__name__, 
            static_url_path='', 
            static_folder='.',
            template_folder='.')
CORS(app)

# Route pour la page d'accueil
@app.route('/')
def index():
    return send_file('index.html')

# Route pour la page scanner
@app.route('/scanner')
def scanner():
    return send_file('scanner.html')

# Route pour l'analyse
@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    
    if not data or 'repo_url' not in data:
        return jsonify({'error': 'URL du repository manquante'}), 400
    
    repo_url = data['repo_url']
    
    try:
        # Exécution du script Python avec l'option --json
        result = subprocess.run(
            [sys.executable, 'runRiskScanner.py', repo_url, '--json'],
            capture_output=True,
            text=True,
            check=True,
            timeout=300  # Timeout de 5 minutes
        )
        
        # Parser la sortie JSON
        output_lines = result.stdout.strip().split('\n')
        json_output = None
        
        for line in reversed(output_lines):
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                try:
                    json_output = json.loads(line)
                    break
                except:
                    continue
        
        if json_output:
            return jsonify(json_output)
        else:
            return jsonify({'error': 'Format de réponse invalide du scanner'}), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout - L\'analyse a pris trop de temps'}), 408
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        return jsonify({'error': f'Erreur lors de l\'analyse: {error_msg}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route pour la plaquette
@app.route('/plaquetteRunRiskV12.pdf')
def plaquette():
    try:
        return send_file('plaquetteRunRiskV12.pdf')
    except:
        return "Fichier non trouvé", 404

# Route pour le logo
@app.route('/logo.png')
def logo():
    try:
        return send_file('logo.png')
    except:
        return "Fichier non trouvé", 404

if __name__ == '__main__':
    # Vérifier que les fichiers nécessaires existent
    required_files = ['index.html', 'scanner.html', 'runRiskScanner.py']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"Fichiers manquants: {', '.join(missing_files)}")
        sys.exit(1)
    
    print("Serveur RUN Risk Scanner démarré sur http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)