import smtplib, imaplib, email, getpass
username = 'rex.garland'
password = getpass.getpass("Enter your Gmail password: ")
server = smtplib.SMTP("smtp.gmail.com",587)
server.starttls()
server.login(username, password)
server.sendmail('Rex', '3109244701@txt.att.net', 'test message')
