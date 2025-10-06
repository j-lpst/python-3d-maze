# --------------------------------------------------------------
# Random Maze First‑Person Demo (Ursina 8.2.0)
# --------------------------------------------------------------
# pip install ursina
# --------------------------------------------------------------
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random

# --------------------------------------------------------------
# Simple chasing entity (uses chaser.png)
# --------------------------------------------------------------
class Chaser(Entity):
    """
    A very small AI that constantly moves toward the player.
    It is a cube textured with *chaser.png*.
    """
    def __init__(self, player, **kwargs):
        super().__init__(
            model='cube',
            texture='chaser.png',          # <-- your sprite
            collider='box',
            **kwargs,
        )
        self.player = player
        self.speed = 3.5                 # units per second (tweakable)

    def update(self):
        # Move only on the X‑Z plane (ignore Y)
        direction = self.player.position - self.position
        direction.y = 0
        if direction.length() > 0.1:          # avoid jitter when on top of player
            direction = direction.normalized()
            self.position += direction * self.speed * time.dt

        # “Got you!” – you can replace this with any game‑over logic you like
        if distance(self.position, self.player.position) < 1.0:
            print('☠️  Caught!  Game Over')
            application.quit()


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

    # Create the chasing entity
    chaser = Chaser(
        player=player,
        position=(
            chaser_cell_x * CELL_SIZE,
            WALL_HEIGHT * 0.4,                     # raise it a little off the floor
            chaser_cell_y * CELL_SIZE,
        ),
        scale=(CELL_SIZE * 0.6, WALL_HEIGHT * 0.6, CELL_SIZE * 0.6),
        color=color.red,                         # optional tint
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
