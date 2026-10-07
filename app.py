import random
import string
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'snake_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

rooms = {}
WORLD_SIZE = 5000

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def handle_join(data):
    room_name = data.get('room', 'default')
    join_room(room_name)
    sid = request.sid

    if room_name not in rooms:
        rooms[room_name] = {
            'players': {},
            'foods': []
        }
        for _ in range(400):
            food_id = ''.join(random.choices(string.ascii_letters + string.digits, k=9))
            rooms[room_name]['foods'].append({
                'id': food_id,
                'x': random.uniform(0, WORLD_SIZE),
                'y': random.uniform(0, WORLD_SIZE),
                'color': f"hsl({random.uniform(0, 360)}, 70%, 60%)",
                'radius': 3 + random.uniform(0, 5)
            })

    player = {
        'id': sid,
        'name': data.get('name', 'Player'),
        'room': room_name,
        'segments': [],
        'x': random.uniform(0, WORLD_SIZE),
        'y': random.uniform(0, WORLD_SIZE),
        'angle': 0,
        'radius': 15,
        'color': f"hsl({random.uniform(0, 360)}, 70%, 50%)",
        'score': 10,
        'boosting': False,
        'dead': False
    }

    rooms[room_name]['players'][sid] = player
    emit('init', {'id': sid, 'foods': rooms[room_name]['foods']})

@socketio.on('update')
def handle_update(data):
    sid = request.sid
    for r in rooms:
        if sid in rooms[r]['players']:
            p = rooms[r]['players'][sid]
            p['x'] = data.get('x')
            p['y'] = data.get('y')
            p['angle'] = data.get('angle')
            p['score'] = data.get('score')
            p['segments'] = data.get('segments')
            p['boosting'] = data.get('boosting')
            break

@socketio.on('eatFood')
def handle_eat_food(food_id):
    for r in rooms:
        room = rooms[r]
        foods = room['foods']
        found = next((f for f in foods if f['id'] == food_id), None)
        if found:
            foods.remove(found)
            new_food = {
                'id': ''.join(random.choices(string.ascii_letters + string.digits, k=9)),
                'x': random.uniform(0, WORLD_SIZE),
                'y': random.uniform(0, WORLD_SIZE),
                'color': f"hsl({random.uniform(0, 360)}, 70%, 60%)",
                'radius': 3 + random.uniform(0, 5)
            }
            foods.append(new_food)
            socketio.emit('foodEaten', {'removedId': food_id, 'newFood': new_food}, room=r)
            break

@socketio.on('chat')
def handle_chat(text):
    sid = request.sid
    for r in rooms:
        if sid in rooms[r]['players']:
            p = rooms[r]['players'][sid]
            socketio.emit('chat', {'name': p['name'], 'text': text}, room=r)
            break

@socketio.on('die')
def handle_die(segments):
    sid = request.sid
    for r in rooms:
        room = rooms[r]
        if sid in room['players']:
            player = room['players'][sid]
            player['dead'] = True
            dropped_food = []
            for seg in segments:
                food = {
                    'id': ''.join(random.choices(string.ascii_letters + string.digits, k=9)),
                    'x': seg['x'] + random.uniform(-10, 10),
                    'y': seg['y'] + random.uniform(-10, 10),
                    'color': player['color'],
                    'radius': 5 + random.uniform(0, 5)
                }
                room['foods'].append(food)
                dropped_food.append(food)
            socketio.emit('playerDeath', {'id': sid, 'name': player['name'], 'droppedFood': dropped_food}, room=r)
            break

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    for r in list(rooms.keys()):
        if sid in rooms[r]['players']:
            del rooms[r]['players'][sid]
            socketio.emit('playerLeave', sid, room=r)
            if not rooms[r]['players']:
                del rooms[r]
            break

def background_thread():
    while True:
        socketio.sleep(1.0 / 30.0)
        for r in list(rooms.keys()):
            socketio.emit('state', rooms[r]['players'], room=r)

if __name__ == '__main__':
    socketio.start_background_task(background_thread)
    socketio.run(app, host='0.0.0.0', port=5000)
