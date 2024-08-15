from pprint import pprint
import os
import random
import uw

from collections import defaultdict
from collections import Counter

{'drill': {'recipe': 'metal', 'n': 3, 'by': None, 'dependency': {}}}

# TODO handle drills
# TODO handle pumps
# TODO handle taloses
# 'name': 'drill', 'recipe': 'metal', 'n': 1},
#                      {'name': 'concrete plant', 'n': 2}

ORDER = [
    {
        'concrete plant':
            {
                'by': {'name': 'drill', 'recipe': 'metal', 'radius': 25},
                'dependencies': [
                    [{'name': 'drill', 'recipe': 'metal', 'n': 1}],
                    [{'name': 'drill', 'recipe': 'metal', 'n': 2}],
                ],
            },
    },
    {
        'factory':
            {
                'recipe': 'paladin',
                'by': {'name': 'drill', 'recipe': 'metal', 'radius': 25},
                'dependencies': [
                    [{'name': 'drill', 'recipe': 'metal', 'n': 1},
                     {'name': 'concrete plant', 'n': 2}],
                    [{'name': 'drill', 'recipe': 'metal', 'n': 2},
                     {'name': 'concrete plant', 'n': 2}],
                ],
            },
    },
    {
        'arsenal':
            {
                'recipe': 'plasma emitter',
                'by': {'name': 'pump', 'recipe': 'oil', 'radius': 25},
                'dependencies': [
                    [{'name': 'pump', 'recipe': 'oil;', 'n': 1},
                     {'name': 'concrete plant', 'n': 2}],
                ],
            },
    },
    {
        'laboratory':
            {
                'recipe': 'shield projector',
                'by': {'name': 'drill', 'recipe': 'crystals', 'radius': 25},
                'dependencies': [
                    [{'name': 'drill', 'recipe': 'crystals', 'n': 1},
                     {'name': 'concrete plant', 'n': 2}],
                ],
            },
    },
    {
        'bot assembler':
            {
                'recipe': 'juggernaut',
                'by': {'name': 'drill', 'recipe': 'crystals', 'radius': 25},
                'dependencies': [
                    [{'name': 'drill', 'recipe': 'metal', 'n': 2},
                     {'name': 'drill', 'recipe': 'crystals', 'n': 1},
                     {'name': 'concrete plant', 'n': 2},
                     {'name': 'laboratory', 'laboratory': 'shield projector', 'n': 2},
                     {'name': 'arsenal', 'laboratory': 'plasma emitter', 'n': 2},
                     ],
                ],
            },
    },
]


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
        self.inverted_recipes_prototypes = {}
        self.resource_prototypes = {}
        self.construction_prototypes = {}
        self.inverted_construction_prototypes = {}
        self.drills_by_type = {}
        self.constructed_drills_by_type = {}
        self.pumps_by_type = {}
        self.constructed_pumps_by_type = {}
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
            # port = int(os.environ.get("UNNATURAL_CONNECT_PORT", "45528"))
            if lobby != "":
                self.game.connect_lobby_id(lobby)
            elif addr != "" and port != "":
                self.game.connect_direct(addr, port)
            else:
                self.game.connect_new_server()
        self.game.log_info("done")

    def inspect_players(self):
        try:
            players = set()
            for e in self.game.world.entities().values():
                if not hasattr(e, 'Player') or not hasattr(e, 'Owner'):
                    continue
                # players[e.Player.steamUserId] = e.Owner.force
                players.add(e.Player.steamUserId)
            print('PLAYERS:')
            pprint(players)
        except Exception as e:
            print('>>> Players not recognised <<<')
            print(e)
            pass

    def attack_nearest_enemy(self, unit, enemy_units):
        _id = unit.Id
        pos = unit.Position.position
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

    def atack_strategy(self):
        # TODO huddle the army first
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

        enemy_units = [
            e
            for e in self.game.world.entities().values()
            if e.policy() == uw.Policy.Enemy and e.has("Unit")
        ]

        enemy_units = sorted(
            enemy_units,
            key=lambda x: self.game.map.distance_estimate(
                self.main_building.Position.position, x.Position.position
            ),
        )
        if enemy_units and self.game.map.distance_estimate(enemy_units[0].Position.position,
                                                           self.main_building.Position.position) < 400:
            for u in own_units:
                self.attack_nearest_enemy(u, enemy_units)
            return

        if len(own_units) < 1000:
            close_positions = self.get_points_in_radius(self.main_building.Position.position, 150)
            position = close_positions[int(self.step / 100) % len(close_positions)]
            for u in own_units:
                self.game.commands.order(u.Id, self.game.commands.run_to_position(position))
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

    def find_other_bases(self):
        return self.find_units('nucleus', own=False)

    def init_prototypes(self):
        if self.prototypes:
            return
        for p in self.game.prototypes.all():
            self.prototypes.append({
                "id": p,
                "name": self.game.prototypes.name(p),
                "type": self.game.prototypes.type(p),
            })

    def find_units(self, name, own=True):
        u = []
        for e in self.game.world.entities().values():
            if own:
                if not (e.own() and hasattr(e, "Unit")):
                    continue
            else:
                if not (not e.own() and hasattr(e, "Unit")):
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
        n_paladins = 2
        n_kitsune = 1  # TODO
        for e in self.game.world.entities().values():
            if not (e.own() and hasattr(e, "Unit")):
                continue
            recipes = self.game.prototypes.unit(e.Proto.proto)
            if not recipes:
                continue
            recipes = recipes["recipes"]
            paladin_recipe = self.recipes_prototypes["paladin"]
            if paladin_recipe["id"] in recipes:
                self.game.commands.command_set_recipe(e.Id, paladin_recipe["id"])

    def assign_arsenal_recipes(self):
        for e in self.game.world.entities().values():
            if not (e.own() and hasattr(e, "Unit")):
                continue
            recipes = self.game.prototypes.unit(e.Proto.proto)
            if not recipes:
                continue
            recipes = recipes["recipes"]
            recipe = self.recipes_prototypes["plasma emitter"]
            if recipe["id"] in recipes:
                self.game.commands.command_set_recipe(e.Id, recipe["id"])

    def assign_laboratory_recipes(self):
        for e in self.game.world.entities().values():
            if not (e.own() and hasattr(e, "Unit")):
                continue
            recipes = self.game.prototypes.unit(e.Proto.proto)
            if not recipes:
                continue
            recipes = recipes["recipes"]
            recipe = self.recipes_prototypes["shield projector"]
            if recipe["id"] in recipes:
                self.game.commands.command_set_recipe(e.Id, recipe["id"])

    def assign_bot_assembler_recipes(self):
        for e in self.game.world.entities().values():
            if not (e.own() and hasattr(e, "Unit")):
                continue
            recipes = self.game.prototypes.unit(e.Proto.proto)
            if not recipes:
                continue
            recipes = recipes["recipes"]
            recipe = self.recipes_prototypes["juggernaut"]
            if recipe["id"] in recipes:
                self.game.commands.command_set_recipe(e.Id, recipe["id"])

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

    def ensure_talos(self, n=10):
        other_bases = self.find_other_bases()
        if not other_bases:
            return
        other_bases = sorted(other_bases,
                             key=lambda x: self.game.map.distance_estimate(self.main_building.Position.position,
                                                                           x.Position.position))
        if len(self.find_units("concrete plant")) < 2:
            return
        if len(self.find_units('talos')) < n and not len(self.find_constructed_units('talos')):
            next_other_base = other_bases[len(self.find_units('talos')) % len(other_bases)]
            close_positions = self.get_points_in_radius(self.main_building.Position.position, 140)
            close_positions = sorted(
                close_positions,
                key=lambda x: self.game.map.distance_estimate(
                    next_other_base.Position.position, x))
            self.build_construction("talos", len(self.find_units('talos')) + 1, close_positions[:1])

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

    def update_drills_by_type(self):
        self.drills_by_type = defaultdict(list)
        for d in self.find_units("drill"):
            if d.Recipe.recipe in self.inverted_recipes_prototypes:
                self.drills_by_type[self.inverted_recipes_prototypes[d.Recipe.recipe]["name"]].append(d)

    def update_constructed_drills_by_type(self):
        self.constructed_drills_by_type = defaultdict(list)
        for d in self.find_constructed_units("drill"):
            if d.Recipe.recipe in self.inverted_recipes_prototypes:
                self.constructed_drills_by_type[self.inverted_recipes_prototypes[d.Recipe.recipe]["name"]].append(d)

    def update_pumps_by_type(self):
        self.pumps_by_type = defaultdict(list)
        for d in self.find_units("pump"):
            if d.Recipe.recipe in self.inverted_recipes_prototypes:
                self.pumps_by_type[self.inverted_recipes_prototypes[d.Recipe.recipe]["name"]].append(d)

    def update_constructed_pumps_by_type(self):
        self.constructed_pumps_by_type = defaultdict(list)
        for d in self.find_constructed_units("pump"):
            if d.Recipe.recipe in self.inverted_recipes_prototypes:
                self.constructed_pumps_by_type[self.inverted_recipes_prototypes[d.Recipe.recipe]["name"]].append(d)

    def ensure_drills(self, drill_counts):
        for type_name, n in drill_counts.items():
            if (n - len(self.drills_by_type[type_name]) - len(self.constructed_drills_by_type[type_name])) > 0:
                # TODO consider distance
                for i in self.resources_map[type_name]:
                    used = False
                    for ent in self.game.map.entities(i.Position.position):
                        e = self.game.world.entity(ent)
                        if e.own():
                            used = True
                    if used:
                        continue
                    self.build("drill", i.Position.position)
                    break

    def ensure_pumps(self, pump_counts):
        for type_name, n in pump_counts.items():
            if (n - len(self.pumps_by_type[type_name]) - len(self.constructed_pumps_by_type[type_name])) > 0:
                # TODO consider distance
                for i in self.resources_map[type_name]:
                    used = False
                    for ent in self.game.map.entities(i.Position.position):
                        e = self.game.world.entity(ent)
                        if e.own():
                            used = True
                    if used:
                        continue
                    self.build("pump", i.Position.position)
                    break

    def ensure_arsenal(self):
        for i in self.pumps_by_type["oil"]:
            own = False
            # TODO how to use connected
            for j in self.game.map.area_neighborhood(i.Position.position, 25):
                for ent in self.game.map.entities(j):
                    e = self.game.world.entity(ent)
                    if not e.own():
                        continue
                    if self.inverted_construction_prototypes.get(e.Proto.proto, {}).get("name",
                                                                                        "") == "arsenal":
                        own = True
                        break
                    if not e.has("Unit"):
                        continue
                    unit = self.game.prototypes.unit(e.Proto.proto)
                    if not unit:
                        continue
                    if unit.get("name", "") == "arsenal":
                        own = True
                        break
            if own:
                continue
            self.build("arsenal", int(i.Position.position))

    def ensure_laboratory(self):
        for i in self.drills_by_type["crystals"]:
            own = False
            # TODO how to use connected
            for j in self.game.map.area_neighborhood(i.Position.position, 25):
                for ent in self.game.map.entities(j):
                    e = self.game.world.entity(ent)
                    if not e.own():
                        continue
                    if self.inverted_construction_prototypes.get(e.Proto.proto, {}).get("name",
                                                                                        "") == "laboratory":
                        own = True
                        break
                    if not e.has("Unit"):
                        continue
                    unit = self.game.prototypes.unit(e.Proto.proto)
                    if not unit:
                        continue
                    if unit.get("name", "") == "laboratory":
                        own = True
                        break
            if own:
                continue
            self.build("laboratory", int(i.Position.position))

    def ensure_concrete_plants(self):
        for i in self.drills_by_type["metal"]:
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

    def ensure_factories(self):
        if len(self.drills_by_type["metal"]) > 1:
            close_positions = self.get_points_in_radius(self.main_building.Position.position, 60)
            self.build_construction("factory", 2, close_positions)

    def ensure_arsenal2(self):
        if len(self.pumps_by_type["oil"]) > 0:
            close_positions = self.get_points_in_radius(self.main_building.Position.position, 80)
            self.build_construction("arsenal", 2, close_positions)

    def ensure_bot_assembler(self):
        if len(self.drills_by_type["metal"]) > 1:
            close_positions = self.get_points_in_radius(self.main_building.Position.position, 60)
            self.build_construction("bot assembler", 1, close_positions)

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
                self.atack_strategy()
                self.get_closest_ores()
                unit = [i for i in self.prototypes if i["type"] == uw.Prototype.Unit]

                if self.step == 1:
                    self.construction_prototypes = {i["name"]: i for i in self.prototypes if
                                                    i["type"] == uw.Prototype.Construction}
                    self.recipes_prototypes = {i["name"]: i for i in self.prototypes if
                                               i["type"] == uw.Prototype.Recipe}
                    self.resource_prototypes = {i["name"]: i for i in self.prototypes if
                                                i["type"] == uw.Prototype.Resource}
                    self.inverted_construction_prototypes = {i["id"]: i for i in self.prototypes if
                                                             i["type"] == uw.Prototype.Construction}
                    self.inspect_players()

                # print(set(self.game.map.overview()))
                # pprint([e for e in self.game.map.overview() if e & uw.OverviewFlags.Resource])

                self.inverted_recipes_prototypes = {i['id']: i for i in self.prototypes if
                                                    i["type"] == uw.Prototype.Recipe}

                self.update_drills_by_type()
                self.update_constructed_drills_by_type()
                self.update_pumps_by_type()
                self.update_constructed_pumps_by_type()

                self.ensure_drills({'metal': 3, 'crystals': 1})
                self.ensure_pumps({'oil': 1})
                self.ensure_concrete_plants()
                self.ensure_factories()
                self.ensure_talos(n=30)
                self.ensure_laboratory()
                self.ensure_arsenal()
                # self.ensure_arsenal2()
                self.ensure_bot_assembler()

                resource_count = Counter()
                for r in self.get_resources():
                    resource = self.game.prototypes.resource(r.Proto.proto)
                    resource_count[resource.get("name", "")] += r.Amount.amount

                if self.step % 50 == 1:
                    pprint(resource_count)

                # for i in self.find_units("factory"):
                #     self.game.commands.command_set_priority(i.Id, uw.Priority.Disabled)

                if resource_count["reinforced concrete"] > 10:
                    for i in self.find_units("concrete plant"):
                        self.game.commands.command_set_priority(i.Id, uw.Priority.Disabled)

                if resource_count["reinforced concrete"] < 4:
                    for i in self.find_units("concrete plant"):
                        self.game.commands.command_set_priority(i.Id, uw.Priority.Normal)

                # Repair buildings
                for i in self.find_constructed_units("pump"):
                    if hasattr(i, 'Priority') and i.Priority.priority == uw.Priority.Disabled:
                        print('repairing pump')
                        self.game.commands.command_set_priority(i.Id, uw.Priority.Normal)
                for i in self.find_constructed_units("drill"):
                    if hasattr(i, 'Priority') and i.Priority.priority == uw.Priority.Disabled:
                        print('repairing drill')
                        self.game.commands.command_set_priority(i.Id, uw.Priority.Normal)
                for d in ORDER:
                    name = list(d)[0]
                    for i in self.find_constructed_units(name):
                        if hasattr(i, 'Priority') and i.Priority.priority == uw.Priority.Disabled:
                            print('repairing', name)
                            self.game.commands.command_set_priority(i.Id, uw.Priority.Normal)

                self.assign_paladin_recipes()
                self.assign_laboratory_recipes()
                self.assign_arsenal_recipes()
                self.assign_bot_assembler_recipes()

                # TODO for each shooting unit
                # * move to the edge of the base
                # * guard
                # * detect close enough enemies and move closer

        return update_callback


if __name__ == "__main__":
    bot = Bot()
    bot.start()
