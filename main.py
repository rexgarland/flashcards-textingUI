"""
A module to schedule and send flashcard messages from a server. 

The module uses the selection.py module to create selections and save them to a daily file.

1) Function for scheduling messages to be sent each day.

2) method for creating a message with a given flashcard.

3) method for sending a message.

"""
import selection, flashcardIO
import imaplib, smtplib, email, getpass
import os, re, threading, pickle, sys
import time, datetime, dateutil
import numpy as np

RECEIVEDFILE = 'received.dat'

def create_message(card):
	return "Subject: "+str(card.id)+"\n\n"+card.message()

def send_message(server, card):
	server.sendmail('Rex', '3109244701@txt.att.net', create_message(card))

def wait_until(datetimethen):
	# seconds = (datetimethen-datetime.datetime.now()).seconds
	# for i in range(seconds):
	# 	m, s = divmod(seconds-i, 60)
	# 	h, m = divmod(m, 60)
	# 	print "%02d:%02d:%02d" % (h, m, s)
	# 	time.sleep(1)
	seconds = (datetimethen-datetime.datetime.now()).seconds
	for i in range(seconds):
		m, s = divmod(seconds-i, 60)
		h, m = divmod(m, 60)
		sys.stdout.write("\r"*8+"%02d:%02d:%02d" % (h, m, s))
		sys.stdout.flush()
		time.sleep(1)

def minutes2datetime(minutes):
	now = datetime.datetime.now()
	hour = minutes//60
	dtminutes = minutes-hour*60
	return datetime.datetime(now.year, now.month, now.day, hour, dtminutes)

datetime2minutes = lambda dt: 60*dt.hour+dt.minute

def ahead(datetime_then):
	return (datetime_then-datetime.datetime.now()).total_seconds()>0

class Send(threading.Thread):
	def __init__(self, username, password):
		threading.Thread.__init__(self)
		self.username = username
		self.password = password
		self.server = None
		self.abort = False
		try:
			self.update_server()
		except:
			print "Error: smtp authentication failed. Check login information."
			self.abort = True

	def update_server(self):
		self.server = smtplib.SMTP("smtp.gmail.com", 587)
		self.server.starttls()
		self.server.login(self.username, self.password)

	def run(self):
		while self.abort==False:
			events = selection.schedule() # schedule 15 minutes in advance (TESTING purposes)
			for event in events:
				print event[1], event[0]
			# loop until all cards have been sent, catch negative times and continue
			for event in sorted(events, key = lambda item: item[1]):
				try:
					if ahead(event[1]):
						print 'next event at', str(event[1])
						wait_until(event[1])
						print "server updating..."
						self.update_server()
						print "...done\nsending message..."
						send_message(self.server, event[0])
						print "...done"
					else:
						print "Event scheduled for past time: %s" % event[1]
				except:
					print "Error for event: '%s'." % str(event[0])
			# wait until a little after midnight to restart (this gives the Receive thread time to update received data)
			delay_seconds = 30
			tmrw = datetime.datetime.now()+datetime.timedelta(days=1)
			midnight = datetime.datetime(tmrw.year, tmrw.month, tmrw.day, 0, 0, delay_seconds)
			wait_until(midnight)

def pctoffset_from_string(s):
	h = int(s[1:3]); m = int(s[3:5])
	if int(s)<0: 
		hours = -h
		minutes = -m
	else:
		hours = h
		minutes = m
	offsethours = hours+8
	offsetminutes = minutes
	return datetime.timedelta(hours = offsethours, minutes = offsetminutes)

