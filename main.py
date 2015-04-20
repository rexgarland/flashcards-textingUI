"""
A module to schedule and send flashcard messages from the server. 

The module uses the selection.py module to create selections and save them to a daily file.

1) Function for scheduling messages to be sent each day.

2) method for creating a message with a given flashcard.

3) method for sending a message.

"""

import selection, flashcardIO, time, imaplib, datetime, smtplib, email, getpass, imaplib, os, re, threading
import numpy as np

HOURLYFILE = 'hourly_probabilities.dat'
RECEIVEDFILE = 'received.dat'

def create_message(card, id):
	return "Subject: "+id+"\n\n"+card.to_text()

def send_message(server, card, id):
	server.sendmail('Rex', '3109244701@txt.att.net', create_message(card, id))

wait_until = lambda datetimethen: time.sleep((datetimethen-datetime.datetime.now()).seconds)

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

	def update_server(self):
		self.server = smtplib.SMTP("smtp.gmail.com", 587)
		self.server.starttls()
		self.server.login(self.username, self.password)

	def run(self):
		while True:
			try:
				# controls sending of flashcards and saving of data

				events = selection.schedule()

				# loop until all cards have been sent, catch negative times and continue
				for event in events:
					try:
						wait_until(minutes2datetime(event[1]))
						self.update_server()
						send_message(self.server, event[0], event[0].id)
					except IOError:
						print "Error: past time for sending card '%s'." % event[0].text[0]
					except:
						print "Error: unable to send card '%s'." % event[0].text[0]
				

				# wait until a little after midnight to restart (this gives collect.py time to update received data)
				delay_seconds = 30
				tmrw = datetime.datetime.now()+datetime.datetime.timedelta(1)
				midnight = datetime.datetime(tmrw.year, tmrw.month, tmrw.day, 0, 0, 10)
				wait_until(midnight)
			except KeyboardInterrupt:
				print "Program exited."
				break





def parse_message(message):
	flash_id = int(message.get('Subject').split()[1])
	dt = message.get('Date')
	t = time.strptime(' '.join(dt.split()[:-1]), "%a, %d %b %Y %H:%M:%S")
	date = datetime.datetime.fromtimestamp(time.mktime(t))
	s = message.as_string()
	text = re.match(r'.*?X-OPWV-Extra-Message-Type: Reply\n\n(?P<response>.*?)\r\n\r\n', s, re.DOTALL).groups(0).strip()
	if text.lower()=='yes':
		correct=True
	if text.lower()=='no':
		correct=False
	return (flash_id, date, correct)

def fetch_responses(server):
	server.select("INBOX")

	resp, items = server.search(None, 'FROM', '"3109244701.txt.att.net"') # you could filter using the IMAP rules here (check http://www.example-code.com/csharp/imap-search-critera.asp)
	items = items[0].split() # getting the mails id
	with open(RECEIVEDFILE, 'r') as f:
		received_ids = pickle.load(f)
	for i in range(len(items)):
		if items[i] in received_ids:
			del items[i]

	responses = []
	read_ids = []

	for emailid in items:
		try:
			resp, data = server.fetch(emailid, "(RFC822)") # fetching the mail, "`(RFC822)`" means "get the whole stuff", but you can ask for headers only, etc
			email_body = data[0][1] # getting the mail content
			message = email.message_from_string(email_body) # parsing the mail content to get a mail object

			responses.append(parse_message(message))

			read_ids.append(emailid)
		except:
			print "Error: failed to read user response with email id %s." % emailid

	with open(RECEIVEDFILE, 'w') as f:
		pickle.dump(received_ids+read_ids, f)

	return responses

def log_responses(server):
	responses = fetch_responses(server)
	if responses:
		list_of_minutes = [datetime2minutes(date) for (flash_id, date, correct) in responses]
		write_times(list_of_minutes)
		flashcardIO.update_cards({flash_id: correct for  (flash_id, date, correct) in responses})

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

	with open(HOURLYFILE,'r') as f:
		old_indices = pickle.load(f)
	with open(HOURLYFILE,'w') as f:
		try:
			pickle.dump(np.append(old_indices, new_indices).reshape(old_indices.shape[0]+1, old_indices.shape[1]), f)
		except ValueError:
			print "Error: failure adding new response times to the data file %s." % HOURLYFILE


class Receive(threading.Thread):
	def __init__(self, username, password):
		threading.Thread.__init__(self)
		self.username = username
		self.password = password
		self.server = None

	def update_server(self):
		self.server = imaplib.IMAP4_SSL("imap.gmail.com")
		self.server.login(self.username, self.password)

	def run(self):
		while True:
			try:
				# wait until midnight
				tmrw = datetime.datetime.now()+datetime.timedelta(1)
				midnight = datetime.datetime(tmrw.year, tmrw.month, tmrw.day, 0, 0)
				wait_until(midnight)

				self.update_server()
				log_responses(self.server())
			except KeyboardInterrupt:
				print "Program exited."
				break

if __name__=='__main__':
	USERNAME = 'rex.garland'
	PASSWORD = getpass.getpass("Enter your Gmail password: ")
	thread1 = Send(USERNAME, PASSWORD)
	thread2 = Receive(USERNAME, PASSWORD)
	thread1.start()
	thread2.start()
	
