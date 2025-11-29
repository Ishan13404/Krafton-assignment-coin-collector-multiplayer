import asyncio
import websockets
import pygame
import json
import sys
import time
from typing import Dict, Optional

# Game constants
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 400
PLAYER_SIZE = 30
COIN_SIZE = 20
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GOLD = (255, 215, 0)
GRAY = (100, 100, 100)
RED = (255, 100, 100)
GREEN = (100, 255, 100)
DARK_GRAY = (50, 50, 50)

# Interpolation settings
INTERPOLATION_DELAY = 0.1  # 100ms buffer for smooth interpolation


class InterpolatedEntity:
    """Entity with position interpolation for smooth rendering"""
    def __init__(self, entity_id: str, x: float, y: float, name: str = "Player"):
        self.id = entity_id
        self.name = name
        self.server_x = x
        self.server_y = y
        self.display_x = x
        self.display_y = y
        self.target_x = x
        self.target_y = y
        self.score = 0
        self.color = [255, 255, 255]

    def update_server_position(self, x: float, y: float):
        """Update the target position from server"""
        self.target_x = x
        self.target_y = y

    def interpolate(self, alpha: float = 0.3):
        """Smoothly interpolate towards target position"""
        # Linear interpolation with smoothing factor
        old_display_x = self.display_x
        old_display_y = self.display_y
        
        self.display_x += (self.target_x - self.display_x) * alpha
        self.display_y += (self.target_y - self.display_y) * alpha
        
        # Log interpolation to prove smooth movement
        distance_to_target = ((self.target_x - self.display_x)**2 + (self.target_y - self.display_y)**2)**0.5
        if distance_to_target > 1 and int(self.display_x) % 50 == 0:  # Log occasionally
            print(f"[INTERPOLATION] Smoothing position: display=({self.display_x:.1f},{self.display_y:.1f}) → target=({self.target_x:.1f},{self.target_y:.1f})")


