from collections import deque
import json
import random
import bisect
from path_finding import a_star_search
from operator import truediv

if (sys.version_info > (3, 0)):
    print("Python 3.X detected")
    import socketserver as ss
else:
    print("Python 2.X detected")
    import SocketServer as ss

import sys
import socketserver as ss
import heapq

class NetworkHandler(ss.StreamRequestHandler):
    def handle(self):
        game = Game()
        while True:
            data = self.rfile.readline().decode()  # reads until '\n' encountered
            json_data = json.loads(str(data))
            print(json.dumps(json_data, indent=4, sort_keys=True))
            response = game.get_random_move(json_data).encode()
            self.wfile.write(response)


class Game:
    def __init__(self):
        self.units = set()  # set of unique unit ids
        self.directions = ['N', 'S', 'E', 'W']
        self.dirs = ((-1, 0), (1, 0), (0, 1), (0, -1))
        self.grid = []
        self.visited = set()
        self.width = 0
        self.height = 0

    def get_random_move(self, json_data):
        # If the first move
        if "game_info" in json_data:
            self.create_grid(json_data["game_info"])

        # Update grid after every move
        self.update_grid(json_data["tile_updates"])

        # Add new units to the set of units
        units = set()
        for unit in json_data['unit_updates']:
            if unit['type'] != 'base':
                x, y = unit['x'], unit['y']
                units.add((unit['id'], x, y))
                self.visited.add((x, y))


        self.units |= units # Add any other we encounter
        print("units", units)

        commands = []
        move = 'MOVE'

        for unit, x, y in units:
            s = []

            for i in range(len(self.dirs)):
                dx, dy = self.dirs[i]
                newX, newY = x + dx, y + dy

                if (0 <= newX < self.height and 
                   0 <= newY < self.width and 
                   (not self.grid[newX][newY]['blocked'])):
                        heapq.heappush(s, ((newX, newY) in self.visited, i, newX, newY))
            
            b, idx, newX, newY = heapq.heappop(s)
            direction = self.directions[idx] 
            self.visited.add((newX, newY))
            commands.append({"command": "MOVE", "unit": unit, "dir": direction})

        print(commands)
        command = {"commands": commands}
        response = json.dumps(command, separators=(',', ':')) + '\n'
        return response

    def update_workers(self, worker_updates):
        for worker_update in worker_updates:
            # adds worker if it does not exist
            if worker_update["id"] not in self.worker_dict:
                self.worker_dict[worker_update["id"]] = worker_update

            # updates existing worker
            else:
                self.worker_dict[worker_update["id"]].update(worker_update)


    def add_resource(self, new_resource_info, resource_loc):
        self.resources_info[new_resource_info["id"]] = {}
        self.resources_info[new_resource_info["id"]]["path"] = a_star_search(self.grid, self.base_location, resource_loc)
        self.resources_info[new_resource_info["id"]]["resource_rev"] = new_resource_info["value"]/((len(self.resources_info[new_resource_info["id"]]["path"])-1)*2+2)

        # TODO make faster
        if not self.resource_priorities:
            self.resource_priorities.append(new_resource_info["id"])
        else:
            for index, resource_id in enumerate(self.resource_priorities):
                if self.resources_info[new_resource_info["id"]]["resource_rev"] > self.resources_info[resource_id]["resource_rev"]:
                    self.resource_priorities.insert(index, new_resource_info["id"])


    def remove_resource(self, resource_id):
        self.resource_priorities.remove(resource_id)
    def get_direction_from_move(self, current_position, move):
        # Returns the direction to move from current_position to move
        x1, y1 = current_position
        x2, y2 = move
        if x1 < x2: return 'S'
        if x1 > x2: return 'N'
        if y1 < y2: return 'E'
        if y1 > y2: return 'W'


    def create_grid(self, game_info):
        self.width = game_info["map_width"]
        self.height = game_info["map_height"]
        self.grid = [[dict() for _ in range(self.width)] for _ in range(self.height)]


    def update_grid(self, tile_updates):
        for item in tile_updates:
            x = item['x']
            y = item['y']
            visible = item['visible']
            self.grid[x][y]['visible'] = visible

            if visible:
                blocked = item['blocked']
                resources = item['resources']
                self.grid[x][y]['blocked'] = blocked
                self.grid[x][y]['resources'] = resources


if __name__ == "__main__":
    port = int(sys.argv[1]) if (len(sys.argv) > 1 and sys.argv[1]) else 9090
    host = '0.0.0.0'

    server = ss.TCPServer((host, port), NetworkHandler)
    print("listening on {}:{}".format(host, port))
    server.serve_forever()
