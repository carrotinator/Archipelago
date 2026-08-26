from BaseClasses import LocationProgressType, Location
from rule_builder.rules import *
from typing import TYPE_CHECKING
from .. import PhantomHourglassWorld, PhantomHourglassOptions

cost_multiplier = 0.7

def beedle_discount(state: CollectionState, player) -> float:
    """
    Calculate current beedle discount from beedle points
    """
    thresholds = {100: 0.7, 50: 0.8, 20: 0.9}
    points = state.count("Beedle Points", player)
    for threshold, discount in thresholds.items():
        if points >= threshold:
            return discount
    return 1


def beedle_eval(state: CollectionState, player, options: PhantomHourglassOptions, price) -> bool:
    """
    Evaluate if you have enough rupees for beedle
    """
    if state.has("_UT_Glitched_Logic", player):
        return True
    if can_farm_rupees(state, player):
        return True
    # Multiplier only applies to non-linear items
    multiplier = 0.7 if options.shop_hints else 1
    other_costs = 500 * multiplier + 50
    discount = beedle_discount(state, player)  # Discount from points
    # Island shop items
    if state.has("Bow (Progressive)", player):
        other_costs += 1000
        if state.has("Bombchus (Progressive)", player):
            other_costs += 3000
    if state.has("Bombs (Progressive)", player):
        other_costs += 1000 * discount * multiplier  # Bomb bag is affected by discount
    if options.randomize_masked_beedle:
        other_costs += 1500 * multiplier
    if state.has("Freebie Card", player):
        other_costs -= 500 * discount  # Freebie card assumed to be used for the 500r wisdom gem.
    return count_rupees(state, player) >= price * discount + other_costs

def can_farm_rupees(state, player):
    return any([
        all([
            state.has("_has_treasure_teller", player),  # Can Sell Treasure
            any([
                all([
                    state.has("_can_farm_totok", player),
                    state.has("Sword (Progressive)", player, 2),
                ]),
                all([  # Can Farm Minigames
                    state.multiworld.worlds[player].options.randomize_minigames,
                    any([
                        state.has("_can_play_archery", player),
                        state.has("_can_play_cannon_game", player),
                        state.has("_can_play_goron_race", player),
                    ])
                ])
            ]),
        ]),
        all([  # Can farm harrow (and chooses to play with harrow)
            state.has("_can_play_harrow", player),
            state.multiworld.worlds[player].options.randomize_harrow
        ]),
    ])

def count_rupees(state, player):
    rupees = state.count("Rupees", player)
    if state.has("_has_treasure_teller", player):
        rupees += state.count("Treasure", player)
    return rupees

def buy_beedle_points_eval(state, player, options: PhantomHourglassOptions, points) -> bool:
    """
    Evaluate if you have enough rupees to buy beedle points
    """
    points_res = points - state.count("Beedle Points", player)
    if points_res > 0:
        cost = points_res * 100
    else:
        return True
    if state.has("Bombs (Progressive)", player):
        cost -= 1000 * beedle_discount(state, player)
    return beedle_eval(state, player, options, cost)

tloz_ph = PhantomHourglassWorld.game

class PHShop(Rule[PhantomHourglassWorld], game=tloz_ph):
    """
    Base class for shared code in shops
    """
    price: int

    def __init__(self, price: int):
        self.price = price
        super().__init__()

    def _instantiate(self, world: PhantomHourglassWorld) -> Rule.Resolved:
        return self.Resolved(
            self.price,
            player=world.player,
            caching_enabled=False)

    class Resolved(Rule.Resolved):
        price: int


