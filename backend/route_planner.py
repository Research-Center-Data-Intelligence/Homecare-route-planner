import os
import pickle
import math
import time
import pandas as pd
import numpy as np
import networkx as nx
import osmnx as ox
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'osm_cache')
CACHE_AUTO = os.path.join(CACHE_DIR, 'heerlen_drive.pkl')
CACHE_FIETS = os.path.join(CACHE_DIR, 'heerlen_bike.pkl')
GEOCODE_CACHE = os.path.join(CACHE_DIR, 'geocode_cache.pkl')
os.makedirs(CACHE_DIR, exist_ok=True)

G_AUTO = None
G_FIETS = None

geocoder = Nominatim(user_agent="thuiszorg_planner", timeout=10)
geocode_cache = {}

def _load_geocode_cache():
    global geocode_cache
    if os.path.exists(GEOCODE_CACHE):
        with open(GEOCODE_CACHE, 'rb') as f:
            geocode_cache = pickle.load(f)

def _save_geocode_cache():
    with open(GEOCODE_CACHE, 'wb') as f:
        pickle.dump(geocode_cache, f)

def geocode_address(address):
    if address in geocode_cache:
        return geocode_cache[address]
    try:
        loc = geocoder.geocode(address + ", Heerlen, Nederland")
        if loc:
            coords = (loc.latitude, loc.longitude)
            geocode_cache[address] = coords
            _save_geocode_cache()
            return coords
        return None
    except GeocoderTimedOut:
        return None

def _load_osm_graph(cache_path, network_type):
    if os.path.exists(cache_path):
        with open(cache_path, 'rb') as f:
            return pickle.load(f)
    G = ox.graph_from_place('Heerlen, Netherlands', network_type=network_type)
    if network_type == 'drive':
        G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    with open(cache_path, 'wb') as f:
        pickle.dump(G, f)
    return G

def init_graphs():
    global G_AUTO, G_FIETS
    G_AUTO = _load_osm_graph(CACHE_AUTO, 'drive')
    G_FIETS = _load_osm_graph(CACHE_FIETS, 'bike')
    _load_geocode_cache()

def haversine(coord1, coord2):
    R = 6371000
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def _nearest_nodes(G, coords):
    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    return ox.nearest_nodes(G, lons, lats)

def compute_distance_matrix(G, coords, nodes=None, fallback_factor=1.4):
    n = len(coords)
    if nodes is None:
        nodes = _nearest_nodes(G, coords)
    matrix = [[0]*n for _ in range(n)]
    for i in range(n):
        try:
            lengths = nx.single_source_dijkstra_path_length(G, nodes[i], weight='length')
        except nx.NodeNotFound:
            lengths = {}
        for j in range(n):
            if i == j:
                continue
            if nodes[j] in lengths:
                matrix[i][j] = int(lengths[nodes[j]])
            else:
                matrix[i][j] = int(haversine(coords[i], coords[j]) * fallback_factor)
    return matrix, nodes

def can_assign(employee, client, strict_smoking=False):
    dogs = employee.get('dogs', 0)
    cats = employee.get('cats', 0)
    smokes = employee.get('smokes', False)
    if dogs == -1 and client.get('heeft_hond', False):
        return False
    if cats == -1 and client.get('heeft_kat', False):
        return False
    if strict_smoking and not smokes and client.get('rookt', False):
        return False
    return True

def build_match_matrix(employees, clients):
    n_mw = len(employees)
    n_cl = len(clients)
    match = [[False]*n_cl for _ in range(n_mw)]
    for i, e in enumerate(employees):
        for j, c in enumerate(clients):
            match[i][j] = can_assign(e, c)
    return match

def solve_vrp(distance_matrix, match_matrix, n_mw, max_time_sec=30, max_visits=4):
    n_cl = len(match_matrix[0]) if match_matrix else 0
    n_nodes = n_mw + n_cl
    depots = list(range(n_mw))
    manager = pywrapcp.RoutingIndexManager(n_nodes, n_mw, depots, depots)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_index)

    routing.AddDimension(transit_index, 0, 10_000_000, True, 'Distance')
    routing.GetDimensionOrDie('Distance').SetGlobalSpanCostCoefficient(100)

    def demand_callback(from_index):
        node = manager.IndexToNode(from_index)
        return 1 if node >= n_mw else 0

    demand_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_index, 0, [max_visits] * n_mw, True, 'Capacity'
    )

    for cl_idx in range(n_cl):
        cl_node = n_mw + cl_idx
        cl_index = manager.NodeToIndex(cl_node)
        allowed = [mw_idx for mw_idx in range(n_mw) if match_matrix[mw_idx][cl_idx]]
        if allowed:
            routing.VehicleVar(cl_index).SetValues(allowed)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = max_time_sec

    solution = routing.SolveWithParameters(search_parameters)
    if not solution:
        return None, "GEEN OPLOSSING"

    routes = {}
    for mw_idx in range(n_mw):
        index = routing.Start(mw_idx)
        route = []
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node >= n_mw:
                route.append(node - n_mw)
            index = solution.Value(routing.NextVar(index))
        routes[mw_idx] = route

    status_map = {1: "OPTIMAAL", 2: "GOED GENOEG"}
    status = status_map.get(routing.status(), f"STATUS {routing.status()}")
    return routes, status

