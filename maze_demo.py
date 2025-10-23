# --------------------------------------------------------------
# Random Maze First-Person Demo (Ursina 8.2.0)
# Modified: player now contains running/stamina/cooldown & ESC handling
# --------------------------------------------------------------
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from collections import deque          # <-- needed for BFS
import random
import math                           # for optional exponential curve
import time
# --------------------------------------------------------------
# Simple chasing entity (uses chaser.png as a billboard quad)
# (unchanged)
# --------------------------------------------------------------
class Chaser(Entity):
    """
    Billboard sprite that pursues the player.
    Speed increases the longer the player survives.
    """
    def __init__(self,
                 player,
                 maze,
                 cell_size,
                 wall_height,
                 base_speed:float = 3.0,
                 speed_increment:float = 0.25,
                 max_speed:float = 12.0,
                 **kwargs):
        super().__init__(
            model='quad',
            texture='resources/textures/chaser/chaser.png',
            texture_normal='resources/textures/chaser/chaser_normal.png',
            billboard=True,
            unlit=True,
            collider='box',
            **kwargs,
        )

        # ------------------------------------------------------------------
        # References & movement parameters
        # ------------------------------------------------------------------
        self.player = player
        self.maze   = maze
        self.cell_size   = cell_size
        self.wall_height = wall_height

        # Speed-ramp configuration
        self.base_speed      = base_speed
        self.speed_increment = speed_increment
        self.max_speed       = max_speed
        self.speed = self.base_speed

        # Remember when the monster was spawned
        self.spawn_time = time.time()          # <-- call!

        # Path-finding bookkeeping
        self.recalc_interval = 0.2
        self._timer   = 0
        self._path    = []          # list of (x, y) cells
        self._path_index = 0

        # ------------------------------------------------------------------
        # Sound – manual attenuation
        # ------------------------------------------------------------------
        # Old implementation, causes long sound files to stop after a few seconds due to a bug in the library
        #self.sound = Audio(
        #    'resources/sounds/chaser/chaser.mp3',
        #    loop=True,
        #    autoplay=True,
        #    spatial=False,
        #    volume=1.0,
        #)

        # stream the file with Panda3D and hand the AudioSound to Ursina
        clip = loader.loadMusic('resources/sounds/chaser/chaser.mp3')
        clip.setLoop(True)                 # keep looping
        # (volume will be overridden later by the distance‑attenuation logic)
        
        self.sound = Audio(
            clip,                          # <-- pass the loaded AudioSound
            loop=True,                     # keep these flags for consistency
            autoplay=True,
            spatial=False,                 # keep 2‑D sound; set to True if you want 3‑D panning
            volume=1.0,                    # initial volume (overridden by update())
            auto_destroy=False,            # keep entity alive even if sound stops
        )
        self.max_hear_distance = 30.0
        self.base_volume = 0.6

    # ------------------------------------------------------------------
    # Called every frame by Ursina
    # ------------------------------------------------------------------
    def update(self):
        if is_paused:
            return
        # --------------------------------------------------------------
        # 0. Update speed according to survival time
        # --------------------------------------------------------------
        elapsed = time.time() - self.spawn_time
        self.speed = min(self.max_speed,
                         self.base_speed + self.speed_increment * elapsed)

        # --------------------------------------------------------------
        # 1. Recalculate BFS path occasionally
        # --------------------------------------------------------------
        self._timer += time.dt
        if self._timer >= self.recalc_interval:
            self._timer = 0
            self._recalc_path()

        # --------------------------------------------------------------
        # 2. Follow BFS path if one exists
        # --------------------------------------------------------------
        moved = False
        if self._path:
            target_cell = self._path[self._path_index]
            target_world = Vec3(
                target_cell[0] * self.cell_size,
                self.y,
                target_cell[1] * self.cell_size,
            )
            direction = target_world - self.position
            dist = direction.length()

            if dist < 0.1:
                if self._path_index < len(self._path) - 1:
                    self._path_index += 1
                else:
                    self._path = []
            else:
                self.position += direction.normalized() * self.speed * time.dt
                moved = True

        # --------------------------------------------------------------
        # 3. Fallback chase when no path or near the player
        # --------------------------------------------------------------
        player_dist = distance_2d(self.position, self.player.position)
        # if no path or player is within one cell radius, go direct
        if not moved or player_dist < self.cell_size * 1.2:
            to_player = self.player.position - self.position
            ray = raycast(
                self.position,
                to_player.normalized(),
                distance=to_player.length(),
                ignore=(self, self.player),
                debug=False
            )
            # if we can see the player or already close, move directly
            if (not ray.hit) or player_dist < 2.5:
                self.position += to_player.normalized() * self.speed * time.dt

        # --------------------------------------------------------------
        # 4. “Caught” check
        # --------------------------------------------------------------
        if distance(self.position, self.player.position) < 3.0:
            print('☠  Caught! Game Over')
            application.quit()

        # --------------------------------------------------------------
        # 5. Sound & volume attenuation (unchanged)
        # --------------------------------------------------------------
        self.sound.position = self.position
        if not self.sound.spatial:
            d = distance(self.position, self.player.position)
            vol = max(0.0, min(1.0,
                      (self.max_hear_distance - d) / self.max_hear_distance)) * self.base_volume
            self.sound.volume = vol

    # ------------------------------------------------------------------
    # Private: recompute shortest path (unchanged)
    # ------------------------------------------------------------------
    def _recalc_path(self):
        start = (
            int(round(self.position.x / self.cell_size)),
            int(round(self.position.z / self.cell_size)),
        )
        goal = (
            int(round(self.player.position.x / self.cell_size)),
            int(round(self.player.position.z / self.cell_size)),
        )
        if start == goal:
            self._path = []
            return

        self._path = bfs_path(self.maze, start, goal)
        if len(self._path) >= 2:
            self._path_index = 1
        else:
            self._path = []