class IslandShop(PHShop, game=tloz_ph):
    class Resolved(Rule.Resolved):
        price: int

        def calculate_costs(self, state):
            other_costs = 0
            options: PhantomHourglassOptions = state.multiworld.worlds[self.player].options
            if state.has("SW Sea Chart", self.player):
                # Includes cannon island, but not salvage arm cause that also unlocks treasure shop
                other_costs += 1550
                if options.randomize_masked_beedle:
                    other_costs += 1500
                other_costs *= cost_multiplier
            return other_costs

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            if state.has("_UT_Glitched_Logic", self.player):
                return True
            if can_farm_rupees(state, self.player):
                return True
            other_costs = self.calculate_costs(state)
            return count_rupees(state, self.player) >= self.price+other_costs

        def __str__(self):
            return f"Has a bunch of Rupees (Island Shop)"


class BeedleShop(PHShop, game=tloz_ph):
    class Resolved(Rule.Resolved):
        price: int

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            options: PhantomHourglassOptions = state.multiworld.worlds[self.player].options
            return beedle_eval(state, self.player, options, self.price)

        def __str__(self):
            return f"Has a bunch of Rupees (Beedle)"


class HasBeedlePoints(PHShop, game=tloz_ph):
    class Resolved(Rule.Resolved):
        price: int

        @override
        def _evaluate(self, state: CollectionState):
            if state.has("_UT_Glitched_Logic", self.player):
                return True
            points = self.price  # lol don't care
            options: PhantomHourglassOptions = state.multiworld.worlds[self.player].options
            if options.randomize_beedle_membership == "randomize":
                if self.price <= 20:  # Buying 20 points is always in logic
                    return buy_beedle_points_eval(state, self.player, options, points)
                return state.count("Beedle Points", self.player) >= points
            elif options.randomize_beedle_membership == "randomize_with_grinding":
                return buy_beedle_points_eval(state, self.player, options, points)
            return False

        def __str__(self):
            return f"Has {self.price} Beedle Points"

class IsUT(Rule[PhantomHourglassWorld], game=tloz_ph):
    """
    Is Universal Tracker
    """
    toggle: bool
    def __init__(self, toggle=True):
        self.toggle = toggle

    def _instantiate(self, world: PhantomHourglassWorld) -> Rule.Resolved:
        return self.Resolved(
            self.toggle,
            player=world.player,
            caching_enabled=True)

    class Resolved(Rule.Resolved):
        toggle: bool
        @override
        def _evaluate(self, state: CollectionState):
            return getattr(state.multiworld, "generation_is_fake", False) == self.toggle

        def __str__(self):
            return f"Is Universal Tracker"


class HasTime(Rule[PhantomHourglassWorld], game=tloz_ph):
    """
    Determine if you have enough time
    """
    time: int
    floor_func: "Callable"
    room: int or str

    def __init__(self, time, floor_func, room=4):
        self.time = time
        self.room = room
        self.floor_func = floor_func
        super().__init__()

    def _instantiate(self, world: PhantomHourglassWorld) -> Rule.Resolved:
        return self.Resolved(
            self.time,
            self.room,
            self.floor_func,
            player=world.player,
            caching_enabled=False)

    class Resolved(Rule.Resolved):
        time: int
        room: int or str
        floor_func: "Callable"

        @override
        def _evaluate(self, state: CollectionState):
            options: PhantomHourglassOptions = state.multiworld.worlds[self.player].options
            time_option = options.ph_time_logic.value
            if state.has("_UT_Glitched_Logic", self.player) or time_option == 5:
                return True
            if time_option > 2:
                room_lookup = {3: 0, 4: 3}
                return self.room > room_lookup[time_option]
            if options.ph_required and not state.has("Phantom Hourglass", self.player):
                return False

            total_sand = state.count("Sand", self.player)
            time_lookup = {0: 1, 1: 2, 2: 4, -1: 0.5}
            multiplier = time_lookup.get(time_option, 1)

            floor_time = self.floor_func(state, self.player) + self.time

            return total_sand >= floor_time // multiplier

        def __str__(self):
            return f"Has enough Sand to reach floor {self.room} + {self.time}/time_logic_difficulty"

