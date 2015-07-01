from qrcode import QRCode

def qrcode(msg):
    qr = QRCode()
    qr.add_data(msg)
    return qr

def qrcode_png_buffer(qr):
    import io
    image = qr.make_image()
    buf = io.BytesIO()
    image.save(buf, 'PNG')
    return buf

def send_email(config, email, subject, body):
    print 'sending email to %s (%s)' % (email, subject)
    if config.email.use_mandrill:
        import flask
        from flask.ext.mandrill import Mandrill

        mandrill = Mandrill(flask.current_app)
        mandrill.send_email(
            subject=subject,
            to=[{'email': email}],
            text=body
        )
    else:
        import smtplib
        from email.mime.text import MIMEText

        # Create a text/plain message
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = config.email.from_
        msg['To'] = email

        # Send the message via our own SMTP server, but don't include the
        # envelope header.
        s = smtplib.SMTP(config.email.smtp)
        if config.email.use_auth:
            s.starttls()
            s.login(config.email.user, config.email.password)
        s.sendmail(config.email.from_, [email], msg.as_string())
        s.quit()


def send_email_beer_alert(config, beer):
    subject = 'beerme order'
    body = """%s at table %s has ordered a %s""" % (beer.name, beer.table, beer.brew)
    send_email(config, config.email.beer_alert, subject, body)

