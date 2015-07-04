"""
A module for calculating properties on flashcards.

1) a simple class for flashcard
	- fields: front, back, correct_count, incorrect_count, 
		neglectedness

2) a metric for flashcard difficulty
	- includes counts

3) a metric for necessity
	- includes difficulty and days_old

4) a method for rewriting a data file

"""
import selection
import numpy as np
import os, pickle

METADATAFILE = 'metadata.dat'

class Flashcard(object):
	def __init__(self, data):
		self.text = data['text']
		self.correct_count = data['correct_count']
		self.incorrect_count = data['incorrect_count']
		self.days_old = data['days_old']
		self.id = data['id']

	def difficulty(self):
		# returns difficulty as a result of correct/incorrect
		# counts
		total = self.correct_count+self.incorrect_count
		return total*np.exp(float(self.incorrect_count-self.correct_count))+1

	def necessity(self):
		# updates necessity by including difficulty and neglectedness
		# TESTING: not a dynamic necessity function as of yet
		return 1

	def metadata(self):
		return (self.correct_count, self.incorrect_count, self.days_old)

	def message(self):
		# creates text to display when sending card to user
		return self.text[0]+'\n'*4+self.text[1]

	def __str__(self):
		return self.text[0]+'\t'+self.text[1]+'\t'+str(self.id)

def loadmetadata():
	metadata = {}
	if os.path.isfile(METADATAFILE):
		with open(METADATAFILE, 'r') as f:
			metadata = pickle.load(f)
	return metadata

def new_id(metadata):
	# assign smallest available id
	if not metadata:
		return 0
	else:
		for i in range(max(metadata)):
			if i not in metadata:
				return i
		return max(metadata)+1

def line_to_flashcard(line, metadata):
	split = line.strip().split('\t')
	card = {}
	if len(split)==2 or len(split)>3:
		card['text'] = tuple(split)
		card['correct_count'] = 0
		card['incorrect_count'] = 0
		card['days_old'] = 0
		card['id'] = new_id(metadata)
		metadata[card['id']] = (card['correct_count'], card['incorrect_count'], card['days_old'])
	elif len(split)==3:
		card['text'] = tuple(split[:2])
		card['id'] = int(split[2])
		card['correct_count'], card['incorrect_count'], card['days_old'] = metadata[card['id']]
	else:
		raise Exception
	return Flashcard(card), metadata

def load(datafile):
	# returns a list of flashcard instances
	buffer_file = open('buffer.txt','w')
	read_file = open(datafile, 'r')
	flashcards_dict = {}

	metadata = loadmetadata()

	change = False
	lines = read_file.readlines()
	line_no = 0
	for line in lines:
		line_no += 1
		if line[0]=='#':
			buffer_file.write(line)
			continue
		if line=='\n':
			continue
		try:
			current_card, metadata = line_to_flashcard(line, metadata)
		except:
			"Error: could not convert line %d of file '%s' to flashcard. Flashcard ignored." % (line_no, datafile)
			buffer_file.write(line)
			continue
		change = True
		flashcards_dict[current_card.id] = current_card
		buffer_file.write(str(current_card)+'\n')

	read_file.close()
	buffer_file.close()

	with open(METADATAFILE, 'w') as metafile:
		pickle.dump(metadata, metafile)

	if change:
		os.remove(datafile)
		os.rename('buffer.txt', datafile)
	else:
		os.remove('buffer.txt')

	return flashcards_dict.values()

def write_updated(flashcards_dict):
	metadata = loadmetadata()

	for cardid in flashcards_dict:
		metadata[cardid] = flashcards_dict[cardid].metadata()

	with open(METADATAFILE, 'w') as metafile:
		pickle.dump(metadata, metafile)

def clean_metadata():
	ids = []
	for filename in selection.find_files():
		ids.extend([flashcard.id for flashcard in load(filename)])
	metadata = loadmetadata()
	new_metadata = {}
	for id in ids:
		if id in metadata:
			new_metadata[id] = metadata[id]
	with open(METADATAFILE, 'w') as metafile:
		pickle.dump(new_metadata, metafile)

def clear_metadata(filename):
	metadata = loadmetadata()
	with open(filename, 'r') as f:
		lines = f.readlines()
	line_no = 0
	for line in lines:
		line_no += 1
		split = line.strip().split('\t')
		if len(split)==3:
			try:
				del metadata[int(split[2])]
				buffer_file.write(split[0]+'\t'+split[1]+'\n')
			except:
				print "Error: could not read id from line %d in file '%s'." % (line_no, filename)
		else:
			buffer_file.write(line)
	buffer_file.close()
	with open(METADATAFILE, 'w') as metafile:
		pickle.dump(metadata, metafile)
	with open(filename, 'r') as f:
		lines = f.readlines()
	clean_metadata()

def daily_update(updates_dict):
	"""updates_dict is a dict of flashcard ids and corresponding "correct" 
	booleans"""
	for filename in selection.find_files():
		cards = {}
		for card in load(filename):
			if card.id in updates_dict:
				card.correct_count +=  int(updates_dict[card.id])
				card.incorrect_count +=  int(not updates_dict[card.id])
				card.days_old = 0
				cards[card.id] = card
			else:
				card.days_old += 1
				cards[card.id] = card
		write_updated(cards)
