import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import Zork
from Zork import Item, creature, room, weapon


def run_command(cmd, hero_obj, confirmation="n"):
	output = io.StringIO()
	with patch("builtins.input", return_value=confirmation) as mock_input:
		with redirect_stdout(output):
			Zork.analyze(cmd, hero_obj)
	return output.getvalue(), mock_input


class BuildCharacterTests(unittest.TestCase):
	def test_characters_share_the_same_supplied_world(self):
		world = Zork.buildWorld()
		first = Zork.buildCharacter("Alice", world)
		second = Zork.buildCharacter("Bob", world)

		self.assertIs(first.room, second.room)

	def test_each_character_gets_an_independent_inventory(self):
		world = Zork.buildWorld()
		first = Zork.buildCharacter("Alice", world)
		second = Zork.buildCharacter("Bob", world)

		self.assertEqual([], first.inventory)
		self.assertIsNot(first.inventory, second.inventory)
		first.inventory.append(Item("rock", "A small rock", 1.0))
		self.assertEqual([], second.inventory)

	def test_name_prompt_is_unchanged(self):
		with patch("builtins.input", return_value="Alice") as mock_input:
			hero_obj = Zork.buildCharacter()

		mock_input.assert_called_once_with("What is your name traveler? ")
		self.assertEqual("Alice", hero_obj.name)

	def test_starting_room_text_is_unchanged(self):
		world = Zork.buildWorld()

		self.assertEqual("Tunnel", world.name)
		self.assertEqual(
			"You are in a dark tunnel. The tunnel extends both east and west",
			world.description,
		)
		self.assertEqual("A dark tunnel extends", world.info)


class CommandParsingTests(unittest.TestCase):
	def setUp(self):
		self.world = Zork.buildWorld()
		self.hero = Zork.buildCharacter("Alice", self.world)

	def test_commands_are_not_accepted_as_prefixes(self):
		cases = [
			"exitnow",
			"examine room carefully",
			"inventorys",
			"helpful",
			"take sword now",
			"east now",
			"attack troll now",
		]

		for cmd in cases:
			with self.subTest(cmd=cmd):
				output, mock_input = run_command(cmd, self.hero)
				mock_input.assert_not_called()
				self.assertNotIn(self.world.description, output)
				self.assertIn("I don't understand that", output)

	def test_exact_exit_can_be_cancelled_without_state_change(self):
		output, mock_input = run_command("exit", self.hero)

		mock_input.assert_called_once_with("Are you sure? Y/N: ")
		self.assertTrue(self.hero.alive)
		self.assertIs(self.hero.room, self.world)
		self.assertEqual("", output)

	def test_confirmed_exit_raises_system_exit(self):
		with patch("builtins.input", return_value="y"):
			with redirect_stdout(io.StringIO()):
				with self.assertRaises(SystemExit):
					Zork.analyze("quit", self.hero)

	def test_examine_commands_match_exactly(self):
		output, _ = run_command("examine room", self.hero)
		self.assertIn(self.world.description, output)

		output, _ = run_command("examine", self.hero)
		self.assertIn("Examine what?", output)


class ItemPickupTests(unittest.TestCase):
	def setUp(self):
		self.world = Zork.buildWorld()
		self.hero = Zork.buildCharacter("Alice", self.world)

	def test_taking_an_item_moves_ownership_once(self):
		run_command("take sword", self.hero)

		self.assertEqual(["sword"], [item.name for item in self.hero.inventory])
		self.assertNotIn("sword", self.world.items)
		self.assertIs(self.hero.weapon, self.hero.inventory[0])

		output, _ = run_command("take sword", self.hero)

		self.assertEqual(1, len(self.hero.inventory))
		self.assertIn("There is no sword here", output)

	def test_missing_item_does_not_change_inventory(self):
		output, _ = run_command("take excalibur", self.hero)

		self.assertEqual([], self.hero.inventory)
		self.assertIn("There is no excalibur here", output)


class RoomStateTests(unittest.TestCase):
	def test_room_containers_are_not_shared(self):
		first = room("First", "First description", "First info")
		second = room("Second", "Second description", "Second info")
		first.items["rock"] = Item("rock", "A rock", 1.0)
		first.creatures.append(creature("bat", "A bat"))

		self.assertEqual({}, second.items)
		self.assertEqual({}, second.interactables)
		self.assertEqual([], second.creatures)

	def test_items_remain_in_their_room_when_switching_rooms(self):
		world = Zork.buildWorld()
		hero_obj = Zork.buildCharacter("Alice", world)

		run_command("east", hero_obj)
		self.assertIs(hero_obj.room, world.eastRoom)

		output, _ = run_command("take sword", hero_obj)
		self.assertIn("There is no sword here", output)
		self.assertEqual([], hero_obj.inventory)

		run_command("west", hero_obj)
		self.assertIs(hero_obj.room, world)
		self.assertIn("sword", world.items)


