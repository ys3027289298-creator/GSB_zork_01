import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import Zork
from Zork import Item, creature, room, weapon


def run_analyze(cmd, hero_obj, input_response="n"):
	#Runs analyze() with stdin/stdout captured. Returns (output, mock_input).
	buf = io.StringIO()
	with patch("builtins.input", return_value=input_response) as mock_input:
		with redirect_stdout(buf):
			Zork.analyze(cmd, hero_obj)
	return buf.getvalue(), mock_input


class CharacterBuildTests(unittest.TestCase):
	#Bug repro: buildCharacter used to duplicate the world on every call and
	#left hero.inventory as a shared/None default.

	def test_shared_world_is_not_duplicated(self):
		world = Zork.buildWorld()
		first = Zork.buildCharacter("Alice", world)
		second = Zork.buildCharacter("Bob", world)
		self.assertIs(first.room, second.room)

	def test_each_hero_has_independent_inventory(self):
		world = Zork.buildWorld()
		first = Zork.buildCharacter("Alice", world)
		second = Zork.buildCharacter("Bob", world)
		self.assertEqual([], first.inventory)
		self.assertIsNot(first.inventory, second.inventory)
		first.inventory.append(Item("rock", "A rock", 1.0))
		self.assertEqual([], second.inventory)

	def test_name_prompt_is_unchanged(self):
		with patch("builtins.input", return_value="Alice") as mock_input:
			hero_obj = Zork.buildCharacter()
		mock_input.assert_called_once_with("What is your name traveler? ")
		self.assertEqual("Alice", hero_obj.name)

	def test_original_room_text_is_preserved(self):
		world = Zork.buildWorld()
		self.assertEqual("Tunnel", world.name)
		self.assertEqual("You are in a dark tunnel. The tunnel extends both east and west", world.description)
		self.assertEqual("A dark tunnel extends", world.info)


class CommandParsingTests(unittest.TestCase):
	#Bug repro: command regexes only matched a prefix of the input.

	def setUp(self):
		self.world = Zork.buildWorld()
		self.hero = Zork.buildCharacter("Alice", self.world)

	def test_prefixed_exit_does_not_trigger_exit_prompt(self):
		out, mock_input = run_analyze("exitnow", self.hero)
		mock_input.assert_not_called() #must not ask "Are you sure?"
		self.assertTrue(self.hero.alive)

	def test_exact_exit_prompts_and_abort_is_reversible(self):
		out, mock_input = run_analyze("exit", self.hero, input_response="n")
		mock_input.assert_called_once_with("Are you sure? Y/N: ")
		self.assertTrue(self.hero.alive)
		self.assertIs(self.hero.room, self.world)

	def test_exact_exit_confirm_quits(self):
		with patch("builtins.input", return_value="y"):
			with redirect_stdout(io.StringIO()):
				with self.assertRaises(SystemExit):
					Zork.analyze("quit", self.hero)

	def test_prefixed_examine_does_not_match(self):
		out, _ = run_analyze("examine room carefully", self.hero)
		self.assertNotIn(self.world.description, out)

	def test_exact_examine_room_still_works(self):
		out, _ = run_analyze("examine room", self.hero)
		self.assertIn(self.world.description, out)

	def test_bare_examine_asks_for_target(self):
		out, _ = run_analyze("examine", self.hero)
		self.assertIn("Examine what?", out)

	def test_prefixed_inventory_does_not_match(self):
		out, _ = run_analyze("inventorys", self.hero)
		self.assertIn("I don't understand", out)

	def test_prefixed_help_does_not_match(self):
		out, _ = run_analyze("helpful", self.hero)
		self.assertIn("I don't understand", out)


class ItemPickupTests(unittest.TestCase):
	#Bug repro: picked up items were never removed from the room, so the same
	#item could be picked up over and over.

	def setUp(self):
		self.world = Zork.buildWorld()
		self.hero = Zork.buildCharacter("Alice", self.world)

	def test_take_moves_item_from_room_to_inventory(self):
		run_analyze("take sword", self.hero)
		self.assertEqual(["sword"], [item.name for item in self.hero.inventory])
		self.assertNotIn("sword", self.world.items)

	def test_cannot_pick_up_same_item_twice(self):
		run_analyze("take sword", self.hero)
		out, _ = run_analyze("take sword", self.hero)
		self.assertEqual(1, len(self.hero.inventory))
		self.assertIn("no sword", out)

	def test_taken_weapon_is_equipped(self):
		run_analyze("take sword", self.hero)
		self.assertIsNotNone(self.hero.weapon)
		self.assertEqual("sword", self.hero.weapon.name)


class RoomItemsTests(unittest.TestCase):
	#Bug repro: items leaked between rooms (shared containers), so items were
	#still present after switching rooms.

	def test_rooms_do_not_share_item_containers(self):
		first = room("A", "desc a", "info a")
		second = room("B", "desc b", "info b")
		first.items["rock"] = Item("rock", "A rock", 1.0)
		self.assertNotIn("rock", second.items)

	def test_items_stay_behind_when_switching_rooms(self):
		world = Zork.buildWorld()
		hero_obj = Zork.buildCharacter("Alice", world)
		run_analyze("east", hero_obj)
		self.assertIs(hero_obj.room, world.eastRoom)
		out, _ = run_analyze("take sword", hero_obj)
		self.assertIn("no sword", out)
		self.assertEqual([], hero_obj.inventory)
		run_analyze("west", hero_obj)
		self.assertIs(hero_obj.room, world)
		self.assertIn("sword", world.items)


