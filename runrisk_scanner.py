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
        """Clone le repository Git (deep clone limité à 1000 commits pour performance)."""
        print(f"Clonage de {self.repo_url}...", file=sys.stderr)
        try:
            # Clone avec profondeur limitée pour les grands repos
            subprocess.run(
                ['git', 'clone', '--depth', '1000', self.repo_url, self.repo_name],
                cwd=self.temp_dir,
                capture_output=True,
                text=True,
                check=True,
                timeout=120  # Timeout de 2 minutes
            )
            self.repo_path = os.path.join(self.temp_dir, self.repo_name)
            print(f"Repository cloné dans {self.repo_path}", file=sys.stderr)
            return True

        except subprocess.TimeoutExpired:
            print("Timeout: Le clonage a pris trop de temps (limite: 2 minutes)", file=sys.stderr)
            return False

        except subprocess.CalledProcessError as e:
            # Gestion correcte de l'erreur stderr
            error_msg = e.stderr if e.stderr else "Erreur inconnue"
            if isinstance(error_msg, bytes):
                error_msg = error_msg.decode('utf-8', errors='ignore')
            print(f"Erreur lors du clonage: {error_msg}", file=sys.stderr)
            return False

        except Exception as e:
            print(f"Erreur inattendue: {str(e)}", file=sys.stderr)
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
        except subprocess.TimeoutExpired:
            print("Timeout: Récupération du nombre de commits", file=sys.stderr)
            return 0
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
                    # Format: "1234\tJohn Doe <john@example.com>"
                    parts = line.strip().split('\t')
                    if len(parts) == 2:
                        try:
                            count = int(parts[0].strip())
                            author = parts[1].strip()
                            authors.append((author, count))
                        except ValueError:
                            continue
            return authors
        except subprocess.TimeoutExpired:
            print("Timeout: Récupération des auteurs", file=sys.stderr)
            return []
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
        except subprocess.TimeoutExpired:
            print("Timeout: Récupération des fichiers", file=sys.stderr)
            return 0
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
        except subprocess.TimeoutExpired:
            print("Timeout: Récupération des hotspots", file=sys.stderr)
            return []
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
        except subprocess.TimeoutExpired:
            print("Timeout: Récupération du code churn", file=sys.stderr)
            return 0
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
        except subprocess.TimeoutExpired:
            print("Timeout: Récupération de l'âge du projet", file=sys.stderr)
            return 0
        except:
            return 0

    def calculate_bus_factor(self, authors):
        """
        Calcule le bus factor (nombre minimum de développeurs dont 
        la perte mettrait le projet en danger).
        """
        if not authors:
            return 1

        total_commits = sum(count for _, count in authors)
        if total_commits == 0:
            return 1

        # Tri par nombre de commits décroissant
        sorted_authors = sorted(authors, key=lambda x: x[1], reverse=True)

        cumulative = 0
        bus_factor = 0
        threshold = 0.5  # 50% des commits

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

        # Pourcentage des commits par le contributeur principal
        top_contributor_pct = (max(counts) / total) * 100
        return round(top_contributor_pct, 1)

    def calculate_complexity(self, file_count, commit_count, authors_count):
        """Calcule un indice de complexité structurelle."""
        if file_count == 0:
            return "N/A"

        # Ratio commits par fichier
        commits_per_file = commit_count / max(1, file_count)

        if commits_per_file > 10:
            return "elevee"
        elif commits_per_file > 5:
            return "moyenne"
        else:
            return "faible"

    def calculate_risk_score(self, metrics):
        """
        Calcule le score de risque RUN (0-100).
        Plus le score est élevé, plus le risque est grand.
        """
        score = 0

        # Bus factor (plus c'est petit, plus c'est risqué)
        if metrics['bus_factor'] <= 1:
            score += 30
        elif metrics['bus_factor'] == 2:
            score += 20
        elif metrics['bus_factor'] == 3:
            score += 10

        # Concentration des connaissances
        if metrics['knowledge_concentration'] > 70:
            score += 25
        elif metrics['knowledge_concentration'] > 50:
            score += 15
        elif metrics['knowledge_concentration'] > 30:
            score += 5

        # Code churn
        if metrics['code_churn'] > 50:
            score += 20
        elif metrics['code_churn'] > 20:
            score += 10

        # Hotspots
        if metrics['hotspots_count'] > 10:
            score += 15
        elif metrics['hotspots_count'] > 5:
            score += 8

        # Taille du projet (complexité)
        if metrics['file_count'] > 500:
            score += 10
        elif metrics['file_count'] > 200:
            score += 5

        return min(100, score)

    def generate_recommendations(self, metrics):
        """Génère des recommandations basées sur les métriques."""
        recommendations = []

        if metrics['bus_factor'] <= 2:
            recommendations.append("Reduire la dependance a un expert - Bus factor critique")
            recommendations.append("Mettre en place du binomage sur les modules critiques")

        if metrics['knowledge_concentration'] > 50:
            recommendations.append("Documenter les modules critiques")
            recommendations.append("Equilibrer la repartition des contributions")

        if metrics['code_churn'] > 30:
            recommendations.append("Stabiliser les modules les plus modifies")
            recommendations.append("Analyser les causes du code churn eleve")

        if metrics['hotspots_count'] > 5:
            recommendations.append("Refactorer les hotspots critiques")
            recommendations.append("Cartographier les flux applicatifs")

        if metrics['file_count'] > 300:
            recommendations.append("Envisager une modularisation du code")

        if metrics['project_age_days'] > 365 * 3:  # Plus de 3 ans
            recommendations.append("Identifier et moderniser les modules legacy")

        # Recommendations par défaut si rien d'autre
        if not recommendations:
            recommendations = [
                "Maintenir la documentation a jour",
                "Surveiller l evolution des metriques",
                "Mettre en place des revues de code regulieres"
            ]

        return recommendations[:6]  # Max 6 recommandations

    def cleanup(self):
        """Nettoie les fichiers temporaires."""
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except:
                pass

    def analyze(self):
        """Exécute l'analyse complète."""
        if not self.clone_repository():
            return None

        print("Analyse en cours...", file=sys.stderr)

        # Collecte des métriques
        authors_data = self.get_authors()
        commit_count = self.get_commit_count()
        file_count = self.get_file_count()
        hotspots = self.get_hotspots(10)
        code_churn = self.get_code_churn()
        project_age = self.get_project_age_days()
        bus_factor = self.calculate_bus_factor(authors_data)
        knowledge_conc = self.calculate_knowledge_concentration(authors_data)
        complexity = self.calculate_complexity(file_count, commit_count, len(authors_data))

        metrics = {
            'repo_url': self.repo_url,
            'commit_count': commit_count,
            'authors_count': len(authors_data),
            'authors': [(a[0].split('<')[0].strip(), a[1]) for a in authors_data[:5]] if authors_data else [],
            'bus_factor': bus_factor,
            'knowledge_concentration': knowledge_conc,
            'code_churn': code_churn,
            'hotspots': hotspots,
            'hotspots_count': len(hotspots),
            'file_count': file_count,
            'project_age_days': project_age,
            'complexity': complexity,
            'risk_score': 0,
            'recommendations': []
        }

        # Calcul du score de risque
        metrics['risk_score'] = self.calculate_risk_score(metrics)

        # Génération des recommandations
        metrics['recommendations'] = self.generate_recommendations(metrics)

        return metrics


