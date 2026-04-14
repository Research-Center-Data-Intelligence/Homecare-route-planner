# app.py (complete, corrected time extraction + 5‑minute buffer + vehicle_type support)
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
import hashlib

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# ---------- 1. Load road network ----------
EDGES_PATH = '../output/heerlen_edge_table.csv'
G = None
node_coords = {}
edge_geom = {}
kd_tree = None
node_ids = []

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
    print("Road network loaded.")
else:
    print(f"Warning: {EDGES_PATH} not found. Routing will be unavailable.")

def nearest_node(lon, lat):
    if kd_tree is None:
        return 0
    _, idx = kd_tree.query([lon, lat])
    return node_ids[idx]

# ---------- 2. Geocoding (fallback) ----------
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
geolocator = Nominatim(user_agent="homecare_planner")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

def geocode_address(street, postcode, city):
    cache_file = 'geocode_cache.json'
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache = json.load(f)
    key = f"{street}, {postcode} {city}".lower()
    if key in cache:
        return cache[key]
    try:
        loc = geocode(f"{street}, {postcode} {city}, Netherlands")
        if loc:
            result = (loc.latitude, loc.longitude)
            cache[key] = result
            with open(cache_file, 'w') as f:
                json.dump(cache, f)
            return result
    except Exception as e:
        print(f"Geocoding error: {e}")
    return None, None

# ---------- 3. CSV loading and saving ----------
EMPLOYEES_CSV = '../output/employees_vehicle_type.csv'
CLIENTS_CSV = '../output/clients.csv'

def parse_coordinates(coord_str):
    try:
        parts = coord_str.strip().split()
        return float(parts[0]), float(parts[1])
    except:
        return None, None

def load_employees():
    if not os.path.exists(EMPLOYEES_CSV):
        print(f"Warning: {EMPLOYEES_CSV} not found.")
        return []
    df = pd.read_csv(EMPLOYEES_CSV)
    employees = []
    all_weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
    for idx, row in df.iterrows():
        lat, lon = parse_coordinates(row['coordinates'])
        if lat is None:
            continue
        smokes_val = row.get('smokes', False)
        if isinstance(smokes_val, str):
            smokes = smokes_val.lower() == 'true'
        else:
            smokes = bool(smokes_val)

        display_name = row.get('fullname', row.get('name', ''))
        if not display_name:
            display_name = row.get('name', '')

        avail_str = row.get('availability', row.get('available_days', ''))
        if pd.isna(avail_str) or str(avail_str).strip() == '':
            days = all_weekdays.copy()
        else:
            raw = str(avail_str).strip()
            sep = ',' if ',' in raw else ';'
            parts = [p.strip().lower() for p in raw.split(sep) if p.strip()]
            days = []
            for p in parts:
                if p in all_weekdays:
                    days.append(p)
                else:
                    day_map = {'maandag':'monday','dinsdag':'tuesday','woensdag':'wednesday','donderdag':'thursday','vrijdag':'friday'}
                    eng = day_map.get(p)
                    if eng:
                        days.append(eng)
            if not days:
                days = all_weekdays.copy()

        emp = {
            'id': int(hashlib.md5(display_name.encode()).hexdigest()[:8], 16) % 1000000,
            'name': display_name,
            'email': '',
            'phone': '',
            'street': row['address'].split(',')[0] if ',' in row['address'] else row['address'],
            'postcode': '',
            'city': 'Heerlen',
            'start_time': row['time_window_start'],
            'end_time': row['time_window_end'],
            'days': days,
            'lat': lat,
            'lon': lon,
            'dogs': int(row.get('dogs', -1)),
            'cats': int(row.get('cats', -1)),
            'smokes': smokes,
            'vehicle_type': row.get('vehicle_type', 'car')   # nieuw veld
        }
        employees.append(emp)
    return employees

