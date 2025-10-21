# --------------------------------------------------------------
# Random Maze First‑Person Demo (Ursina 8.2.0)
# --------------------------------------------------------------
# pip install ursina
# --------------------------------------------------------------
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from collections import deque          # <-- needed for BFS
import random
import math                           # for optional exponential curve
import time
# --------------------------------------------------------------
# Simple chasing entity (uses chaser.png as a billboard quad)
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
            texture='chaser.png',
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

        # Speed‑ramp configuration
        self.base_speed      = base_speed
        self.speed_increment = speed_increment
        self.max_speed       = max_speed
        self.speed = self.base_speed

        # Remember when the monster was spawned
        self.spawn_time = time.time()          # <-- call!

        # Path‑finding bookkeeping
        self.recalc_interval = 0.2
        self._timer   = 0
        self._path    = []          # list of (x, y) cells
        self._path_index = 0

        # ------------------------------------------------------------------
        # Sound – manual attenuation (kept from your original code)
        # ------------------------------------------------------------------
        self.sound = Audio(
            'chaser.mp3',
            loop=True,
            autoplay=True,
            spatial=False,
            volume=1.0,
        )
        self.max_hear_distance = 30.0
        self.base_volume = 0.6

    # ------------------------------------------------------------------
    # Called every frame by Ursina
    # ------------------------------------------------------------------
    def update(self):
        # --------------------------------------------------------------
        # 0️⃣  Update speed according to survival time
        # --------------------------------------------------------------
        elapsed = time.time() - self.spawn_time          # <-- call again each frame
        self.speed = min(self.max_speed,
                         self.base_speed + self.speed_increment * elapsed)

        # --------------------------------------------------------------
        # 1️⃣  Re‑calculate a path every few frames
        # --------------------------------------------------------------
        self._timer += time.dt
        if self._timer >= self.recalc_interval:
            self._timer = 0
            self._recalc_path()

        # --------------------------------------------------------------
        # 2️⃣  Follow the path
        # --------------------------------------------------------------
        if self._path:
            target_cell = self._path[self._path_index]
            target_world = Vec3(
                target_cell[0] * self.cell_size,
                self.y,
                target_cell[1] * self.cell_size,
            )
            direction = target_world - self.position
            dist = direction.length()
            if dist < 0.05:
                if self._path_index < len(self._path) - 1:
                    self._path_index += 1
                else:
                    self._path = []
            else:
                self.position += direction.normalized() * self.speed * time.dt

        # --------------------------------------------------------------
        # 3️⃣  Caught check
        # --------------------------------------------------------------
        if distance(self.position, self.player.position) < 3.0:
            print('☠  Caught! Game Over')
            application.quit()

        # --------------------------------------------------------------
        # 4️⃣  Keep sound attached to the monster
        # --------------------------------------------------------------
        self.sound.position = self.position

        # --------------------------------------------------------------
        # 5️⃣  Manual volume attenuation
        # --------------------------------------------------------------
        if not self.sound.spatial:
            d = distance(self.position, self.player.position)
            vol = max(0.0,
                      min(1.0,
                          (self.max_hear_distance - d) / self.max_hear_distance
                         )
                     ) * self.base_volume
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
# Maze generation – recursive backtracker
# --------------------------------------------------------------
class Maze:
    """Rectangular maze built with depth‑first backtracking."""
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
# Helper functions for turning the logical maze into 3‑D entities
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
        texture='floor_tile.png',           # <-- your texture here
        texture_normal='brick_normal.png',
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
                    texture='brick.png',
                    texture_normal='brick_normal.png',
                    color=color.white,
                    scale=scale,
                    position=pos,
                    collider='box',
                    texture_scale=tex_scale
                )
                walls.append(wall)
    return floor, walls
# --------------------------------------------------------------
# Path‑finding helpers (BFS) – respect the Maze walls
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
    Breadth‑first search that returns a list of cells from *start* → *goal*.
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
    # Re‑construct the path
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
# Helper: pick a random spawn cell for the monster
# --------------------------------------------------------------
def random_spawn_cell(width, height, exclude, min_dist=4):
    """Return a random (x, y) cell that is at least *min_dist* cells away from *exclude*."""
    while True:
        cx = random.randint(0, width - 1)
        cy = random.randint(0, height - 1)
        if (cx, cy) != exclude and (abs(cx - exclude[0]) + abs(cy - exclude[1]) >= min_dist):
            return cx, cy
# --------------------------------------------------------------
# Main – set up Ursina, create the maze, drop the player, etc.
# --------------------------------------------------------------
def main():
    app = Ursina()
    window.title = 'Random Maze – First‑Person Demo'
    window.fullscreen = False
    window.borderless = False
    window.exit_button.visible = True
    window.fps_counter.enabled = True
    # ---- tweakable parameters ------------------------------------
    MAZE_W, MAZE_H = 12, 12               # cells horizontally / vertically
    WALL_HEIGHT = 5.0
    WALL_THICKNESS = 0.08                  # optional: slightly thicker walls
    CELL_SIZE = 5.0                        # <-- larger = wider corridors
    # ---- generate maze and build its 3‑D representation ------------
    maze = Maze(MAZE_W, MAZE_H)
    floor, wall_entities = build_3d_maze(
        maze,
        wall_h=WALL_HEIGHT,
        thickness=WALL_THICKNESS,
        cell_size=CELL_SIZE,
    )
    # remove or replace the glowing sky
    sky = Entity(model='sphere', scale=500, double_sided=True, color=color.rgb(10, 0, 0), unlit=False)

    DirectionalLight(color=color.rgb(60, 20, 20), rotation=(45, -45, 0), shadows=True)
    AmbientLight(color=color.rgba(30, 0, 0, 40))

    scene.fog_color = color.rgb(10, 0, 0)
    scene.fog_density = 0.02
    # ---- player ---------------------------------------------------
    player = FirstPersonController(
        position=(MAZE_W // 2 * CELL_SIZE, 2, MAZE_H // 2 * CELL_SIZE),
        speed=5,
        mouse_sensitivity=(100, 100),   # left/right works, up/down enabled
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
    # --------------------------------------------------------------
    # OPTIONAL: tweak the speed‑ramp parameters here:
    #   base_speed      – starting speed (world‑units per second)
    #   speed_increment – how many units per second are added each second of survival
    #   max_speed       – hard cap (set to a very high value if you want “no cap”)
    # --------------------------------------------------------------
    chaser = Chaser(
        player=player,
        maze=maze,
        cell_size=CELL_SIZE,
        wall_height=WALL_HEIGHT,
        # ---- uncomment / adjust the three lines below if you want a custom ramp ----
        base_speed=2.0,
        speed_increment=0.25,
        max_speed=999.0,
        # -------------------------------------------------------------------------
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
        text='WASD – move | mouse – look (horizontal only) | ESC – quit',
        origin=(0, 0),
        position=(-0.85, 0.45),
        scale=1.5,
        background=True,
        color=color.white,
    )
    # lock mouse cursor for FPS‑style look
    mouse.locked = True
    # optional: quit on ESC (Ursina already handles this)
    def input(key):
        if key == 'escape':
            application.quit()
    app.run()
if __name__ == '__main__':
    main()
 