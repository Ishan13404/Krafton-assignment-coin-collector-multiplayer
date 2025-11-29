# Coin Collector - Multiplayer Game

A real-time multiplayer coin collection game with authoritative server architecture and interpolated rendering for smooth gameplay despite network latency.

## Features

- ✅ **Server-Authoritative Architecture**: All game logic runs on the server
- ✅ **Two Game Modes**:
  - **Sprint Mode**: First player to collect 10 coins wins
  - **Endless Mode**: Play continuously without win condition
- ✅ **Smooth Interpolation**: Client-side interpolation for smooth movement despite 200ms latency
- ✅ **Network Simulation**: Built-in 200ms latency simulation
- ✅ **Real-time Synchronization**: WebSocket-based state synchronization
- ✅ **Collision Detection**: Server validates all coin pickups
- ✅ **Named Players**: Alice (Red) and Bob (Blue)
- ✅ **Performance Metrics**: Real-time FPS and latency display
- ✅ **Intuitive UI**: Clear lobby instructions and game status
- ✅ **Player Customization**: Choose your player name before joining
- ✅ **Performance Metrics**: Real-time FPS and ping display
- ✅ **Visual Polish**: Score panels, player name tags, and winner animations

## Technical Implementation

### Architecture
- **Server** (`server.py`): Authoritative game server handling all game logic
  - Player position validation
  - Collision detection
  - Score management
  - Coin spawning
  - 200ms latency simulation
  
- **Client** (`client.py`): Pygame-based visual client
  - Sends only input (movement intent), not positions
  - Implements entity interpolation for smooth rendering
  - Receives authoritative state updates from server

### Network Protocol
- Uses **WebSockets** for reliable bidirectional communication
- Simulates **200ms latency** on all messages (both server and client)
- Clients send input vectors (direction), not positions
- Server broadcasts authoritative state at 60 FPS

### Security
- Clients cannot spoof coin collection or positions
- Server validates all collision detection
- All game state maintained server-side

## Verifying Server Authority

The implementation includes comprehensive logging to prove server authority. When running the game, you'll see:

### Client Logs (Proof clients only send intent):
```
[CLIENT] Sent INPUT intent to server: dx=1, dy=0 (NO position sent)
[CLIENT] Sent INPUT intent to server: dx=0, dy=1 (NO position sent)
[CLIENT] Sent STOP intent to server
[CLIENT] Received authoritative position from server: (245.0, 178.0)
[CLIENT] Coin removed by server (collision detected server-side)
```

### Server Logs (Proof server is authoritative):
```
[INPUT] Player 12345678 sent movement intent: dx=1, dy=0 (NOT position)
[SERVER-AUTHORITY] Player 12345678 position calculated by server: (245.0, 178.0)
[SERVER-AUTHORITY] Server spawned coin 5 at random position
[SERVER-AUTHORITY] Collision detected!
  ├─ Player 12345678 at (245.0, 178.0)
  ├─ Coin 5 at (250.0, 180.0)
  ├─ Distance: 5.4 < Threshold: 25.0
  └─ Score updated: 4 → 5 (SERVER VALIDATES)
[SERVER-AUTHORITY] Winner determined by server: Player 12345678
```

### Key Proofs of Server Authority:

1. **Clients Send Intent Only**: Logs show `dx` and `dy` values (direction), never `x` and `y` positions
2. **Server Calculates Positions**: Server logs show position calculations happen server-side
3. **Server Validates Collisions**: Collision detection with distance calculations only on server
4. **Server Manages Score**: Score updates only happen on server after validation
5. **Server Spawns Coins**: Coin generation is server-controlled
6. **Clients Receive Authority**: Clients log receiving positions from server, not calculating them

This logging demonstrates full server authority as required by the assignment.

## Testing Smoothness & Security

### Test 1: Verify Interpolation (Smoothness)
1. Start the game and move a player
2. **Without interpolation**: You'd see the player "jump" every 200ms (stutter)
3. **With interpolation**: Player moves smoothly despite 200ms latency
4. **In logs**: Look for `[INTERPOLATION]` messages showing smooth position updates between server updates

**Expected client log:**
```
[CLIENT] Received authoritative position from server: (300.0, 200.0)
[INTERPOLATION] Smoothing position: display=(285.5,195.2) → target=(300.0,200.0)
[INTERPOLATION] Smoothing position: display=(290.8,197.1) → target=(300.0,200.0)
[INTERPOLATION] Smoothing position: display=(295.4,198.6) → target=(300.0,200.0)
```
This shows the client smoothly moving toward the server's position over multiple frames.

### Test 2: Verify Server Authority (Security)

#### A. Try to Cheat - Modify Client Code
Try adding this to `client.py` in `send_input()`:
```python
# Attempt to send false position (SHOULD BE IGNORED)
message = {
    'type': 'input',
    'dx': dx,
    'dy': dy,
    'x': 9999,  # Try to cheat
    'y': 9999,
    'score': 100
}
```

**Result**: Server ignores `x`, `y`, and `score` fields. Position is still calculated server-side. Client cannot cheat!

#### B. Verify Collision Detection
1. Watch server logs when collecting a coin
2. Server logs show distance calculation and validation
3. Client never reports the collision - server detects it

**Expected server log:**
```
[SERVER-AUTHORITY] Collision detected!
  ├─ Player 12345678 at (245.0, 178.0)
  ├─ Coin 5 at (250.0, 180.0)
  ├─ Distance: 5.4 < Threshold: 25.0
  └─ Score updated: 4 → 5 (SERVER VALIDATES)
```

