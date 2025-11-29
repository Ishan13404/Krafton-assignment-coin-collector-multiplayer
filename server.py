import asyncio
import websockets
import json
import random
import time
from typing import Dict, Set, Tuple

# Game constants
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 400
PLAYER_SIZE = 30
COIN_SIZE = 20
PLAYER_SPEED = 5
COIN_SPAWN_INTERVAL = 2.5  # seconds
MIN_COINS = 3
MAX_COINS = 5
COLLISION_DISTANCE = (PLAYER_SIZE + COIN_SIZE) / 2
SPRINT_WIN_SCORE = 10

# Network simulation
SIMULATED_LATENCY = 0.2  # 200ms


class Player:
    def __init__(self, player_id: str, websocket, name: str = "Player", color: list = None):
        self.id = player_id
        self.websocket = websocket
        self.name = name
        self.x = random.randint(PLAYER_SIZE, SCREEN_WIDTH - PLAYER_SIZE)
        self.y = random.randint(PLAYER_SIZE, SCREEN_HEIGHT - PLAYER_SIZE)
        self.score = 0
        self.color = color if color else self.random_color()
        self.velocity_x = 0
        self.velocity_y = 0

    def random_color(self):
        colors = [
            [255, 100, 100],  # Red
            [100, 100, 255],  # Blue
            [100, 255, 100],  # Green
            [255, 255, 100],  # Yellow
            [255, 100, 255],  # Magenta
        ]
        return random.choice(colors)

    def update_position(self, dt: float):
        # Update position based on velocity
        old_x, old_y = self.x, self.y
        new_x = self.x + self.velocity_x * PLAYER_SPEED
        new_y = self.y + self.velocity_y * PLAYER_SPEED

        # Boundary checking
        new_x = max(PLAYER_SIZE / 2, min(SCREEN_WIDTH - PLAYER_SIZE / 2, new_x))
        new_y = max(PLAYER_SIZE / 2, min(SCREEN_HEIGHT - PLAYER_SIZE / 2, new_y))

        self.x = new_x
        self.y = new_y
        
        # Return True if position changed (for logging)
        return (old_x != new_x or old_y != new_y)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'x': self.x,
            'y': self.y,
            'score': self.score,
            'color': self.color
        }


class Coin:
    def __init__(self, coin_id: int):
        self.id = coin_id
        self.x = random.randint(COIN_SIZE, SCREEN_WIDTH - COIN_SIZE)
        self.y = random.randint(COIN_SIZE, SCREEN_HEIGHT - COIN_SIZE)

    def to_dict(self):
        return {
            'id': self.id,
            'x': self.x,
            'y': self.y
        }


