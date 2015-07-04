"""
A module to schedule and send flashcard messages from a server. 

The module uses the selection.py module to create selections and save them to a daily file.

1) Function for scheduling messages to be sent each day.

2) method for creating a message with a given flashcard.

3) method for sending a message.

"""
import selection, flashcardIO
import imaplib, smtplib, email, getpass
import os, re, threading, pickle
import time, datetime, dateutil
import numpy as np

HOURLYFILE = 'hourly_probabilities.dat'
RECEIVEDFILE = 'received.dat'

def create_message(card):
	return "Subject: "+str(card.id)+"\n\n"+card.message()

def send_message(server, card):
	server.sendmail('Rex', '3109244701@txt.att.net', create_message(card))

def wait_until(datetimethen):
	seconds = (datetimethen-datetime.datetime.now()).seconds
	for i in range(seconds):
		m, s = divmod(seconds-i, 60)
		h, m = divmod(m, 60)
		print "%02d:%02d:%02d" % (h, m, s)
		time.sleep(1)

def minutes2datetime(minutes):
	now = datetime.datetime.now()
	hour = minutes//60
	dtminutes = minutes-hour*60
	return datetime.datetime(now.year, now.month, now.day, hour, dtminutes)

datetime2minutes = lambda dt: 60*dt.hour+dt.minute


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
			# controls sending of flashcards and saving of data

			events = selection.schedule(time_forward=1) # schedule 15 minutes in advance (TESTING purposes)
			for event in events:
				print event[1], event[0]
			# loop until all cards have been sent, catch negative times and continue
			for event in events:
				try:
					print 'next event at', str(event[1])
					wait_until(event[1])
					print "server updating..."
					self.update_server()
					print "done\nsending message..."
					send_message(self.server, event[0])
					print "done"
				except:
					print "Error for event: '%s'." % str(event[0])

			# wait until a little after midnight to restart (this gives the Receive thread time to update received data)
			delay_seconds = 30
			tmrw = datetime.datetime.now()+datetime.timedelta(1)
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
	# s = message.as_string()
	# regex = re.compile(r'.*?\nDate:(?P<date>.*?)\n.*?\nSubject: RE:(?P<id>.*?)\n.*?Message-Type: Reply(?P<response>.*?)-----Original Message-----', re.DOTALL)
	# match = regex.match(s).groupdict()

	# flash_id = int(match['id'])
	# date = dateutil.parser.parse(match['date'].strip())
	# # move to PCT timezone
	# date = date.astimezone(MY_TIMEZONE).replace(tzinfo=None)
	# text = match['response'].strip()
	# if text.lower()=='yes':
	# 	correct=True
	# if text.lower()=='no':
	# 	correct=False

	# return (flash_id, date, correct)

	s = message.as_string()
	regex = re.compile(r'.*?Subject: RE: (?P<id>[0-9]*).*?[\n\r]{2,4}(?P<response>.*?)[\n\r]{2,4}', re.DOTALL|re.UNICODE)
	match = regex.match(s).groupdict()

	flash_id = int(match['id'])
	d = message.values()[message.keys().index('Date')]
	date = datetime.datetime.strptime(d[:-6], '%a, %d %b %Y %H:%M:%S')
	# move to PCT timezone
	date = date + pctoffset_from_string(d[-5:])
	text = match['response'].strip()
	if text.lower()[0]=='y':
		correct=True
	if text.lower()[0]=='n':
		correct=False

	return (flash_id, date, correct)

	message.values()[message.keys().index('Date')]

def is_recent(date):
	delta = datetime.datetime.now() - date
	return delta.days<=1

def fetch_responses(server):
	server.select("INBOX")

	resp, items = server.search(None, 'FROM', '"3109244701.txt.att.net"') # you could filter using the IMAP rules here (check http://www.example-code.com/csharp/imap-search-critera.asp)
	items = items[0].split() # getting the mails id
	with open(RECEIVEDFILE, 'r') as f:
		received_ids = pickle.load(f)
	# only consider emails that haven't been checked
	temp = []
	for i in range(len(items)):
		if items[i] not in received_ids:
			temp.append(items[i])

	responses = []
	read_ids = []

	for emailid in temp:
		resp, data = server.fetch(emailid, "(RFC822)") # fetching the mail, "`(RFC822)`" means "get the whole stuff", but you can ask for headers only, etc
		email_body = data[0][1] # getting the mail content
		message = email.message_from_string(email_body) # parsing the mail content to get a mail object

		try:
			response = parse_message(message)
			if is_recent(response[1]):
				responses.append(response)
			read_ids.append(emailid)
		except Exception as e:
			print "~"*80+'\n'+"ERROR: failed to read user response with email id {}., Error text...{}\n".format(emailid, str(e))+"~"*80+"\nText below:\n\n{}".format(message.as_string())

	with open(RECEIVEDFILE, 'w') as f:
		pickle.dump(received_ids+read_ids, f)

	return responses

def log_responses(server):
	responses = fetch_responses(server)
	if responses:
		list_of_minutes = [datetime2minutes(date) for (flash_id, date, correct) in responses]
		write_times(list_of_minutes)
		flashcardIO.daily_update({flash_id: correct for  (flash_id, date, correct) in responses})

time2index = lambda time: int(time//15)
def indices2array(indices):
	a = np.zeros((24*4))
	for index in indices:
		a[index]+=1
	return a

def write_times(list_of_minutes):
	# write times that responses were received from the user into the file containing hourly probabilities
	indices = np.array([time2index(time) for time in list_of_minutes])
	new_indices = indices2array(indices)

	if not os.path.isfile(HOURLYFILE):
		with open(HOURLYFILE,'w') as f:
			pickle.dump([np.ones(24*4)])
	with open(HOURLYFILE,'r') as f:
		old_indices = pickle.load(f)
	with open(HOURLYFILE,'w') as f:
		try:
			print 'times being written'
			pickle.dump(np.append(old_indices, new_indices).reshape(old_indices.shape[0]+1, old_indices.shape[1]), f)
		except ValueError:
			print "Error: failure adding new response times to the data file %s." % HOURLYFILE


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
			# wait until midnight
			tmrw = datetime.datetime.now()+datetime.timedelta(1)
			midnight = datetime.datetime(tmrw.year, tmrw.month, tmrw.day, 0, 0)
			wait_until(midnight)

			self.update_server()
			log_responses(self.server)


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
