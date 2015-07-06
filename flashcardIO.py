"""
This module contains a simple Flashcard class and methods surrounding that class.
Methods include reading flashcards from a file and writing metadata about those flashcards to a file.
It also includes a method for updating metadata from a daily user responses (e.g. correct/incorrect count).
"""
import selection
import numpy as np
import os, pickle, datetime

METADATAFILE = 'metadata.dat'
"""Metadata is a dict whose keys are flashcard ids and values are lists of reviews.
Each review is a tuple (datetime, correct_boolean)."""

class Flashcard(object):
	def __init__(self, data):
		self.text = data['text']
		self.reviews = data['reviews']
		self.id = data['id']

	def correct_count(self):
		return sum([i[1] for i in self.reviews])

	def incorrect_count(self):
		return len(self.reviews)-self.correct_count()

	def time_since_last(self):
		"""Return datetime.timedelta for the time past since the last review of this card."""
		return datetime.datetime.now()-max(self.reviews)[0]

	def message(self):
		"""Return text to display when sending flashcard to user."""
		return self.text[0]+'\n'*4+self.text[1]

	def __str__(self):
		"""Return text to write when writing flashcard to file."""
		return self.text[0]+'\t'+self.text[1]+'\t'+str(self.id)

def loadmetadata():
	metadata = {}
	if os.path.isfile(METADATAFILE):
		with open(METADATAFILE, 'r') as f:
			metadata = pickle.load(f)
	else: # create new file
		writemetadata(metadata)
	return metadata

def writemetadata(metadata):
	with open(METADATAFILE, 'w') as metafile:
			pickle.dump(metadata, metafile)

def new_id(metadata):
	# assign smallest available id
	if not metadata:
		return 0
	else:
		for i in range(max(metadata)):
			if i not in metadata:
				return i
		return max(metadata)+1

def isintstring(s):
	try:
		int(s)
		return True
	except:
		return False

def parse_line(line, metadata):
	"""Parses a line from a flashcard data file (in the format front\tback[\tid]).
	Returns a Flashcard instance from that line and updates the metadata to include the new id."""
	split = line.strip().split('\t')
	data = {}
	if len(split)==2:
		data['text'] = tuple(split)
		data['id'] = new_id(metadata)
		data['reviews'] = []
	elif len(split)==3 and isintstring(split[2]):
		data['text'] = tuple(split[:2])
		data['id'] = int(split[2])
		if data['id'] not in metadata:
			data['id'] = new_id(metadata)
			data['reviews'] = []
		else:
			data['reviews'] = metadata[data['id']]
	else:
		raise Exception
	return Flashcard(data)

def load(datafile):
	"""Returns a list of flashcard instances from a flashcard data file."""
	buffer_file = open('buffer.txt','w')
	read_file = open(datafile, 'r')
	flashcards = []

	metadata = loadmetadata()

	change = False
	lines = read_file.readlines()
	line_no = 0
	for line in lines:
		line_no += 1
		if line.strip()[0]=='#':
			buffer_file.write(line)
			continue
		if not line.strip():
			continue
		try:
			card = parse_line(line, metadata)
			if card.id not in metadata:
				metadata[cardid] = []
		except:
			"Error: could not convert line %d of file '%s' to flashcard." % (line_no, datafile)
			buffer_file.write(line)
			continue
		change = True
		flashcards.append(card)
		buffer_file.write(str(card)+'\n')

	read_file.close()
	buffer_file.close()

	writemetadata(metadata)

	if change:
		os.remove(datafile)
		os.rename('buffer.txt', datafile)
	else:
		os.remove('buffer.txt')

	clear_old_metadata()
	return flashcards

def write_update(metadata_update):
	"""Writes metadata update to metadata file."""
	metadata = loadmetadata()
	for cardid in metadata_update:
		if cardid not in metadata:
			metadata[cardid] = []
		metadata[cardid] += metadata_update[cardid]
	writemetadata(metadata)

def clear_old_metadata():
	"""Clears metadata from flashcards which are no longer located in the tracked files."""
	cardids = []
	for filename in selection.find_files():
		cardids += [flashcard.id for flashcard in load(filename)]
	metadata = loadmetadata()
	new_metadata = {}
	for cardid in cardids:
		if cardid in metadata:
			new_metadata[cardid] = metadata[cardid]
	writemetadata(new_metadata)

def clear_metadata(filename):
	"""Clears the metadata associated with flashcards in the file "filename"."""
	metadata = loadmetadata()
	buffer_file = open('buffer.txt','w')
	with open(filename, 'r') as f:
		lines = f.readlines()
	line_changes = []
	line_no = 0
	for line in lines:
		line_no += 1
		if not line.strip() or line.strip()[0]=='#'
			buffer_file.write(line)
			continue
		split = line.strip().split('\t')
		if len(split)==3 and isintstring(split[2]):
			cardid = int(split[2])
			if cardid in metadata:
				del metadata[cardid]
		newline = split[0]+'\t'+split[1]+'\n'
		buffer_file.write(newline)
		if line!=newline:
			changes.append( (line_no, line, newline) )
	buffer_file.close()
	print "The following lines will be replaced:"
	for line_change in line_changes:
		print line_no, '-\t'+line_change[1]
		print line_no, '+\t'+line_change[2]
	answer = raw_input('\nContinue? ([y]/n)')
	if answer=='y' or not answer:
		os.remove(filename)
		os.rename('buffer.txt', filename)
		print "File '%s' was replaced." % filename
	writemetadata(metadata)

def daily_update(reviews):
	"""Updates metadata after user responses have been received.
	Metadata: {flash_card_id: list_of_reviews}"""
	for filename in selection.find_files():
		metadata = {}
		for card in load(filename):
			if card.id in reviews:
				if card.id not in metadata:
					metadata[card.id] = []
				metadata[card.id] += reviews[card.id]
		if metadata:
			write_update(metadata)