class CombatTests(unittest.TestCase):
	def setUp(self):
		self.world = Zork.buildWorld()
		self.hero = Zork.buildCharacter("Alice", self.world)

	def test_dead_hero_cannot_perform_more_commands(self):
		room_before = self.hero.room
		self.hero.health = 1.0
		self.world.creatures.append(
			creature("bat", "A giant bat", health=50.0, damage=50.0)
		)

		output, _ = run_command("attack", self.hero)

		self.assertIn("You have died.", output)
		self.assertFalse(self.hero.alive)

		run_command("east", self.hero)
		run_command("take sword", self.hero)

		self.assertIs(self.hero.room, room_before)
		self.assertEqual([], self.hero.inventory)
		self.assertIn("sword", self.world.items)

	def test_game_loop_stops_immediately_after_death(self):
		self.hero.health = 1.0
		self.world.creatures.append(
			creature("bat", "A giant bat", health=50.0, damage=50.0)
		)
		commands = iter(["attack", "take sword", "exit", "y"])

		with redirect_stdout(io.StringIO()):
			Zork.gameLoop(self.hero, lambda prompt: next(commands))

		self.assertFalse(self.hero.alive)
		self.assertEqual([], self.hero.inventory)
		self.assertIn("sword", self.world.items)

	def test_a_killed_creature_does_not_retaliate_or_remain_targetable(self):
		run_command("take sword", self.hero)
		run_command("east", self.hero)
		troll = self.world.eastRoom.creatures[0]

		run_command("attack", self.hero)
		self.assertEqual(3.0, troll.health)
		self.assertEqual(8.0, self.hero.health)

		run_command("attack", self.hero)
		self.assertFalse(troll.alive)
		self.assertEqual(0.0, troll.health)
		self.assertEqual(8.0, self.hero.health)

		output, _ = run_command("attack", self.hero)
		self.assertIn("There is nothing to attack here", output)


class WeaponBoundaryTests(unittest.TestCase):
	def setUp(self):
		self.arena = room("Arena", "Arena description", "Arena info")
		self.target = creature(
			"dummy", "A training dummy", health=5.0, damage=0.0
		)
		self.arena.creatures.append(self.target)
		self.hero = Zork.buildCharacter("Alice", self.arena)

	def test_weapon_constructor_initializes_item_fields_and_damage(self):
		sword = weapon("sword", "A rusty sword", 3.0, 5.0)

		self.assertEqual("sword", sword.name)
		self.assertEqual("A rusty sword", sword.description)
		self.assertEqual(3.0, sword.weight)
		self.assertEqual(5.0, sword.damage)

	def test_zero_damage_weapon_deals_no_damage(self):
		self.hero.weapon = weapon("stick", "A wooden stick", 1.0, 0.0)

		run_command("attack", self.hero)

		self.assertEqual(5.0, self.target.health)
		self.assertTrue(self.target.alive)

	def test_negative_damage_weapon_does_not_heal(self):
		self.target.health = 3.0
		self.hero.weapon = weapon("cursed", "A cursed blade", 1.0, -4.0)

		run_command("attack", self.hero)

		self.assertEqual(3.0, self.target.health)
		self.assertTrue(self.target.alive)

	def test_unarmed_hero_uses_base_damage(self):
		self.assertIsNone(self.hero.weapon)

		run_command("attack", self.hero)

		self.assertEqual(4.0, self.target.health)


class GameLoopTests(unittest.TestCase):
	def test_full_take_move_fight_move_exit_transition(self):
		world = Zork.buildWorld()
		hero_obj = Zork.buildCharacter("Alice", world)
		commands = iter([
			"take sword",
			"east",
			"attack",
			"attack",
			"west",
			"inventory",
			"exit",
			"y",
		])

		with redirect_stdout(io.StringIO()):
			with self.assertRaises(SystemExit):
				Zork.gameLoop(hero_obj, lambda prompt: next(commands))

		self.assertIs(hero_obj.room, world)
		self.assertEqual(["sword"], [item.name for item in hero_obj.inventory])
		self.assertFalse(world.eastRoom.creatures[0].alive)
		self.assertEqual(8.0, hero_obj.health)
		self.assertTrue(hero_obj.alive)

	def test_loop_prompts_are_unchanged(self):
		hero_obj = Zork.buildCharacter("Alice", Zork.buildWorld())
		prompts = []

		def fake_input(prompt):
			prompts.append(prompt)
			return "exit" if len(prompts) == 1 else "y"

		with redirect_stdout(io.StringIO()):
			with self.assertRaises(SystemExit):
				Zork.gameLoop(hero_obj, fake_input)

		self.assertEqual([">>>", "Are you sure? Y/N: "], prompts)


class IllegalCommandTests(unittest.TestCase):
	def test_illegal_commands_do_not_crash_or_change_state(self):
		world = Zork.buildWorld()
		hero_obj = Zork.buildCharacter("Alice", world)
		commands = [
			"",
			"   ",
			"xyzzy",
			"take",
			"take excalibur",
			"drop sword",
			"go",
			"go nowhere",
			"north",
			"examine",
			"examine nothing",
			"attack nothing",
			"help me",
			"exitnow",
			"inventorys",
		]

		for cmd in commands:
			with self.subTest(cmd=cmd):
				room_before = hero_obj.room
				inventory_before = list(hero_obj.inventory)
				health_before = hero_obj.health

				output, _ = run_command(cmd, hero_obj)

				self.assertIs(room_before, hero_obj.room)
				self.assertEqual(inventory_before, hero_obj.inventory)
				self.assertEqual(health_before, hero_obj.health)
				self.assertTrue(hero_obj.alive)
				self.assertIn("sword", world.items)
				if cmd in {"", "   ", "xyzzy", "take", "drop sword", "go", "go nowhere", "exitnow", "inventorys"}:
					self.assertIn("I don't understand that", output)


if __name__ == "__main__":
	unittest.main()
