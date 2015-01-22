"""
A module for randomly selecting flashcards to test, weighing flashcard necessity and time of the day. Selection data is created daily at midnight so that the server can send messages at preselected times during the following day.

This module uses statistics.py to weigh each flashcard and randomly select a specific amount for each day.

1) a method for selecting random cards to display

"""
from datetime import datetime
import numpy as np
import flashcardIO, pickle

OCCURRENCEFILE = 'daily_frequencies.txt'
# hourly file must be a pickled list of tuples representing occurrences in 15 minute bins
HOURLYFILE = 'hourly_probabilities.dat'
# pickles a list of numpy arrays storing data on when responses are received from the user

normalize = lambda nparray: nparray.astype(np.float)/np.sum(nparray)

def rv_discrete(size=100, values=([0],[0])):
	indices = values[0]
	probs = np.array(values[1], np.float)
	probabilities = probs/sum(probs)
	integrated_probs = [sum(probabilities[:i+1]) for i in range(len(probabilities))]
	random = np.random.random(size)
	def integrate2index(r):
		i = 0
		while r>integrated_probs[i]:
			i+=1
		return indices[i]
	return [integrate2index(r) for r in random]

def select_cards():
	occurrences = find_card_frequencies()
	total_cards = []

	for filename in occurrences.keys():
		cards = flashcardIO.load(filename)
		number = occurrences[filename]
		weights = []
		for index, card in enumerate(cards):
			weights.append((index, card.necessity()))
		xk, pk = zip(*weights)
		pk = np.array(pk); pk = normalize(pk)
		R = rv_discrete(size=number, values=(xk, pk))
		total_cards.append([cards[index] for index in R])

	return total_cards

def find_card_frequencies():
	datafile = open(OCCURRENCEFILE,'r')
	occurrences = {}

	while True:
		try:
			line = datafile.next()
			if line[0]=='#' or line=='\n':
				continue
			data = line.strip().split('\t')
			filename = data[0].strip(); number = int(data[1].strip())
			occurrences[filename] = number
		except StopIteration:
			break
		except:
			print "Error: could not read 'datafile.txt' file to read flashcard set occurrences."
			datafile.close()
			exit()

	datafile.close()
	return occurrences

def find_files():
	return find_card_frequencies().keys()

index2random_time = lambda index: index*15+int(np.random.rand()*15)
def index2random_datetime(index):
	now = datetime.now()
	rando_minute = index2random_time(index)
	datetime(now.year, now.month, now.day, rando_minute//60, rando_minute-60*(rando_minute//60))

def select_times(total_number):
	# selects times during the day to test total_number cards
	with open(HOURLYFILE, 'r') as datafile:
		data = pickle.load(datafile)
	# data is weighted exponentially to decrease with days past
	weighted = normalize(reduce(lambda x,y: 0.9*x+y, data))
	R = rv_discrete(size=total_number, values=(range(24*4), weighted))
	return [index2random_time(item) for item in R]

def schedule():

	# returns a list of events, each event being a tuple with flashcard and time
	cards = select_cards()
	times = select_times(len(cards))
	return zip(cards, times)