from pprint import pprint
import os
import random
import uw

from collections import defaultdict
from collections import Counter


class Bot:
    def __init__(self):
        self.game = uw.Game()
        self.step = 0

        # register update callback
        self.game.add_update_callback(self.update_callback_closure())

        self.prototypes = []
        self.resources_map = defaultdict(list)  # resource types sorted by distance
        self.used_resources = set()
        self.main_building = None
        self.recipes_prototypes = {}
        self.resource_prototypes = {}
        self.construction_prototypes = {}
        self.inverted_construction_prototypes = {}
        self.atvs = []
        self.built = False

    def start(self):
        self.game.log_info("starting")
        self.game.set_player_name("tivvit&ales")

        if not self.game.try_reconnect():
            self.game.set_start_gui(True)
            lobby = os.environ.get("UNNATURAL_CONNECT_LOBBY", "")
            addr = os.environ.get("UNNATURAL_CONNECT_ADDR", "")
            # addr = os.environ.get("UNNATURAL_CONNECT_ADDR", "192.168.2.102")
            port = os.environ.get("UNNATURAL_CONNECT_PORT", "")
            # port = int(os.environ.get("UNNATURAL_CONNECT_PORT", "9409"))
            if lobby != "":
                self.game.connect_lobby_id(lobby)
            elif addr != "" and port != "":
                self.game.connect_direct(addr, port)
            else:
                self.game.connect_new_server()
        self.game.log_info("done")

    def attack_nearest_enemies(self):
        own_units = [
            e
            for e in self.game.world.entities().values()
            if e.own()
               and e.has("Unit")
               and self.game.prototypes.unit(e.Proto.proto)
               and self.game.prototypes.unit(e.Proto.proto).get("dps", 0) > 0
        ]
        if not own_units:
            return

        if len(own_units) < 10:
            return

        enemy_units = [
            e
            for e in self.game.world.entities().values()
            if e.policy() == uw.Policy.Enemy and e.has("Unit")
        ]
        if not enemy_units:
            return

        for u in own_units:
            _id = u.Id
            pos = u.Position.position
            if len(self.game.commands.orders(_id)) == 0:
                enemy = sorted(
                    enemy_units,
                    key=lambda x: self.game.map.distance_estimate(
                        pos, x.Position.position
                    ),
                )[0]
                self.game.commands.order(
                    _id, self.game.commands.fight_to_entity(enemy.Id)
                )

    def find_main_base(self):
        if self.main_building:
            return
        self.main_building = self.find_units("nucleus")[0]

    def init_prototypes(self):
        if self.prototypes:
            return
        for p in self.game.prototypes.all():
            self.prototypes.append({
                "id": p,
                "name": self.game.prototypes.name(p),
                "type": self.game.prototypes.type(p),
            })

    def find_units(self, name):
        u = []
        for e in self.game.world.entities().values():
            if not (e.own() and hasattr(e, "Unit")):
                continue
            unit = self.game.prototypes.unit(e.Proto.proto)
            if not unit:
                continue
            if unit.get("name", "") == name:
                u.append(e)
        return u

    def find_constructed_units(self, name):
        u = []
        for e in self.game.world.entities().values():
            if not e.own():
                continue
            if self.inverted_construction_prototypes.get(e.Proto.proto, {}).get("name", "") == name:
                u.append(e)
        return u

    def get_closest_ores(self):
        for e in self.game.world.entities().values():
            if not (hasattr(e, "Unit")) and not e.own():
                continue
            unit = self.game.prototypes.unit(e.Proto.proto)
            if not unit:
                continue
            if "deposit" not in unit.get("name", ""):
                continue
            name = unit.get("name", "").replace(" deposit", "")
            self.resources_map[name].append(e)
        if not self.main_building:
            return
        for r in self.resources_map:
            self.resources_map[r].sort(key=lambda x: self.game.map.distance_estimate(
                self.main_building.Position.position, x.Position.position
            ))

    def assign_paladin_recipes(self):
        for e in self.game.world.entities().values():
            if not (e.own() and hasattr(e, "Unit")):
                continue
            recipes = self.game.prototypes.unit(e.Proto.proto)
            if not recipes:
                continue
            recipes = recipes["recipes"]
            paladin_recepie = self.recipes_prototypes["paladin"]
            if paladin_recepie["id"] in recipes:
                self.game.commands.command_set_recipe(e.Id, paladin_recepie["id"])

    def build(self, what, position):
        construction_prototype = self.construction_prototypes[what]["id"]
        p = self.game.map.find_construction_placement(construction_prototype,
                                                      position)
        self.game.commands.command_place_construction(construction_prototype, p)

    def count_construction(self, name):
        return len(self.find_units(name)) + len(self.find_constructed_units(name))

    def get_points_in_radius(self, position, radius):
        return self.game.map.area_neighborhood(position, radius)

    def build_construction(self, name, n, positions):
        for i in range(n - self.count_construction(name)):
            self.build(name, random.choice(positions))

    def get_resources(self):
        r = []
        for e in self.game.world.entities().values():
            if not e.own():
                continue
            resource = self.game.prototypes.resource(e.Proto.proto)
            if not resource:
                continue
            r.append(e)
        return r

    def update_callback_closure(self):
        def update_callback(stepping):
            if not stepping:
                return
            self.step += 1  # save some cpu cycles by splitting work over multiple steps

            if self.step % 10 == 1:
                if self.game.map_state() != uw.MapState.Loaded or self.game.game_state() != uw.GameState.Game:
                    return

                self.init_prototypes()
                self.find_main_base()
                self.atvs = self.find_units("ATV")
                # print(f"atv count {len(self.atvs)}")
                self.attack_nearest_enemies()
                self.get_closest_ores()
                unit = [i for i in self.prototypes if i["type"] == uw.Prototype.Unit]
                self.construction_prototypes = {i["name"]: i for i in self.prototypes if
                                                i["type"] == uw.Prototype.Construction}
                self.recipes_prototypes = {i["name"]: i for i in self.prototypes if
                                           i["type"] == uw.Prototype.Recipe}
                self.resource_prototypes = {i["name"]: i for i in self.prototypes if
                                            i["type"] == uw.Prototype.Resource}
                # print(self.recipes_prototypes, 'recipes_prototypes')
                self.inverted_construction_prototypes = {i["id"]: i for i in self.prototypes if
                                                         i["type"] == uw.Prototype.Construction}

                # print(set(self.game.map.overview()))
                # pprint([e for e in self.game.map.overview() if e & uw.fOverviewFlags.Resource])

                self.inverse_recipes_prototypes = {i['id']: i for i in self.prototypes if
                                                   i["type"] == uw.Prototype.Recipe}
                drills_by_type = defaultdict(list)
                for d in self.find_units("drill"):
                    if d.Recipe.recipe in self.inverse_recipes_prototypes:
                        drills_by_type[self.inverse_recipes_prototypes[d.Recipe.recipe]["name"]].append(d)

                constructed_drills_by_type = defaultdict(list)
                for d in self.find_constructed_units("drill"):
                    if d.Recipe.recipe in self.inverse_recipes_prototypes:
                        constructed_drills_by_type[self.inverse_recipes_prototypes[d.Recipe.recipe]["name"]].append(d)

                if (2 - len(drills_by_type["metal"]) - len(constructed_drills_by_type["metal"])) > 0:
                    # TODO consider distance
                    for i in self.resources_map["metal"]:
                        used = False
                        for ent in self.game.map.entities(i.Position.position):
                            e = self.game.world.entity(ent)
                            if e.own():
                                used = True
                        if used:
                            continue
                        self.build("drill", i.Position.position)
                        break

                if (1 - len(drills_by_type["crystals"]) - len(constructed_drills_by_type["crystals"])) > 0:
                    for i in self.resources_map["crystals"]:
                        used = False
                        for ent in self.game.map.entities(i.Position.position):
                            e = self.game.world.entity(ent)
                            if e.own():
                                used = True
                        if used:
                            continue
                        self.build("drill", i.Position.position)
                        break

                for i in drills_by_type["metal"]:
                    own = False
                    # TODO how to use connected
                    for j in self.game.map.area_neighborhood(i.Position.position, 25):
                        for ent in self.game.map.entities(j):
                            e = self.game.world.entity(ent)
                            if not e.own():
                                continue
                            if self.inverted_construction_prototypes.get(e.Proto.proto, {}).get("name",
                                                                                                "") == "concrete plant":
                                own = True
                                break
                            if not e.has("Unit"):
                                continue
                            unit = self.game.prototypes.unit(e.Proto.proto)
                            if not unit:
                                continue
                            if unit.get("name", "") == "concrete plant":
                                own = True
                                break

                    if own:
                        continue
                    self.build("concrete plant", int(i.Position.position))

                if len(drills_by_type["metal"]) > 1:
                    close_positions = self.get_points_in_radius(self.main_building.Position.position, 50)
                    self.build_construction("factory", 2, close_positions)

                resource_count = Counter()
                for r in self.get_resources():
                    resource = self.game.prototypes.resource(r.Proto.proto)
                    resource_count[resource.get("name", "")] += 1

                if self.step % 50 == 1:
                    pprint(resource_count)

                if resource_count["reinforced concrete"] > 5:
                    for i in self.find_units("concrete plant"):
                        self.game.commands.command_set_priority(i.Id, uw.Priority.Disabled)

                if resource_count["reinforced concrete"] < 2:
                    for i in self.find_units("concrete plant"):
                        self.game.commands.command_set_priority(i.Id, uw.Priority.Normal)

                if len(self.find_units("concrete plant")) > 1:
                    close_positions = self.get_points_in_radius(self.main_building.Position.position, 140)
                    # TODO scaling
                    self.build_construction("talos", 10, close_positions)

                self.assign_paladin_recipes()

                # TODO for each shooting unit
                # * move to the edge of the base
                # * guard
                # * detect close enough enemies and move closer

        return update_callback


if __name__ == "__main__":
    bot = Bot()
    bot.start()
