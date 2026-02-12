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


def beedle_eval(state: CollectionState, player, options, price) -> bool:
    """
    Evaluate if you have enough rupees for beedle
    """
    if state.has("_UT_Glitched_Logic", player):
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
    return state.has("Rupees", player, price * discount + other_costs)


def buy_beedle_points_eval(state, player, options, points) -> bool:
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


class PHShop(Rule[PhantomHourglassWorld], game="The Legend of Zelda - Phantom Hourglass"):
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
            world.options,
            player=world.player,
            caching_enabled=False)

    class Resolved(Rule.Resolved):
        price: int
        options: PhantomHourglassOptions


class IslandShop(PHShop):
    class Resolved(Rule.Resolved):
        price: int
        options: PhantomHourglassOptions

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            if state.has("_UT_Glitched_Logic", self.player):
                return True
            other_costs = 0
            if state.has("SW Sea Chart", self.player):
                # Includes cannon island, but not salvage arm cause that also unlocks treasure shop
                other_costs += 1550
                if self.options.randomize_masked_beedle:
                    other_costs += 1500
                other_costs *= cost_multiplier
            return state.has("Rupees", self.price+other_costs)


class BeedleShop(PHShop):
    class Resolved(Rule.Resolved):
        price: int
        options: PhantomHourglassOptions

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            return beedle_eval(state, self.player, self.options, self.price)


class HasBeedlePoints(PHShop):
    class Resolved(Rule.Resolved):
        price: int
        options: PhantomHourglassOptions

        @override
        def _evaluate(self, state: CollectionState):
            if state.has("_UT_Glitched_Logic", self.player):
                return True
            points = self.price  # lol don't care
            option = self.options.randomize_beedle_membership
            if option == "randomize":
                if self.price <= 20:  # Buying 20 points is always in logic
                    return buy_beedle_points_eval(state, self.player, self.options, points)
                return state.count("Beedle Points", self.player) >= points
            elif option == "randomize_with_grinding":
                return buy_beedle_points_eval(state, self.player, self.options, points)
            return False

class IsUT(Rule[PhantomHourglassWorld], game="The Legend of Zelda - Phantom Hourglass"):
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


class HasTime(Rule[PhantomHourglassWorld], game="The Legend of Zelda - Phantom Hourglass"):
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
            world.options,
            player=world.player,
            caching_enabled=False)

    class Resolved(Rule.Resolved):
        time: int
        room: int or str
        floor_func: "Callable"
        options: PhantomHourglassOptions

        @override
        def _evaluate(self, state: CollectionState):
            time_option = self.options.ph_time_logic.value
            if state.has("_UT_Glitched_Logic", self.player) or time_option == 5:
                return True
            if state.has("Phantom Hourglass", self.player):
                return True
            if time_option > 2:
                room_lookup = {3: 0, 4: 3}
                return self.room > room_lookup[time_option]
            if self.options.ph_required and not state.has("Phantom Hourglass", self.player):
                return False

            total_sand = state.count("Sand", self.player)
            time_lookup = {0: 1, 1: 2, 2: 4, -1: 0.5}
            multiplier = time_lookup.get(self.options.ph_time_logic.value, 1)

            floor_time = self.floor_func(state, self.player) + self.time

            return total_sand >= floor_time // multiplier

class TotOKSmallKeys(Rule[PhantomHourglassWorld], game="The Legend of Zelda - Phantom Hourglass"):
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
            world.options,
            player=world.player,
            caching_enabled=False)

    class Resolved(Rule.Resolved):
        base_count: int
        options: "PhantomHourglassOptions"

        @override
        def _evaluate(self, state: CollectionState):
            sub = 0
            ut_glitched = state.has("_UT_Glitched_Logic", self.player)
            if self.base_count >= 2 and ut_glitched and not state.has("_UT_got_chart", self.player):
                sub += 1
            if all([
                self.base_count >= 5,
                any([
                    state.has("Grappling Hook", self.player),
                    all([
                        self.options.randomize_pedestal_items, # Not vanilla
                        any([
                            ut_glitched,
                            self.options.logic in ["hard", "glitched"],
                            self.options.randomize_pedestal_items.value > 1,
                        ])
                    ])
                ])
            ]):
                sub += 1
            return state.has("Small Key (Temple of the Ocean King)", self.base_count - sub)

class LocationNotExcluded(Rule[PhantomHourglassWorld], game="The Legend of Zelda - Phantom Hourglass"):
    loc: str
    def __init__(self, loc):
        self.loc = loc
        super().__init__()

    def _instantiate(self, world: PhantomHourglassWorld) -> Rule.Resolved:
        return self.Resolved(
            world.get_location(self.loc),
            player=world.player,
            caching_enabled=False)

    class Resolved(Rule.Resolved):
        location: "Location"

        @override
        def _evaluate(self, state: CollectionState):
            return self.location.progress_type != LocationProgressType.EXCLUDED

class Not(Rule[PhantomHourglassWorld], game="The Legend of Zelda - Phantom Hourglass"):
    invert_rule: Callable
    def __init__(self, invert_rule, **kwargs):
        self.invert_rule = invert_rule
        self.kwargs = kwargs
        super().__init__()

    def _instantiate(self, world: PhantomHourglassWorld) -> Rule.Resolved:
        return self.Resolved(
            self.invert_rule,
            self.kwargs,
            player=world.player,
            caching_enabled=False)

    class Resolved(Rule.Resolved):
        invert_rule: Callable
        kwargs: Any

        @override
        def _evaluate(self, state: CollectionState):
            return not self.invert_rule(state, self.player, **self.kwargs)