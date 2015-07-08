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

def parse_message(message):
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

def message_from_id(emailid, imapserver):
	resp, data = imapserver.fetch(str(emailid), "(RFC822)") # fetching the mail, "`(RFC822)`" means "get the whole stuff", but you can ask for headers only, etc
	email_body = data[0][1] # get the mail content
	return email.message_from_string(email_body) # parsing the mail content to get a mail object

def isintstring(s):
	try:
		int(s)
		return True
	except:
		return False

def fetch_reviews(server):
	"""Returns a dictionary of reviews {flashcard_id: reviews}.
	Reviews is a list of tuples (datetime, correct?)"""
	server.select("INBOX")
	with open(RECEIVEDFILE, 'r') as f:
		log_dict = pickle.load(f)
	if 'last_update' in log_dict:
		last_update = datetime.datetime.strftime(log_dict['last_update'], '%d-%b-%Y')
		resp, items = server.search(None, 'FROM', '"3109244701.txt.att.net"', 'SINCE', last_update) # you could filter using the IMAP rules here (check http://www.example-code.com/csharp/imap-search-critera.asp)
	else:
		resp, items = server.search(None, 'FROM', '"3109244701.txt.att.net"')
	log_dict['last_update'] = datetime.datetime.now()
	items = items[0].split() # get the mails id
	if 'received_ids' not in log_dict:
		log_dict['received_ids'] = []
	new_email_ids = [item for item in items if item not in log_dict['received_ids']] # only consider emails that haven't been checked
	responses = []
	for emailid in new_email_ids:
		message = message_from_id(emailid, server)
		number = message.values()[message.keys().index('Subject')].strip('RE: ')
		if isintstring(number):
			try:
				review = parse_message(message)
				assert review['datetime'] and review['correct']
				responses += [(int(number), review)]
				log_dict['received_ids'] += [emailid]
			except Exception as e:
				print "~"*80+'\n'+"ERROR: failed to read user review with email id {}., Error text...{}\n".format(emailid, str(e))+"~"*80+"\nText below:\n\n{}".format(message.as_string())
	with open(RECEIVEDFILE, 'w') as f:
		pickle.dump(log_dict, f)
	reviews = {}
	for r in responses:
		if r[0] not in reviews:
			reviews[r[0]] = []
		reviews[r[0]] += [(r[1]['datetime'], r[1]['correct'])]
	return reviews

time2index = lambda time: int(time//15)
def indices2array(indices):
	a = np.zeros((24*4))
	for index in indices:
		a[index]+=1
	return a

def log_reviews(server):
	reviews = fetch_reviews(server)
	flashcardIO.daily_update(reviews)

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
			log_reviews(self.server)

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



