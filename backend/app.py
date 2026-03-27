from flask import Flask, request, jsonify
from flask_cors import CORS
import route_planner
import pandas as pd
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app)

route_planner.init_graphs()

# Pad naar CSV bestanden (zelfde map als app.py)
EMPLOYEES_CSV = os.path.join(os.path.dirname(__file__), 'medewerkers.csv')
CLIENTS_CSV = os.path.join(os.path.dirname(__file__), 'clienten.csv')

@app.route('/api/employees', methods=['GET'])
def get_employees():
    try:
        df = pd.read_csv(EMPLOYEES_CSV)
        # Zet om naar lijst van dicts
        employees = []
        for _, row in df.iterrows():
            dagen = str(row['Werkdagen']).split(';') if pd.notna(row['Werkdagen']) else []
            employees.append({
                'id': int(row.name) + 1,  # tijdelijke id
                'naam': row['Naam'],
                'email': row['Email'],
                'telefoon': row['Telefoon'],
                'straat': row['Straat'],
                'postcode': row['Postcode'],
                'stad': row['Stad'],
                'startTijd': row['Start Tijd'],
                'eindTijd': row['Eind Tijd'],
                'dagen': dagen,
                'dogs': 0,
                'cats': 0,
                'smokes': False
            })
        return jsonify(employees)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients', methods=['GET'])
def get_clients():
    try:
        df = pd.read_csv(CLIENTS_CSV)
        clients = []
        for _, row in df.iterrows():
            dagen = str(row['Dagen']).split(';') if pd.notna(row['Dagen']) else []
            tijdvensters = row['Tijdvensters'] if pd.notna(row['Tijdvensters']) else ''
            opmerkingen = row['Opmerkingen'] if pd.notna(row['Opmerkingen']) else ''
            clients.append({
                'id': int(row.name) + 1,
                'naam': row['Naam'],
                'telefoon': row['Telefoon'],
                'typeZorg': row['Type Zorg'],
                'duur': int(row['Duur (min)']),
                'straat': row['Straat'],
                'postcode': row['Postcode'],
                'stad': row['Stad'],
                'dagen': dagen,
                'tijdvensters': tijdvensters,
                'opmerkingen': opmerkingen,
                'heeft_hond': 'Hond' in opmerkingen,
                'heeft_kat': 'Kat' in opmerkingen,
                'rookt': 'Rookt' in opmerkingen
            })
        return jsonify(clients)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/plan', methods=['POST'])
def plan():
    data = request.get_json()
    employees = data.get('medewerkers', [])
    clients = data.get('clienten', [])

    emp_list = []
    for e in employees:
        emp_list.append({
            'id': e['id'],
            'naam': e['naam'],
            'dogs': e.get('dogs', 0),
            'cats': e.get('cats', 0),
            'smokes': e.get('smokes', False),
            'straat': e.get('straat', ''),
            'postcode': e.get('postcode', ''),
            'stad': e.get('stad', '')
        })

    cl_list = []
    for c in clients:
        cl_list.append({
            'id': c['id'],
            'naam': c['naam'],
            'heeft_hond': c.get('heeft_hond', False),
            'heeft_kat': c.get('heeft_kat', False),
            'rookt': c.get('rookt', False),
            'duur': c.get('duur', 60),
            'tijdvensters': c.get('tijdvensters', ''),
            'straat': c.get('straat', ''),
            'postcode': c.get('postcode', ''),
            'stad': c.get('stad', '')
        })

    try:
        result, status = route_planner.plan_routes(emp_list, cl_list, transport_mode='auto')
        if result is None:
            return jsonify({'error': f'Planning mislukt: {status}'}), 500
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/plan_week', methods=['POST'])
def plan_week():
    data = request.get_json()
    week_offset = data.get('week_offset', 0)
    employees = data.get('medewerkers', [])
    clients = data.get('clienten', [])

    emp_list = []
    for e in employees:
        emp_list.append({
            'id': e['id'],
            'naam': e['naam'],
            'dogs': e.get('dogs', 0),
            'cats': e.get('cats', 0),
            'smokes': e.get('smokes', False),
            'straat': e.get('straat', ''),
            'postcode': e.get('postcode', ''),
            'stad': e.get('stad', ''),
            'werkdagen': e.get('werkdagen', [])
        })

    cl_list = []
    for c in clients:
        cl_list.append({
            'id': c['id'],
            'naam': c['naam'],
            'heeft_hond': c.get('heeft_hond', False),
            'heeft_kat': c.get('heeft_kat', False),
            'rookt': c.get('rookt', False),
            'duur': c.get('duur', 60),
            'tijdvensters': c.get('tijdvensters', ''),
            'straat': c.get('straat', ''),
            'postcode': c.get('postcode', ''),
            'stad': c.get('stad', ''),
            'dagen': c.get('dagen', [])
        })

    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    week_start = monday + timedelta(weeks=week_offset)

    try:
        result = route_planner.plan_week(emp_list, cl_list, week_start, transport_mode='auto')
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)