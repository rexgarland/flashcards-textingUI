"""
A module for randomly selecting flashcards to test, weighing flashcard necessity and time of the day. Selection data is created daily at midnight so that the server can send messages at preselected times during the following day.

This module uses statistics.py to weigh each flashcard and randomly select a specific amount for each day.

1) a method for selecting random cards to display

Options for improvement:
- neural network for learning when I "know" a card
- 
"""
from datetime import datetime
import numpy as np
import flashcardIO, pickle, os

OCCURRENCEFILE = 'daily_frequencies.txt'
# hourly file must be a pickled list of tuples representing occurrences in 15 minute bins
HOURLYFILE = 'hourly_probabilities.dat'
# pickles a list of numpy arrays storing data on when responses are received from the user

MIDNIGHT = 24*4-1
FORGETTING_RATE = 0.9

normalize = lambda nparray: nparray.astype(np.float)/np.sum(nparray)

def rv_discrete(size=100, values=[0], weights=[0]):
	probs = np.array(weights, np.float)
	probabilities = probs/sum(probs)
	integrated_probs = [sum(probabilities[:i+1]) for i in range(len(probabilities))]
	random = np.random.random(size)
	def integrate2index(r):
		i = 0
		while r>integrated_probs[i]:
			i+=1
		return values[i]
	return [integrate2index(r) for r in random]

def select_cards():
	occurrences = find_card_frequencies()
	total_cards = []

	for filename in occurrences:
		cards = flashcardIO.load(filename)
		number = occurrences[filename]
		if cards and number>0:
			weights = []
			for index, card in enumerate(cards):
				weights.append((index, card.necessity()))
			xk, pk = zip(*weights)
			pk = np.array(pk); pk = normalize(pk)
			R = rv_discrete(size=number, values=xk, weights=pk)
			total_cards += [cards[index] for index in R]

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
			print "Error: could not read '%s' file to read flashcard set occurrences." % OCCURRENCEFILE
			datafile.close()
			exit()

	datafile.close()
	return occurrences

def find_files():
	return find_card_frequencies().keys()

datetime2index = lambda dt: dt.hour*4+dt.minute//15
index2random_time = lambda index: index*15+int(np.random.rand()*15)
def index2random_datetime(index):
	now = datetime.now()
	rando_minute = index2random_time(index)
	return datetime(now.year, now.month, now.day, rando_minute//60, rando_minute-60*(rando_minute//60))

def select_times(total_number, until=MIDNIGHT):
	# selects times during the day to test total_number cards (now until the "until" variable)
	if not os.path.isfile(HOURLYFILE):
		with open(HOURLYFILE,'w') as f:
			pickle.dump([np.ones(24*4)], f)
	with open(HOURLYFILE, 'r') as datafile:
		data = pickle.load(datafile)
		if not data:
			data = [np.ones(24*4)]
	# data is weighted exponentially to decrease with days past
	weights = reduce(lambda x,y: FORGETTING_RATE*x+y, data)
	now = datetime2index(datetime.today())
	for index in range(len(weights)):
		if index<=now or index>until:
			weights[index]=0
	weights = normalize(weights)
	R = rv_discrete(size=total_number, values=range(24*4), weights=weights)
	return [index2random_datetime(item) for item in R]

def schedule(time_forward=None):
	# returns a list of events, each event being a tuple with flashcard and time
	cards = select_cards()
	if time_forward:
		index = datetime2index(datetime.now())+time_forward
		times = select_times(len(cards), until=index)
	else:
		times = select_times(len(cards))
	return sorted(zip(cards, times), key = lambda item: item[1])


if __name__=='__main__':
	print [str(t) for t in select_times(10, until=datetime2index(datetime.today())+1)]


