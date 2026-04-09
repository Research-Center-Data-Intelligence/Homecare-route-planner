import os
import pandas as pd
import numpy as np
import networkx as nx
from shapely import wkt
from scipy.spatial import cKDTree
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
from datetime import datetime
import time

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# ---------- 1. Wegennet laden ----------
EDGES_PATH = '../output/heerlen_edge_table.csv'
G = None
node_coords = {}
edge_geom = {}
kd_tree = None

if os.path.exists(EDGES_PATH):
    edges_df = pd.read_csv(EDGES_PATH)
    edges_df['geometry'] = edges_df['geometry'].apply(wkt.loads)
    G = nx.Graph()
    for _, row in edges_df.iterrows():
        geom = row['geometry']
        coords = list(geom.coords)
        u, v = row['u'], row['v']
        G.add_edge(u, v, weight=row['travel_time_min'], geometry=geom)
        node_coords[u] = (coords[0][0], coords[0][1])
        node_coords[v] = (coords[-1][0], coords[-1][1])
        edge_geom[(u, v)] = geom
        edge_geom[(v, u)] = geom
    node_ids = list(node_coords.keys())
    node_lons_arr = np.array([node_coords[n][0] for n in node_ids])
    node_lats_arr = np.array([node_coords[n][1] for n in node_ids])
    kd_tree = cKDTree(np.column_stack((node_lons_arr, node_lats_arr)))
    print("Wegennet geladen")
else:
    print(f"Waarschuwing: {EDGES_PATH} niet gevonden. Routing niet mogelijk.")

def nearest_node(lon, lat):
    if kd_tree is None:
        return 0
    _, idx = kd_tree.query([lon, lat])
    return node_ids[idx]

# ---------- 2. Geocoding (fallback) ----------
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
geolocator = Nominatim(user_agent="thuiszorg_planner")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)  # 1 sec tussen requests

def geocode_address(straat, postcode, stad):
    cache_file = 'geocode_cache.json'
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache = json.load(f)
    key = f"{straat}, {postcode} {stad}".lower()
    if key in cache:
        return cache[key]
    try:
        loc = geocode(f"{straat}, {postcode} {stad}, Nederland")
        if loc:
            result = (loc.latitude, loc.longitude)
            cache[key] = result
            with open(cache_file, 'w') as f:
                json.dump(cache, f)
            return result
    except Exception as e:
        print(f"Geocoding fout: {e}")
    return None, None

# ---------- 3. CSV laden en opslaan ----------
EMPLOYEES_CSV = 'employees.csv'
CLIENTS_CSV = 'clients.csv'

def parse_coordinates(coord_str):
    try:
        parts = coord_str.strip().split()
        return float(parts[0]), float(parts[1])
    except:
        return None, None

def load_employees():
    if not os.path.exists(EMPLOYEES_CSV):
        return []
    df = pd.read_csv(EMPLOYEES_CSV)
    employees = []
    for _, row in df.iterrows():
        lat, lon = parse_coordinates(row['coordinates'])
        if lat is None:
            continue
        smokes_val = row.get('smokes', False)
        if isinstance(smokes_val, str):
            smokes = smokes_val.lower() == 'true'
        else:
            smokes = bool(smokes_val)
        emp = {
            'id': hash(row['name']) % 1000000,
            'naam': row['name'],
            'email': '',
            'telefoon': '',
            'straat': row['address'].split(',')[0] if ',' in row['address'] else row['address'],
            'postcode': '',
            'stad': 'Heerlen',
            'startTijd': row['time_window_start'],
            'eindTijd': row['time_window_end'],
            'dagen': ['monday','tuesday','wednesday','thursday','friday'],
            'lat': lat,
            'lon': lon,
            'dogs': int(row.get('dogs', -1)),
            'cats': int(row.get('cats', -1)),
            'smokes': smokes
        }
        employees.append(emp)
    return employees

