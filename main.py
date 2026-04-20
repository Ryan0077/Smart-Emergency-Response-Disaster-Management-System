from flask import Flask, request, redirect, url_for, render_template_string
import heapq
from datetime import datetime

app = Flask(__name__)

# -----------------------------
# DATA STORAGE
# -----------------------------
# Graph: area -> list of (neighbor, distance)
city_graph = {
    'Central': [('North', 6), ('East', 4), ('West', 5)],
    'North': [('Central', 6), ('HillSide', 3), ('RiverBank', 7)],
    'East': [('Central', 4), ('RiverBank', 2), ('Industrial', 5)],
    'West': [('Central', 5), ('HillSide', 4), ('ShelterZone', 6)],
    'HillSide': [('North', 3), ('West', 4)],
    'RiverBank': [('North', 7), ('East', 2), ('ShelterZone', 3)],
    'Industrial': [('East', 5), ('ShelterZone', 4)],
    'ShelterZone': [('RiverBank', 3), ('Industrial', 4), ('West', 6)]
}

hospitals = [
    {'name': 'CityCare Hospital', 'location': 'Central', 'beds': 18},
    {'name': 'North General Hospital', 'location': 'North', 'beds': 10},
    {'name': 'RiverSide Medical', 'location': 'RiverBank', 'beds': 8}
]

ambulances = [
    {'id': 'AMB-101', 'location': 'Central', 'available': True},
    {'id': 'AMB-102', 'location': 'East', 'available': True},
    {'id': 'AMB-103', 'location': 'West', 'available': True}
]

shelters = [
    {'name': 'Community Shelter A', 'location': 'ShelterZone', 'capacity': 50, 'occupied': 20},
    {'name': 'HillSafe Camp', 'location': 'HillSide', 'capacity': 30, 'occupied': 12},
    {'name': 'West Relief Center', 'location': 'West', 'capacity': 25, 'occupied': 10}
]