# --------------------------------------------------------------
# Maze generation – recursive backtracker (unchanged)
# --------------------------------------------------------------
class Maze:
    """Rectangular maze built with depth-first backtracking."""
    def __init__(self, width: int, height: int):
        self.width, self.height = width, height
        self.grid = [
            [{'visited': False,
              'walls': {'N': True, 'S': True, 'E': True, 'W': True}}
             for _ in range(height)] for _ in range(width)
        ]
        self._carve()
    def _carve(self):
        stack = []
        sx = random.randint(0, self.width - 1)
        sy = random.randint(0, self.height - 1)
        self.grid[sx][sy]['visited'] = True
        stack.append((sx, sy))
        while stack:
            x, y = stack[-1]
            neighbours = self._unvisited_neighbours(x, y)
            if neighbours:
                nx, ny, direction = random.choice(neighbours)
                self.grid[x][y]['walls'][direction] = False
                opposite = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
                self.grid[nx][ny]['walls'][opposite[direction]] = False
                self.grid[nx][ny]['visited'] = True
                stack.append((nx, ny))
            else:
                stack.pop()
    def _unvisited_neighbours(self, x, y):
        dirs = [
            ('N', (x, y + 1)),
            ('S', (x, y - 1)),
            ('E', (x + 1, y)),
            ('W', (x - 1, y)),
        ]
        result = []
        for d, (nx, ny) in dirs:
            if 0 <= nx < self.width and 0 <= ny < self.height:
                if not self.grid[nx][ny]['visited']:
                    result.append((nx, ny, d))
        return result

# --------------------------------------------------------------
# Helper functions for turning the logical maze into 3-D entities
# (unchanged)
# --------------------------------------------------------------
def neighbour_coords(x, y, direction, w, h):
    if direction == 'N':
        nx, ny = x, y + 1
    elif direction == 'S':
        nx, ny = x, y - 1
    elif direction == 'E':
        nx, ny = x + 1, y
    elif direction == 'W':
        nx, ny = x - 1, y
    else:
        return None, None
    if 0 <= nx < w and 0 <= ny < h:
        return nx, ny
    return None, None
def wall_transform(x, y, direction, wall_h, thickness, cell_size):
    half_h = wall_h / 2
    if direction == 'N':
        pos = (x * cell_size, half_h, (y + 0.5) * cell_size)
        scale = (cell_size, wall_h, thickness)
    elif direction == 'S':
        pos = (x * cell_size, half_h, (y - 0.5) * cell_size)
        scale = (cell_size, wall_h, thickness)
    elif direction == 'E':
        pos = ((x + 0.5) * cell_size, half_h, y * cell_size)
        scale = (thickness, wall_h, cell_size)
    elif direction == 'W':
        pos = ((x - 0.5) * cell_size, half_h, y * cell_size)
        scale = (thickness, wall_h, cell_size)
    else:
        pos = (x * cell_size, half_h, y * cell_size)
        scale = (cell_size, wall_h, cell_size)
    return pos, scale