#### C. Network Packet Inspection (Advanced)
To see EXACTLY what's sent over the wire:
1. Add this to client before sending:
```python
print(f"PACKET SENT: {json.dumps(message)}")
```
2. You'll see ONLY: `{"type": "input", "dx": 1, "dy": 0}`
3. Never see: `x`, `y`, `score`, or `coin_id` in client packets

### Test 3: Two-Client Synchronization
1. Run two clients side-by-side
2. Move player 1 to collect a coin
3. **Both clients** see the coin disappear simultaneously
4. **Both clients** see the score update simultaneously
5. This proves server is the single source of truth

**Why this matters**: If clients were authoritative, you'd see desync between the two views. Server authority ensures perfect synchronization.

## Requirements

- Python 3.8+
- pygame 2.5.2
- websockets 12.0

## Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Game

### Step 1: Start the Server
Open a terminal and run:
```bash
python server.py
```

You should see:
```
Server started on ws://localhost:8765
Waiting for players to connect...
```

### Step 2: Start First Client
Open a second terminal and run:
```bash
python client.py
```
- Enter your player name (e.g., "Alice")
- Press ENTER to join

### Step 3: Start Second Client
Open a third terminal and run:
```bash
python client.py
```
- Enter your player name (e.g., "Bob")
- Press ENTER to join

### Step 4: Select Game Mode
Once both clients are connected, you'll see the mode selection screen:
- Press **1** for **Sprint Mode** (first to 10 coins wins)
- Press **2** for **Endless Mode** (continuous play)

Either player can select the mode to start the game.

## Controls

- **WASD** or **Arrow Keys**: Move your player
- **1**: Select Sprint Mode (in lobby)
- **2**: Select Endless Mode (in lobby)
- **ESC**: Quit game

## Game Rules

### Sprint Mode
- First player to collect **10 coins** wins
- Game resets after someone wins
- Returns to lobby for mode selection

### Endless Mode
- No win condition
- Play indefinitely
- Compete for highest score

### Gameplay
- 3-5 coins spawn on the map at random intervals (every 2-3 seconds)
- Players move around the 800x600 play area
- Collect coins by touching them
- Boundary prevents players from leaving the map

## Demo Video Requirements

When recording your demo video, show:
1. **Two client windows side-by-side** (use split screen or record both)
2. **Name entry** for both players
3. Both clients connecting to the server
4. Mode selection process
5. **Smooth player movement** (demonstrating interpolation works despite 200ms latency)
6. **FPS counter** showing stable 60 FPS
7. **Ping display** showing ~400ms round-trip (200ms each way)
8. Coin collection and score updates
9. **Player name tags** above characters
10. Server-authoritative behavior (coins disappear for both players simultaneously)
11. Win condition with winner announcement (in Sprint Mode)

## Project Structure

```
coin-collector-multiplayer/
├── server.py          # Authoritative game server
├── client.py          # Pygame client with interpolation
├── requirements.txt   # Python dependencies
└── README.md         # This file
```

## Implementation Details

### Interpolation
The client implements entity interpolation to smooth out movement:
- Server sends position updates at 60 FPS
- Client interpolates between received positions
- Uses linear interpolation with smoothing factor (alpha = 0.3)
- Provides smooth rendering despite 200ms network delay

### Latency Simulation
- Server uses `asyncio.sleep(0.2)` before sending/receiving messages
- Simulates realistic network conditions
- Tests resilience of synchronization approach

### Collision Detection
- Server checks distance between player center and coin center
- Uses collision radius: `(PLAYER_SIZE + COIN_SIZE) / 2`
- Only server can validate coin pickups
- Prevents client-side cheating

## Assumptions Made

1. **Player Count**: Game requires exactly 2 players
2. **Player Assignment**: First connection = Alice (Red), Second = Bob (Blue)
3. **Window Size**: Fixed at 600x400 pixels for consistent gameplay
4. **Coin Spawning**: 3-5 coins maintained on map, spawn every 2-3 seconds
5. **Player Size**: 30x30 pixel squares
6. **Coin Size**: 20x20 pixel circles
7. **Movement Speed**: 5 pixels per frame at 60 FPS
8. **Win Score**: 10 coins for Sprint Mode
9. **Map Boundaries**: Simple boundary checking, no walls
10. **Respawn**: Players start at random positions, no respawn mechanism

## Potential Enhancements

- Add player names/customization
- Implement powerups (speed boost, magnet, etc.)
- Add obstacles/walls
- Support more than 2 players
- Add matchmaking/room system
- Implement lag compensation techniques (client-side prediction)
- Add sound effects and music
- Leaderboard for Endless Mode

## Testing Checklist

- [x] Server starts and accepts connections
- [x] Two clients can connect simultaneously
- [x] Mode selection works from either client
- [x] Players move smoothly despite 200ms latency
- [x] Coins spawn at intervals
- [x] Collision detection works (server-authoritative)
- [x] Scores update correctly
- [x] Sprint Mode: Game ends when player reaches 10 coins
- [x] Endless Mode: Game continues indefinitely
- [x] Boundary checking prevents out-of-bounds movement
- [x] Client disconnect handling
- [x] Multiple game rounds work correctly

## License

This project is created as a technical assessment for game development position.

---

## Project Information

**Built by:** Ishan Grover  
**Roll No.:** 22B1528  
**Email:** 22b1528@iitb.ac.in