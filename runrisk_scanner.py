#!/usr/bin/env python3
"""
RUN Risk Scanner - Moteur d'analyse Git
Analyse un repository Git et calcule des métriques de risque structurel.
"""

import os
import sys
import json
import tempfile
import subprocess
import shutil
import re
from collections import Counter
import argparse


class GitAnalyzer:
    def __init__(self, repo_url):
        self.repo_url = repo_url
        self.repo_name = repo_url.split('/')[-1].replace('.git', '')
        self.temp_dir = tempfile.mkdtemp(prefix="runrisk_")
        self.repo_path = None

    def clone_repository(self):
      def clone_repository(self):
    """Clone le repository Git (deep clone limité à 1000 commits pour performance)."""
    print(f"Clonage de {self.repo_url}...", file=sys.stderr)
    try:
        # Vérifier que git est installé
        try:
            subprocess.run(['git', '--version'], capture_output=True, check=True)
        except:
            print("Git n'est pas installé ou n'est pas dans le PATH", file=sys.stderr)
            return False
            
        # Clone sans check=True pour gérer les erreurs nous-mêmes
        result = subprocess.run(
            ['git', 'clone', '--depth', '1000', self.repo_url, self.repo_name],
            cwd=self.temp_dir,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else "Erreur inconnue"
            print(f"Erreur lors du clonage: {error_msg}", file=sys.stderr)
            return False
            
        self.repo_path = os.path.join(self.temp_dir, self.repo_name)
        print(f"Repository cloné dans {self.repo_path}", file=sys.stderr)
        return True

    except subprocess.TimeoutExpired:
        print("Timeout: Le clonage a pris trop de temps", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Erreur inattendue: {str(e)}", file=sys.stderr)
        return False
            return False

    def get_commit_count(self):
        """Retourne le nombre total de commits."""
        try:
            result = subprocess.run(
                ['git', 'rev-list', '--count', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            return int(result.stdout.strip())
        except:
            return 0

    def get_authors(self):
        """Retourne la liste des auteurs et leur nombre de commits."""
        try:
            result = subprocess.run(
                ['git', 'shortlog', '-sne', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            authors = []
            for line in result.stdout.strip().split('\n'):
                if line and line.strip():
                    parts = line.strip().split('\t')
                    if len(parts) == 2:
                        try:
                            count = int(parts[0].strip())
                            author = parts[1].strip()
                            authors.append((author, count))
                        except ValueError:
                            continue
            return authors
        except:
            return []

    def get_file_count(self):
        """Compte le nombre de fichiers dans le repository."""
        try:
            result = subprocess.run(
                ['git', 'ls-files'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            files = result.stdout.strip().split('\n')
            return len([f for f in files if f and f.strip()])
        except:
            return 0

    def get_hotspots(self, top_n=10):
        """Identifie les fichiers les plus modifiés."""
        try:
            result = subprocess.run(
                ['git', 'log', '--pretty=format:', '--name-only'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )
            files = [f for f in result.stdout.strip().split('\n') if f and f.strip()]
            hotspots = Counter(files).most_common(top_n)
            return hotspots
        except:
            return []

    def get_code_churn(self):
        """Calcule le code churn (modifications moyennes par commit)."""
        try:
            result = subprocess.run(
                ['git', 'log', '--shortstat'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )
            total_insertions = 0
            total_deletions = 0
            commit_count = 0

            for line in result.stdout.split('\n'):
                if 'insertion' in line or 'deletion' in line:
                    insertions = re.search(r'(\d+) insertion', line)
                    deletions = re.search(r'(\d+) deletion', line)

                    if insertions:
                        total_insertions += int(insertions.group(1))
                    if deletions:
                        total_deletions += int(deletions.group(1))
                    commit_count += 1

            if commit_count == 0:
                return 0
            return (total_insertions + total_deletions) // commit_count
        except:
            return 0

    def get_project_age_days(self):
        """Calcule l'âge du projet en jours."""
        try:
            result = subprocess.run(
                ['git', 'log', '--reverse', '--pretty=format:%ct', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            timestamps = result.stdout.strip().split('\n')
            if len(timestamps) < 2:
                return 0

            first_commit = int(timestamps[0])
            last_commit = int(timestamps[-1])
            return (last_commit - first_commit) // (60 * 60 * 24)
        except:
            return 0

    def get_recent_activity(self):
        """Évalue l'activité récente (30 derniers jours)."""
        try:
            result = subprocess.run(
                ['git', 'log', '--since', '30 days ago', '--pretty=format:%h'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            commits_last_30 = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            
            if commits_last_30 > 50:
                return "Très active"
            elif commits_last_30 > 20:
                return "Active"
            elif commits_last_30 > 5:
                return "Modérée"
            else:
                return "Faible"
        except:
            return "Inconnue"

    def calculate_bus_factor(self, authors):
        """Calcule le bus factor."""
        if not authors:
            return 1

        total_commits = sum(count for _, count in authors)
        if total_commits == 0:
            return 1

        sorted_authors = sorted(authors, key=lambda x: x[1], reverse=True)

        cumulative = 0
        bus_factor = 0
        threshold = 0.5

        for _, count in sorted_authors:
            cumulative += count
            bus_factor += 1
            if cumulative / total_commits >= threshold:
                break

        return max(1, bus_factor)

    def calculate_knowledge_concentration(self, authors):
        """Calcule la concentration des connaissances."""
        if not authors:
            return 0

        counts = [count for _, count in authors]
        total = sum(counts)
        if total == 0:
            return 0

        top_contributor_pct = (max(counts) / total) * 100
        return round(top_contributor_pct, 1)
def calculate_complexity(self, file_count, commit_count):
    """Calcule un indice de complexité structurelle."""
    if file_count == 0:
        return "N/A"

    commits_per_file = commit_count / max(1, file_count)

    if commits_per_file > 10:
        return "Elevée"
    elif commits_per_file > 5:
        return "Moyenne"
    else:
        return "Faible"
    def calculate_risk_score(self, metrics):
        """Calcule le score de risque RUN (0-100)."""
        score = 0

        if metrics['bus_factor'] <= 1:
            score += 30
        elif metrics['bus_factor'] == 2:
            score += 20
        elif metrics['bus_factor'] == 3:
            score += 10

        if metrics['knowledge_concentration'] > 70:
            score += 25
        elif metrics['knowledge_concentration'] > 50:
            score += 15
        elif metrics['knowledge_concentration'] > 30:
            score += 5

        if metrics['code_churn'] > 50:
            score += 20
        elif metrics['code_churn'] > 20:
            score += 10

        if metrics['hotspots_count'] > 10:
            score += 15
        elif metrics['hotspots_count'] > 5:
            score += 8

        if metrics['file_count'] > 500:
            score += 10
        elif metrics['file_count'] > 200:
            score += 5

        return min(100, score)

   def generate_recommendations(self, metrics):
    """Génère des recommandations."""
    recommendations = []

    if metrics['bus_factor'] <= 2:
        recommendations.append("Reduire la dependance a un seul developpeur")
        recommendations.append("Mettre en place du binomage sur les modules critiques")

    if metrics['knowledge_concentration'] > 50:
        recommendations.append("Renforcer la documentation des modules critiques")
        recommendations.append("Equilibrer la repartition des contributions")

    if metrics['code_churn'] > 30:
        recommendations.append("Stabiliser les modules les plus modifies")
        recommendations.append("Analyser les causes du code churn eleve")

    if metrics['hotspots_count'] > 5:
        recommendations.append("Refactorer les hotspots critiques")
        recommendations.append("Cartographier les flux applicatifs")

    if metrics['file_count'] > 300:
        recommendations.append("Envisager une modularisation du code")

    if metrics['project_age_days'] > 365 * 3:
        recommendations.append("Identifier et moderniser les modules legacy")

    if not recommendations:
        recommendations = [
            "Maintenir la documentation a jour",
            "Surveiller l evolution des metriques",
            "Mettre en place des revues de code regulieres"
        ]

    return recommendations[:6]