class TotOKSmallKeys(Rule[PhantomHourglassWorld], game=tloz_ph):
    """
    Determine if you have enough time
    """
    base_count: int

    def __init__(self, base_count):
        self.base_count = base_count
        super().__init__()

    def _instantiate(self, world: PhantomHourglassWorld) -> Rule.Resolved:
        return self.Resolved(
            self.base_count,
            player=world.player,
            caching_enabled=False)

    class Resolved(Rule.Resolved):
        base_count: int

        @override
        def _evaluate(self, state: CollectionState):
            sub = 0
            ut_glitched = state.has("_UT_Glitched_Logic", self.player)
            options: PhantomHourglassOptions = state.multiworld.worlds[self.player].options
            if self.base_count >= 2 and ut_glitched and not state.has("_UT_got_chart", self.player):
                sub += 1
            if all([
                self.base_count >= 5,
                any([
                    state.has("Grappling Hook", self.player),
                    all([
                        options.randomize_pedestal_items, # Not vanilla
                        any([
                            ut_glitched,
                            options.logic in ["hard", "glitched"],
                            options.randomize_pedestal_items.value > 1,
                        ])
                    ])
                ])
            ]):
                sub += 1
            return state.has("Small Key (Temple of the Ocean King)", self.base_count - sub)

    def __str__(self):
        return f"Has {self.base_count}-shortcuts TotOK Small Keys"

class LocationNotExcluded(Rule[PhantomHourglassWorld], game=tloz_ph):
    loc: str
    def __init__(self, loc):
        self.loc = loc
        super().__init__()

    def _instantiate(self, world: PhantomHourglassWorld) -> Rule.Resolved:
        return self.Resolved(
            world.get_location(self.loc),
            player=world.player,
            caching_enabled=False)

    @override
    def __str__(self) -> str:
        options = f", options={self.options}" if self.options else ""
        return f"{self.__class__.__name__}({self.loc}{options})"

    class Resolved(Rule.Resolved):
        location: "Location"

        @override
        def _evaluate(self, state: CollectionState):
            return self.location.progress_type != LocationProgressType.EXCLUDED

        def __str__(self):
            return f"Location {self.location} is not Excluded"

class NotWayfarerTrade(Rule[PhantomHourglassWorld], game=tloz_ph):
    def _instantiate(self, world: PhantomHourglassWorld) -> Rule.Resolved:
        return self.Resolved(
            player=world.player,
            caching_enabled=False)

    def __str__(self):
        return f"Not Has _wayfarer_trade"

    class Resolved(Rule.Resolved):
        @override
        def _evaluate(self, state: CollectionState):
            return not state.has("_wayfarer_trade", self.player)

        def __str__(self):
            return f"Not Has _wayfarer_trade"

class NotToCCrystals(Rule[PhantomHourglassWorld], game=tloz_ph):
    def _instantiate(self, world: PhantomHourglassWorld) -> Rule.Resolved:
        return self.Resolved(
            player=world.player,
            caching_enabled=False)

    def __str__(self):
        return "Not Has any of (Square Crystal (Temple of Courage), Square Crystals, Square Pedestal North (Temple of Courage))"

    class Resolved(Rule.Resolved):
        @override
        def _evaluate(self, state: CollectionState):
            shape, dung_name, diff = "Square", "Temple of Courage", "North"
            return any([
                state.has(f"{shape} Crystal ({dung_name})", self.player),
                state.has(f"{shape} Crystals", self.player),
                state.has(f"{shape} Pedestal {diff} ({dung_name})", self.player),
            ])

        def __str__(self):
            return "Not Has any of (Square Crystal (Temple of Courage), Square Crystals, Square Pedestal North (Temple of Courage))"

class HasRequiredMetals(Rule[PhantomHourglassWorld], game=tloz_ph):
    def _instantiate(self, world: PhantomHourglassWorld) -> Rule.Resolved:
        return HasGroup("Metals", world.required_metals).resolve(world)

class HasZauzMetals(Rule[PhantomHourglassWorld], game=tloz_ph):
    def _instantiate(self, world: PhantomHourglassWorld) -> Rule.Resolved:
        return HasGroup("Metals", world.options.zauz_required_metals.value).resolve(world)