def build_3d_maze(maze: Maze, wall_h=2.0, thickness=0.1, cell_size=1.0):
    # ---- floor ------------------------------------------------
    floor = Entity(
        model='cube',
        scale=(maze.width * cell_size, 0.1, maze.height * cell_size),
        position=((maze.width - 1) * cell_size / 2, -0.05, (maze.height - 1) * cell_size / 2),
        texture='resources/textures/level/floor_tile.png',           # <-- your texture here
        texture_normal='resources/textures/level/brick_normal.png',
        color=color.white,                  # keep white so texture shows correctly
        texture_scale=(maze.width, maze.height),  # repeat texture across the floor
        collider='box',
        name='floor',
    )
    # ---- walls ------------------------------------------------
    processed = set()
    walls = []
    for x in range(maze.width):
        for y in range(maze.height):
            cell = maze.grid[x][y]
            for direction, present in cell['walls'].items():
                if not present:
                    continue
                nx, ny = neighbour_coords(x, y, direction,
                                          maze.width, maze.height)
                if nx is None:               # boundary wall
                    edge_id = (x, y, direction)
                else:
                    edge_id = tuple(sorted(((x, y), (nx, ny))))
                if edge_id in processed:
                    continue
                processed.add(edge_id)
                pos, scale = wall_transform(x, y, direction,
                                            wall_h, thickness, cell_size)
                # Determine which axes the wall face spans
                if direction in ('N', 'S'):
                    tex_scale = (scale[0]/2, scale[1]/2)  # width x height
                else:  # 'E', 'W'
                    tex_scale = (scale[2]/2, scale[1]/2)  # depth x height

                wall = Entity(
                    model='cube',
                    texture='resources/textures/level/brick.png',
                    texture_normal='resources/textures/level/brick_normal.png',
                    color=color.white,
                    scale=scale,
                    position=pos,
                    collider='box',
                    texture_scale=tex_scale
                )
                walls.append(wall)
    return floor, walls
def spawn_random_crates(num_crates, maze, cell_size, wall_height):
    crates = []
    placed_positions = []

    def is_valid_position(x, y, world_pos, min_dist=3.0):
        """Check if position is valid (not near wall or another crate)."""
        # 1. Check distance from other crates
        for pos in placed_positions:
            if distance(world_pos, pos) < min_dist:
                return False

        # 2. Check maze cell — skip if too close to a wall
        cell = maze.grid[x][y]
        margin = cell_size * 0.35  # don’t go too close to walls
        # walls block edges; we only spawn if open enough
        if cell['walls']['N'] and world_pos.z > y * cell_size + margin:
            return False
        if cell['walls']['S'] and world_pos.z < y * cell_size - margin:
            return False
        if cell['walls']['E'] and world_pos.x > x * cell_size + margin:
            return False
        if cell['walls']['W'] and world_pos.x < x * cell_size - margin:
            return False
        return True

    tries = 0
    while len(crates) < num_crates and tries < num_crates * 10:
        tries += 1

        # pick a random maze cell
        x = random.randint(0, maze.width - 1)
        y = random.randint(0, maze.height - 1)

        # random offset inside that cell
        offset_x = random.uniform(-cell_size * 0.5, cell_size * 0.5)
        offset_z = random.uniform(-cell_size * 0.5, cell_size * 0.5)

        # crate properties
        size = random.uniform(1, 1.8)
        rot_y = random.uniform(0, 360)

        # compute world position
        pos = Vec3(x * cell_size + offset_x, size / 2, y * cell_size + offset_z)

        # ✅ skip if position invalid
        if not is_valid_position(x, y, pos):
            continue

        crate = Entity(
            model='cube',
            texture='resources/textures/level/crate.png',
            color=color.white,
            position=pos,
            scale=(size, size, size),
            rotation=(0, rot_y, 0),
            collider='box',
            name=f'crate_{x}_{y}'
        )

        # random color variation
        crate.color = color.rgb(
            random.randint(80, 120),
            random.randint(60, 80),
            random.randint(40, 60)
        )

        crates.append(crate)
        placed_positions.append(pos)

    return crates