def load_clients():
    if not os.path.exists(CLIENTS_CSV):
        print(f"Warning: {CLIENTS_CSV} not found.")
        return []
    df = pd.read_csv(CLIENTS_CSV)
    clients = []
    day_map = {
        'maandag': 'monday', 'monday': 'monday',
        'dinsdag': 'tuesday', 'tuesday': 'tuesday',
        'woensdag': 'wednesday', 'wednesday': 'wednesday',
        'donderdag': 'thursday', 'thursday': 'thursday',
        'vrijdag': 'friday', 'friday': 'friday',
        'zaterdag': 'saturday', 'saturday': 'saturday',
        'zondag': 'sunday', 'sunday': 'sunday'
    }
    all_weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']

    for idx, row in df.iterrows():
        lat, lon = parse_coordinates(row['coordinates'])
        if lat is None:
            continue
        care_hours = float(row.get('care_hours', 1.0))
        duration = int(care_hours * 60)
        time_window_str = f"{row['time_window_start']}-{row['time_window_end']}"
        smokes_val = row.get('smokes', False)
        if isinstance(smokes_val, str):
            smokes = smokes_val.lower() == 'true'
        else:
            smokes = bool(smokes_val)

        unavailable_str = row.get('unavailable_days', '')
        if pd.isna(unavailable_str) or str(unavailable_str).strip() == '':
            unavailable_days_raw = []
        else:
            unavailable_days_raw = [d.strip().lower() for d in str(unavailable_str).split(',') if d.strip()]

        unavailable_eng = set()
        for d in unavailable_days_raw:
            eng = day_map.get(d)
            if eng and eng in all_weekdays:
                unavailable_eng.add(eng)

        days = [d for d in all_weekdays if d not in unavailable_eng]
        if not days:
            days = all_weekdays.copy()

        cl = {
            'id': int(hashlib.md5(row['name'].encode()).hexdigest()[:8], 16) % 1000000,
            'name': row['name'],
            'phone': '',
            'care_type': row.get('care_arrangement', ''),
            'duration': duration,
            'street': row['address'].split(',')[0] if ',' in row['address'] else row['address'],
            'postcode': '',
            'city': 'Heerlen',
            'days': days,
            'time_windows': time_window_str,
            'notes': '',
            'lat': lat,
            'lon': lon,
            'has_dog': int(row.get('dogs', 0)) > 0,
            'has_cat': int(row.get('cats', 0)) > 0,
            'smokes': smokes
        }
        clients.append(cl)
    return clients

def save_employees(employees):
    data = []
    for emp in employees:
        data.append({
            'name': emp['name'].split()[0] if ' ' in emp['name'] else emp['name'],
            'fullname': emp['name'],
            'address': f"{emp['street']}, Heerlen",
            'coordinates': f"{emp['lat']} {emp['lon']}",
            'time_window_start': emp['start_time'],
            'time_window_end': emp['end_time'],
            'available_hours': '',
            'availability': ', '.join(emp.get('days', [])),
            'dogs': emp['dogs'],
            'cats': emp['cats'],
            'smokes': emp['smokes'],
            'vehicle_type': emp.get('vehicle_type', 'car')
        })
    df = pd.DataFrame(data)
    os.makedirs(os.path.dirname(EMPLOYEES_CSV), exist_ok=True)
    df.to_csv(EMPLOYEES_CSV, index=False)

def save_clients(clients):
    data = []
    day_map_reverse = {
        'monday': 'maandag', 'tuesday': 'dinsdag', 'wednesday': 'woensdag',
        'thursday': 'donderdag', 'friday': 'vrijdag'
    }
    all_weekdays_eng = ['monday','tuesday','wednesday','thursday','friday']
    for cl in clients:
        avail_days = cl.get('days', [])
        unavailable_eng = set(all_weekdays_eng) - set(avail_days)
        unavailable_nl = [day_map_reverse[d] for d in unavailable_eng if d in day_map_reverse]
        unavailable_str = ', '.join(unavailable_nl)

        data.append({
            'name': cl['name'],
            'address': f"{cl['street']}, Heerlen",
            'coordinates': f"{cl['lat']} {cl['lon']}",
            'care_arrangement': cl['care_type'],
            'preferences': '',
            'time_window_start': cl['time_windows'].split('-')[0] if '-' in cl['time_windows'] else '08:00',
            'time_window_end': cl['time_windows'].split('-')[1] if '-' in cl['time_windows'] else '18:00',
            'care_hours': cl['duration'] / 60,
            'dogs': 1 if cl['has_dog'] else 0,
            'cats': 1 if cl['has_cat'] else 0,
            'smokes': cl['smokes'],
            'unavailable_days': unavailable_str
        })
    df = pd.DataFrame(data)
    os.makedirs(os.path.dirname(CLIENTS_CSV), exist_ok=True)
    df.to_csv(CLIENTS_CSV, index=False)

