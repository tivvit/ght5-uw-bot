from pprint import pprint
import os
import random
import uw

from collections import defaultdict


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
        for e in self.game.world.entities().values():
            if not (e.own() and hasattr(e, "Unit")):
                continue
            unit = self.game.prototypes.unit(e.Proto.proto)
            if not unit:
                continue
            if unit.get("name", "") == "nucleus":
                self.main_building = e

    def init_prototypes(self):
        if self.prototypes:
            return
        for p in self.game.prototypes.all():
            self.prototypes.append({
                "id": p,
                "name": self.game.prototypes.name(p),
                "type": self.game.prototypes.type(p),
            })

    def find_atvs(self):
        self.atvs = []
        for e in self.game.world.entities().values():
            if not (e.own() and hasattr(e, "Unit")):
                continue
            unit = self.game.prototypes.unit(e.Proto.proto)
            if not unit:
                continue
            if unit.get("name", "") == "ATV":
                self.atvs.append(e)

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
        p = self.game.map.find_construction_placement(what,
                                                      position)
        self.game.commands.command_place_construction(what, p)

    def count_construction(self, name):
        return len(self.find_units(name)) + len(self.find_constructed_units(name))

    def get_points_in_radius(self, position, radius):
        return self.game.map.area_neighborhood(position, radius)

    def build_construction(self, name, n, positions):
        for i in range(n - self.count_construction(name)):
            self.build(self.construction_prototypes[name]["id"], random.choice(positions))

    def update_callback_closure(self):
        def update_callback(stepping):
            if not stepping:
                return
            self.step += 1  # save some cpu cycles by splitting work over multiple steps

            if self.step % 10 == 1:
                # print(set(self.game.map.overview()))
                # pprint([e for e in self.game.map.overview() if e & uw.fOverviewFlags.Resource])

                self.inverse_recipes_prototypes = {i['id']: i for i in self.prototypes if
                                           i["type"] == uw.Prototype.Recipe}
                drills = self.find_units("drill")
                drills_by_type = defaultdict(list)
                for d in drills:
                    if d.Recipe.recipe in self.inverse_recipes_prototypes:
                        drills_by_type[self.inverse_recipes_prototypes[d.Recipe.recipe]["name"]].append(d)
                pprint(drills_by_type)

                self.init_prototypes()
                self.find_main_base()
                self.atvs = self.find_units("ATV")
                # print(f"atv count {len(self.atvs)}")
                self.attack_nearest_enemies()
                self.get_closest_ores()
                unit = [i for i in self.prototypes if i["type"] == uw.Prototype.Unit]
                if self.step == 1:
                    self.construction_prototypes = {i["name"]: i for i in self.prototypes if
                                                    i["type"] == uw.Prototype.Construction}
                    self.recipes_prototypes = {i["name"]: i for i in self.prototypes if
                                               i["type"] == uw.Prototype.Recipe}
                    print(self.recipes_prototypes,'recipes_prototypes')
                    self.inverted_construction_prototypes = {i["id"]: i for i in self.prototypes if
                                                             i["type"] == uw.Prototype.Construction}
                    if self.count_construction("drill") < 5:
                        for i in self.resources_map["metal"][:3]:
                            self.build(self.construction_prototypes["drill"]["id"], i.Position.position)
                        for i in self.resources_map["crystals"][:2]:
                            self.build(self.construction_prototypes["drill"]["id"], i.Position.position)

                close_positions = self.get_points_in_radius(self.main_building.Position.position, 50)
                self.build_construction("concrete plant", 2, close_positions)

                factory_cnt = self.count_construction("factory")
                self.build_construction("factory", 3, close_positions)

                if len(self.find_units("concrete plant")) > 1:
                    close_positions = self.get_points_in_radius(self.main_building.Position.position, 140)
                    self.build_construction("talos", 10, close_positions)
                self.assign_paladin_recipes()

        return update_callback


if __name__ == "__main__":
    bot = Bot()
    bot.start()
