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
        self.atvs = []

    def start(self):
        self.game.log_info("starting")
        self.game.set_player_name("tivvit&ales")

        if not self.game.try_reconnect():
            self.game.set_start_gui(True)
            lobby = os.environ.get("UNNATURAL_CONNECT_LOBBY", "")
            addr = os.environ.get("UNNATURAL_CONNECT_ADDR", "192.168.2.102")
            port = int(os.environ.get("UNNATURAL_CONNECT_PORT", "14203"))
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

        if len(own_units) < 5:
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

    def assign_random_recipes(self):
        for e in self.game.world.entities().values():
            if not (e.own() and hasattr(e, "Unit")):
                continue
            recipes = self.game.prototypes.unit(e.Proto.proto)
            if not recipes:
                continue
            recipes = recipes["recipes"]
            if len(recipes) > 0:
                self.game.commands.command_set_recipe(e.Id, random.choice(recipes))
            # for r in recipes:
            #     if r.get("name", "") == "golem":
            #         self.game.commands.command_set_recipe(e.Id, r)

    def build(self, what, position):
        p = self.game.map.find_construction_placement(what,
                                                      position)
        self.game.commands.command_place_construction(what, p)

    def update_callback_closure(self):
        def update_callback(stepping):
            if not stepping:
                return
            self.step += 1  # save some cpu cycles by splitting work over multiple steps

            if self.step % 10 == 1:
                self.init_prototypes()
                self.find_main_base()
                self.find_atvs()
                self.
                print(f"atv count {len(self.atvs)}")
                self.attack_nearest_enemies()
                self.get_closest_ores()
                constructions = [i for i in self.prototypes if i["type"] == uw.Prototype.Construction]
                unit = [i for i in self.prototypes if i["type"] == uw.Prototype.Unit]
                miner_construction = [i for i in constructions if i["name"] == "drill"][0]
                if self.step == 1:
                    for i in self.resources_map["metal"][:2]:
                        self.build(miner_construction["id"], i.Position.position)
                        factory_construction = [i for i in constructions if i["name"] == "factory"][0]
                        self.build(factory_construction["id"], i.Position.position)
                    for i in self.resources_map["crystals"][:2]:
                        self.build(miner_construction["id"], i.Position.position)
                    concrete_plant = [i for i in constructions if i["name"] == "concrete plant"][0]
                    self.build(concrete_plant["id"], self.main_building.Position.position)


            if self.step % 10 == 5:
                self.assign_random_recipes()

        return update_callback


if __name__ == "__main__":
    bot = Bot()
    bot.start()