def load_clients():
    if not os.path.exists(CLIENTS_CSV):
        return []
    df = pd.read_csv(CLIENTS_CSV)
    clients = []
    for _, row in df.iterrows():
        lat, lon = parse_coordinates(row['coordinates'])
        if lat is None:
            continue
        care_hours = float(row.get('care_hours', 1.0))
        duur = int(care_hours * 60)
        tijdvensters = f"{row['time_window_start']}-{row['time_window_end']}"
        smokes_val = row.get('smokes', False)
        if isinstance(smokes_val, str):
            rookt = smokes_val.lower() == 'true'
        else:
            rookt = bool(smokes_val)
        cl = {
            'id': hash(row['name']) % 1000000,
            'naam': row['name'],
            'telefoon': '',
            'typeZorg': row.get('care_arrangement', ''),
            'duur': duur,
            'straat': row['address'].split(',')[0] if ',' in row['address'] else row['address'],
            'postcode': '',
            'stad': 'Heerlen',
            'dagen': ['monday','tuesday','wednesday','thursday','friday'],
            'tijdvensters': tijdvensters,
            'opmerkingen': '',
            'lat': lat,
            'lon': lon,
            'heeft_hond': int(row.get('dogs', 0)) > 0,
            'heeft_kat': int(row.get('cats', 0)) > 0,
            'rookt': rookt
        }
        clients.append(cl)
    return clients

def save_employees(employees):
    data = []
    for emp in employees:
        data.append({
            'name': emp['naam'],
            'address': f"{emp['straat']}, Heerlen",
            'coordinates': f"{emp['lat']} {emp['lon']}",
            'time_window_start': emp['startTijd'],
            'time_window_end': emp['eindTijd'],
            'dogs': emp['dogs'],
            'cats': emp['cats'],
            'smokes': emp['smokes']
        })
    df = pd.DataFrame(data)
    df.to_csv(EMPLOYEES_CSV, index=False)

def save_clients(clients):
    data = []
    for cl in clients:
        data.append({
            'name': cl['naam'],
            'address': f"{cl['straat']}, Heerlen",
            'coordinates': f"{cl['lat']} {cl['lon']}",
            'care_arrangement': cl['typeZorg'],
            'preferences': '',
            'time_window_start': cl['tijdvensters'].split('-')[0] if '-' in cl['tijdvensters'] else '08:00',
            'time_window_end': cl['tijdvensters'].split('-')[1] if '-' in cl['tijdvensters'] else '18:00',
            'care_hours': cl['duur'] / 60,
            'dogs': 1 if cl['heeft_hond'] else 0,
            'cats': 1 if cl['heeft_kat'] else 0,
            'smokes': cl['rookt']
        })
    df = pd.DataFrame(data)
    df.to_csv(CLIENTS_CSV, index=False)

