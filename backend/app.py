from flask import Flask, request, jsonify
from flask_cors import CORS
import route_planner
import pandas as pd
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app)

route_planner.init_graphs()

# Pad naar CSV bestanden in de output map
EMPLOYEES_CSV = os.path.join(os.path.dirname(__file__), '..', 'output', 'employees.csv')
CLIENTS_CSV = os.path.join(os.path.dirname(__file__), '..', 'output', 'clients.csv')

@app.route('/api/employees', methods=['GET'])
def get_employees():
    try:
        df = pd.read_csv(EMPLOYEES_CSV)
        cols = df.columns.tolist()

        # Ondersteuning voor zowel Nederlandse als Engelse kolomnamen
        def col(nl, en):
            return nl if nl in cols else en

        employees = []
        for idx, row in df.iterrows():
            dag_col = col('Werkdagen', 'working_days')
            dagen_raw = str(row[dag_col]) if dag_col in cols and pd.notna(row.get(dag_col)) else ''
            dagen = [d.strip() for d in dagen_raw.split(';') if d.strip()] if dagen_raw and dagen_raw != 'nan' else []

            employees.append({
                'id': int(idx) + 1,
                'naam': row.get(col('Naam', 'name'), ''),
                'email': row.get(col('Email', 'email'), ''),
                'telefoon': row.get(col('Telefoon', 'phone'), ''),
                'straat': row.get(col('Straat', 'street'), ''),
                'postcode': row.get(col('Postcode', 'postal_code'), ''),
                'stad': row.get(col('Stad', 'city'), ''),
                'startTijd': str(row.get(col('Start Tijd', 'start_time'), '08:00')),
                'eindTijd': str(row.get(col('Eind Tijd', 'end_time'), '17:00')),
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
        cols = df.columns.tolist()

        def col(nl, en):
            return nl if nl in cols else en

        clients = []
        for idx, row in df.iterrows():
            dag_col = col('Dagen', 'days')
            dagen_raw = str(row[dag_col]) if dag_col in cols and pd.notna(row.get(dag_col)) else ''
            dagen = [d.strip() for d in dagen_raw.split(';') if d.strip()] if dagen_raw and dagen_raw != 'nan' else []

            tijdvensters = str(row.get(col('Tijdvensters', 'time_windows'), '') or '')
            opmerkingen = str(row.get(col('Opmerkingen', 'notes'), '') or '')
            if opmerkingen == 'nan':
                opmerkingen = ''

            clients.append({
                'id': int(idx) + 1,
                'naam': row.get(col('Naam', 'name'), ''),
                'telefoon': row.get(col('Telefoon', 'phone'), ''),
                'typeZorg': row.get(col('Type Zorg', 'care_type'), ''),
                'duur': int(row.get(col('Duur (min)', 'duration_min'), 60) or 60),
                'straat': row.get(col('Straat', 'street'), ''),
                'postcode': row.get(col('Postcode', 'postal_code'), ''),
                'stad': row.get(col('Stad', 'city'), ''),
                'dagen': dagen,
                'tijdvensters': tijdvensters if tijdvensters != 'nan' else '',
                'opmerkingen': opmerkingen,
                'heeft_hond': 'hond' in opmerkingen.lower(),
                'heeft_kat': 'kat' in opmerkingen.lower(),
                'rookt': 'rookt' in opmerkingen.lower()
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