def assign_clients_to_days_with_capacity(clients, employees, days_of_week, max_visits_per_emp=4):
    """
    Assign each client to exactly ONE day in the week.
    Constraints:
      - Max 4 clients per employee per day
      - Each client is scheduled at most once (1x per week)
      - Employee weekly hours limited to ~40h (tracked via client duration)
    """
    from collections import defaultdict

    # Build per-day employee lists
    emp_per_day = {day: [] for day in days_of_week}
    for emp in employees:
        for d in emp.get('werkdagen', []):
            if d in emp_per_day:
                emp_per_day[d].append(emp['id'])

    # Slots per day = number of employees that day * max_visits_per_emp
    capacity_per_day = {day: len(emps) * max_visits_per_emp for day, emps in emp_per_day.items()}

    # Track minutes scheduled per employee per week (max ~2400 min = 40h)
    emp_weekly_minutes = defaultdict(int)
    MAX_WEEKLY_MINUTES = 40 * 60  # 2400 min

    # Sort clients: least available days first (most constrained first)
    sorted_clients = sorted(clients, key=lambda c: len(c.get('dagen', [])))

    assignments = defaultdict(list)
    remaining_capacity = capacity_per_day.copy()
    assigned_ids = set()  # ensure each client only once
    unassigned = []

    for cl in sorted_clients:
        if cl['id'] in assigned_ids:
            continue  # already assigned (safety check)

        available = [d for d in days_of_week if d in cl.get('dagen', [])]
        if not available:
            unassigned.append(cl)
            continue

        # Pick the day with most remaining capacity (spread load)
        available_with_cap = [d for d in available if remaining_capacity[d] > 0]
        if not available_with_cap:
            unassigned.append(cl)
            continue

        # Choose day with most remaining capacity to spread load
        best_day = max(available_with_cap, key=lambda d: remaining_capacity[d])

        # Check if at least one employee on that day still has weekly hours left
        emps_on_day = emp_per_day[best_day]
        has_capacity = any(
            emp_weekly_minutes[eid] + cl.get('duur', 60) <= MAX_WEEKLY_MINUTES
            for eid in emps_on_day
        )
        if not has_capacity:
            unassigned.append(cl)
            continue

        assignments[best_day].append(cl)
        remaining_capacity[best_day] -= 1
        assigned_ids.add(cl['id'])

        # Distribute minutes equally across employees working that day
        if emps_on_day:
            per_emp = cl.get('duur', 60) / len(emps_on_day)
            for eid in emps_on_day:
                emp_weekly_minutes[eid] += per_emp

    return assignments, unassigned

def plan_day(employees_day, clients_day, transport_mode='auto', max_time_sec=30, max_visits=4):
    G = G_AUTO if transport_mode == 'auto' else G_FIETS
    n_mw = len(employees_day)
    n_cl = len(clients_day)
    if n_mw == 0 or n_cl == 0:
        return {}, "GEEN MEDEWERKERS OF CLIËNTEN", []

    all_coords = [e['coords'] for e in employees_day] + [c['coords'] for c in clients_day]
    distance_matrix, _ = compute_distance_matrix(G, all_coords)
    match_matrix = build_match_matrix(employees_day, clients_day)

    for j in range(n_cl):
        if not any(match_matrix[i][j] for i in range(n_mw)):
            raise ValueError(f"Client {clients_day[j]['naam']} heeft geen geschikte medewerker!")

    routes, status = solve_vrp(distance_matrix, match_matrix, n_mw, max_time_sec, max_visits)
    return routes, status, clients_day

def plan_week(employees, clients, week_start_date, transport_mode='auto'):
    init_graphs()
    for e in employees:
        if 'coords' not in e:
            addr = f"{e['straat']} {e['postcode']} {e['stad']}"
            e['coords'] = geocode_address(addr)
    for c in clients:
        if 'coords' not in c:
            addr = f"{c['straat']} {c['postcode']} {c['stad']}"
            c['coords'] = geocode_address(addr)

    days_of_week = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
    dag_clienten, unassigned = assign_clients_to_days_with_capacity(
        clients, employees, days_of_week, max_visits_per_emp=4
    )

    result = {}
    for dag in days_of_week:
        emp_day = [e for e in employees if dag in e.get('werkdagen', [])]
        cl_day = dag_clienten.get(dag, [])
        if not emp_day or not cl_day:
            result[dag] = []
            continue
        # Hard cap: max 4 clients per employee per day
        MAX_PER_EMP = 4
        max_total = len(emp_day) * MAX_PER_EMP
        if len(cl_day) > max_total:
            # Put overflow in unassigned
            overflow = cl_day[max_total:]
            cl_day = cl_day[:max_total]
            unassigned.extend(overflow)

        routes, status, _ = plan_day(emp_day, cl_day, transport_mode, max_time_sec=30, max_visits=MAX_PER_EMP)
        if routes is None:
            result[dag] = []
            continue
        day_routes = []
        for mw_idx, route in routes.items():
            mw = emp_day[mw_idx]
            bezoeken = []
            for cl_idx in route:
                cl = cl_day[cl_idx]
                bezoeken.append({
                    'client_naam': cl['naam'],
                    'duur': cl['duur'],
                    'tijdvensters': cl.get('tijdvensters', '')
                })
            day_routes.append({
                'medewerker_id': mw['id'],
                'medewerker_naam': mw['naam'],
                'bezoeken': bezoeken
            })
        result[dag] = day_routes

    result['unassigned'] = [{'naam': c['naam'], 'duur': c['duur']} for c in unassigned]
    return result