# --------------------------------------------------------------
# Path-finding helpers (BFS) – respect the Maze walls (unchanged)
# --------------------------------------------------------------
def get_neighbors(maze, x, y):
    """Return a list of neighbour (nx, ny) cells that are reachable from (x, y)."""
    dirs = {
        'N': (0, 1),
        'S': (0, -1),
        'E': (1, 0),
        'W': (-1, 0)
    }
    result = []
    for d, (dx, dy) in dirs.items():
        if not maze.grid[x][y]['walls'][d]:          # wall missing → passage
            nx, ny = x + dx, y + dy
            if 0 <= nx < maze.width and 0 <= ny < maze.height:
                result.append((nx, ny))
    return result
def bfs_path(maze, start, goal):
    """
    Breadth-first search that returns a list of cells from *start* → *goal*.
    The list includes both the start and goal cells.
    If no path exists, an empty list is returned.
    """
    if start == goal:
        return [start]
    queue = deque([start])
    came_from = {start: None}
    while queue:
        cur = queue.popleft()
        if cur == goal:
            break
        for nb in get_neighbors(maze, *cur):
            if nb not in came_from:
                came_from[nb] = cur
                queue.append(nb)
    # Re-construct the path
    if goal not in came_from:
        return []                     # no path (shouldn’t happen in a perfect maze)
    path = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = came_from[cur]
    path.reverse()
    return path

# --------------------------------------------------------------
# Helper function for chaser to get you in corners
# --------------------------------------------------------------
def distance_2d(a, b):
    return math.sqrt((a.x - b.x)**2 + (a.z - b.z)**2)
# --------------------------------------------------------------
# Helper: pick a random spawn cell for the monster (unchanged)
# --------------------------------------------------------------
def random_spawn_cell(width, height, exclude, min_dist=4):
    """Return a random (x, y) cell that is at least *min_dist* cells away from *exclude*."""
    while True:
        cx = random.randint(0, width - 1)
        cy = random.randint(0, height - 1)
        if (cx, cy) != exclude and (abs(cx - exclude[0]) + abs(cy - exclude[1]) >= min_dist):
            return cx, cy