def parse_message(message, type='review'):
	"""Returns parsed data of user information from an email message.
	For review-type messages, the returned data is a dict of the review.
	For add_cards-type messages, the returned data is a tuple (filename, cards), where cards are separated by newlines and back/front text separated by '--' in the user's message."""
	assert type=='review' or type=='add_cards', "parse_message not given valid type of message (either review or add_cards)."
	if type=='review':
		s = message.as_string()
		regex = re.compile(r'.*?Subject: RE: (?P<id>[0-9]*).*?[\n\r]{2,4}(?P<correct>.*?)[\n\r]{2,4}', re.DOTALL|re.UNICODE)
		match = regex.match(s).groupdict()
		d = message.values()[message.keys().index('Date')]
		try:
			date = datetime.datetime.strptime(d[:-6], '%a, %d %b %Y %H:%M:%S')
			# move to PCT timezone
			date = date + pctoffset_from_string(d[-5:])
		except:
			date = None
		text = match['correct'].strip()
		if text.lower()[0]=='y':
			correct=True
		elif text.lower()[0]=='n':
			correct=False
		else:
			correct = None
		return {'datetime': date, 'correct': correct}
	else:
		s = str(message.get_payload()[0].get_payload()[0]).replace('\r','')
		regex = re.compile(r'.*?\<td\>(?P<body>.*?)\</td\>', re.DOTALL|re.UNICODE)
		body = regex.match(s).groupdict()['body'].strip()
		lines = body.split('\n')
		filename = lines[0].strip()
		cards = [tuple(line.split('--')) for line in lines[1:]]
		return filename, cards

def message_from_id(emailid, imapserver):
	"""Returns the message string from an email with email id "emailid" on server "imapserver"."""
	imapserver.select("INBOX")
	resp, data = imapserver.fetch(str(emailid), "(RFC822)") # fetching the mail, "`(RFC822)`" means "get the whole stuff", but you can ask for headers only, etc
	email_body = data[0][1] # get the mail content
	return email.message_from_string(email_body) # parsing the mail content to get a mail object

def isintstring(s):
	try:
		assert type(s) is str
		int(s)
		return True
	except:
		return False

def isemailidlist(l):
	if type(l) is not list:
		return False
	else:
		if not all([(len(str(s))==4 and isintstring(s)) for s in l]):
			return False
		else:
			return True

def get_log_dict():
	"""Method for loading the log dict. Returns the log dict with guaranteed 'last_update' and 'received_ids' elements."""
	try:
		with open(RECEIVEDFILE, 'r') as f:
			log_dict = pickle.load(f)
		assert type(log_dict) is dict
	except:
		# set initial last_update to a year ago
		log_dict = {'last_update': datetime.datetime.now()-datetime.timedelta(days=365), 'received_ids' = []}
	try:
		assert type(log_dict['last_update']) is datetime.datetime
	except:
		log_dict['last_update'] = datetime.datetime.now()-datetime.timedelta(days=365)
	if not isemailidlist(log_dict['received_ids']):
		log_dict['received_ids'] = []
	return log_dict

def write_log_dict(log_dict):
	assert type(log_dict) is dict
	assert isemailidlist(log_dict['received_ids'])
	assert type(log_dict['last_update']) is datetime.datetime
	with open(RECEIVEDFILE, 'w') as f:
		pickle.dump(log_dict, f)

def get_new_email_ids(server):
	"""Returns a list of email ids of emails on the imap server "server" from my cellphone that haven't been fetched yet."""
	server.select("INBOX")
	log_dict = get_log_dict()
	last_update = datetime.datetime.strftime(log_dict['last_update'], '%d-%b-%Y')
	resp, items1 = server.search(None, 'FROM', '"3109244701@txt.att.net"', 'SINCE', last_update) # you could filter using the IMAP rules here (check http://www.example-code.com/csharp/imap-search-critera.asp)
	resp, items2 = server.search(None, 'FROM', '"3109244701@mms.att.net"', 'SINCE', last_update)
	items = items1[0].split() + items2[0].split()
	return [item for item in items if item not in log_dict['received_ids']] # only consider emails that haven't been checked

def write_read_email_ids(emailids):
	"""Records a list of email ids "emailids" that have been fetched and read."""
	log_dict = get_log_dict()
	for emailid in emailids:
		if str(emailid) not in log_dict['received_ids']:
			log_dict['received_ids'] += [str(emailid)]
	write_log_dict(log_dict)

def write_log_time(last_update):
	log_dict = get_log_dict()
	log_dict['last_update'] = last_update
	write_log_dict(log_dict)