incidents = [
    {
        'id': 1,
        'type': 'Fire',
        'location': 'Industrial',
        'severity': 'High',
        'victims': 5,
        'status': 'Active',
        'reported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
]

# relation: victim name -> shelter name
victim_shelter_relation = {}

# set of all active resource names/ids in use
allocated_resources = set()

# -----------------------------
# LOGIC + FUNCTIONS
# -----------------------------
def dijkstra(graph, start, end):
    distances = {node: float('inf') for node in graph}
    previous = {node: None for node in graph}
    distances[start] = 0
    pq = [(0, start)]

    while pq:
        current_distance, current_node = heapq.heappop(pq)

        if current_node == end:
            break

        if current_distance > distances[current_node]:
            continue

        for neighbor, weight in graph[current_node]:
            distance = current_distance + weight
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                previous[neighbor] = current_node
                heapq.heappush(pq, (distance, neighbor))

    path = []
    node = end
    while node is not None:
        path.append(node)
        node = previous[node]
    path.reverse()

    if path and path[0] == start:
        return distances[end], path
    return float('inf'), []


def nearest_hospital(location):
    best = None
    best_distance = float('inf')
    best_path = []

    for hospital in hospitals:
        distance, path = dijkstra(city_graph, location, hospital['location'])
        if distance < best_distance:
            best_distance = distance
            best = hospital
            best_path = path

    return best, best_distance, best_path


def nearest_available_ambulance(location):
    best = None
    best_distance = float('inf')
    best_path = []

    for ambulance in ambulances:
        if ambulance['available']:
            distance, path = dijkstra(city_graph, ambulance['location'], location)
            if distance < best_distance:
                best_distance = distance
                best = ambulance
                best_path = path

    return best, best_distance, best_path


def best_shelter(location, victims_count):
    available_shelters = []

    for shelter in shelters:
        free_space = shelter['capacity'] - shelter['occupied']
        if free_space >= victims_count:
            distance, path = dijkstra(city_graph, location, shelter['location'])
            available_shelters.append((distance, shelter, path))

    if not available_shelters:
        return None, None, []

    available_shelters.sort(key=lambda x: x[0])
    return available_shelters[0][1], available_shelters[0][0], available_shelters[0][2]


def priority_score(severity, victims):
    severity_points = {
        'Low': 1,
        'Medium': 2,
        'High': 3,
        'Critical': 4
    }
    return severity_points.get(severity, 1) * 10 + victims


def allocate_resources(incident):
    result = {
        'hospital': None,
        'hospital_distance': None,
        'hospital_path': [],
        'ambulance': None,
        'ambulance_distance': None,
        'ambulance_path': [],
        'shelter': None,
        'shelter_distance': None,
        'shelter_path': []
    }

    hospital, hd, hp = nearest_hospital(incident['location'])
    ambulance, ad, ap = nearest_available_ambulance(incident['location'])
    shelter, sd, sp = best_shelter(incident['location'], incident['victims'])

    if hospital:
        result['hospital'] = hospital
        result['hospital_distance'] = hd
        result['hospital_path'] = hp
        allocated_resources.add(hospital['name'])

    if ambulance:
        result['ambulance'] = ambulance
        result['ambulance_distance'] = ad
        result['ambulance_path'] = ap
        ambulance['available'] = False
        allocated_resources.add(ambulance['id'])

    if shelter:
        result['shelter'] = shelter
        result['shelter_distance'] = sd
        result['shelter_path'] = sp
        shelter['occupied'] += incident['victims']
        allocated_resources.add(shelter['name'])

    return result


def get_dashboard_data():
    active_incidents = [i for i in incidents if i['status'] == 'Active']
    total_victims = sum(i['victims'] for i in active_incidents)
    available_ambulance_count = sum(1 for a in ambulances if a['available'])
    total_free_shelter = sum(s['capacity'] - s['occupied'] for s in shelters)

    sorted_incidents = sorted(
        active_incidents,
        key=lambda x: priority_score(x['severity'], x['victims']),
        reverse=True
    )

    return {
        'active_incidents': active_incidents,
        'total_victims': total_victims,
        'available_ambulance_count': available_ambulance_count,
        'total_free_shelter': total_free_shelter,
        'priority_incidents': sorted_incidents
    }

# -----------------------------
# HTML TEMPLATE
# -----------------------------
HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Smart Emergency Response & Disaster Management System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            background: #f4f7fb;
            color: #222;
        }
        header {
            background: linear-gradient(90deg, #c62828, #ef5350);
            color: white;
            padding: 20px;
            text-align: center;
        }
        .container {
            width: 92%;
            max-width: 1200px;
            margin: 20px auto;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 18px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        h2, h3 {
            margin-top: 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        table, th, td {
            border: 1px solid #ddd;
        }
        th, td {
            padding: 10px;
            text-align: left;
        }
        th {
            background: #f0f3f7;
        }
        input, select, button {
            width: 100%;
            padding: 10px;
            margin: 7px 0 12px 0;
            border-radius: 8px;
            border: 1px solid #ccc;
            box-sizing: border-box;
        }
        button {
            background: #d32f2f;
            color: white;
            border: none;
            cursor: pointer;
            font-weight: bold;
        }
        button:hover {
            background: #b71c1c;
        }
        .section {
            margin-bottom: 20px;
        }
        .tag {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 20px;
            background: #ffe5e5;
            color: #b71c1c;
            font-size: 12px;
            margin-right: 6px;
        }
        .success {
            background: #e8f5e9;
            color: #2e7d32;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 15px;
        }
        .path {
            background: #eef4ff;
            padding: 8px;
            border-radius: 8px;
            margin-top: 6px;
        }
    </style>
</head>
<body>
    <header>
        <h1>Smart Emergency Response & Disaster Management System</h1>
        <p>Graphs + Sets + Relations + Logic + Functions</p>
    </header>

    <div class="container">
        {% if message %}
        <div class="success">{{ message }}</div>
        {% endif %}

        <div class="grid">
            <div class="card">
                <h3>Active Incidents</h3>
                <p><strong>{{ dashboard.active_incidents|length }}</strong></p>
            </div>
            <div class="card">
                <h3>Total Victims</h3>
                <p><strong>{{ dashboard.total_victims }}</strong></p>
            </div>
            <div class="card">
                <h3>Available Ambulances</h3>
                <p><strong>{{ dashboard.available_ambulance_count }}</strong></p>
            </div>
            <div class="card">
                <h3>Free Shelter Capacity</h3>
                <p><strong>{{ dashboard.total_free_shelter }}</strong></p>
            </div>
        </div>

        <div class="grid">
            <div class="card section">
                <h2>Report New Incident</h2>
                <form method="POST" action="/add_incident">
                    <label>Incident Type</label>
                    <select name="type" required>
                        <option value="Accident">Accident</option>
                        <option value="Fire">Fire</option>
                        <option value="Flood">Flood</option>
                        <option value="Earthquake">Earthquake</option>
                    </select>

                    <label>Location</label>
                    <select name="location" required>
                        {% for location in city_graph.keys() %}
                        <option value="{{ location }}">{{ location }}</option>
                        {% endfor %}
                    </select>

                    <label>Severity</label>
                    <select name="severity" required>
                        <option value="Low">Low</option>
                        <option value="Medium">Medium</option>
                        <option value="High">High</option>
                        <option value="Critical">Critical</option>
                    </select>

                    <label>Number of Victims</label>
                    <input type="number" name="victims" min="1" required>

                    <button type="submit">Add Incident</button>
                </form>
            </div>

            <div class="card section">
                <h2>System Concepts Used</h2>
                <p><span class="tag">Graphs</span> Shortest path for routes using Dijkstra's Algorithm</p>
                <p><span class="tag">Sets</span> Track allocated resources without duplicates</p>
                <p><span class="tag">Relations</span> Victim-to-shelter mapping</p>
                <p><span class="tag">Logic</span> Priority score using severity + victims</p>
                <p><span class="tag">Functions</span> Modular allocation and search functions</p>
            </div>
        </div>

        <div class="card section">
            <h2>Incident Priority Queue</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Location</th>
                    <th>Severity</th>
                    <th>Victims</th>
                    <th>Priority Score</th>
                    <th>Action</th>
                </tr>
                {% for incident in dashboard.priority_incidents %}
                <tr>
                    <td>{{ incident.id }}</td>
                    <td>{{ incident.type }}</td>
                    <td>{{ incident.location }}</td>
                    <td>{{ incident.severity }}</td>
                    <td>{{ incident.victims }}</td>
                    <td>{{ priority_score(incident.severity, incident.victims) }}</td>
                    <td>
                        <form method="POST" action="/allocate/{{ incident.id }}">
                            <button type="submit">Allocate Resources</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="card section">
            <h2>Current Incidents</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Location</th>
                    <th>Severity</th>
                    <th>Victims</th>
                    <th>Status</th>
                    <th>Reported At</th>
                </tr>
                {% for incident in incidents %}
                <tr>
                    <td>{{ incident.id }}</td>
                    <td>{{ incident.type }}</td>
                    <td>{{ incident.location }}</td>
                    <td>{{ incident.severity }}</td>
                    <td>{{ incident.victims }}</td>
                    <td>{{ incident.status }}</td>
                    <td>{{ incident.reported_at }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="grid">
            <div class="card">
                <h2>Hospitals</h2>
                <table>
                    <tr><th>Name</th><th>Location</th><th>Beds</th></tr>
                    {% for h in hospitals %}
                    <tr><td>{{ h.name }}</td><td>{{ h.location }}</td><td>{{ h.beds }}</td></tr>
                    {% endfor %}
                </table>
            </div>

            <div class="card">
                <h2>Ambulances</h2>
                <table>
                    <tr><th>ID</th><th>Location</th><th>Available</th></tr>
                    {% for a in ambulances %}
                    <tr><td>{{ a.id }}</td><td>{{ a.location }}</td><td>{{ a.available }}</td></tr>
                    {% endfor %}
                </table>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h2>Shelters</h2>
                <table>
                    <tr><th>Name</th><th>Location</th><th>Capacity</th><th>Occupied</th></tr>
                    {% for s in shelters %}
                    <tr><td>{{ s.name }}</td><td>{{ s.location }}</td><td>{{ s.capacity }}</td><td>{{ s.occupied }}</td></tr>
                    {% endfor %}
                </table>
            </div>

            <div class="card">
                <h2>Allocated Resources Set</h2>
                {% if allocated_resources %}
                    <ul>
                        {% for item in allocated_resources %}
                        <li>{{ item }}</li>
                        {% endfor %}
                    </ul>
                {% else %}
                    <p>No resources allocated yet.</p>
                {% endif %}

                <h2>Victim ↔ Shelter Relation</h2>
                {% if victim_shelter_relation %}
                    <ul>
                        {% for victim, shelter in victim_shelter_relation.items() %}
                        <li>{{ victim }} → {{ shelter }}</li>
                        {% endfor %}
                    </ul>
                {% else %}
                    <p>No victim-shelter mapping yet.</p>
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>
'''

# -----------------------------
# ROUTES
# -----------------------------
@app.route('/')
def home():
    dashboard = get_dashboard_data()
    message = request.args.get('message', '')
    return render_template_string(
        HTML,
        city_graph=city_graph,
        dashboard=dashboard,
        incidents=incidents,
        hospitals=hospitals,
        ambulances=ambulances,
        shelters=shelters,
        allocated_resources=allocated_resources,
        victim_shelter_relation=victim_shelter_relation,
        priority_score=priority_score,
        message=message
    )


@app.route('/add_incident', methods=['POST'])
def add_incident():
    incident_type = request.form['type']
    location = request.form['location']
    severity = request.form['severity']
    victims = int(request.form['victims'])

    new_incident = {
        'id': len(incidents) + 1,
        'type': incident_type,
        'location': location,
        'severity': severity,
        'victims': victims,
        'status': 'Active',
        'reported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    incidents.append(new_incident)

    return redirect(url_for('home', message='Incident reported successfully.'))


@app.route('/allocate/<int:incident_id>', methods=['POST'])
def allocate(incident_id):
    incident = next((i for i in incidents if i['id'] == incident_id), None)
    if not incident:
        return redirect(url_for('home', message='Incident not found.'))

    result = allocate_resources(incident)

    if result['shelter']:
        for i in range(1, incident['victims'] + 1):
            victim_name = f"Incident{incident_id}_Victim{i}"
            victim_shelter_relation[victim_name] = result['shelter']['name']

    incident['status'] = 'Resources Allocated'

    parts = []
    if result['hospital']:
        parts.append(
            f"Hospital: {result['hospital']['name']} via {' -> '.join(result['hospital_path'])}"
        )
    if result['ambulance']:
        parts.append(
            f"Ambulance: {result['ambulance']['id']} via {' -> '.join(result['ambulance_path'])}"
        )
    if result['shelter']:
        parts.append(
            f"Shelter: {result['shelter']['name']} via {' -> '.join(result['shelter_path'])}"
        )

    final_message = ' | '.join(parts) if parts else 'No suitable resources found.'
    return redirect(url_for('home', message=final_message))


if __name__ == '__main__':
    app.run(debug=True)