# ---------- 4. OR-Tools VRP ----------
def solve_vrp(employees_from_frontend, clients_from_frontend, week_offset=0):
    if G is None:
        return {'error': 'Wegennet niet beschikbaar. Kan geen planning maken.'}
    
    employees = load_employees()
    clients = load_clients()
    if not employees or not clients:
        return {'error': 'Geen medewerkers of cliënten in CSV'}
    
    dag_index = {'monday':0,'tuesday':1,'wednesday':2,'thursday':3,'friday':4}
    
    for emp in employees:
        if 'node' not in emp:
            emp['node'] = nearest_node(emp['lon'], emp['lat'])
    
    for cl in clients:
        if 'node' not in cl:
            cl['node'] = nearest_node(cl['lon'], cl['lat'])
        if 'tijdvensters' in cl and cl['tijdvensters']:
            parts = cl['tijdvensters'].split(';')[0].split('-')
            if len(parts) == 2:
                start_h, start_m = map(int, parts[0].split(':'))
                end_h, end_m = map(int, parts[1].split(':'))
                cl['tw_min'] = start_h*60 + start_m - 420
                cl['tw_max'] = end_h*60 + end_m - 420
            else:
                cl['tw_min'] = 0
                cl['tw_max'] = 660
        else:
            cl['tw_min'] = 0
            cl['tw_max'] = 660
        cl['care_min'] = cl.get('duur', 60)
    
    N_EMPLOYEES = len(employees)
    N_CLIENTS = len(clients)
    N_TOTAL = N_EMPLOYEES + N_CLIENTS
    SCALE = 100
    
    all_nodes = [emp['node'] for emp in employees] + [cl['node'] for cl in clients]
    
    time_matrix = np.zeros((N_TOTAL, N_TOTAL), dtype=np.int64)
    for i, src in enumerate(all_nodes):
        lengths = nx.single_source_dijkstra_path_length(G, src, weight='weight')
        for j, dst in enumerate(all_nodes):
            t = lengths.get(dst, float('inf'))
            time_matrix[i][j] = int(t * SCALE) if t != float('inf') else 10_000_000
    
    vehicles = []
    for emp_id, emp in enumerate(employees):
        werkdagen = emp.get('dagen', [])
        for dag in werkdagen:
            if dag in dag_index:
                vehicles.append({
                    'vehicle_id': len(vehicles),
                    'emp_id': emp_id,
                    'day': dag_index[dag],
                    'start_node': emp_id,
                    'end_node': emp_id
                })
    N_VEHICLES = len(vehicles)
    if N_VEHICLES == 0:
        return {'error': 'Geen medewerkers met werkdagen'}
    
    data = {
        'time_matrix': time_matrix.tolist(),
        'num_vehicles': N_VEHICLES,
        'starts': [v['start_node'] for v in vehicles],
        'ends': [v['end_node'] for v in vehicles],
        'demands': [0]*N_EMPLOYEES + [1]*N_CLIENTS,
        'capacities': [3]*N_VEHICLES
    }
    
    service_time = [0]*N_EMPLOYEES + [cl['care_min'] for cl in clients]
    time_windows = [(0, 660)]*N_EMPLOYEES
    for cl in clients:
        time_windows.append((cl['tw_min'], cl['tw_max']))
    
    manager = pywrapcp.RoutingIndexManager(N_TOTAL, N_VEHICLES, data['starts'], data['ends'])
    routing = pywrapcp.RoutingModel(manager)
    
    def total_time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        travel = data['time_matrix'][from_node][to_node]
        service = service_time[from_node] * SCALE
        return travel + service
    
    transit_callback = routing.RegisterTransitCallback(total_time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback)
    
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, data['capacities'], True, 'Capacity')
    
    routing.AddDimension(transit_callback, 0, 660*SCALE, False, 'Time')
    time_dim = routing.GetDimensionOrDie('Time')
    for node in range(N_TOTAL):
        index = manager.NodeToIndex(node)
        tw_min, tw_max = time_windows[node]
        time_dim.CumulVar(index).SetRange(tw_min*SCALE, tw_max*SCALE)
    
    MAX_WORK = 360 * SCALE
    for v in range(N_VEHICLES):
        time_dim.SetSpanUpperBoundForVehicle(MAX_WORK, v)
    
    compatible_emp_per_client = []
    for cid, cl in enumerate(clients):
        compat = []
        for emp_id, emp in enumerate(employees):
            if emp.get('dogs', -1) != -1 and cl.get('heeft_hond', False) and cl['heeft_hond'] > emp['dogs']:
                continue
            if emp.get('cats', -1) != -1 and cl.get('heeft_kat', False) and cl['heeft_kat'] > emp['cats']:
                continue
            if not emp.get('smokes', False) and cl.get('rookt', False):
                continue
            compat.append(emp_id)
        compatible_emp_per_client.append(compat)
    
    solver = routing.solver()
    for cid in range(N_CLIENTS):
        node_idx = manager.NodeToIndex(N_EMPLOYEES + cid)
        if not compatible_emp_per_client[cid]:
            routing.AddDisjunction([node_idx], 10_000_000)
        else:
            vehicle_var = routing.VehicleVar(node_idx)
            for v in range(N_VEHICLES):
                emp_id = vehicles[v]['emp_id']
                if emp_id not in compatible_emp_per_client[cid]:
                    solver.Add(vehicle_var != v)
    
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_params.time_limit.seconds = 120
    
    solution = routing.SolveWithParameters(search_params)
    if not solution:
        return {'error': 'Geen oplossing gevonden'}
    
    routes_per_day = {day: [] for day in ['monday','tuesday','wednesday','thursday','friday']}
    unassigned = []
    
    for v in range(N_VEHICLES):
        index = routing.Start(v)
        nodes = []
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            nodes.append(node)
            index = solution.Value(routing.NextVar(index))
        nodes.append(manager.IndexToNode(index))
        client_ids = [n - N_EMPLOYEES for n in nodes if n >= N_EMPLOYEES]
        if not client_ids:
            continue
        emp_id = vehicles[v]['emp_id']
        day = vehicles[v]['day']
        day_name = list(routes_per_day.keys())[day]
        bezoeken = []
        for cid in client_ids:
            cl = clients[cid]
            bezoeken.append({
                'client_id': cl['id'],
                'client_naam': cl['naam'],
                'duur': cl['care_min']
            })
        routes_per_day[day_name].append({
            'medewerker_id': employees[emp_id]['id'],
            'medewerker_naam': employees[emp_id]['naam'],
            'bezoeken': bezoeken
        })
    
    geplande_client_ids = set()
    for day in routes_per_day:
        for route in routes_per_day[day]:
            for b in route['bezoeken']:
                geplande_client_ids.add(b['client_id'])
    for cl in clients:
        if cl['id'] not in geplande_client_ids:
            unassigned.append({
                'id': cl['id'],
                'naam': cl['naam'],
                'duur': cl.get('duur', 60)
            })
    
    result = {day: routes_per_day[day] for day in routes_per_day}
    result['unassigned'] = unassigned
    return result

