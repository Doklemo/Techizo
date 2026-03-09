from py_vapid import Vapid
import base64
v = Vapid()
v.generate_keys()
v.save_key('private_key.pem')
v.save_public_key('public_key.pem')

public_bytes = v.public_key.to_string()
b64_pub = base64.urlsafe_b64encode(public_bytes).decode('utf-8').rstrip('=')
print("APPLICATION_SERVER_KEY:", b64_pub)
