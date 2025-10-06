# --------------------------------------------------------------
# Random Maze First‑Person Demo (Ursina 8.2.0)
# --------------------------------------------------------------
# pip install ursina
# --------------------------------------------------------------
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from collections import deque          # <-- needed for BFS
import random

# --------------------------------------------------------------
# Simple chasing entity (uses chaser.png as a billboard quad)
# --------------------------------------------------------------
class Chaser(Entity):
    """
    A billboard sprite that constantly pursues the player.
    It walks only through open passages of the Maze (never through walls).
    """
    def __init__(self, player, maze, cell_size, wall_height, **kwargs):
        super().__init__(
            model='quad',                 # flat 2‑D plane
            texture='chaser.png',         # your sprite file
            billboard=True,               # always faces the camera
            # ---- use an un‑lit material ----
            # Option A (recommended):
            unlit=True,                   # <-- automatically picks the un‑lit shader
            # Option B (equivalent):
            # lit=False,
            collider='box',
            **kwargs,
        )
        self.player = player
        self.maze = maze
        self.cell_size = cell_size
        self.wall_height = wall_height

        self.speed = 3.0                 # world‑units per second
        self.recalc_interval = 0.2       # seconds between path recalcs
        self._timer = 0

        # Path data
        self._path = []                  # list of (x, y) cells
        self._path_index = 0

    # ------------------------------------------------------------------
    # PUBLIC: called each frame by Ursina
    # ------------------------------------------------------------------
    def update(self):
        # --------------------------------------------------------------
        # 1️⃣  Re‑calculate a path from us → player every few frames
        # --------------------------------------------------------------
        self._timer += time.dt
        if self._timer >= self.recalc_interval:
            self._timer = 0
            self._recalc_path()

        # --------------------------------------------------------------
        # 2️⃣  Follow the path (move toward the centre of the next cell)
        # --------------------------------------------------------------
        if self._path:
            # target cell = the next cell on the path
            target_cell = self._path[self._path_index]
            target_world = Vec3(
                target_cell[0] * self.cell_size,
                self.y,                         # keep same height
                target_cell[1] * self.cell_size,
            )
            direction = target_world - self.position
            dist = direction.length()
            if dist < 0.05:                     # we have reached this cell
                if self._path_index < len(self._path) - 1:
                    self._path_index += 1       # head for the next one
                else:
                    self._path = []             # reached player‑cell; wait for new path
            else:
                self.position += direction.normalized() * self.speed * time.dt

        # --------------------------------------------------------------
        # 3️⃣  “Caught!” – simple distance check (you can replace with any logic)
        # --------------------------------------------------------------
        if distance(self.position, self.player.position) < 0.9:
            print('☠️  Caught! Game Over')
            application.quit()

    # ------------------------------------------------------------------
    # PRIVATE: recompute a shortest‑path from us to the player
    # ------------------------------------------------------------------
    def _recalc_path(self):
        # ----- convert world positions → cell coordinates ----------------
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

        # ----- BFS that respects the maze walls ------------------------
        self._path = bfs_path(self.maze, start, goal)

        # ----- we want to start moving *away* from our current cell -----
        if len(self._path) >= 2:
            self._path_index = 1      # index 0 is our own cell; go to the next one
        else:
            self._path = []           # no path (shouldn’t happen)


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
        position=(
            (maze.width - 1) * cell_size / 2,
            -0.05,
            (maze.height - 1) * cell_size / 2,
        ),
        color=color.light_gray,
        texture='white_cube',
        texture_scale=(maze.width, maze.height),
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
                wall = Entity(
                    model='cube',
                    color=color.dark_gray,
                    scale=scale,
                    position=pos,
                    collider='box',
                    name=f'wall_{x}_{y}_{direction}'
                )
                walls.append(wall)
    # ---- white corner “posts” (visual depth cue) ---------------
    corner_scale_xy = 0.2
    half_h = wall_h / 2
    for cx in range(maze.width + 1):
        for cz in range(maze.height + 1):
            corner = Entity(
                model='cube',
                color=color.white,
                scale=(corner_scale_xy, wall_h, corner_scale_xy),
                position=((cx - 0.5) * cell_size, half_h, (cz - 0.5) * cell_size),
                collider=None,
                name=f'corner_{cx}_{cz}'
            )
            walls.append(corner)
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
    WALL_HEIGHT = 2.5
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

    # ---- sky & simple lighting (optional but nice) ---------------
    Sky()
    DirectionalLight(y=2, z=3, shadows=True)
    AmbientLight(color=color.rgba(255, 255, 255, 100))

    # ---- player ---------------------------------------------------
    player = FirstPersonController(
        position=(MAZE_W // 2 * CELL_SIZE, 2, MAZE_H // 2 * CELL_SIZE),
        speed=5,
        mouse_sensitivity=(0, 110),   # left/right works, up/down disabled
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
        position=(
            chaser_cell_x * CELL_SIZE,
            WALL_HEIGHT * 0.4,                     # just above the floor
            chaser_cell_y * CELL_SIZE,
        ),
        scale=(CELL_SIZE * 0.7, CELL_SIZE * 0.7),   # size of the sprite
        # optional tint – remove if you want the original colours
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