class CoinCollectorClient:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Coin Collector - Multiplayer")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        self.tiny_font = pygame.font.Font(None, 18)

        # Game state
        self.running = True
        self.connected = False
        self.game_started = False
        self.my_player_id = None
        self.players: Dict[str, InterpolatedEntity] = {}
        self.coins = []
        self.game_mode = None
        self.winner = None
        self.winner_name = ""

        # Input state
        self.keys = {
            'left': False,
            'right': False,
            'up': False,
            'down': False
        }
        self.last_input_sent = {'dx': 0, 'dy': 0}

        # FPS and latency tracking
        self.fps = 0
        self.frame_times = []
        self.simulated_latency = 200  # Default

        # WebSocket
        self.websocket = None
        self.receive_task = None

    async def connect_to_server(self, uri: str = "ws://localhost:8765"):
        """Connect to game server"""
        try:
            # Simulate 200ms latency on client side too
            self.websocket = await websockets.connect(uri)
            self.connected = True
            print(f"Connected to server at {uri}")

            # Start receiving messages
            self.receive_task = asyncio.create_task(self.receive_messages())

        except Exception as e:
            print(f"Failed to connect: {e}")
            self.running = False

    async def receive_messages(self):
        """Continuously receive messages from server"""
        try:
            async for message in self.websocket:
                await self.handle_server_message(message)
        except websockets.exceptions.ConnectionClosed:
            print("Connection to server closed")
            self.connected = False
            self.running = False

    async def handle_server_message(self, message: str):
        """Handle incoming server messages"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'welcome':
                self.my_player_id = data['player_id']
                self.simulated_latency = data.get('simulated_latency', 200)
                player_data = data['player_data']
                # Create interpolated entity for self
                player = InterpolatedEntity(
                    self.my_player_id,
                    player_data['x'],
                    player_data['y'],
                    player_data.get('name', 'Player')
                )
                player.color = player_data['color']
                self.players[self.my_player_id] = player
                print(f"Assigned player ID: {self.my_player_id}")
                print(f"Player name: {player.name}")
                print(f"Network latency: {self.simulated_latency}ms")

            elif msg_type == 'lobby_ready':
                print(data['message'])

            elif msg_type == 'game_start':
                self.game_started = True
                self.game_mode = data['mode']
                self.winner = None
                self.winner_name = ""
                print(f"Game started! Mode: {self.game_mode}")

            elif msg_type == 'state_update':
                self.update_game_state(data)

            elif msg_type == 'game_over':
                self.winner = data['winner']
                self.winner_name = data.get('winner_name', 'Unknown')
                self.game_started = False
                print(f"Game Over! Winner: {self.winner_name}")

        except json.JSONDecodeError:
            print("Invalid JSON received")

    def update_game_state(self, data: dict):
        """Update local game state from server state"""
        # Update players
        server_player_ids = set()
        for player_data in data.get('players', []):
            player_id = player_data['id']
            player_name = player_data.get('name', 'Player')
            server_player_ids.add(player_id)

            if player_id in self.players:
                # Update existing player
                entity = self.players[player_id]
                old_x, old_y = entity.target_x, entity.target_y
                entity.update_server_position(player_data['x'], player_data['y'])
                entity.score = player_data['score']
                entity.color = player_data['color']
                entity.name = player_name
                
                # LOG: Client receives authoritative position from server
                if player_id == self.my_player_id and (old_x != player_data['x'] or old_y != player_data['y']):
                    # Only log occasionally to avoid spam (every ~20 updates)
                    if int(player_data['x']) % 20 == 0:
                        print(f"[CLIENT] Received authoritative position from server: ({player_data['x']:.1f}, {player_data['y']:.1f})")
            else:
                # Create new player
                entity = InterpolatedEntity(
                    player_id,
                    player_data['x'],
                    player_data['y'],
                    player_name
                )
                entity.score = player_data['score']
                entity.color = player_data['color']
                self.players[player_id] = entity
                print(f"[CLIENT] New player joined: {player_name}")

        # Remove disconnected players
        current_ids = set(self.players.keys())
        for player_id in current_ids - server_player_ids:
            if player_id in self.players:
                print(f"[CLIENT] Player {self.players[player_id].name} disconnected")
            del self.players[player_id]

        # Update coins (no interpolation needed)
        old_coin_count = len(self.coins)
        self.coins = data.get('coins', [])
        if len(self.coins) < old_coin_count:
            print(f"[CLIENT] Coin removed by server (collision detected server-side)")
        
        self.game_started = data.get('game_started', False)
        self.game_mode = data.get('mode', 'endless')

    async def send_input(self):
        """Send input to server (only intent, not position)"""
        if not self.connected or not self.websocket:
            return

        # Calculate input vector from keys
        dx = 0
        dy = 0

        if self.keys['left']:
            dx -= 1
        if self.keys['right']:
            dx += 1
        if self.keys['up']:
            dy -= 1
        if self.keys['down']:
            dy += 1

        # Only send if input changed
        if dx != self.last_input_sent['dx'] or dy != self.last_input_sent['dy']:
            message = {
                'type': 'input',
                'dx': dx,
                'dy': dy
            }
            await self.websocket.send(json.dumps(message))
            self.last_input_sent = {'dx': dx, 'dy': dy}
            # LOG: Client sends only intent, NOT position
            if dx != 0 or dy != 0:
                print(f"[CLIENT] Sent INPUT intent to server: dx={dx}, dy={dy} (NO position sent)")
            else:
                print(f"[CLIENT] Sent STOP intent to server")

    async def send_game_start(self, mode: str):
        """Request game start with mode"""
        if not self.connected or not self.websocket:
            return

        message = {
            'type': 'start_game',
            'mode': mode
        }
        await self.websocket.send(json.dumps(message))

    def handle_events(self):
        """Handle Pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                # Movement keys
                if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                    self.keys['left'] = True
                elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                    self.keys['right'] = True
                elif event.key == pygame.K_UP or event.key == pygame.K_w:
                    self.keys['up'] = True
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    self.keys['down'] = True

                # Game mode selection
                elif event.key == pygame.K_1 and not self.game_started:
                    asyncio.create_task(self.send_game_start('sprint'))
                elif event.key == pygame.K_2 and not self.game_started:
                    asyncio.create_task(self.send_game_start('endless'))

                # Quit
                elif event.key == pygame.K_ESCAPE:
                    self.running = False

            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                    self.keys['left'] = False
                elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                    self.keys['right'] = False
                elif event.key == pygame.K_UP or event.key == pygame.K_w:
                    self.keys['up'] = False
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    self.keys['down'] = False

    def update(self):
        """Update game state (interpolation)"""
        # Interpolate all player positions for smooth rendering
        for player in self.players.values():
            player.interpolate(alpha=0.3)

        # Update FPS
        current_time = time.time()
        self.frame_times.append(current_time)
        # Keep only last second of frame times
        self.frame_times = [t for t in self.frame_times if current_time - t < 1.0]
        self.fps = len(self.frame_times)

    def draw(self):
        """Render the game"""
        self.screen.fill(BLACK)

        if not self.connected:
            # Connection lost
            text = self.font.render("Connection Lost", True, RED)
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2))

        elif not self.game_started:
            # Lobby screen
            if len(self.players) < 2:
                text = self.font.render("Waiting for players...", True, WHITE)
                self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, 150))
                count_text = self.small_font.render(f"Players: {len(self.players)}/2", True, GRAY)
                self.screen.blit(count_text, (SCREEN_WIDTH // 2 - count_text.get_width() // 2, 200))
                
                # Show connected players
                y_offset = 240
                for player in self.players.values():
                    player_text = self.small_font.render(f"✓ {player.name}", True, tuple(player.color))
                    self.screen.blit(player_text, (SCREEN_WIDTH // 2 - player_text.get_width() // 2, y_offset))
                    y_offset += 30
            else:
                title = self.font.render("Select Game Mode", True, WHITE)
                self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))

                # Show players ready
                y_offset = 150
                for player in self.players.values():
                    player_text = self.small_font.render(f"✓ {player.name} (Ready)", True, tuple(player.color))
                    self.screen.blit(player_text, (SCREEN_WIDTH // 2 - player_text.get_width() // 2, y_offset))
                    y_offset += 30

                # Game mode options
                y_offset += 20
                mode1 = self.small_font.render("Press 1: Sprint Mode", True, GOLD)
                mode2 = self.small_font.render("Press 2: Endless Mode", True, GOLD)
                self.screen.blit(mode1, (SCREEN_WIDTH // 2 - mode1.get_width() // 2, y_offset))
                self.screen.blit(mode2, (SCREEN_WIDTH // 2 - mode2.get_width() // 2, y_offset + 30))
                
                # Instructions
                y_offset += 80
                inst1 = self.tiny_font.render("Sprint: First to 10 coins wins", True, GRAY)
                inst2 = self.tiny_font.render("Endless: Play forever", True, GRAY)
                self.screen.blit(inst1, (SCREEN_WIDTH // 2 - inst1.get_width() // 2, y_offset))
                self.screen.blit(inst2, (SCREEN_WIDTH // 2 - inst2.get_width() // 2, y_offset + 20))

        else:
            # Draw boundary
            pygame.draw.rect(self.screen, GRAY, (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), 3)

            # Draw coins
            for coin in self.coins:
                pygame.draw.circle(
                    self.screen,
                    GOLD,
                    (int(coin['x']), int(coin['y'])),
                    COIN_SIZE // 2
                )
                # Draw coin outline
                pygame.draw.circle(
                    self.screen,
                    WHITE,
                    (int(coin['x']), int(coin['y'])),
                    COIN_SIZE // 2,
                    2
                )

            # Draw players
            for player_id, player in self.players.items():
                color = tuple(player.color)

                # Draw player square
                pygame.draw.rect(
                    self.screen,
                    color,
                    (int(player.display_x - PLAYER_SIZE // 2),
                     int(player.display_y - PLAYER_SIZE // 2),
                     PLAYER_SIZE,
                     PLAYER_SIZE)
                )

                # Highlight own player
                if player_id == self.my_player_id:
                    pygame.draw.rect(
                        self.screen,
                        WHITE,
                        (int(player.display_x - PLAYER_SIZE // 2),
                         int(player.display_y - PLAYER_SIZE // 2),
                         PLAYER_SIZE,
                         PLAYER_SIZE),
                        3
                    )

                # Draw player name above
                name_text = self.tiny_font.render(player.name, True, WHITE)
                self.screen.blit(
                    name_text,
                    (int(player.display_x - name_text.get_width() // 2),
                     int(player.display_y - PLAYER_SIZE // 2 - 20))
                )

            # Draw scores
            y_offset = 10
            mode_text = self.small_font.render(
                f"Mode: {'Sprint' if self.game_mode == 'sprint' else 'Endless'}",
                True,
                WHITE
            )
            self.screen.blit(mode_text, (10, y_offset))
            y_offset += 30

            for player_id, player in self.players.items():
                score_text = self.small_font.render(
                    f"{player.name}: {player.score}",
                    True,
                    tuple(player.color)
                )
                self.screen.blit(score_text, (10, y_offset))
                y_offset += 25

            # Draw winner message
            if self.winner:
                winner_text = self.font.render("GAME OVER!", True, GOLD)
                self.screen.blit(
                    winner_text,
                    (SCREEN_WIDTH // 2 - winner_text.get_width() // 2, SCREEN_HEIGHT // 2 - 60)
                )

                if self.winner == self.my_player_id:
                    msg = f"🎉 {self.players[self.my_player_id].name} Wins! 🎉"
                    msg_color = GREEN
                else:
                    msg = f"{self.winner_name} Wins!"
                    msg_color = WHITE

                msg_text = self.small_font.render(msg, True, msg_color)
                self.screen.blit(
                    msg_text,
                    (SCREEN_WIDTH // 2 - msg_text.get_width() // 2, SCREEN_HEIGHT // 2)
                )

                # Show final scores
                y_offset = SCREEN_HEIGHT // 2 + 40
                for player_id, player in sorted(self.players.items(), key=lambda x: x[1].score, reverse=True):
                    score_text = self.tiny_font.render(
                        f"{player.name}: {player.score} coins",
                        True,
                        tuple(player.color)
                    )
                    self.screen.blit(
                        score_text,
                        (SCREEN_WIDTH // 2 - score_text.get_width() // 2, y_offset)
                    )
                    y_offset += 25

        # Draw FPS and Latency (always visible during game)
        if self.connected:
            fps_text = self.tiny_font.render(f"FPS: {self.fps}", True, GREEN if self.fps >= 55 else RED)
            self.screen.blit(fps_text, (SCREEN_WIDTH - 100, 10))

            latency_text = self.tiny_font.render(f"Latency: {int(self.simulated_latency)}ms", True, GRAY)
            self.screen.blit(latency_text, (SCREEN_WIDTH - 100, 30))

        # Draw controls hint
        controls = self.small_font.render("Controls: WASD or Arrow Keys", True, GRAY)
        self.screen.blit(controls, (SCREEN_WIDTH - controls.get_width() - 10, SCREEN_HEIGHT - 30))

        pygame.display.flip()

    async def run(self):
        """Main game loop"""
        await self.connect_to_server()

        while self.running:
            self.handle_events()
            await self.send_input()
            self.update()
            self.draw()
            self.clock.tick(FPS)

            # Small async yield
            await asyncio.sleep(0.001)

        # Cleanup
        if self.websocket:
            await self.websocket.close()
        pygame.quit()


async def main():
    client = CoinCollectorClient()
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())