# --------------------------------------------------------------
# NEW: PlayerController subclass of FirstPersonController
# All running, stamina, cooldown and ESC handling lives here.
# --------------------------------------------------------------
class PlayerController(FirstPersonController):
    def __init__(self,
                 walk_speed=5,
                 run_multiplier=2.0,
                 max_stamina=5.0,
                 stamina_drain_rate=1.0,
                 stamina_recovery_rate=1.0,
                 stamina_cooldown=2.0,
                 stamina_bar_scale=0.4,
                 stamina_bar_y=-0.45,
                 *args, **kwargs):
        # speed passed to super will be set to walk_speed initially
        super().__init__(speed=walk_speed, *args, **kwargs)

        # speeds
        self.walk_speed = walk_speed
        self.run_multiplier = run_multiplier
        self.run_speed = self.walk_speed * self.run_multiplier

        # stamina mechanics
        self.max_stamina = max_stamina
        self.stamina = max_stamina
        self.stamina_drain_rate = stamina_drain_rate
        self.stamina_recovery_rate = stamina_recovery_rate
        self.stamina_cooldown = stamina_cooldown

        # cooldown bookkeeping
        self.can_run = True
        self._last_depleted_time = 0.0

        # UI: stamina bar attached to camera.ui
        self._stamina_bar_width = stamina_bar_scale
        self._stamina_bar_height = 0.03
        self._stamina_bar_y = stamina_bar_y

        # Use the same origin for bg and fg so they align.
        # We'll left-anchor both and position them so the left edge is at (center_x - width/2).
        left_anchor_x = -self._stamina_bar_width / 2
        origin = (-0.5, 0.5)

        # background (left anchored)
        self.stamina_bg = Entity(
            parent=camera.ui,
            model='quad',
            color=color.gray,
            scale=(self._stamina_bar_width, self._stamina_bar_height),
            position=(left_anchor_x, self._stamina_bar_y),
            origin=origin
        )

        # foreground (left-anchored via origin)
        self.stamina_bar = Entity(
            parent=camera.ui,
            model='quad',
            color=color.azure,
            scale=(self._stamina_bar_width, self._stamina_bar_height),
            position=(left_anchor_x, self._stamina_bar_y),
            origin=origin
        )
        # ---- Footstep sounds ---------------------------------------
        # You can replace 'step_walk.wav' and 'step_run.wav' with your own files.
        #self.walk_sounds = [Audio('step_walk.wav', autoplay=False) for _ in range(4)]
        #self.run_sounds  = [Audio('step_run.wav',  autoplay=False) for _ in range(4)]
        #self._footstep_timer = 0.0
        #self._footstep_interval_walk = 0.5  # seconds between steps when walking
        #self._footstep_interval_run  = 0.3  # faster when running
        #self._last_foot_index = 0

        # ensure player starts at walk speed
        self.speed = self.walk_speed

    def input(self, key):
        # keep default FirstPersonController input behavior
        super().input(key)

        # ESC handling inside player (your requested place)
        if key == 'escape':
            toggle_pause_menu()

    def update(self):
        if is_paused:
            return
        # keep default movement behavior
        super().update()

        # Running logic — handled inside player instance
        # Use global held_keys (Ursina)
        is_holding_shift = held_keys['shift']

        if is_holding_shift and self.stamina > 0 and self.can_run:
            # run
            self.speed = self.run_speed
            self.stamina -= self.stamina_drain_rate * time.dt
            if self.stamina <= 0:
                self.stamina = 0
                self.can_run = False
                self._last_depleted_time = time.time()
        else:
            # walk
            self.speed = self.walk_speed
            # check cooldown start/finish
            if not self.can_run:
                if (time.time() - self._last_depleted_time) >= self.stamina_cooldown:
                    self.can_run = True  # allow regen from now on
            # recover stamina only if allowed
            if self.can_run and self.stamina < self.max_stamina:
                self.stamina += self.stamina_recovery_rate * time.dt
                if self.stamina > self.max_stamina:
                    self.stamina = self.max_stamina

        # update stamina bar scale.x
        fill = self.stamina / self.max_stamina if self.max_stamina > 0 else 0
        # keep full width in X; origin left anchored so scale reduces to the right
        self.stamina_bar.scale_x = self._stamina_bar_width * fill

        # visual feedback: bar color when empty / low
        if self.stamina <= 0:
            self.stamina_bar.color = color.red
        elif self.stamina < self.max_stamina * 0.25:
            self.stamina_bar.color = color.rgb(255, 180, 0)  # orange-ish
        else:
            self.stamina_bar.color = color.green

        # ---- Footstep sound logic ----------------------------------
        #velocity = Vec3(self.forward * self.direction.z + self.right * self.direction.x)
        #moving = velocity.length() > 0.1

        #self._footstep_timer -= time.dt
        #if self.grounded and moving:
            # choose interval based on whether running or walking
            #interval = self._footstep_interval_run if self.speed == self.run_speed else self._footstep_interval_walk
            #if self._footstep_timer <= 0:
                # play next footstep sound
                #if self.speed == self.run_speed:
                    #sound = random.choice(self.run_sounds)
                #else:
                    #sound = random.choice(self.walk_sounds)
                #sound.pitch = random.uniform(0.9, 1.1)  # small variation
                #sound.volume = 0.6 if self.speed == self.walk_speed else 1.0
                #sound.play()

                # reset timer
                #self._footstep_timer = interval
        #else:
            # reset timer if not moving
            #self._footstep_timer = 0
# --------------------------------------------------------------
# Pause menu
# --------------------------------------------------------------
is_paused = False
pause_menu = None

def toggle_pause_menu():
    global is_paused, pause_menu, chaser

    if not pause_menu:
        # --- create menu only once ---
        pause_menu = Entity(parent=camera.ui, enabled=False)
        # Full-screen black transparent overlay
        Entity(
            parent=pause_menu,
            model='quad',
            color=color.rgba(0, 0, 0, 0.5),  # mostly black but still see-through
            scale=(2, 2)
        )
        # “Paused” text
        Text(
            text='PAUSED',
            parent=pause_menu,
            origin=(0, 0),
            position=(0, 0.15),
            color=color.rgb(255, 0, 0),   # bright red text
            scale=3
        )
        # Continue button
        Button(
            text='CONTINUE',
            parent=pause_menu,
            color=color.rgb(100, 0, 0),   # dark red button
            text_color=color.rgb(0, 0, 0),
            scale=(0.3, 0.1),
            position=(0, 0),
            on_click=lambda: toggle_pause_menu()
        )
        # Quit button
        Button(
            text='QUIT',
            parent=pause_menu,
            color=color.rgb(100, 0, 0),
            text_color=color.rgb(0, 0, 0),
            scale=(0.3, 0.1),
            position=(0, -0.15),
            on_click=application.quit
        )
    # --- toggle on/off ---
    is_paused = not is_paused
    pause_menu.enabled = is_paused
    time.paused = is_paused
    mouse.locked = not is_paused
    # --- handle chaser sound ---
    try:
        if chaser and hasattr(chaser, 'sound'):
            if is_paused:
                chaser.sound.pause()
            else:
                chaser.sound.resume()
    except NameError:
        pass
