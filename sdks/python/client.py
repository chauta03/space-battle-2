#!/usr/bin/python

import sys
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
            data = self.rfile.readline().decode() # reads until '\n' encountered
            json_data = json.loads(str(data))
            # uncomment the following line to see pretty-printed data
            print(json.dumps(json_data, indent=4, sort_keys=True))
            response = game.get_random_move(json_data).encode()
            self.wfile.write(response)



class Game:
    def __init__(self):
        self.units = set() # set of unique unit ids
        self.resource_assignments = dict() # dict with key resource id and list of assigned workers
        self.directions = ['N', 'S', 'E', 'W']
        self.base_location = None # TODO update
        self.resource_priorities = [] # stores the id of each resource in priority order
        self.resources_info = dict() # provides using id as key, provides path to resource, revenue per turn, location # TODO maybe don't store????
        self.worker_dict = dict()


    def get_random_move(self, json_data):
        units = set([unit['id'] for unit in json_data['unit_updates'] if unit['type'] != 'base'])
        self.units |= units # add any additional ids we encounter

        # loops through units getting workers
        worker_updates = [unit for unit in json_data['unit_updates'] if unit['type'] == 'worker']
        self.update_workers(worker_updates)

        # loops through idle workers and assigns them to a resource
        for worker_id in self.worker_dict:
            if self.worker_dict[worker_id]["status"] == "idle":
                for resource_id in self.resource_priorities:
                    if not self.resource_assignments.get(resource_id):
                        self.resource_assignments[resource_id] =  self.worker_dict[worker_id]["id"]

        # completes the moves for each worker in each resource assignment
        commands = []
        move = 'MOVE'
        for resource_id in self.resource_assignments:
            # ensure worker is on correct path for resource
            worker_loc = (self.worker_dict[self.resource_assignments[resource_id]]["x"], self.worker_dict[self.resource_assignments[resource_id]]["y"])
            # if worker_loc not in self.resources_info["path"]:
            #     #move to path

            # moves to resource if carrying nothing
            if self.worker_dict[self.resource_assignments[resource_id]]["resource"] == 0:
                path = a_star_search(self.grid, worker_loc, self.resources_info[resource_id]["location"])
                direction = self.find_direction(worker_loc, path[0])
            else:
                path = a_star_search(self.grid, worker_loc, self.base_location)
                direction = self.find_direction(worker_loc, path[0])
            commands.append({"command": move, "unit": self.resource_assignments[resource_id], "dir": direction})

        response = json.dumps(commands, separators=(',',':')) + '\n'
        return response


    def find_direction(self, start, end):
        x1, y1 = start
        x2, y2 = end

        # Determine vertical direction
        if y2 > y1:
            vertical = "N"
        elif y2 < y1:
            vertical = "S"
        else:
            vertical = ""

        # Determine horizontal direction
        if x2 > x1:
            horizontal = "E"
        elif x2 < x1:
            horizontal = "W"
        else:
            horizontal = ""

        # Combine directions
        return vertical + horizontal or "Same location"


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


if __name__ == "__main__":
    port = int(sys.argv[1]) if (len(sys.argv) > 1 and sys.argv[1]) else 9090
    host = '0.0.0.0'

    server = ss.TCPServer((host, port), NetworkHandler)
    print("listening on {}:{}".format(host, port))
    server.serve_forever()
