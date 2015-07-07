"""
This module contains a simple Flashcard class and methods surrounding that class.
Methods include reading flashcards from a file and writing metadata about those flashcards to a file.
It also includes a method for updating metadata from a daily user responses (e.g. correct/incorrect count).
"""
import selection
import numpy as np
import os, pickle, datetime, time

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
		with open(METADATAFILE, 'r') as metafile:
			metadata = pickle.load(metafile)
	else: # create new file
		writemetadata(metadata)
		for filename in selection.tracked_files():
			clear_metadata(filename)
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
	data['text'] = tuple(split[:2])
	data['id'] = int(split[2])
	data['reviews'] = metadata[data['id']]
	return Flashcard(data)

def load(datafile):
	"""Returns a list of flashcard instances from a flashcard data file.
	When card id's are added to the flashcard file, the user is notified with the changes before the file is updated."""
	biject_db() # add flashcard ids to lines without one
	with open(datafile, 'r') as f:
		lines = f.readlines()
	metadata = loadmetadata()
	flashcards = []
	for line in lines:
		if line.strip()[0]=='#' or not line.strip():
			continue
		try:
			card = parse_line(line, metadata)
		except:
			print "Error: bijection failed from metadata ids to written ids."
		flashcards += [card]
	return flashcards

def write_update(metadata_update):
	"""Writes metadata update to metadata file."""
	metadata = loadmetadata()
	for cardid in metadata_update:
		if cardid not in metadata:
			metadata[cardid] = []
		metadata[cardid] += metadata_update[cardid]
	writemetadata(metadata)

def fetch_file(cardid):
	target_files = []
	for filename in selection.tracked_files():
		if cardid in get_ids(filename):
			target_files += [filename]
	assert len(target_files)<=1, "multiple files contain card id {}:\n{}".format(cardid, target_files)
	if target_files:
		return target_files[0]
	else:
		return None

def fetch_card(cardid):
	metadata = loadmetadata()
	target_file = fetch_file(cardid)
	if target_file:
		with open(target_file, 'r') as f:
			lines = f.readlines()
		for line in lines:
			split = line.strip().split('\t')
			if len(split)==3 and isintstring(split[2]):
				if cardid==int(split[2]):
					return parse_line(line, metadata)
	else:
		return None

def get_ids(filename):
	cardids = []
	with open(filename, 'r') as f:
		lines = f.readlines()
	for line in lines:
		split = line.strip().split('\t')
		if len(split)==3 and isintstring(split[2]):
			cardids.append(int(split[2]))
	return cardids

def written_ids():
	cardids = []
	for filename in selection.tracked_files():
		cardids += get_ids(filename)
	return cardids

def clear_metadata(filename):
	"""Clears the metadata associated with flashcards in the file "filename"."""
	metadata = loadmetadata()
	with open(filename, 'r') as f:
		lines = f.readlines()
	new_lines = []
	for line in lines:
		if not line.strip() or line.strip()[0]=='#':
			new_lines += [line]
		else:
			split = line.strip().split('\t')
			if has_id(line):
				cardid = int(split[2])
				if cardid in metadata:
					del metadata[cardid]
				new_lines += ['\t'.join(split[:2])+'\n']
			else:
				new_lines += ['\t'.join(split[:2])+'\n']
	if lines!=new_lines:
		print "The following lines of '%s' will be rewritten:\n" % filename
		assert len(lines)==len(new_lines), "lines from the original file do not correspond to those in the rewrite file"
		for (line, new_line) in zip(lines, new_lines):
			if line!=new_line:
				print '-\t'+line.strip()
				print '+\t'+new_line.strip()
		print "Continue file rewrite? (ctrl-C to abort within 3 seconds...)"
		try:
			time.sleep(3)
			replace = True
		except KeyboardInterrupt:
			replace = False
		if replace:
			write_lines(new_lines, filename)
			print "File '%s' was rewritten." % filename
			writemetadata(metadata)
		else:
			print "File rewrite of '%s' aborted. No changed made." % filename

def clear_old_metadata(metadata):
	"""Clears metadata from flashcards which are no longer located in the tracked files."""
	new_metadata = {}
	cardids = written_ids()
	for cardid in metadata:
		if cardid in cardids:
			new_metadata[cardid] = metadata[cardid]
	return new_metadata

def write_lines(lines, filename):
	with open(filename, 'w') as f:
		for line in lines:
			f.write(line)

def has_id(line):
	split = line.strip().split('\t')
	if len(split)<3:
		return False
	elif isintstring(split[2]):
		return True
	else:
		return False

def biject_db():
	"""Cleans the database of metadata to erase empty maps (leaving a bijection between ids and tracked lines).
	It checks each written line to make sure each flashcard gets a unique id in metadata.
	If there are multiple flashcards with the same id, the metadata associate with that id is deleted and they are assigned unique ids (i.e. flashcards are distinguished only by their id)."""
	new_metadata = {}
	metadata = clear_old_metadata(loadmetadata()) # clear maps to nonexistent lines: metadata now contains equal to or less than the number of ids written in files
	for filename in selection.tracked_files():
		new_lines = []
		with open(filename, 'r') as f:
			lines = f.readlines()
		for line in lines:
			if not has_id(line):
				split = line.strip().split('\t')
				if len(split)<2:
					new_lines += [line]
				else:
					newid = new_id(metadata)
					new_lines += [split[0]+'\t'+split[1]+'\t'+str(newid)+'\n']
					new_metadata[newid] = []
					metadata[newid] = []
			else:
				split = line.strip().split('\t')
				written_id = int(split[2])
				if written_id in new_metadata: # code optimized to utilize the fact that ids are ordered in metadata, not in written files
					new_metadata[written_id] = [] # delete metadata associated with double-mapped ids
					newid = new_id(metadata) # creates first new id possible given that all ids in metadata are mapped to at least one tracked flashcard already
					new_metadata[newid] = []
					metadata[newid] = []
					new_lines += [split[0]+'\t'+split[1]+'\t'+str(newid)+'\n']
				elif written_id in metadata:
					new_metadata[written_id] = metadata[written_id]
					new_lines += [line]
				else:
					newid = new_id(metadata)
					new_metadata[newid] = []
					metadata[newid] = []
					new_lines += [split[0]+'\t'+split[1]+'\t'+str(newid)+'\n']
		if lines!=new_lines:
			print "The following lines of '%s' will be rewritten:\n" % filename
			assert len(lines)==len(new_lines), "lines from the original file do not correspond to those in the rewrite file"
			for (line, new_line) in zip(lines, new_lines):
				if line!=new_line:
					print '-\t'+line.strip()
					print '+\t'+new_line.strip()
			print "Continue file rewrite? (ctrl-C to abort within 3 seconds...)"
			try:
				time.sleep(3)
				replace = True
			except KeyboardInterrupt:
				replace = False
			if replace:
				write_lines(new_lines, filename)
				print "File '%s' was rewritten." % filename
			else:
				print "File rewrite of '%s' aborted. No changed made." % filename
	writemetadata(new_metadata)

def daily_update(reviews):
	"""Updates metadata after user responses have been received.
	Metadata: {flash_card_id: list_of_reviews}"""
	for filename in selection.tracked_files():
		metadata = {}
		for card in load(filename):
			if card.id in reviews:
				if card.id not in metadata:
					metadata[card.id] = []
				metadata[card.id] += reviews[card.id]
		if metadata:
			write_update(metadata)