class CombatTests(unittest.TestCase):
	#Bug repro: the game kept accepting commands after the hero died in combat.

	def setUp(self):
		self.world = Zork.buildWorld()
		self.hero = Zork.buildCharacter("Alice", self.world)

	def test_hero_death_blocks_further_commands(self):
		self.hero.health = 1.0
		self.world.creatures.append(creature("bat", "A giant bat", health=50.0, damage=50.0))
		out, _ = run_analyze("attack", self.hero)
		self.assertIn("died", out)
		self.assertFalse(self.hero.alive)
		room_before = self.hero.room
		run_analyze("east", self.hero)
		run_analyze("take sword", self.hero)
		self.assertIs(room_before, self.hero.room)
		self.assertEqual([], self.hero.inventory)

	def test_game_loop_ends_on_death(self):
		self.hero.health = 1.0
		self.world.creatures.append(creature("bat", "A giant bat", health=50.0, damage=50.0))
		cmds = iter(["attack", "take sword", "exit"])
		with redirect_stdout(io.StringIO()):
			Zork.gameLoop(self.hero, lambda prompt: next(cmds))
		self.assertFalse(self.hero.alive)
		#"take sword" was queued after the fatal blow and must never run.
		self.assertEqual([], self.hero.inventory)
		self.assertIn("sword", self.world.items)

	def test_killing_creature_stops_retaliation(self):
		run_analyze("take sword", self.hero) #sword deals 5 damage
		run_analyze("east", self.hero)
		troll = self.world.eastRoom.creatures[0] #8 health, 2 damage
		run_analyze("attack", self.hero) #troll at 3, retaliates for 2
		self.assertEqual(8.0, self.hero.health)
		run_analyze("attack", self.hero) #troll dies, no retaliation
		self.assertFalse(troll.alive)
		self.assertEqual(8.0, self.hero.health)


class WeaponBoundaryTests(unittest.TestCase):
	#Bug repro: weapon's constructor passed bad args to Item, and damage at
	#boundary values (zero/negative) behaved abnormally.

	def setUp(self):
		self.world = Zork.buildWorld()
		self.hero = Zork.buildCharacter("Alice", self.world)
		self.arena = room("Arena", "desc", "info")
		self.target = creature("dummy", "A training dummy", health=5.0, damage=0.0)
		self.arena.creatures.append(self.target)
		self.hero.room = self.arena

	def test_weapon_constructor_sets_fields(self):
		sword = weapon("sword", "A rusty sword", 3.0, 5.0)
		self.assertEqual("sword", sword.name)
		self.assertEqual("A rusty sword", sword.description)
		self.assertEqual(3.0, sword.weight)
		self.assertEqual(5.0, sword.damage)

	def test_zero_damage_weapon_deals_no_damage(self):
		self.hero.weapon = weapon("stick", "A stick", 1.0, 0.0)
		run_analyze("attack", self.hero)
		self.assertEqual(5.0, self.target.health)
		self.assertTrue(self.target.alive)

	def test_negative_damage_weapon_does_not_heal(self):
		self.target.health = 3.0
		self.hero.weapon = weapon("cursed", "A cursed blade", 1.0, -4.0)
		run_analyze("attack", self.hero)
		self.assertEqual(3.0, self.target.health) #clamped to 0, never heals

	def test_unarmed_attack_uses_base_damage(self):
		self.hero.weapon = None
		run_analyze("attack", self.hero)
		self.assertEqual(4.0, self.target.health) #base damage of 1


class MainLoopTests(unittest.TestCase):
	#State transitions of the main loop: take -> move -> fight -> move -> exit.

	def test_main_loop_state_transitions(self):
		world = Zork.buildWorld()
		hero_obj = Zork.buildCharacter("Alice", world)
		cmds = iter(["take sword", "east", "attack", "attack", "west", "inventory", "exit", "y"])
		with redirect_stdout(io.StringIO()):
			with self.assertRaises(SystemExit):
				Zork.gameLoop(hero_obj, lambda prompt: next(cmds))
		self.assertIs(hero_obj.room, world)
		self.assertEqual(["sword"], [item.name for item in hero_obj.inventory])
		self.assertFalse(world.eastRoom.creatures[0].alive)
		self.assertEqual(8.0, hero_obj.health)
		self.assertTrue(hero_obj.alive)

	def test_game_loop_uses_unchanged_prompts(self):
		world = Zork.buildWorld()
		hero_obj = Zork.buildCharacter("Alice", world)
		prompts = []

		def fake_input(prompt):
			prompts.append(prompt)
			return "exit" if len(prompts) == 1 else "y"

		with redirect_stdout(io.StringIO()):
			with self.assertRaises(SystemExit):
				Zork.gameLoop(hero_obj, fake_input)
		self.assertEqual(">>>", prompts[0])
		self.assertEqual("Are you sure? Y/N: ", prompts[1])


class IllegalCommandTests(unittest.TestCase):
	#Illegal commands must neither crash nor cause irreversible state changes.

	def test_illegal_commands_are_safe_and_reversible(self):
		world = Zork.buildWorld()
		hero_obj = Zork.buildCharacter("Alice", world)
		illegal = ["", "   ", "xyzzy", "take", "take excalibur", "drop sword",
			"go", "go nowhere", "north", "examine", "examine nothing",
			"attack nothing", "help me", "exitnow", "inventorys"]
		for cmd in illegal:
			with self.subTest(cmd=cmd):
				room_before = hero_obj.room
				inventory_before = list(hero_obj.inventory)
				health_before = hero_obj.health
				out, _ = run_analyze(cmd, hero_obj) #must not raise
				self.assertIs(room_before, hero_obj.room)
				self.assertEqual(inventory_before, hero_obj.inventory)
				self.assertEqual(health_before, hero_obj.health)
				self.assertTrue(hero_obj.alive)
				self.assertIn("sword", world.items)


if __name__ == '__main__':
	unittest.main()
