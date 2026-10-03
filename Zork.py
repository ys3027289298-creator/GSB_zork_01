import re
import sys

exitCmd = re.compile(r'(?:Exit|Quit|Close|End|Suicide)$', flags=re.IGNORECASE)
examineCmd = re.compile(r'(?:Look at|Examine|Inspect) (\w+)$', flags=re.IGNORECASE)
examineBareCmd = re.compile(r'(?:Look at|Examine|Inspect)$', flags=re.IGNORECASE)
inventoryCmd = re.compile(r'(?:Inventory|Items)$', flags=re.IGNORECASE)
helpCmd = re.compile(r'(?:Help|H|\?|-H|-Help)(?:\s+(.*))?$', flags=re.IGNORECASE)
goCmd = re.compile(r'(?:Go )?(North|East|South|West)$', flags=re.IGNORECASE)
takeCmd = re.compile(r'(?:Take|Grab|Pick up) (\w+)$', flags=re.IGNORECASE)
attackCmd = re.compile(r'(?:Attack|Fight|Kill)(?: (\w+))?$', flags=re.IGNORECASE)

class everything:
	def __init__(self, name, description):
		self.name = name
		self.description = description

	def examine(self):
		#Examine something
		print(self.description)

class creature(everything):
	def __init__(self, name, description=None, health=10.0, damage=1.0):
		super(creature, self).__init__(name, description) #Accesses parent class (Item) and calls it's constructor.
		self.health = health #(Float) Number representing the remaining health of the creature
		self.damage = damage #(Float) Damage the creature deals when it retaliates
		self.alive = True #(Bool) Whether the creature is still alive

	def takeDamage(self, damage):
		#Damage is clamped at zero so an attack can never heal the target.
		self.health -= max(0.0, damage)
		if self.health <= 0:
			self.health = 0
			self.alive = False

class hero(creature):
	def __init__(self, name, room, inventory=None, weapon=None):
		super(hero, self).__init__(name) #Accesses parent class (Item) and calls it's constructor.
		self.room = room #(room) Object reference to the room that the hero currently resides in.
		self.inventory = inventory if inventory is not None else [] #(List) List of items that the hero holds
		self.strength = 10.00#(Float) Number representing the max weight hero can hold
		self.weapon = weapon #(weapon) Object reference to the weapon the hero currently wields

	def attackDamage(self):
		#Boundary safe: an unarmed hero falls back to base damage and a broken
		#weapon (zero or negative damage) can never deal negative damage.
		if self.weapon is None:
			return self.damage
		return max(0.0, self.weapon.damage)

class room(everything):
	def __init__(self, name, description, info, interactables=None, north=None, east=None, south=None, west=None, items=None, creatures=None):
		super(room, self).__init__(name, description) #Accesses parent class (Item) and calls it's constructor.
		self.info = info #(String) Information used in describing the room without entering it.
		self.northRoom = north #(Room) Object reference to the room that exists at the north
		self.eastRoom = east #(Room) Object reference to the room that exists at the east
		self.southRoom = south #(Room) Object reference to the room that exists at the south
		self.westRoom = west #(Room) Object reference to the room that exists at the west
		self.items = items if items is not None else {} #(Dict) Dict[name] = Item of items that exist in the room. Works like a hash map.
		self.interactables = interactables if interactables is not None else {} #(Dict) Dict[name] = Item of items that can be interacted with in the room.
		self.creatures = creatures if creatures is not None else [] #(List) List of creatures that reside in the room.


class Item(everything):
	def __init__(self, name, description, weight):
		self.name = name #(String) Name of the item
		self.description = description #(String) Description of the item
		self.weight = weight #(Float) weight of an item


class weapon(Item):
	def __init__(self, name, description, weight, damage=1.0):
		super(weapon, self).__init__(name, description, weight) #Accesses parent class (Item) and calls it's constructor.
		self.damage = damage #(Float) Damage the weapon deals per attack.

# class sword(weapon):

# class club(weapon):