# --------------------------------------------------------------
# Main – set up Ursina, create the maze, drop the player, etc.
# (mostly unchanged; player replaced by PlayerController)
# --------------------------------------------------------------
def main():
    app = Ursina()
    window.title = 'Random Maze – First-Person Demo'
    window.fullscreen = False
    window.borderless = False
    window.exit_button.visible = True
    window.fps_counter.enabled = True
    # ---- tweakable parameters ------------------------------------
    MAZE_W, MAZE_H = 15, 15               # cells horizontally / vertically
    WALL_HEIGHT = 5.0
    WALL_THICKNESS = 0.2                  # optional: slightly thicker walls
    CELL_SIZE = 5.0                        # <-- larger = wider corridors
    # ---- generate maze and build its 3-D representation ------------
    maze = Maze(MAZE_W, MAZE_H)
    floor, wall_entities = build_3d_maze(
        maze,
        wall_h=WALL_HEIGHT,
        thickness=WALL_THICKNESS,
        cell_size=CELL_SIZE,
    )
    # --- spawn random crates ------------------------------------
    num_crates = 25  # adjust how many you want
    crates = spawn_random_crates(num_crates, maze, CELL_SIZE, WALL_HEIGHT)
    # remove or replace the glowing sky
    sky = Entity(model='sphere', scale=500, double_sided=True, color=color.rgb(10, 0, 0), unlit=False)

    DirectionalLight(color=color.rgb(60, 20, 20), rotation=(45, -45, 0), shadows=True)
    AmbientLight(color=color.rgba(30, 0, 0, 40))

    scene.fog_color = color.rgb(10, 0, 0)
    scene.fog_density = 0.03
    # ---- player (now using PlayerController) ---------------------
    player = PlayerController(
        position=(MAZE_W // 2 * CELL_SIZE, 2, MAZE_H // 2 * CELL_SIZE),
        walk_speed=5,
        run_multiplier=2.0,            # run twice as fast
        max_stamina=5.0,               # seconds of run
        stamina_drain_rate=1.0,        # per second
        stamina_recovery_rate=0.5,     # per second
        stamina_cooldown=2.0,          # seconds before regen after deplete
        mouse_sensitivity=(100, 100),  # left/right works, up/down enabled
    )
    player.collider = 'box'
    # ---- spawn the chaser -----------------------------------------
    # Convert the player's world position to cell coordinates
    player_cell_x = int(round(player.x / CELL_SIZE))
    player_cell_y = int(round(player.z / CELL_SIZE))
    # Pick a cell far enough away from the player
    chaser_cell_x, chaser_cell_y = random_spawn_cell(
        MAZE_W, MAZE_H,
        exclude=(player_cell_x, player_cell_y),
        min_dist=6                     # you can tweak this distance
    )
    # Create the chasing entity (billboard sprite)
    chaser = Chaser(
        player=player,
        maze=maze,
        cell_size=CELL_SIZE,
        wall_height=WALL_HEIGHT,
        base_speed=2.0,
        speed_increment=0.25,
        max_speed=999.0,
        position=(
            chaser_cell_x * CELL_SIZE,
            2,                     # just above the floor
            chaser_cell_y * CELL_SIZE,
        ),
        scale=(CELL_SIZE * 1.0, CELL_SIZE * 1.0),   # size of the sprite
        color=color.white,
    )
    # ---- help text ------------------------------------------------
    Text(
        text='WASD – move | mouse – look (horizontal only) | ESC – quit | Hold Shift – run (stamina)',
        origin=(0, 0),
        position=(-0.85, 0.45),
        scale=1.5,
        background=True,
        color=color.white,
    )
    # lock mouse cursor for FPS-style look
    mouse.locked = True

    # NOTE: We no longer define a global input() function for ESC since the player handles it.
    app.run()

if __name__ == '__main__':
    main()