# ---------- 5. Flask routes ----------
@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'dashboard.html')

@app.route('/api/employees', methods=['GET'])
def get_employees():
    employees = load_employees()
    colors = ['blue','green','purple','orange']
    for i, emp in enumerate(employees):
        emp['color'] = colors[i % len(colors)]
    return jsonify(employees)

@app.route('/api/clients', methods=['GET'])
def get_clients():
    clients = load_clients()
    return jsonify(clients)

@app.route('/api/upload/employees', methods=['POST'])
def upload_employees_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'Geen bestand'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Leeg bestand'}), 400
    df = pd.read_csv(file)
    employees = []
    for _, row in df.iterrows():
        lat, lon = None, None
        if 'coordinates' in df.columns and pd.notna(row['coordinates']):
            lat, lon = parse_coordinates(row['coordinates'])
        if lat is None:
            adres = row.get('Straat', row.get('address', ''))
            postcode = row.get('Postcode', '')
            stad = row.get('Stad', 'Heerlen')
            lat, lon = geocode_address(adres, postcode, stad)
        emp = {
            'naam': row.get('Naam', row.get('name', '')),
            'straat': row.get('Straat', row.get('address', '')),
            'postcode': row.get('Postcode', ''),
            'stad': row.get('Stad', 'Heerlen'),
            'startTijd': row.get('Start Tijd', '08:00'),
            'eindTijd': row.get('Eind Tijd', '17:00'),
            'dagen': row.get('Dagen', 'monday;tuesday;wednesday;thursday;friday').split(';'),
            'lat': lat,
            'lon': lon,
            'dogs': int(row.get('dogs', 0)),
            'cats': int(row.get('cats', 0)),
            'smokes': str(row.get('smokes', 'false')).lower() == 'true'
        }
        employees.append(emp)
    save_employees(employees)
    return jsonify({'employees': employees})

@app.route('/api/upload/clients', methods=['POST'])
def upload_clients_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'Geen bestand'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Leeg bestand'}), 400
    df = pd.read_csv(file)
    clients = []
    for _, row in df.iterrows():
        lat, lon = None, None
        if 'coordinates' in df.columns and pd.notna(row['coordinates']):
            lat, lon = parse_coordinates(row['coordinates'])
        if lat is None:
            adres = row.get('Straat', row.get('address', ''))
            postcode = row.get('Postcode', '')
            stad = row.get('Stad', 'Heerlen')
            lat, lon = geocode_address(adres, postcode, stad)
        duur = int(row.get('Duur (min)', row.get('care_hours', 1)*60))
        cl = {
            'naam': row.get('Naam', row.get('name', '')),
            'telefoon': row.get('Telefoon', ''),
            'typeZorg': row.get('Type Zorg', row.get('care_arrangement', '')),
            'duur': duur,
            'straat': row.get('Straat', row.get('address', '')),
            'postcode': row.get('Postcode', ''),
            'stad': row.get('Stad', 'Heerlen'),
            'dagen': row.get('Dagen', 'monday;tuesday;wednesday;thursday;friday').split(';'),
            'tijdvensters': row.get('Tijdvensters', '08:00-18:00'),
            'opmerkingen': row.get('Opmerkingen', ''),
            'lat': lat,
            'lon': lon,
            'heeft_hond': 'hond' in row.get('Opmerkingen', '').lower(),
            'heeft_kat': 'kat' in row.get('Opmerkingen', '').lower(),
            'rookt': 'rookt' in row.get('Opmerkingen', '').lower()
        }
        clients.append(cl)
    save_clients(clients)
    return jsonify({'clients': clients})

@app.route('/plan_week', methods=['POST'])
def plan_week():
    data = request.get_json()
    employees = data.get('medewerkers', [])
    clients = data.get('clienten', [])
    week_offset = data.get('week_offset', 0)
    if not employees or not clients:
        return jsonify({'error': 'Geen medewerkers of cliënten'}), 400
    result = solve_vrp(employees, clients, week_offset)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)