def buildWorld():
	#Builds the world exactly once so every character shares the same rooms
	#instead of receiving a duplicated copy of the world.
	tunnel = room("Tunnel", "You are in a dark tunnel. The tunnel extends both east and west", "A dark tunnel extends")
	cavern = room("Cavern", "You are in a damp cavern. The tunnel leads back west", "A damp cavern")
	cellar = room("Cellar", "You are in a cold cellar. The tunnel leads back east", "A cold cellar")
	tunnel.eastRoom = cavern
	cavern.westRoom = tunnel
	tunnel.westRoom = cellar
	cellar.eastRoom = tunnel
	tunnel.items["sword"] = weapon("sword", "A rusty sword. It has seen better days", 3.0, 5.0)
	cellar.items["torch"] = Item("torch", "A burning torch", 1.0)
	cavern.creatures.append(creature("troll", "A hulking troll blocks your path", health=8.0, damage=2.0))
	return tunnel


def main():
	print(open("README.txt").read())
	world = buildWorld()
	hero = buildCharacter(startRoom=world)
	print("Goodnight {0}".format(hero.name))
	print("You wake up. Your head hurts and you're thirsty.")
	print(hero.room.description)
	gameLoop(hero)

def gameLoop(hero, inputFn=None):
	#Main loop. Ends as soon as the hero dies so no commands are processed
	#after death.
	if inputFn is None:
		inputFn = input
	while(hero.alive):
		#informUser():
		cmd = inputFn(">>>")
		analyze(cmd, hero, inputFn)

#def informUser():
	#Informs the user about their location.

	#Items that exist on the ground
	#Directions they can travel
	#if hero.room.north != None:

	#Objects of interest (Mailbox etc)

def buildCharacter(name=None, startRoom=None):
	if name is None:
		name = input("What is your name traveler? ")
	if startRoom is None:
		startRoom = buildWorld()
	return(hero(name, startRoom))

def analyze(cmd, hero, inputFn=None):
	if inputFn is None:
		inputFn = input
	if not hero.alive:
		#A dead hero cannot act. Prevents playing on after death in combat.
		return
	if exitCmd.match(cmd):
		if(inputFn("Are you sure? Y/N: ").lower() == 'y'):
			sys.exit()
		else:
			return
	if examineBareCmd.match(cmd):
		print("Examine what?")
		return
	if examineCmd.match(cmd):
		cmdParams = examineCmd.match(cmd).groups()
		target = cmdParams[0].lower()
		if target == 'room':
			hero.room.examine()
		elif target in hero.room.items:
			hero.room.items[target].examine()
		elif hero.weapon is not None and target == hero.weapon.name.lower():
			hero.weapon.examine()
		else:
			print("There is no {0} around here".format(cmdParams[0])) if not cmdParams[0].endswith("s") else print("There are no {0} around here".format(cmdParams[0])) #Crappy plural checker statement
		return
	if inventoryCmd.match(cmd):
		if not hero.inventory:
			print("You are carrying nothing")
		else:
			for item in hero.inventory:
				print(item.name)
		return
	if helpCmd.match(cmd):
		print("Commands: examine <thing>, inventory, go <direction>, take <item>, attack [creature], exit")
		return
	if goCmd.match(cmd):
		direction = goCmd.match(cmd).groups()[0].lower()
		nextRoom = getattr(hero.room, direction + "Room")
		if nextRoom is None:
			print("You can't go that way")
		else:
			hero.room = nextRoom
			print(hero.room.description)
		return
	if takeCmd.match(cmd):
		name = takeCmd.match(cmd).groups()[0].lower()
		if name in hero.room.items:
			#Pop the item out of the room so it cannot be picked up twice.
			item = hero.room.items.pop(name)
			hero.inventory.append(item)
			if isinstance(item, weapon) and hero.weapon is None:
				hero.weapon = item
			print("You take the {0}".format(item.name))
		else:
			print("There is no {0} here".format(name))
		return
	if attackCmd.match(cmd):
		name = attackCmd.match(cmd).groups()[0]
		targets = [c for c in hero.room.creatures if c.alive]
		if name is not None:
			targets = [c for c in targets if c.name.lower() == name.lower()]
		if not targets:
			print("There is nothing to attack here")
			return
		target = targets[0]
		damage = hero.attackDamage()
		target.takeDamage(damage)
		print("You hit the {0} for {1} damage".format(target.name, damage))
		if not target.alive:
			print("The {0} is dead".format(target.name))
		else:
			hero.takeDamage(target.damage)
			print("The {0} hits you for {1} damage".format(target.name, target.damage))
			if not hero.alive:
				print("You have died.")
		return
	print("I don't understand that")


if __name__ == '__main__':
	main()
