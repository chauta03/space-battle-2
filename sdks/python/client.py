import sys
import socketserver as ss
import heapq
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
        self.base_location = None # TODO update
        self.resource_assignments = {} # key: resource id value: worker assigned
        self.resource_priorities = [] # stores the id of each resource in priority order
        self.resources_info = dict() # provides using id as key, provides path to resource, revenue per turn, location # TODO maybe don't store????
        self.worker_dict = dict()
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

        # loops through units getting workers
        worker_updates = [unit for unit in json_data['unit_updates'] if unit['type'] == 'worker']
        self.update_workers(worker_updates)

        # checks status of all resources
        resource_updates = [tile for tile in json_data['tile_updates'] if tile['resources']]
        for resource in resource_updates:
            if resource["total"] <= 0:
                self.resource_priorities.remove(resource["id"])
                del self.resource_assignments[resource["id"]]

        # loops through idle workers and assigns them to a resource
        for worker_id in self.worker_dict:
            if self.worker_dict[worker_id]["status"] == "idle": # Todo may need to do check when resource runs out
                for resource_id in self.resource_priorities:
                    if not self.resource_assignments.get(resource_id):
                        self.resource_assignments[resource_id] =  self.worker_dict[worker_id]["id"]

        # completes the moves for each worker in each resource assignment
        commands = []
        move = 'MOVE'
        gather = "GATHER"
        for resource_id in self.resource_assignments:
            # gets id and location of current worker
            worker_id = self.resource_assignments[resource_id]
            worker_loc = (self.worker_dict[worker_id]["x"], self.worker_dict[worker_id]["y"])

            # checks if the workers has no resources
            if self.worker_dict[worker_id]["resource"] == 0:
                # checks if the worker can gather
                if self.is_adjacent(worker_loc, self.resources_info[resource_id]["location"]):
                    commands.append({"command": gather, "unit": worker_id})

                # if it cannot gather then move to resource
                else:
                    path = a_star_search(self.grid, worker_loc, self.resources_info[resource_id]["location"])
                    direction = self.get_direction_from_move(worker_loc, path[0])
                    commands.append({"command": move, "unit": worker_id, "dir": direction})
            else:
                path = a_star_search(self.grid, worker_loc, self.base_location)
                direction = self.get_direction_from_move(worker_loc, path[0])
                commands.append({"command": move, "unit": worker_id, "dir": direction})

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
        self.resources_info[new_resource_info["id"]]["location"] = resource_loc
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


    def is_adjacent(self, current, target):
        x1, y1 = current
        x2, y2 = target

        # Check if the locations differ by exactly 1 in either x or y, and not both
        return (abs(x1 - x2) == 1 and y1 == y2) or (abs(y1 - y2) == 1 and x1 == x2)


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
