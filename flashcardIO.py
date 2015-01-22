"""
A module for calculating properties on flashcards.

1) a simple class for flashcard
	- fields: front, back, correct_count, incorrect_count, 
		neglectedness

2) a metric for flashcard difficulty
	- includes counts

3) a metric for necessity
	- includes difficulty and neglectedness

4) a method for rewriting a data file

"""
import numpy as np
import os, pickle

class Flashcard(object):
	def __init__(self, data):
		self.text = tuple(data[:2])
		self.correct_count = data[2]
		self.incorrect_count = data[3]
		self.neglectedness = data[4]
		self.id = data[5]

	def difficulty(self):
		# returns difficulty as a result of correct/incorrect
		# counts
		total = self.correct_count+self.incorrect_count
		return total*np.exp(float(self.incorrect_count-self.correct_count))+1

	def necessity(self):
		# updates necessity by including difficulty and neglectedness
		return (1-np.exp(-float(self.neglectedness)))*(1-np.exp(-float(self.difficulty())))

	def to_text(self):
		# creates text to display when sending card to user
		return self.text[0]+'\n'*4+self.text[1]

	def __str__(self):
		return self.text[0]+'\t'+self.text[1]+'\t'+str(self.correct_count)+'\t'+str(self.incorrect_count)+'\t'+str(self.neglectedness)+'\t'+str(self.id)

def new_id():
	with open('ids.dat','r') as f:
		ids = pickle.load(f)
	rando = np.random.randint(10000)
	while rando in ids:
		rando = np.random.randint(10000)
	with open('ids.dat','w') as f:
		pickle.dump(ids+[rando], f)
	return rando

def line_to_flashcard(line):
	split = line.strip().split('\t')
	if len(split)==2 or len(split)==5:
		rando = new_id()
		flash = split[:]+[0,0,10000,rando]
	elif len(split)==6:
		flash = split[:2]+[int(split[2])]+[int(split[3])]+[float(split[4])]+[int(split[5])]
	else:
		raise Exception
	return Flashcard(flash)

def load(datafile):
	# returns a list of flashcard instances
	f = open(datafile, 'r')
	flashcards = []
	line_no = 0

	while True:
		try:
			line_no += 1
			line = f.next()
			if line[0]=='#' or line=='\n':
				continue
			flashcards.append(line_to_flashcard(line))
		except StopIteration:
			break
		except ValueError:
			print "Error: could not convert line %d of reading file %s to flashcard data." % (line_no, datafile)
			break
		except:
			print "Error: unexpected error at line %d of reading file %s." % (line_no, datafile)
			break

	f.close()
	return flashcards

def write(datafile, flashcard_list):
	buffer_file = open('buffer.txt','w')
	read_file = open(datafile, 'r')
	status = True

	list_of_firsts = [flashcard.text[0].strip() for flashcard in flashcard_list]

	while True:
		try:
			line = read_file.next()
			if line[0]=='#' or line=='\n':
				buffer_file.write(line)
				continue
			first = line.split('\t')[0].strip()
			try:
				current_card = flashcard_list[list_of_firsts.index(first)]
			except:
				print "Error: could not match current file with loaded flashcards. Instance: %s" % first
				status = False
				break
			buffer_file.write(str(current_card)+'\n')
		except StopIteration:
			break
		except:
			status = False
			print "Error: unexpected error. File reading/writing stopped. File: " + __file__
			break

	buffer_file.close()
	read_file.close()

	if status:
		os.remove(datafile)
		os.rename('buffer.txt', datafile)

def update_cards(updates_dict):
	# updates_dict is a dict of flashcard ids and corresponding "correct" booleans
	ids = update_dict.keys()
	for filename in selection.find_files():
		cards = flashcardIO.load(filename)
		for card in cards:
			if card.id in ids:
				card.correct_count +=  int(updates_dict[card.id])
				card.incorrect_count +=  int(not updates_dict[card.id])
				card.neglectedness = 0
				del updates_dict[card.id]
			else:
				card.neglectedness += 1
		write(filename, cards)