def fetch_reviews(server):
	"""Returns a dictionary of reviews {flashcard_id: reviews}.
	Reviews is a list of tuples (datetime, correct?)"""
	new_email_ids = get_new_email_ids(server)
	responses = []
	read_ids = []
	for emailid in new_email_ids:
		message = message_from_id(emailid, server)
		if 'Subject' in message.values(): # avoids email threads initiated by the cellphone (i.e. user input flashcards)
			cardid = message.values()[message.keys().index('Subject')].strip('RE: ')
			if isintstring(cardid):
				try:
					review = parse_message(message, type='review')
					assert review['datetime'] and review['correct']
					responses += [(int(cardid), review)]
					read_ids += [emailid]
				except Exception as e:
					print "~"*80+'\n'+"ERROR: failed to read user review with email id {}., Error text...{}\n".format(emailid, e)+"~"*80+"\nText below:\n\n{}".format(message)
	write_read_email_ids(read_ids)
	reviews = {}
	for r in responses:
		if r[0] not in reviews:
			reviews[r[0]] = []
		reviews[r[0]] += [(r[1]['datetime'], r[1]['correct'])]
	return reviews

def fetch_new_cards(server):
	"""Fetches responses from the server that contain flashcard additions from the user.
	Flashcard additions are signaled in the user's text message by prefixing the text message with a filename on the first line.
	Returns a card_updates dict {filename: cards}, where cards is a list of tuples (front_text, back_text)."""
	valid_filenames = selection.tracked_files()
	new_email_ids = get_new_email_ids(server)
	update_cards = {}
	read_ids = []
	for emailid in new_email_ids:
		message = message_from_id(emailid, server)
		if 'Subject' not in message.keys(): # email threads initiated by a cellphone will not have a subject line
			try:
				filename, cards = parse_message(message, type='add_cards')
				if os.path.isfile(filename):
					if filename not in update_cards:
						update_cards[filename] = []
					update_cards[filename] += cards
				else:
					print "Error: filename '{}' is not in tracked files. Information in email with email id {} not logged.".format(filename, emailid)
				read_ids += [emailid]
			except Exception as e:
				print "~"*80+'\n'+"ERROR: failed to read user cards in email with email id {}., Error text...{}\n".format(emailid, e)+"~"*80+"\nText below:\n\n{}".format(message)
	write_read_email_ids(read_ids)
	return update_cards

time2index = lambda time: int(time//15)
def indices2array(indices):
	a = np.zeros((24*4))
	for index in indices:
		a[index]+=1
	return a

def log(server):
	reviews = fetch_reviews(server)
	flashcardIO.update_reviews(reviews)
	card_updates = fetch_new_cards(server)
	flashcardIO.update_cards(card_updates)
	write_log_time(datetime.datetime.now())

class Receive(threading.Thread):
	def __init__(self, username, password):
		threading.Thread.__init__(self)
		self.username = username
		self.password = password
		self.server = None
		self.abort = False

	def update_server(self):
		self.server = imaplib.IMAP4_SSL("imap.gmail.com")
		self.server.login(self.username, self.password)

	def run(self):
		while self.abort==False:
			tmrw = datetime.datetime.now()+datetime.timedelta(1)
			midnight = datetime.datetime(tmrw.year, tmrw.month, tmrw.day, 0, 0)
			wait_until(midnight)
			try:
				self.update_server()
			except:
				print "Error: smtp authentication failed. Check login information."
				self.abort = True
			log(self.server)

if __name__=='__main__':
	USERNAME = 'rex.garland'
	PASSWORD = getpass.getpass("Enter your Gmail password: ")
	thread1 = Send(USERNAME, PASSWORD); thread1.daemon = True
	thread2 = Receive(USERNAME, PASSWORD); thread2.daemon = True
	thread1.start()
	thread2.start()
	# keyboard exit functionality
	try:
		while (thread1.isAlive() and thread2.isAlive()):
			time.sleep(1)
	except KeyboardInterrupt:
		thread1.abort = True
		thread2.abort = True
	PASSWORD = '\0'*100