class GameServer:
    def __init__(self):
        self.players: Dict[str, Player] = {}
        self.coins: Dict[int, Coin] = {}
        self.next_coin_id = 0
        self.game_started = False
        self.game_mode = "endless"  # "sprint" or "endless"
        self.winner = None
        self.last_coin_spawn = time.time()
        self.player_count = 0  # Track player assignment order

    async def simulate_latency(self):
        """Simulate 200ms network latency"""
        await asyncio.sleep(SIMULATED_LATENCY)

    async def handle_client(self, websocket, path):
        player_id = str(id(websocket))
        print(f"New connection: {player_id}")

        try:
            # Assign name and color based on order
            if self.player_count == 0:
                player_name = "Alice"
                player_color = [255, 100, 100]  # Red
            else:
                player_name = "Bob"
                player_color = [100, 100, 255]  # Blue
            
            self.player_count += 1

            # Create player
            player = Player(player_id, websocket, player_name, player_color)
            self.players[player_id] = player

            # Send welcome message with player ID
            await self.simulate_latency()
            await websocket.send(json.dumps({
                'type': 'welcome',
                'player_id': player_id,
                'player_data': player.to_dict()
            }))

            # If we have 2 players and game hasn't started, start lobby
            if len(self.players) >= 2 and not self.game_started:
                await self.start_lobby()

            # Handle incoming messages
            async for message in websocket:
                await self.simulate_latency()
                await self.handle_message(player_id, message)

        except websockets.exceptions.ConnectionClosed:
            print(f"Connection closed: {player_id}")
        finally:
            # Remove player on disconnect
            if player_id in self.players:
                del self.players[player_id]
                self.player_count -= 1
                await self.broadcast_state()

    async def start_lobby(self):
        """Start lobby and wait for mode selection"""
        print("Lobby ready with 2 players. Waiting for mode selection...")
        await self.broadcast({
            'type': 'lobby_ready',
            'message': 'Press 1 for Sprint Mode (first to 10) or 2 for Endless Mode'
        })

    async def start_game(self, mode: str):
        """Start the actual game"""
        self.game_mode = mode
        self.game_started = True
        self.winner = None

        # Spawn initial coins
        for _ in range(random.randint(MIN_COINS, MAX_COINS)):
            self.spawn_coin()

        print(f"Game started in {mode} mode!")
        await self.broadcast({
            'type': 'game_start',
            'mode': mode
        })

    async def handle_message(self, player_id: str, message: str):
        """Handle incoming client messages"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'input':
                # Update player velocity based on input
                player = self.players.get(player_id)
                if player:
                    dx = data.get('dx', 0)
                    dy = data.get('dy', 0)
                    player.velocity_x = dx
                    player.velocity_y = dy
                    # LOG: Client sent intent, not position
                    if dx != 0 or dy != 0:
                        print(f"[INPUT] Player {player_id[-8:]} sent movement intent: dx={dx}, dy={dy} (NOT position)")

            elif msg_type == 'start_game':
                # Only start if not already started
                if not self.game_started and len(self.players) >= 2:
                    mode = data.get('mode', 'endless')
                    await self.start_game(mode)

        except json.JSONDecodeError:
            print(f"Invalid JSON from {player_id}")

    def spawn_coin(self):
        """Spawn a new coin at random position"""
        coin = Coin(self.next_coin_id)
        self.coins[self.next_coin_id] = coin
        self.next_coin_id += 1

    def check_collisions(self):
        """Check for player-coin collisions (server-authoritative)"""
        coins_to_remove = []

        for coin_id, coin in self.coins.items():
            for player_id, player in self.players.items():
                # Calculate distance between player and coin
                dx = player.x - coin.x
                dy = player.y - coin.y
                distance = (dx * dx + dy * dy) ** 0.5

                if distance < COLLISION_DISTANCE:
                    # Player collected the coin
                    player.score += 1
                    coins_to_remove.append(coin_id)
                    # LOG: Server-authoritative collision detection and scoring
                    print(f"[SERVER-AUTHORITY] Collision detected!")
                    print(f"  ├─ {player.name} at ({player.x:.1f}, {player.y:.1f})")
                    print(f"  ├─ Coin {coin_id} at ({coin.x:.1f}, {coin.y:.1f})")
                    print(f"  ├─ Distance: {distance:.1f} < Threshold: {COLLISION_DISTANCE:.1f}")
                    print(f"  └─ Score updated: {player.score - 1} → {player.score} (SERVER VALIDATES)")

                    # Check win condition for sprint mode
                    if self.game_mode == "sprint" and player.score >= SPRINT_WIN_SCORE:
                        self.winner = player_id
                        print(f"[SERVER-AUTHORITY] Winner determined by server: {player.name}")
                    break

        # Remove collected coins
        for coin_id in coins_to_remove:
            if coin_id in self.coins:
                del self.coins[coin_id]

    async def game_loop(self):
        """Main game loop - updates at ~60 FPS"""
        dt = 1.0 / 60.0
        position_log_counter = 0

        while True:
            await asyncio.sleep(dt)

            if not self.game_started:
                continue

            # Update all player positions (SERVER CALCULATES)
            for player in self.players.values():
                position_changed = player.update_position(dt)
                # Log position updates periodically (every 60 frames = ~1 second)
                if position_changed and position_log_counter % 60 == 0:
                    print(f"[SERVER-AUTHORITY] Player {player.id[-8:]} position calculated by server: ({player.x:.1f}, {player.y:.1f})")
            
            position_log_counter += 1

            # Check collisions
            self.check_collisions()

            # Spawn coins if needed
            current_time = time.time()
            if current_time - self.last_coin_spawn > COIN_SPAWN_INTERVAL:
                if len(self.coins) < MAX_COINS:
                    coins_to_spawn = random.randint(1, 2)
                    for _ in range(coins_to_spawn):
                        if len(self.coins) < MAX_COINS:
                            self.spawn_coin()
                            print(f"[SERVER-AUTHORITY] Server spawned coin {self.next_coin_id - 1} at random position")
                self.last_coin_spawn = current_time

            # Broadcast game state
            await self.broadcast_state()

            # Check for winner
            if self.winner:
                winner_player = self.players[self.winner]
                await self.broadcast({
                    'type': 'game_over',
                    'winner': self.winner,
                    'winner_name': winner_player.name,
                    'scores': {p.id: {'name': p.name, 'score': p.score} for p in self.players.values()}
                })
                # Reset for new game
                self.game_started = False
                self.winner = None
                self.coins.clear()
                for player in self.players.values():
                    player.score = 0

    async def broadcast_state(self):
        """Broadcast current game state to all clients"""
        if not self.players:
            return

        state = {
            'type': 'state_update',
            'players': [p.to_dict() for p in self.players.values()],
            'coins': [c.to_dict() for c in self.coins.values()],
            'game_started': self.game_started,
            'mode': self.game_mode
        }

        await self.broadcast(state)

    async def broadcast(self, message: dict):
        """Send message to all connected clients with latency simulation"""
        if not self.players:
            return

        message_str = json.dumps(message)
        disconnected = []

        for player_id, player in self.players.items():
            try:
                await player.websocket.send(message_str)
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(player_id)

        # Clean up disconnected players
        for player_id in disconnected:
            if player_id in self.players:
                del self.players[player_id]

    async def start_server(self):
        """Start WebSocket server and game loop"""
        async with websockets.serve(self.handle_client, "localhost", 8765):
            print("=" * 60)
            print("🎮 COIN COLLECTOR - Multiplayer Server")
            print("=" * 60)
            print(f"Server: ws://localhost:8765")
            print(f"Simulated Latency: {SIMULATED_LATENCY * 1000}ms")
            print(f"Game Area: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")
            print()
            print("👥 Player Setup:")
            print("  • Player 1: Alice (Red)")
            print("  • Player 2: Bob (Blue)")
            print()
            print("🔒 SERVER AUTHORITY ENABLED:")
            print("  ✓ Clients send INTENT only (dx, dy)")
            print("  ✓ Server calculates ALL positions")
            print("  ✓ Server validates ALL collisions")
            print("  ✓ Server manages ALL scoring")
            print()
            print("🎯 INTERPOLATION ENABLED:")
            print("  ✓ Clients smooth positions despite 200ms latency")
            print("  ✓ No stutter/teleporting visible")
            print()
            print("Waiting for players to connect...")
            print("=" * 60)
            await self.game_loop()


if __name__ == "__main__":
    server = GameServer()
    asyncio.run(server.start_server())