def print_diagnostic(metrics):
    """Affiche le diagnostic formaté."""
    print("\n" + "="*60)
    print("RUN RISK SCANNER - DIAGNOSTIC")
    print("="*60)

    # Score de risque
    print(f"\nRUN Risk Score : {metrics['risk_score']} / 100")
    if metrics['risk_score'] < 30:
        print("   Niveau: Risque faible")
    elif metrics['risk_score'] < 60:
        print("   Niveau: Risque modere")
    else:
        print("   Niveau: Risque eleve")

    # Analyse structurelle
    print("\nANALYSE STRUCTURELLE")
    print("-"*40)
    print(f"Developpeurs actifs      : {metrics['authors_count']}")
    print(f"Bus factor               : {metrics['bus_factor']}")
    print(f"Concentration savoir     : {metrics['knowledge_concentration']}%")
    print(f"Total commits            : {metrics['commit_count']}")
    print(f"Code churn               : {metrics['code_churn']} lignes/commit")
    print(f"Hotspots                 : {metrics['hotspots_count']} fichiers critiques")
    print(f"Age du projet            : {metrics['project_age_days']} jours")
    print(f"Nombre de fichiers       : {metrics['file_count']}")
    print(f"Complexite structurelle  : {metrics['complexity']}")

    # Top hotspots
    if metrics['hotspots']:
        print("\nHOTSPOTS (fichiers les plus modifies)")
        print("-"*40)
        for i, (file, count) in enumerate(metrics['hotspots'][:5], 1):
            display_file = file if len(file) <= 60 else file[:57] + "..."
            print(f"{i}. {display_file} ({count} modifications)")

    # Recommandations
    print("\nRECOMMANDATIONS")
    print("-"*40)
    for rec in metrics['recommendations']:
        print(f"  {rec}")

    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description='RUN Risk Scanner - Analyseur de risques Git')
    parser.add_argument('repo_url', help='URL du repository Git a analyser')
    parser.add_argument('--json', action='store_true', help='Sortie au format JSON')

    args = parser.parse_args()

    analyzer = GitAnalyzer(args.repo_url)

    try:
        metrics = analyzer.analyze()
        if metrics:
            if args.json:
                # Sortie JSON pour l'API
                print(json.dumps(metrics, indent=2))
            else:
                # Sortie formatée pour la ligne de commande
                print_diagnostic(metrics)
        else:
            error_msg = {"error": "L'analyse a echoue"}
            if args.json:
                print(json.dumps(error_msg))
            else:
                print("L'analyse a echoue.", file=sys.stderr)
            sys.exit(1)
    finally:
        analyzer.cleanup()


if __name__ == "__main__":
    main()