# ---------- 4. OR-Tools VRP solver (met vehicle_type afstandscheck) ----------
def solve_vrp(employees_from_frontend, clients_from_frontend, week_offset=0):
    if G is None:
        return {'error': 'Road network unavailable. Cannot create schedule.'}

    employees = load_employees()
    clients = load_clients()
    if not employees or not clients:
        return {'error': 'No employees or clients in CSV files.'}

    day_index = {'monday':0,'tuesday':1,'wednesday':2,'thursday':3,'friday':4}

    for emp in employees:
        if 'node' not in emp:
            emp['node'] = nearest_node(emp['lon'], emp['lat'])

    for cl in clients:
        if 'node' not in cl:
            cl['node'] = nearest_node(cl['lon'], cl['lat'])
        if 'time_windows' in cl and cl['time_windows']:
            parts = cl['time_windows'].split(';')[0].split('-')
            if len(parts) == 2:
                start_h, start_m = map(int, parts[0].split(':'))
                end_h, end_m = map(int, parts[1].split(':'))
                cl['tw_min'] = start_h*60 + start_m
                cl['tw_max'] = end_h*60 + end_m
            else:
                cl['tw_min'] = 0
                cl['tw_max'] = 24*60
        else:
            cl['tw_min'] = 0
            cl['tw_max'] = 24*60
        cl['care_min'] = cl.get('duration', 60)

    def time_to_min(t):
        h, m = map(int, t.split(':'))
        return h*60 + m

    global_min = 24*60
    global_max = 0
    for emp in employees:
        start = time_to_min(emp['start_time'])
        end = time_to_min(emp['end_time'])
        if start < global_min:
            global_min = start
        if end > global_max:
            global_max = end

    global_min = max(0, global_min - 60)
    global_max = min(24*60, global_max + 60)
    horizon = global_max - global_min

    for cl in clients:
        cl['tw_min'] = max(0, cl['tw_min'] - global_min - 30)
        cl['tw_max'] = min(horizon, cl['tw_max'] - global_min + 30)

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
        workdays = emp.get('days', [])
        for day in workdays:
            if day in day_index:
                vehicles.append({
                    'vehicle_id': len(vehicles),
                    'emp_id': emp_id,
                    'day': day_index[day],
                    'start_node': emp_id,
                    'end_node': emp_id,
                    'max_work': (time_to_min(emp['end_time']) - time_to_min(emp['start_time'])) * SCALE
                })
    N_VEHICLES = len(vehicles)
    if N_VEHICLES == 0:
        return {'error': 'No employees with working days.'}

    print(f"Total vehicles: {N_VEHICLES}, Clients: {N_CLIENTS}")

    data = {
        'time_matrix': time_matrix.tolist(),
        'num_vehicles': N_VEHICLES,
        'starts': [v['start_node'] for v in vehicles],
        'ends': [v['end_node'] for v in vehicles],
        'demands': [0]*N_EMPLOYEES + [1]*N_CLIENTS,
        'capacities': [5]*N_VEHICLES
    }

    service_time = [0]*N_EMPLOYEES + [cl['care_min'] for cl in clients]

    time_windows = []
    for emp in employees:
        start_rel = time_to_min(emp['start_time']) - global_min
        end_rel = time_to_min(emp['end_time']) - global_min
        time_windows.append((start_rel, end_rel))
    for cl in clients:
        time_windows.append((cl['tw_min'], cl['tw_max']))

    manager = pywrapcp.RoutingIndexManager(N_TOTAL, N_VEHICLES, data['starts'], data['ends'])
    routing = pywrapcp.RoutingModel(manager)

    BUFFER_MINUTES = 5
    BUFFER_SCALED = BUFFER_MINUTES * SCALE

    def total_time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        travel = data['time_matrix'][from_node][to_node]
        service = service_time[from_node] * SCALE
        buffer = BUFFER_SCALED if from_node >= N_EMPLOYEES else 0
        return travel + service + buffer

    transit_callback = routing.RegisterTransitCallback(total_time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback)

    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, data['capacities'], True, 'Capacity')

    routing.AddDimension(transit_callback, horizon*SCALE, horizon*SCALE, False, 'Time')
    time_dim = routing.GetDimensionOrDie('Time')
    for node in range(N_TOTAL):
        index = manager.NodeToIndex(node)
        tw_min, tw_max = time_windows[node]
        time_dim.CumulVar(index).SetRange(tw_min*SCALE, tw_max*SCALE)

    for v in range(N_VEHICLES):
        max_work = vehicles[v]['max_work']
        time_dim.SetSpanUpperBoundForVehicle(max_work, v)

    # -------------------- vehicle_type constraint via afstand --------------------
    def haversine(lon1, lat1, lon2, lat2):
        R = 6371
        dlon = np.radians(lon2 - lon1)
        dlat = np.radians(lat2 - lat1)
        a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
        return 2 * R * np.arcsin(np.sqrt(a))

    compatible_emp_per_client = []
    for cid, cl in enumerate(clients):
        compat = []
        for emp_id, emp in enumerate(employees):
            # huisdieren & rook check
            if emp.get('dogs', -1) != -1 and cl.get('has_dog', False) and cl['has_dog'] > emp['dogs']:
                continue
            if emp.get('cats', -1) != -1 and cl.get('has_cat', False) and cl['has_cat'] > emp['cats']:
                continue
            if not emp.get('smokes', False) and cl.get('smokes', False):
                continue

            # vehicle_type afstandscheck
            vt = emp.get('vehicle_type', 'car')
            dist = haversine(emp['lon'], emp['lat'], cl['lon'], cl['lat'])
            if vt == 'walking' and dist > 2.0:   # max 2 km voor lopen
                continue
            if vt == 'bike' and dist > 8.0:      # max 8 km voor fiets
                continue
            # car: geen beperking

            compat.append(emp_id)
        compatible_emp_per_client.append(compat)

    client_available_days = []
    for cl in clients:
        avail_days = set(day_index.get(d) for d in cl.get('days', []) if d in day_index)
        if not avail_days:
            avail_days = set(range(5))
        client_available_days.append(avail_days)

    PENALTY = 100000

    solver = routing.solver()
    for cid in range(N_CLIENTS):
        node_idx = manager.NodeToIndex(N_EMPLOYEES + cid)
        routing.AddDisjunction([node_idx], PENALTY)

        if not compatible_emp_per_client[cid]:
            continue
        else:
            vehicle_var = routing.VehicleVar(node_idx)
            for v in range(N_VEHICLES):
                emp_id = vehicles[v]['emp_id']
                day_idx = vehicles[v]['day']
                if emp_id not in compatible_emp_per_client[cid]:
                    solver.Add(vehicle_var != v)
                if day_idx not in client_available_days[cid]:
                    solver.Add(vehicle_var != v)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_params.time_limit.seconds = 300

    solution = routing.SolveWithParameters(search_params)
    if not solution:
        return {'error': 'No solution found. Try relaxing constraints.'}

    routes_per_day = {day: [] for day in ['monday','tuesday','wednesday','thursday','friday']}
    unassigned = []

    for v in range(N_VEHICLES):
        index = routing.Start(v)
        nodes = []
        times = []
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            nodes.append(node)
            times.append(solution.Value(time_dim.CumulVar(index)))
            index = solution.Value(routing.NextVar(index))
        nodes.append(manager.IndexToNode(index))
        times.append(solution.Value(time_dim.CumulVar(index)))

        client_ids = [n - N_EMPLOYEES for n in nodes if n >= N_EMPLOYEES]
        if not client_ids:
            continue

        emp_id = vehicles[v]['emp_id']
        day = vehicles[v]['day']
        day_name = list(routes_per_day.keys())[day]
        employee = employees[emp_id]
        emp_start_min = time_to_min(employee['start_time'])
        emp_end_min = time_to_min(employee['end_time'])

        start_offset = times[0] // SCALE
        route_start_abs = global_min + start_offset

        visits = []
        for i, cid in enumerate(client_ids):
            cl = clients[cid]
            node_idx_in_route = i + 1
            arrival_scaled = times[node_idx_in_route]
            departure_scaled = arrival_scaled + service_time[N_EMPLOYEES + cid] * SCALE

            arrival_min = global_min + (arrival_scaled // SCALE)
            departure_min = global_min + (departure_scaled // SCALE)

            if arrival_min < emp_start_min or departure_min > emp_end_min:
                print(f"Warning: Visit {cl['name']} on {day_name} by {employee['name']} outside hours. Skipping.")
                continue

            start_time_str = f"{arrival_min // 60:02d}:{arrival_min % 60:02d}"
            end_time_str = f"{departure_min // 60:02d}:{departure_min % 60:02d}"
            visits.append({
                'client_id': cl['id'],
                'client_name': cl['name'],
                'duration': cl['care_min'],
                'start_time': start_time_str,
                'end_time': end_time_str
            })

        if visits:
            routes_per_day[day_name].append({
                'employee_id': employee['id'],
                'employee_name': employee['name'],
                'visits': visits
            })

    assigned_ids = set()
    for day in routes_per_day:
        for route in routes_per_day[day]:
            for v in route['visits']:
                assigned_ids.add(v['client_id'])
    for cl in clients:
        if cl['id'] not in assigned_ids:
            unassigned.append({
                'id': cl['id'],
                'name': cl['name'],
                'duration': cl.get('duration', 60)
            })

    print(f"Assigned clients: {len(assigned_ids)} / {N_CLIENTS}")
    result = {day: routes_per_day[day] for day in routes_per_day}
    result['unassigned'] = unassigned
    return result

# ---------- 5. Schedule persistence ----------
SCHEDULE_PATH = '../output/schedule.json'

@app.route('/api/save_schedule', methods=['POST'])
def save_schedule():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    try:
        os.makedirs(os.path.dirname(SCHEDULE_PATH), exist_ok=True)
        with open(SCHEDULE_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        return jsonify({'status': 'saved'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/load_schedule', methods=['GET'])
def load_schedule():
    if os.path.exists(SCHEDULE_PATH):
        try:
            with open(SCHEDULE_PATH, 'r') as f:
                data = json.load(f)
            return jsonify(data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({})

@app.route('/api/clear_schedule', methods=['POST'])
def clear_schedule():
    try:
        if os.path.exists(SCHEDULE_PATH):
            os.remove(SCHEDULE_PATH)
        return jsonify({'status': 'cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------- 6. Flask routes ----------
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
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty file'}), 400
    df = pd.read_csv(file)
    employees = []
    all_weekdays = ['monday','tuesday','wednesday','thursday','friday']
    for _, row in df.iterrows():
        lat, lon = None, None
        if 'coordinates' in df.columns and pd.notna(row['coordinates']):
            lat, lon = parse_coordinates(row['coordinates'])
        if lat is None:
            street = row.get('Straat', row.get('address', ''))
            postcode = row.get('Postcode', '')
            city = row.get('Stad', 'Heerlen')
            lat, lon = geocode_address(street, postcode, city)

        display_name = row.get('fullname', row.get('name', ''))
        if not display_name:
            display_name = row.get('name', '')

        avail_str = row.get('availability', row.get('available_days', ''))
        if pd.isna(avail_str) or str(avail_str).strip() == '':
            days = all_weekdays.copy()
        else:
            raw = str(avail_str).strip()
            sep = ',' if ',' in raw else ';'
            parts = [p.strip().lower() for p in raw.split(sep) if p.strip()]
            days = []
            for p in parts:
                if p in all_weekdays:
                    days.append(p)
                else:
                    day_map = {'maandag':'monday','dinsdag':'tuesday','woensdag':'wednesday','donderdag':'thursday','vrijdag':'friday'}
                    eng = day_map.get(p)
                    if eng:
                        days.append(eng)
            if not days:
                days = all_weekdays.copy()

        emp = {
            'name': display_name,
            'street': row.get('Straat', row.get('address', '')),
            'postcode': row.get('Postcode', ''),
            'city': row.get('Stad', 'Heerlen'),
            'start_time': row.get('Start Tijd', row.get('time_window_start', '08:00')),
            'end_time': row.get('Eind Tijd', row.get('time_window_end', '17:00')),
            'days': days,
            'lat': lat,
            'lon': lon,
            'dogs': int(row.get('dogs', 0)),
            'cats': int(row.get('cats', 0)),
            'smokes': str(row.get('smokes', 'false')).lower() == 'true',
            'vehicle_type': row.get('vehicle_type', 'car')
        }
        employees.append(emp)
    save_employees(employees)
    return jsonify({'employees': employees})

@app.route('/api/upload/clients', methods=['POST'])
def upload_clients_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty file'}), 400
    df = pd.read_csv(file)
    clients = []
    day_map = {
        'maandag': 'monday', 'monday': 'monday',
        'dinsdag': 'tuesday', 'tuesday': 'tuesday',
        'woensdag': 'wednesday', 'wednesday': 'wednesday',
        'donderdag': 'thursday', 'thursday': 'thursday',
        'vrijdag': 'friday', 'friday': 'friday'
    }
    all_weekdays = ['monday','tuesday','wednesday','thursday','friday']
    for _, row in df.iterrows():
        lat, lon = None, None
        if 'coordinates' in df.columns and pd.notna(row['coordinates']):
            lat, lon = parse_coordinates(row['coordinates'])
        if lat is None:
            street = row.get('Straat', row.get('address', ''))
            postcode = row.get('Postcode', '')
            city = row.get('Stad', 'Heerlen')
            lat, lon = geocode_address(street, postcode, city)
        duration = int(row.get('Duur (min)', row.get('care_hours', 1)*60))

        unavailable_str = row.get('unavailable_days', '')
        if pd.isna(unavailable_str) or str(unavailable_str).strip() == '':
            unavailable_days_raw = []
        else:
            unavailable_days_raw = [d.strip().lower() for d in str(unavailable_str).split(',') if d.strip()]
        unavailable_eng = set()
        for d in unavailable_days_raw:
            eng = day_map.get(d)
            if eng and eng in all_weekdays:
                unavailable_eng.add(eng)
        days = [d for d in all_weekdays if d not in unavailable_eng]
        if not days:
            days = all_weekdays.copy()

        cl = {
            'name': row.get('Naam', row.get('name', '')),
            'phone': row.get('Telefoon', ''),
            'care_type': row.get('Type Zorg', row.get('care_arrangement', '')),
            'duration': duration,
            'street': row.get('Straat', row.get('address', '')),
            'postcode': row.get('Postcode', ''),
            'city': row.get('Stad', 'Heerlen'),
            'days': days,
            'time_windows': row.get('Tijdvensters', '08:00-18:00'),
            'notes': row.get('Opmerkingen', ''),
            'lat': lat,
            'lon': lon,
            'has_dog': 'hond' in row.get('Opmerkingen', '').lower(),
            'has_cat': 'kat' in row.get('Opmerkingen', '').lower(),
            'smokes': 'rookt' in row.get('Opmerkingen', '').lower()
        }
        clients.append(cl)
    save_clients(clients)
    return jsonify({'clients': clients})

@app.route('/plan_week', methods=['POST'])
def plan_week():
    data = request.get_json()
    employees = data.get('employees', [])
    clients = data.get('clients', [])
    week_offset = data.get('week_offset', 0)
    if not employees or not clients:
        return jsonify({'error': 'No employees or clients'}), 400
    result = solve_vrp(employees, clients, week_offset)
    if 'error' not in result:
        try:
            os.makedirs(os.path.dirname(SCHEDULE_PATH), exist_ok=True)
            with open(SCHEDULE_PATH, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            print(f"Could not save schedule: {e}")
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)